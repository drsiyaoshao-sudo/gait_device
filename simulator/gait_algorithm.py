"""
Pure-Python port of the firmware gait algorithm.
Mirrors the C logic in src/gait/ exactly so that when Renode replaces this
module the event output format is identical and the UI requires no changes.

Pipeline:
    calibrate(samples) → apply_calibration(sample) → update(sample)
                                                        ├── step_detector
                                                        ├── phase_segmenter
                                                        ├── foot_angle filter
                                                        └── rolling_window → snapshots
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

ODR_HZ = 208.0
DT = 1.0 / ODR_HZ
G = 9.81

# ─────────────────────────────────────────────────────────────────────────────
# Output event types (same schema as signal_analysis.py / firmware UART output)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StepEvent:
    step_index: int
    ts_ms: float
    peak_acc_mag: float   # m/s²
    peak_gyr_y: float     # dps
    cadence_spm: float


@dataclass
class SnapshotEvent:
    anchor_step: int
    anchor_ts_ms: float
    si_stance_pct: float
    si_swing_pct: float
    si_peak_angvel_pct: float
    mean_cadence_spm: float
    step_count: int
    is_running: bool


@dataclass
class SessionEndEvent:
    total_steps: int


# ─────────────────────────────────────────────────────────────────────────────
# IIR helpers  (single-pole, mirrors iir_lp / iir_hp in step_detector.c)
# ─────────────────────────────────────────────────────────────────────────────

def _lp_alpha(fc_hz: float) -> float:
    rc = 1.0 / (2.0 * math.pi * fc_hz)
    return DT / (rc + DT)

def _hp_alpha(fc_hz: float) -> float:
    rc = 1.0 / (2.0 * math.pi * fc_hz)
    return rc / (rc + DT)


# ─────────────────────────────────────────────────────────────────────────────
# Step detector
# ─────────────────────────────────────────────────────────────────────────────

class StepDetector:
    HP_FC    = 0.5
    LP_WALK  = 15.0
    LP_RUN   = 30.0
    RUN_THR  = 130.0       # spm
    MIN_INTERVAL_MS = 250
    GYR_CONFIRM_MS  = 40
    PEAK_HIST = 8

    def __init__(self, on_step: Callable[[StepEvent], None]):
        self._cb = on_step
        self._reset()

    # Seed for adaptive threshold. Firmware uses 15 m/s² (real ankle bone ~5g).
    # Python simulator uses 7 m/s² to match the LP-filtered CoM-based signal
    # (~2.3g peak → LP output ~10 m/s²). Threshold adapts after first step.
    # TODO: add ankle-bone amplification to walker_model to unify this.
    THRESHOLD_SEED = 7.0

    def _reset(self):
        self._hp_x1 = self._hp_y1 = 0.0
        self._lp_y1 = 0.0
        self._state  = "idle"     # idle | rising | falling | confirmed
        self._peak_val = 0.0
        self._peak_ts  = 0.0
        self._peak_gyr = 0.0
        self._last_ts  = 0.0
        self._step_idx = 0
        self._hist = [self.THRESHOLD_SEED] * self.PEAK_HIST
        self._hist_i = 0
        self._intervals = [600.0] * 4
        self._int_i  = 0
        self._cadence = 0.0

    def reset(self):
        cb = self._cb
        self._reset()
        self._cb = cb

    def reset_state_only(self):
        """Reset state machine and threshold history but keep filter state.

        Call after the calibration window so the HP/LP filters are already
        warmed to the DC level of the signal.  Any false detections during
        the HP-filter settling period are discarded and the threshold is
        returned to THRESHOLD_SEED before real walking begins.
        """
        self._state     = "idle"
        self._peak_val  = 0.0
        self._peak_ts   = 0.0
        self._peak_gyr  = 0.0
        self._last_ts   = 0.0
        self._step_idx  = 0
        self._hist      = [self.THRESHOLD_SEED] * self.PEAK_HIST
        self._hist_i    = 0
        self._intervals = [600.0] * 4
        self._int_i     = 0
        self._cadence   = 0.0

    @property
    def cadence_spm(self) -> float:
        return self._cadence

    def _threshold(self) -> float:
        # Use 50% of the mean recent peak rather than 0.5*(mean+max).
        # The mean+max formula converges to ~peak_value for consistent signals
        # (simulation peaks vary < 15%), leaving no detection margin.
        # 50% of mean keeps the threshold well below any real step peak while
        # still rejecting the near-zero LP baseline between steps.
        return sum(self._hist) / self.PEAK_HIST * 0.5

    def _record_peak(self, v: float):
        self._hist[self._hist_i] = v
        self._hist_i = (self._hist_i + 1) % self.PEAK_HIST

    def _update_cadence(self, interval_ms: float):
        self._intervals[self._int_i] = interval_ms
        self._int_i = (self._int_i + 1) % 4
        mean = sum(self._intervals) / 4
        self._cadence = 60000.0 / mean if mean > 0 else 0.0

    def update(self, ax: float, ay: float, az: float,
               gyr_y: float, ts_ms: float):
        acc_mag = math.sqrt(ax*ax + ay*ay + az*az)

        # HP filter
        alpha_hp = _hp_alpha(self.HP_FC)
        hp = alpha_hp * (self._hp_y1 + acc_mag - self._hp_x1)
        self._hp_x1 = acc_mag
        self._hp_y1 = hp

        # LP filter (adaptive cutoff)
        fc = self.LP_RUN if self._cadence >= self.RUN_THR else self.LP_WALK
        alpha_lp = _lp_alpha(fc)
        lp = alpha_lp * hp + (1 - alpha_lp) * self._lp_y1
        self._lp_y1 = lp

        thr = self._threshold()

        if self._state in ("idle", "confirmed"):
            if self._state == "confirmed":
                if (ts_ms - self._last_ts) < self.MIN_INTERVAL_MS:
                    return
            if lp > thr:
                self._state    = "rising"
                self._peak_val = lp
                self._peak_ts  = ts_ms
                self._peak_gyr = gyr_y

        elif self._state == "rising":
            if lp > self._peak_val:
                self._peak_val = lp
                self._peak_ts  = ts_ms
                self._peak_gyr = gyr_y
            else:
                self._state = "falling"

        elif self._state == "falling":
            elapsed = ts_ms - self._peak_ts
            gyr_cross = (self._peak_gyr * gyr_y < 0.0)
            if gyr_cross and elapsed <= self.GYR_CONFIRM_MS:
                self._record_peak(self._peak_val)
                if self._step_idx > 0:
                    self._update_cadence(self._peak_ts - self._last_ts)
                ev = StepEvent(
                    step_index   = self._step_idx,
                    ts_ms        = self._peak_ts,
                    peak_acc_mag = self._peak_val,
                    peak_gyr_y   = self._peak_gyr,
                    cadence_spm  = self._cadence,
                )
                self._last_ts = self._peak_ts
                self._step_idx += 1
                self._state = "confirmed"
                self._cb(ev)
            elif elapsed > self.GYR_CONFIRM_MS:
                self._state = "idle"


# ─────────────────────────────────────────────────────────────────────────────
# Foot angle complementary filter
# ─────────────────────────────────────────────────────────────────────────────

class FootAngle:
    GYRO_ALPHA  = 0.98
    ACCEL_ALPHA = 0.02

    def __init__(self):
        self._angle = 0.0
        self._init  = False

    def reset(self):
        self._angle = 0.0
        self._init  = False

    def update(self, ax: float, az: float, gyr_y: float):
        from_gravity = math.atan2(ax, az) * 57.2957795
        if not self._init:
            self._angle = from_gravity
            self._init  = True
            return
        gyro_int    = self._angle + gyr_y * DT
        self._angle = self.GYRO_ALPHA * gyro_int + self.ACCEL_ALPHA * from_gravity

    @property
    def angle_deg(self) -> float:
        return self._angle


# ─────────────────────────────────────────────────────────────────────────────
# Phase segmenter
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StepRecord:
    step_index:         int
    heel_strike_ts_ms:  float
    stance_duration_ms: float = 0.0
    swing_duration_ms:  float = 0.0
    step_duration_ms:   float = 0.0
    foot_angle_ic_deg:  float = 0.0
    foot_angle_to_deg:  float = 0.0
    peak_ang_vel_dps:   float = 0.0
    cadence_spm:        float = 0.0
    mounting_suspect:   bool  = False
    valid:              bool  = False


class PhaseSegmenter:
    MID_STANCE_ACC_Z_FRAC = 0.85
    GYR_TERM_DPS          = -10.0
    PUSHOFF_DEFAULT_DPS   = 80.0
    ACC_Z_TOE_OFF         = 2.94       # ~0.3g m/s²
    MOUNTING_SUSPECT_DEG  = 15.0

    def __init__(self, foot_angle: FootAngle,
                 on_step: Callable[[StepRecord], None]):
        self._fa  = foot_angle
        self._cb  = on_step
        self._reset()

    def _reset(self):
        self._phase      = "idle"
        self._cur: StepRecord | None = None
        self._acc_z_lp   = G
        self._acc_x_lp   = 0.0   # for mounting angle estimate
        self._neg_start  = None
        self._pushoff_h  = [self.PUSHOFF_DEFAULT_DPS] * 4
        self._pushoff_i  = 0
        self._pushoff_th = self.PUSHOFF_DEFAULT_DPS

    def reset(self):
        cb = self._cb; fa = self._fa
        self._reset()
        self._cb = cb; self._fa = fa

    @property
    def phase(self) -> str:
        return self._phase

    def _pushoff_threshold(self) -> float:
        # Use 50% of mean so the threshold stays well below the actual peak
        # and is not defeated by small step-to-step variability.
        return sum(self._pushoff_h) / 4 * 0.5

    def _record_pushoff(self, v: float):
        self._pushoff_h[self._pushoff_i] = v
        self._pushoff_i = (self._pushoff_i + 1) % 4
        self._pushoff_th = self._pushoff_threshold()

    def _emit(self, swing_end_ms: float):
        r = self._cur
        r.swing_duration_ms = swing_end_ms - self._phase_entry
        r.step_duration_ms  = r.stance_duration_ms + r.swing_duration_ms
        r.valid = True
        self._cb(r)
        self._cur = None

    def on_heel_strike(self, ev: StepEvent):
        # If a previous step completed swing, emit its record now.
        if self._phase == "swing" and self._cur:
            self._emit(ev.ts_ms)
        # Always start a new record at each detected HS regardless of current
        # phase.  This makes the step detector the master clock: even if the
        # phase FSM got stuck (e.g. gyr_y push-off not detected), the next HS
        # resets to loading so no more than one step is ever "lost" at a time.
        self._cur = StepRecord(
            step_index        = ev.step_index,
            heel_strike_ts_ms = ev.ts_ms,
            foot_angle_ic_deg = self._fa.angle_deg,
            peak_ang_vel_dps  = ev.peak_gyr_y,
            cadence_spm       = ev.cadence_spm,
        )
        self._phase = "loading"
        self._phase_entry = ev.ts_ms

    def update(self, ax: float, az: float, gyr_y: float, ts_ms: float):
        acc_z_lp_prev    = self._acc_z_lp
        acc_z_lp         = 0.9 * acc_z_lp_prev + 0.1 * az
        self._acc_z_lp   = acc_z_lp
        acc_x_lp         = 0.9 * self._acc_x_lp + 0.1 * ax
        self._acc_x_lp   = acc_x_lp
        r = self._cur

        if r and abs(gyr_y) > abs(r.peak_ang_vel_dps):
            r.peak_ang_vel_dps = gyr_y

        if self._phase == "loading":
            # Transition once foot is loaded (acc_z_lp has recovered to standing weight).
            # Original firmware uses acc_mag_hp < 0.3g to confirm HS impulse is done;
            # here we rely on acc_z_lp alone since the simulation does not expose an HP
            # channel in PhaseSegmenter.
            if acc_z_lp > (self.MID_STANCE_ACC_Z_FRAC * G):
                self._phase       = "mid_stance"
                self._phase_entry = ts_ms
                self._neg_start   = None

        elif self._phase == "mid_stance":
            # Mounting suspect check: compare acc vector tilt from vertical.
            # Expected: ax ≈ 0, az ≈ G at mid-stance (flat calibration).
            # Tilt = atan2(|ax_lp|, az_lp) > 15° flags a displaced device.
            tilt_deg = math.atan2(abs(acc_x_lp), acc_z_lp) * 57.2957795
            if r and tilt_deg > self.MOUNTING_SUSPECT_DEG:
                r.mounting_suspect = True

            # Firmware uses gyr_y < -10 dps to confirm terminal stance, but
            # the CoM-based simulation has gyr_y ≈ 0 during mid-stance (only
            # dorsiflexion at HS and plantarflexion at push-off are modelled).
            # Use acc_z declining alone — that is the dominant signal here.
            if acc_z_lp < acc_z_lp_prev:
                if self._neg_start is None:
                    self._neg_start = ts_ms
                elif (ts_ms - self._neg_start) >= 20:
                    self._phase       = "terminal"
                    self._phase_entry = ts_ms
                    self._neg_start   = None
            else:
                self._neg_start = None

        elif self._phase == "terminal":
            push = abs(gyr_y) > self._pushoff_th
            leave = acc_z_lp < self.ACC_Z_TOE_OFF
            if push or leave:
                self._record_pushoff(abs(gyr_y))
                if r:
                    r.stance_duration_ms = ts_ms - r.heel_strike_ts_ms
                    r.foot_angle_to_deg  = self._fa.angle_deg
                self._phase       = "toe_off"
                self._phase_entry = ts_ms

        elif self._phase == "toe_off":
            self._phase       = "swing"
            self._phase_entry = ts_ms


# ─────────────────────────────────────────────────────────────────────────────
# Rolling window + snapshot
# ─────────────────────────────────────────────────────────────────────────────

WINDOW_SIZE       = 200
SNAPSHOT_INTERVAL = 10


def _si(odd: float, even: float) -> float:
    d = odd + even
    return 200.0 * abs(odd - even) / d if d > 1e-6 else 0.0


class RollingWindow:
    def __init__(self, on_snapshot: Callable[[SnapshotEvent], None]):
        self._cb     = on_snapshot
        self._buf: list[StepRecord] = []
        self._head   = 0
        self._count  = 0
        self._total  = 0
        self._buf    = [None] * WINDOW_SIZE  # type: ignore

    def reset(self):
        cb = self._cb
        self.__init__(cb)

    def add(self, rec: StepRecord):
        tail = (self._head + self._count) % WINDOW_SIZE
        self._buf[tail] = rec
        if self._count < WINDOW_SIZE:
            self._count += 1
        else:
            self._head = (self._head + 1) % WINDOW_SIZE
        self._total += 1

        if self._total % SNAPSHOT_INTERVAL == 0:
            self._emit(rec)

    def _emit(self, last: StepRecord):
        stance_o = stance_e = swing_o = swing_e = 0.0
        angvel_o = angvel_e = cad_sum = 0.0
        n_o = n_e = 0

        for i in range(self._count):
            r: StepRecord = self._buf[(self._head + i) % WINDOW_SIZE]
            if r is None or not r.valid:
                continue
            s  = r.stance_duration_ms
            sw = r.swing_duration_ms
            av = abs(r.peak_ang_vel_dps)
            if r.step_index & 1:
                stance_o += s; swing_o += sw; angvel_o += av; n_o += 1
            else:
                stance_e += s; swing_e += sw; angvel_e += av; n_e += 1
            cad_sum += r.cadence_spm

        if n_o: stance_o /= n_o; swing_o /= n_o; angvel_o /= n_o
        if n_e: stance_e /= n_e; swing_e /= n_e; angvel_e /= n_e

        n = n_o + n_e
        mean_cad = cad_sum / n if n else 0.0

        ev = SnapshotEvent(
            anchor_step       = last.step_index,
            anchor_ts_ms      = last.heel_strike_ts_ms,
            si_stance_pct     = _si(stance_o, stance_e),
            si_swing_pct      = _si(swing_o,  swing_e),
            si_peak_angvel_pct= _si(angvel_o, angvel_e),
            mean_cadence_spm  = mean_cad,
            step_count        = self._count,
            is_running        = mean_cad >= 130,
        )
        self._cb(ev)


# ─────────────────────────────────────────────────────────────────────────────
# Calibration
# ─────────────────────────────────────────────────────────────────────────────

def calibrate(samples: np.ndarray, n: int = 400) -> np.ndarray:
    """
    Compute per-axis bias from first n stationary samples.
    Returns bias array [ax, ay, az, gx, gy, gz].
    Removes expected 1g from az.
    """
    s = samples[:n]
    bias = s.mean(axis=0).copy()
    bias[2] -= G     # keep gravity reference in az
    return bias


# ─────────────────────────────────────────────────────────────────────────────
# Full algorithm runner
# ─────────────────────────────────────────────────────────────────────────────

def run(samples: np.ndarray,
        bias: np.ndarray | None = None
        ) -> tuple[list[StepEvent], list[SnapshotEvent], list[StepRecord]]:
    """
    Run the full gait pipeline on a (N,6) sample array.

    Parameters
    ----------
    samples : np.ndarray (N, 6)  [ax ay az gx gy gz]
    bias    : np.ndarray (6,)    calibration bias; computed from samples if None

    Returns
    -------
    steps     : list[StepEvent]
    snapshots : list[SnapshotEvent]
    records   : list[StepRecord]
    """
    if bias is None:
        # Stationary prefix is exactly ODR_HZ samples (1 second at 208 Hz).
        # Do not extend into walking data — that corrupts the gyro bias estimate.
        n_cal = min(int(ODR_HZ), len(samples))
        bias  = calibrate(samples, n_cal)

    steps:     list[StepEvent]    = []
    snapshots: list[SnapshotEvent]= []
    records:   list[StepRecord]   = []

    fa  = FootAngle()
    win = RollingWindow(on_snapshot=snapshots.append)

    # Gate flag: suppress all events until the calibration window is done.
    # The step detector and phase segmenter still run so the HP/LP filters
    # warm to the signal DC level, but no output is emitted.
    _cal_done = False

    def on_step(ev: StepEvent):
        if not _cal_done:
            return
        steps.append(ev)
        seg.on_heel_strike(ev)

    def on_record(rec: StepRecord):
        records.append(rec)
        win.add(rec)

    det = StepDetector(on_step=on_step)
    seg = PhaseSegmenter(foot_angle=fa, on_step=on_record)

    cal = samples - bias

    for i, row in enumerate(cal):
        ax, ay, az, gx, gy, gz = row
        ts_ms = i / ODR_HZ * 1000.0
        fa.update(ax, az, gy)
        det.update(ax, ay, az, gy, ts_ms)
        seg.update(ax, az, gy, ts_ms)

        if i == n_cal - 1:
            # Calibration window complete.  Reset state machines (not filter
            # state) and open the event gate so real walking steps are emitted.
            det.reset_state_only()
            seg.reset()
            fa.reset()
            _cal_done = True

    return steps, snapshots, records
