"""
Terrain-aware step detector — Python reference implementation.

Algorithm change from step_detector.c:
  OLD (acc-primary):  acc_filt threshold → 40ms window → gyr_y zero-crossing
  NEW (gyr-primary):  gyr_y_hp neg→pos crossing (push-off) → acc_filt exceeded
                      threshold at any point since last step

Why this is terrain-agnostic:
  - Flat / slope / bad_wear: heel strikes produce both an acc_filt spike AND
    a sharp initial dorsiflexion→rebound gyr_y crossing within 40ms. Both
    mechanisms agree.
  - Stairs (toe/forefoot strike): no sharp acc spike at contact. The slow
    sigmoid loading means acc_filt peaks 141ms into stance while the initial
    gyr_y rebound has already expired 126ms earlier — original detector fails.
    BUT every terrain, including stairs, ends stance with plantar-flexion
    (push-off): gyr_y_hp crosses neg→pos at phase ~0.75 of stance.
    acc_filt always exceeds threshold during the loading phase of stairs.
    The new detector catches every terrain at push-off.

Filter chain (identical to step_detector.c):
  acc_mag → HP(0.5 Hz) → LP(15 Hz walking / 30 Hz running) = acc_filt
  gyr_y   → HP(0.5 Hz)                                      = gyr_y_hp

Detection gate (new):
  gyr_y_hp neg→pos crossing (push-off)
  + acc_filt > adaptive_threshold since last step
  + neg-phase duration >= GYR_STANCE_MIN_DUR_MS (blocks phase-0.10 rebound)
  + elapsed since last step >= MIN_STEP_INTERVAL_MS

Three primitives grounding:
  cadence_spm       → step interval, MIN_STEP_INTERVAL_MS = 250ms (240 spm max)
  vertical_osc      → acc impact amplitude → adaptive threshold seeded at 10 m/s²
  step_length       → walking speed → push-off gyr_y amplitude (>>5 dps on all terrains)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional

ODR_HZ: float = 208.0
DT: float = 1.0 / ODR_HZ

# ── Detection parameters (all traceable to physical quantities) ───────────────
HP_CUTOFF_HZ: float       = 0.5      # remove inter-step drift; step cycle ≥1 Hz
LP_WALKING_HZ: float      = 15.0     # anti-alias for walking (<130 spm)
LP_RUNNING_HZ: float      = 30.0     # anti-alias for running (≥130 spm)
CADENCE_RUN_THRESH: float = 130.0    # spm boundary walk/run
MIN_STEP_INTERVAL_MS: int = 250      # 240 spm max cadence
PEAK_HISTORY: int         = 8        # steps for adaptive acc threshold
ACC_SEED_MS2: float       = 10.0     # seed threshold: ~1g extra above gravity
HS_RING_SIZE: int         = 8        # Option C: ring buffer entries for rejected
                                      # acc_filt crossings → retrospective heel-strike
                                      # 8 entries × 4 bytes = 32 bytes RAM in C
GYR_PUSHOFF_THRESH_DPS: float = 30.0 # gyr_y_hp must exceed this positive value
                                      # before the falling-edge is counted as push-off.
                                      # Physical grounding:
                                      #   minimum push-off = 100 + 65*v_min dps
                                      #   at v=0.1 m/s → 106 dps >> 30 dps
                                      # Phase-0.10 rebound peak = peak × 0.05:
                                      #   flat  (185 dps): +9.3 dps  < 30 → blocked ✓
                                      #   stairs(280 dps): +14.0 dps < 30 → blocked ✓
                                      # Push-off peak = peak × 1.0:
                                      #   flat  : +185 dps >> 30 → detected ✓
                                      #   stairs: +280 dps >> 30 → detected ✓


# ── Filter coefficient helpers ────────────────────────────────────────────────

def _alpha_hp(fc_hz: float) -> float:
    rc = 1.0 / (2.0 * math.pi * fc_hz)
    return rc / (rc + DT)

def _alpha_lp(fc_hz: float) -> float:
    rc = 1.0 / (2.0 * math.pi * fc_hz)
    return DT / (rc + DT)


# ── Output type ───────────────────────────────────────────────────────────────

@dataclass
class StepEvent:
    step_index: int
    ts_ms: float               # push-off timestamp (end of stance)
    acc_peak_ms2: float        # max acc_filt seen during this stance
    heel_strike_ts_ms: float   # Option C: retrospective heel-strike timestamp
                               # = first acc_filt threshold crossing since last step
                               # Falls back to push-off ts if no crossing stored
    stance_duration_ms: float  # push-off ts − heel_strike ts (Option C derived)
    swing_duration_ms: float   # filled in after next step fires (0 until then)


# ── Detector ──────────────────────────────────────────────────────────────────

class TerrainAwareStepDetector:
    """
    Process IMU samples one at a time via update().
    Returns a StepEvent on step detection, otherwise None.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        # HP filter state — acc
        self._hp_acc_x1: float = 0.0
        self._hp_acc_y1: float = 0.0
        # LP filter state — acc
        self._lp_acc_y1: float = 0.0
        # HP filter state — gyr_y
        self._hp_gyr_x1: float = 0.0
        self._hp_gyr_y1: float = 0.0

        # Adaptive acc threshold
        self._peak_history: list[float] = [ACC_SEED_MS2] * PEAK_HISTORY
        self._hist_idx: int = 0

        # Per-stance tracking
        self._acc_peak_this_step: float = 0.0
        self._acc_above: bool = False          # acc_filt exceeded threshold this stance
        self._in_pushoff: bool = False         # gyr_y_hp is above push-off threshold

        # Option C — ring buffer of acc_filt threshold crossings (rejected heel-strikes)
        # Stores timestamps of each new acc_filt > threshold event since last confirmed step.
        # On push-off, oldest entry newer than last_step_ts is used as heel_strike_ts.
        self._hs_ring: list[float] = []        # timestamps in chronological order
        self._acc_was_below: bool = True       # tracks crossing (below→above threshold)

        # Step state
        self._steps: List[StepEvent] = []
        self._step_count: int = 0
        self._last_step_ts_ms: float = -(MIN_STEP_INTERVAL_MS + 1)

        # Cadence
        self._interval_history: list[float] = [600.0] * 4  # seed ≈100 spm
        self._interval_idx: int = 0
        self._cadence_spm: float = 100.0

        # Previous gyr_y_hp for crossing detection
        self._gyr_hp_prev: float = 0.0

    # ── Scalar IIR filters ────────────────────────────────────────────────────

    def _hp_acc(self, x: float) -> float:
        alpha = _alpha_hp(HP_CUTOFF_HZ)
        y = alpha * (self._hp_acc_y1 + x - self._hp_acc_x1)
        self._hp_acc_x1 = x
        self._hp_acc_y1 = y
        return y

    def _lp_acc(self, x: float) -> float:
        alpha = _alpha_lp(
            LP_RUNNING_HZ if self._cadence_spm >= CADENCE_RUN_THRESH
            else LP_WALKING_HZ
        )
        self._lp_acc_y1 = alpha * x + (1.0 - alpha) * self._lp_acc_y1
        return self._lp_acc_y1

    def _hp_gyr(self, x: float) -> float:
        alpha = _alpha_hp(HP_CUTOFF_HZ)
        y = alpha * (self._hp_gyr_y1 + x - self._hp_gyr_x1)
        self._hp_gyr_x1 = x
        self._hp_gyr_y1 = y
        return y

    # ── Adaptive threshold ────────────────────────────────────────────────────

    def _threshold(self) -> float:
        return 0.5 * (sum(self._peak_history) / PEAK_HISTORY)

    def _record_peak(self, peak: float) -> None:
        self._peak_history[self._hist_idx] = peak
        self._hist_idx = (self._hist_idx + 1) % PEAK_HISTORY

    # ── Cadence ───────────────────────────────────────────────────────────────

    def _update_cadence(self, interval_ms: float) -> None:
        self._interval_history[self._interval_idx] = interval_ms
        self._interval_idx = (self._interval_idx + 1) % 4
        mean_ms = sum(self._interval_history) / 4.0
        self._cadence_spm = 60000.0 / mean_ms if mean_ms > 0 else 0.0

    # ── Main update ───────────────────────────────────────────────────────────

    def update(
        self,
        ts_ms: float,
        ax: float, ay: float, az: float,
        gyr_y: float,
    ) -> Optional[StepEvent]:
        """
        Process one 208 Hz IMU sample. Returns StepEvent on step detection.

        Parameters
        ----------
        ts_ms : absolute timestamp in milliseconds
        ax, ay, az : accelerometer axes in m/s²
        gyr_y : gyroscope Y axis in dps
        """
        # ── acc_filt pipeline ─────────────────────────────────────────────────
        acc_mag  = math.sqrt(ax*ax + ay*ay + az*az)
        acc_hp   = self._hp_acc(acc_mag)
        acc_filt = self._lp_acc(acc_hp)

        # ── gyr_y HP (terrain component removal) ─────────────────────────────
        gyr_hp = self._hp_gyr(gyr_y)

        thresh = self._threshold()

        # ── acc confirmation tracking + Option C ring buffer ─────────────────
        if acc_filt > thresh:
            self._acc_above = True
            if acc_filt > self._acc_peak_this_step:
                self._acc_peak_this_step = acc_filt
            # Option C: record first below→above crossing into ring buffer.
            # These are the "rejected" heel-strike candidates — the same acc peaks
            # that time out in the standard detector.  We store the timestamp of
            # each new crossing; on push-off the oldest entry newer than
            # last_step_ts is used as the retrospective heel-strike timestamp.
            if self._acc_was_below:
                self._hs_ring.append(ts_ms)
                if len(self._hs_ring) > HS_RING_SIZE:
                    self._hs_ring.pop(0)
                self._acc_was_below = False
        else:
            self._acc_was_below = True

        # ── Push-off detection: gyr_y_hp rising above threshold (peak entry) ────
        # The phase-0.10 rebound peaks at only peak×0.05 (~9–14 dps) — below
        # GYR_PUSHOFF_THRESH_DPS. The true push-off peaks at peak×1.0 (~185–280 dps).
        # Detect the falling edge (exit from push-off) to timestamp the event.
        if gyr_hp > GYR_PUSHOFF_THRESH_DPS:
            self._in_pushoff = True

        step_event: Optional[StepEvent] = None

        if self._in_pushoff and gyr_hp <= GYR_PUSHOFF_THRESH_DPS:
            # Falling edge of push-off burst — end of stance
            elapsed_since_last = ts_ms - self._last_step_ts_ms

            if (self._acc_above
                    and elapsed_since_last >= MIN_STEP_INTERVAL_MS):

                self._record_peak(self._acc_peak_this_step)

                if self._step_count > 0:
                    self._update_cadence(elapsed_since_last)

                # Option C: find oldest ring buffer entry newer than last_step_ts.
                # This is the first acc_filt threshold crossing since the last
                # confirmed step — the retrospective heel-strike timestamp.
                heel_ts = ts_ms  # fallback: push-off ts if no crossing stored
                for ring_ts in self._hs_ring:
                    if ring_ts > self._last_step_ts_ms:
                        heel_ts = ring_ts
                        break

                stance_ms = ts_ms - heel_ts

                step_event = StepEvent(
                    step_index        = self._step_count,
                    ts_ms             = ts_ms,
                    acc_peak_ms2      = self._acc_peak_this_step,
                    heel_strike_ts_ms = heel_ts,
                    stance_duration_ms= stance_ms,
                    swing_duration_ms = 0.0,
                )

                # Fill swing_duration of the previous step now that we know
                # when this step's push-off fired.
                if self._steps:
                    prev = self._steps[-1]
                    prev.swing_duration_ms = heel_ts - prev.ts_ms

                self._steps.append(step_event)
                self._last_step_ts_ms    = ts_ms
                self._step_count        += 1
                self._acc_above          = False
                self._acc_peak_this_step = 0.0
                self._hs_ring.clear()

            self._in_pushoff = False

        self._gyr_hp_prev = gyr_hp
        return step_event

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def steps(self) -> List[StepEvent]:
        return list(self._steps)

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def cadence_spm(self) -> float:
        return self._cadence_spm
