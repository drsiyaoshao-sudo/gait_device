"""
Walker biomechanical model — signal generator grounded in three first-order primitives:
    1. vertical_oscillation_cm  — CoM vertical displacement per step
    2. cadence_spm              — steps per minute
    3. step_length_m            — meters per step

All signal shape parameters are derived from these three.
Never set hs_impact_g or peak_angvel_dps directly.

Four walkers for standard gait algorithm efficacy study:
    Walker 1 — Healthy adult, flat ground (reference)
    Walker 2 — Healthy adult, flat ground, bad device wearing (mounting error + loose fit)
    Walker 3 — Healthy adult, ascending stairs
    Walker 4 — Healthy adult, ascending slope (~10°)

All walkers are symmetric (si_true = 0%). The study question is:
  Does the standard gait imbalance algorithm correctly report SI ≈ 0%
  under each terrain, or does terrain corrupt the output?
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

ODR_HZ: float = 208.0
G: float = 9.81            # m/s²
IMPACT_DURATION_S: float = 0.05   # typical HS arrest duration

# LSM6DS3TR-C sensor noise (RMS at 208 Hz bandwidth)
_ACCEL_NOISE_RMS: float = (90e-6 * G) * math.sqrt(ODR_HZ / 2)   # m/s²
_GYRO_NOISE_RMS: float  = 4e-3 * math.sqrt(ODR_HZ / 2)           # dps


# ─────────────────────────────────────────────────────────────────────────────
# Profile dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WalkerProfile:
    name: str
    terrain: Literal["flat", "slope", "stairs"]

    # ── Three first-order primitives (set these; everything else is derived) ──
    cadence_spm: float             # steps / minute
    step_length_m: float           # meters per step
    vertical_oscillation_cm: float # CoM vertical movement per step (cm)

    # ── Terrain geometry ────────────────────────────────────────────────────
    slope_deg: float = 0.0         # incline angle in degrees (0 = flat)

    # ── Stance fraction (biomechanical, varies with terrain) ─────────────────
    stance_frac: float = 0.60      # fraction of step cycle spent in stance

    # ── Signal quality (Walker 2 only) ───────────────────────────────────────
    mounting_offset_deg: float = 0.0    # Y-axis IMU rotation error
    loose_fit_attenuation: float = 1.0  # 1.0 = perfect; 0.5 = half peak amplitude

    # ── Natural timing noise ─────────────────────────────────────────────────
    step_variability_ms: float = 15.0

    # ── True symmetry index (healthy = 0) ────────────────────────────────────
    si_stance_true_pct: float = 0.0
    si_swing_true_pct: float  = 0.0

    # ── Derived (computed in __post_init__) ──────────────────────────────────
    walking_speed_ms: float = field(init=False)
    hs_impact_ms2: float    = field(init=False)   # extra acc at heel strike (m/s²)
    peak_angvel_dps: float  = field(init=False)   # push-off angular velocity

    def __post_init__(self) -> None:
        self.walking_speed_ms = (self.cadence_spm / 60.0) * self.step_length_m

        # Heel strike impact: CoM free-falls vert_osc/2 before arrest
        # Stairs: toe-strike — no sharp impulse, use 0 (rise is gradual)
        if self.terrain == "stairs":
            self.hs_impact_ms2 = 0.0
        else:
            v_impact = math.sqrt(2 * G * (self.vertical_oscillation_cm / 200.0))
            self.hs_impact_ms2 = v_impact / IMPACT_DURATION_S

        # Push-off angular velocity: empirical linear fit (validated for 0.8–3 m/s)
        # Slope correction: more ankle work against gravity component
        slope_factor = 1.0 + 0.4 * math.sin(math.radians(self.slope_deg))
        self.peak_angvel_dps = (100.0 + 65.0 * self.walking_speed_ms) * slope_factor

        # Stairs: extra plantarflexion to clear the riser (~18 cm lift)
        if self.terrain == "stairs":
            self.peak_angvel_dps *= 1.5


# ─────────────────────────────────────────────────────────────────────────────
# Built-in profiles
# ─────────────────────────────────────────────────────────────────────────────

PROFILES: dict[str, WalkerProfile] = {
    "flat": WalkerProfile(
        name="Walker 1 — Healthy adult, flat",
        terrain="flat",
        cadence_spm=105,
        step_length_m=0.75,
        vertical_oscillation_cm=4.0,
        slope_deg=0.0,
        stance_frac=0.60,
        step_variability_ms=15,
    ),
    "bad_wear": WalkerProfile(
        name="Walker 2 — Bad wearing, flat",
        terrain="flat",
        cadence_spm=105,
        step_length_m=0.75,
        vertical_oscillation_cm=4.0,
        slope_deg=0.0,
        stance_frac=0.60,
        mounting_offset_deg=20.0,      # realistic field error: device rotated 20°
        loose_fit_attenuation=0.55,    # 45% attenuation of HS impulse peak
        step_variability_ms=15,
    ),
    "stairs": WalkerProfile(
        name="Walker 3 — Ascending stairs",
        terrain="stairs",
        cadence_spm=70,
        step_length_m=0.28,            # stair tread depth
        vertical_oscillation_cm=18.0,  # riser height dominates vertical motion
        slope_deg=0.0,
        stance_frac=0.65,              # longer stance: carrying body up
        step_variability_ms=25,        # more variable timing on stairs
    ),
    "slope": WalkerProfile(
        name="Walker 4 — Ascending slope (10°)",
        terrain="slope",
        cadence_spm=95,
        step_length_m=0.65,
        vertical_oscillation_cm=5.0,
        slope_deg=10.0,
        stance_frac=0.62,
        step_variability_ms=18,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Signal generation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _rotation_y(deg: float) -> np.ndarray:
    """3×3 rotation matrix around Y axis (mounting offset)."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)


def _generate_step(
    profile: WalkerProfile,
    step_idx: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate one step worth of IMU samples.

    Returns array shape (N, 6): [ax, ay, az, gx, gy, gz]
    Units: m/s² for acc, dps for gyro
    """
    odr = ODR_HZ

    # Per-step duration variability
    step_period_s   = 60.0 / profile.cadence_spm
    stance_dur_s    = step_period_s * profile.stance_frac + rng.normal(0, profile.step_variability_ms / 1000)
    swing_dur_s     = step_period_s * (1 - profile.stance_frac) + rng.normal(0, profile.step_variability_ms * 0.5 / 1000)
    stance_dur_s    = max(stance_dur_s, 0.10)
    swing_dur_s     = max(swing_dur_s,  0.08)

    n_stance = max(1, int(stance_dur_s * odr))
    n_swing  = max(1, int(swing_dur_s  * odr))
    n_total  = n_stance + n_swing

    acc = np.zeros((n_total, 3), dtype=np.float32)
    gyr = np.zeros((n_total, 3), dtype=np.float32)

    # ── Slope: permanent DC offsets from gravity projection ──────────────────
    # These are applied to the baseline throughout the whole step.
    # Device was calibrated on flat → slope injects a constant bias the
    # algorithm cannot distinguish from real horizontal acceleration.
    slope_rad   = math.radians(profile.slope_deg)
    acc_x_dc    = G * math.sin(slope_rad)   # always present on slope, 0 on flat
    acc_z_dc    = G * math.cos(slope_rad)   # reduced from G on slope

    # ── Stance phase ─────────────────────────────────────────────────────────
    for i in range(n_stance):
        t     = i / odr
        phase = i / n_stance

        if profile.terrain == "stairs":
            # Toe-strike: no leading Gaussian impulse. acc_z rises gradually
            # as foot rolls back and body weight loads the limb.
            # Shape: sigmoid-like rise from ~0.5g → peak ~1.2g → fall at push-off
            loading = acc_z_dc + G * (0.5 + 0.7 * math.sin(math.pi * phase * 0.85))
            acc[i, 2] = loading

            # Forward lean on stairs: acc_x slightly elevated
            acc[i, 0] = acc_x_dc + 1.5 * math.sin(math.pi * phase)

        else:
            # Flat / slope: heel-strike Gaussian impulse
            hs_sigma = 0.015
            hs_mu    = 0.015
            impulse  = math.exp(-((t - hs_mu) ** 2) / (2 * hs_sigma ** 2))

            # Attenuate peak for loose fit (Walker 2)
            effective_impact = profile.hs_impact_ms2 * profile.loose_fit_attenuation

            acc[i, 0] = acc_x_dc + effective_impact * 0.35 * impulse   # anterior component
            acc[i, 2] = (acc_z_dc
                         + effective_impact * impulse                    # HS impact
                         + 2.0 * math.sin(math.pi * phase * 0.7))       # loading arc

        # gyr_y: dorsiflexion at HS (negative), plantarflexion at push-off (positive)
        #
        # Phase 0.00–0.10: dorsiflexion — ankle rapidly tilts forward at heel contact.
        #   Exponential decay from peak (phase 0.00) to near-zero by phase 0.10.
        #   At the LP-filtered acc_filt peak (~phase 0.07) gyr_y ≈ −8 dps — clearly
        #   above the 5 dps confirmation gate in step_detector.c.
        #
        # Phase 0.10–0.18: brief positive rebound (ankle rocker return).
        #   Real ankles show a small positive gyr_y as the heel fully grounds.
        #   This gives a deterministic positive zero-crossing at phase 0.10 (~14ms
        #   after the acc_filt peak), eliminating noise-dependent confirmation misses
        #   that would otherwise occur ~0.4% of steps and cause ≤3/100 missed detections.
        if phase < 0.10:
            gyr[i, 1] = -profile.peak_angvel_dps * 0.35 * math.exp(-phase * 30)
        elif phase < 0.18:
            rebound_phase = (phase - 0.10) / 0.08
            gyr[i, 1] = profile.peak_angvel_dps * 0.05 * math.sin(math.pi * rebound_phase)
        elif phase > 0.75:
            push_phase = (phase - 0.75) / 0.25
            gyr[i, 1] = profile.peak_angvel_dps * math.sin(math.pi * push_phase)

    # ── Swing phase ───────────────────────────────────────────────────────────
    for i in range(n_swing):
        phase = i / n_swing
        # Foot unloaded; small oscillation in acc_z (leg swing)
        acc[n_stance + i, 2] = acc_z_dc * 0.25 + 1.5 * math.sin(math.pi * phase)
        acc[n_stance + i, 0] = acc_x_dc * 0.3
        # Foot decelerates into next contact
        gyr[n_stance + i, 1] = -profile.peak_angvel_dps * 0.25 * math.sin(math.pi * phase)

    # ── Sensor noise ──────────────────────────────────────────────────────────
    acc += rng.normal(0, _ACCEL_NOISE_RMS, (n_total, 3)).astype(np.float32)
    gyr += rng.normal(0, _GYRO_NOISE_RMS,  (n_total, 3)).astype(np.float32)

    # ── Mounting offset rotation (Walker 2) ───────────────────────────────────
    if profile.mounting_offset_deg != 0.0:
        R = _rotation_y(profile.mounting_offset_deg)
        acc = (R @ acc.T).T.astype(np.float32)
        gyr = (R @ gyr.T).T.astype(np.float32)

    return np.concatenate([acc, gyr], axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

STATIONARY_PREFIX_SAMPLES = int(ODR_HZ)    # 1 second at rest before walking begins


def generate_imu_sequence(
    profile: WalkerProfile,
    n_steps: int,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Generate a synthetic IMU sequence for n_steps steps.

    Returns
    -------
    np.ndarray, shape (N_samples, 6)
        Columns: [ax, ay, az, gx, gy, gz]  (m/s², m/s², m/s², dps, dps, dps)
    """
    if rng is None:
        rng = np.random.default_rng(42)

    # Stationary prefix: device at rest during boot calibration.
    # acc_z = gravity (adjusted for slope), all other axes near zero.
    slope_rad = math.radians(profile.slope_deg)
    static = np.zeros((STATIONARY_PREFIX_SAMPLES, 6), dtype=np.float32)
    static[:, 0] = G * math.sin(slope_rad)    # acc_x DC from slope
    static[:, 2] = G * math.cos(slope_rad)    # acc_z baseline
    static += rng.normal(0, _ACCEL_NOISE_RMS, static.shape).astype(np.float32) * np.array(
        [1, 1, 1, 0, 0, 0], dtype=np.float32)
    static += rng.normal(0, _GYRO_NOISE_RMS, static.shape).astype(np.float32) * np.array(
        [0, 0, 0, 1, 1, 1], dtype=np.float32)

    steps = [_generate_step(profile, i, rng) for i in range(n_steps)]
    return np.concatenate([static] + steps, axis=0)


def profile_summary(profile: WalkerProfile) -> dict:
    """Return derived physical parameters for display in the UI."""
    return {
        "Walking speed (m/s)":       round(profile.walking_speed_ms, 2),
        "HS impact extra (m/s²)":    round(profile.hs_impact_ms2, 1),
        "HS impact (g)":             round((G + profile.hs_impact_ms2) / G, 2),
        "Push-off gyr_y peak (dps)": round(profile.peak_angvel_dps, 0),
        "Stance duration (ms)":      round(profile.stance_frac * 60 / profile.cadence_spm * 1000, 0),
        "Swing duration (ms)":       round((1 - profile.stance_frac) * 60 / profile.cadence_spm * 1000, 0),
        "acc_x DC (slope, m/s²)":   round(G * math.sin(math.radians(profile.slope_deg)), 2),
        "acc_z baseline (m/s²)":    round(G * math.cos(math.radians(profile.slope_deg)), 2),
    }


if __name__ == "__main__":
    for key, profile in PROFILES.items():
        print(f"\n{'─'*60}")
        print(f"  {profile.name}")
        print(f"{'─'*60}")
        for k, v in profile_summary(profile).items():
            print(f"  {k:<35} {v}")
        data = generate_imu_sequence(profile, 20)
        print(f"  Samples generated: {len(data)}")
        print(f"  acc_z mean: {data[:, 2].mean():.2f} m/s²   peak: {data[:, 2].max():.2f} m/s²")
        print(f"  gyr_y min:  {data[:, 4].min():.1f} dps      max: {data[:, 4].max():.1f} dps")
