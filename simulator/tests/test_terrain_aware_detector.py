"""
Python Stage 2 exit criteria for TerrainAwareStepDetector.

Exit criteria (all must pass before porting to C):
  1. flat    100 steps → detected within ±5
  2. bad_wear 100 steps → detected within ±5
  3. slope   100 steps → detected within ±5
  4. stairs  100 steps → detected within ±5  ← key regression fix
  5. SI_interval < 3% for all non-failure profiles (symmetric walkers)
  6. SI_interval < 3% for stairs (symmetric walker, now detectable)
  7. False-positive guard: zero steps on 5s stationary signal
  8. Minimum step interval enforced: no two steps < 250ms apart
  9. Option C heel-strike ring buffer: stance_duration within tolerance (all 4 profiles)
 10. Option C: swing_duration populated and within tolerance (all 4 profiles)
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "simulator"))

from walker_model import PROFILES, generate_imu_sequence
from terrain_aware_step_detector import TerrainAwareStepDetector, ODR_HZ


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_detector(profile, n_steps, seed=42):
    """Feed generate_imu_sequence through TerrainAwareStepDetector. Returns steps list."""
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)
    det     = TerrainAwareStepDetector()

    for i, row in enumerate(samples):
        ts_ms = i / ODR_HZ * 1000.0
        det.update(ts_ms, row[0], row[1], row[2], row[4])

    return det.steps


def step_interval_si(steps, warmup=4):
    """SI from step timestamps. Returns (T_odd, T_even, SI_pct) or (None,None,None)."""
    if len(steps) < warmup + 4:
        return None, None, None
    ts      = {s.step_index: s.ts_ms for s in steps}
    indices = sorted(ts)
    intervals = {indices[i]: ts[indices[i+1]] - ts[indices[i]]
                 for i in range(len(indices) - 1)}
    odd  = [v for k, v in intervals.items() if k >= warmup and k % 2 == 1]
    even = [v for k, v in intervals.items() if k >= warmup and k % 2 == 0]
    if not odd or not even:
        return None, None, None
    T_odd  = sum(odd)  / len(odd)
    T_even = sum(even) / len(even)
    denom  = T_odd + T_even
    if denom < 1e-6:
        return T_odd, T_even, None
    si = 200.0 * abs(T_odd - T_even) / denom
    return T_odd, T_even, si


# ── Step count tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("profile_key,n_steps,tolerance", [
    ("flat",     100, 5),
    ("bad_wear", 100, 5),
    ("slope",    100, 5),
    ("stairs",   100, 5),   # ← terrain patch: stairs now treated as full 100-step profile
])
def test_step_count(profile_key, n_steps, tolerance):
    steps = run_detector(PROFILES[profile_key], n_steps)
    detected = len(steps)
    assert abs(detected - n_steps) <= tolerance, (
        f"{profile_key}: detected {detected}, expected {n_steps} ±{tolerance}"
    )


# ── SI tests ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("profile_key,n_steps", [
    ("flat",     100),
    ("bad_wear", 100),
    ("slope",    100),
    ("stairs",   100),
])
def test_si_interval(profile_key, n_steps):
    steps = run_detector(PROFILES[profile_key], n_steps)
    _, _, si = step_interval_si(steps)
    assert si is not None, f"{profile_key}: not enough steps for SI"
    assert si <= 3.0, (
        f"{profile_key}: SI_interval={si:.2f}% exceeds 3% tolerance "
        f"(symmetric walker should be near 0%)"
    )


# ── False positive test ───────────────────────────────────────────────────────

def test_no_false_positives_stationary():
    """5 seconds of stationary IMU (gravity only + noise) → 0 steps."""
    rng     = np.random.default_rng(0)
    n       = int(5.0 * ODR_HZ)
    # acc_z = 9.81, all others near zero
    samples = np.zeros((n, 6), dtype=np.float32)
    samples[:, 2] = 9.81
    samples += rng.normal(0, 0.01, samples.shape).astype(np.float32)

    det = TerrainAwareStepDetector()
    for i, row in enumerate(samples):
        ts_ms = i / ODR_HZ * 1000.0
        det.update(ts_ms, row[0], row[1], row[2], row[4])

    assert det.step_count == 0, (
        f"Expected 0 steps on stationary signal, got {det.step_count}"
    )


# ── Minimum interval test ─────────────────────────────────────────────────────

def test_minimum_step_interval():
    """No two consecutive detected steps should be < 250ms apart."""
    from terrain_aware_step_detector import MIN_STEP_INTERVAL_MS
    steps = run_detector(PROFILES["flat"], 100)
    for i in range(1, len(steps)):
        interval = steps[i].ts_ms - steps[i-1].ts_ms
        assert interval >= MIN_STEP_INTERVAL_MS, (
            f"Step interval {interval:.1f}ms < {MIN_STEP_INTERVAL_MS}ms "
            f"between steps {i-1} and {i}"
        )


# ── Option C stance/swing accuracy tests ──────────────────────────────────────
#
# Ground truth from walker_model (all symmetric profiles):
#   flat/bad_wear : step_period=571ms, stance_frac=0.60 → stance=343ms, swing=229ms
#   slope (10°)  : step_period=632ms, stance_frac=0.62 → stance=392ms, swing=240ms
#   stairs        : step_period=857ms, stance_frac=0.65 → stance=557ms, swing=300ms
#
# Option C tolerance:
#   flat/bad_wear/slope : heel-strike from sharp acc impulse → ±80ms
#   stairs              : heel-strike from first sigmoid crossing → ±150ms
#   (Option C docs: expected -50 to -100ms error on stairs; better than +295ms without it)
#
# swing_duration (steps 5..N-2 to skip warmup and last step): within ±100ms of GT

@pytest.mark.parametrize("profile_key,gt_stance_ms,stance_tol_ms", [
    ("flat",     343.0, 80),
    ("bad_wear", 343.0, 80),
    ("slope",    392.0, 80),
    ("stairs",   557.0, 150),
])
def test_option_c_stance_duration(profile_key, gt_stance_ms, stance_tol_ms):
    """Option C: mean stance_duration_ms within tolerance of ground truth (steps 5+)."""
    steps = run_detector(PROFILES[profile_key], 100, seed=42)
    assert len(steps) >= 10, f"{profile_key}: too few steps ({len(steps)}) to evaluate stance"
    # Skip warmup steps (first 4) and last step (swing not yet filled)
    core = [s for s in steps if s.step_index >= 4]
    assert core, f"{profile_key}: no steps after warmup"
    mean_stance = sum(s.stance_duration_ms for s in core) / len(core)
    err = mean_stance - gt_stance_ms
    assert abs(err) <= stance_tol_ms, (
        f"{profile_key}: mean stance_duration={mean_stance:.1f}ms  "
        f"GT={gt_stance_ms:.0f}ms  error={err:+.1f}ms  tol=±{stance_tol_ms}ms"
    )


@pytest.mark.parametrize("profile_key,gt_swing_ms,swing_tol_ms", [
    ("flat",     229.0, 100),
    ("bad_wear", 229.0, 100),
    ("slope",    240.0, 100),
    ("stairs",   300.0, 150),
])
def test_option_c_swing_duration(profile_key, gt_swing_ms, swing_tol_ms):
    """Option C: swing_duration populated for all steps except the last; mean within tolerance."""
    steps = run_detector(PROFILES[profile_key], 100, seed=42)
    assert len(steps) >= 10, f"{profile_key}: too few steps"
    # Skip warmup (first 4) and last step (swing_duration stays 0.0 — next push-off not yet fired)
    core = [s for s in steps if s.step_index >= 4 and s.step_index < len(steps) - 1]
    assert core, f"{profile_key}: no steps in core window"
    zero_swing = [s.step_index for s in core if s.swing_duration_ms == 0.0]
    assert not zero_swing, (
        f"{profile_key}: swing_duration=0 on steps {zero_swing} (Option C backfill failed)"
    )
    mean_swing = sum(s.swing_duration_ms for s in core) / len(core)
    err = mean_swing - gt_swing_ms
    assert abs(err) <= swing_tol_ms, (
        f"{profile_key}: mean swing_duration={mean_swing:.1f}ms  "
        f"GT={gt_swing_ms:.0f}ms  error={err:+.1f}ms  tol=±{swing_tol_ms}ms"
    )
