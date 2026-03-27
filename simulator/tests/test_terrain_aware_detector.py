"""
Python Stage 2 exit criteria for TerrainAwareStepDetector.

Exit criteria (all must pass before porting to C):
  1. flat    100 steps → detected within ±5
  2. bad_wear 100 steps → detected within ±5
  3. slope   100 steps → detected within ±5
  4. stairs   50 steps → detected within ±5  ← key regression fix
  5. SI_interval < 3% for all non-failure profiles (symmetric walkers)
  6. SI_interval < 3% for stairs (symmetric walker, now detectable)
  7. False-positive guard: zero steps on 5s stationary signal
  8. Minimum step interval enforced: no two steps < 250ms apart
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
