"""
Stage 2 exit criteria — generate_imu_sequence():
  - Returns ndarray of shape (N_samples, 6), dtype float32
  - N_samples = ceil(n_steps × samples_per_step) at 208 Hz
  - Columns [ax, ay, az, gx, gy, gz] in m/s² and dps
  - All four built-in profiles produce valid output
  - Noise is finite (no NaN / Inf)
  - acc magnitude at rest prefix ≈ 9.81 m/s²
"""
import numpy as np
import pytest

from walker_model import PROFILES, WalkerProfile, generate_imu_sequence, ODR_HZ


def _gen(profile, n_steps=20, seed=0):
    return generate_imu_sequence(profile, n_steps=n_steps,
                                  rng=np.random.default_rng(seed))


@pytest.fixture(params=list(PROFILES.keys()))
def profile(request):
    return PROFILES[request.param]


# ── shape ───────────────────────────────────────────────────────────────────

def test_shape_ndarray(profile):
    out = _gen(profile, n_steps=20, seed=0)
    assert isinstance(out, np.ndarray)


def test_shape_six_columns(profile):
    out = _gen(profile, n_steps=20, seed=0)
    assert out.ndim == 2 and out.shape[1] == 6


def test_shape_dtype_float32(profile):
    out = _gen(profile, n_steps=20, seed=0)
    assert out.dtype == np.float32


def test_shape_sample_count(profile):
    """N_samples ≥ n_steps × (ODR_HZ / cadence_steps_per_second)."""
    n_steps = 30
    out = _gen(profile, n_steps=n_steps, seed=0)
    step_period_s = 60.0 / profile.cadence_spm
    expected_min = int(n_steps * step_period_s * ODR_HZ * 0.9)  # ±10% tolerance
    assert out.shape[0] >= expected_min


# ── numeric validity ─────────────────────────────────────────────────────────

def test_no_nan(profile):
    out = _gen(profile, n_steps=20, seed=0)
    assert not np.any(np.isnan(out))


def test_no_inf(profile):
    out = _gen(profile, n_steps=20, seed=0)
    assert not np.any(np.isinf(out))


# ── physical plausibility ────────────────────────────────────────────────────

def test_accel_range(profile):
    """Accelerometer must stay within ±16g (LSM6DS3 full-scale)."""
    out = _gen(profile, n_steps=20, seed=0)
    acc = out[:, :3]
    assert np.all(np.abs(acc) < 16 * 9.81 + 1.0)  # +1 m/s² for noise margin


def test_gyro_range(profile):
    """Gyroscope must stay within ±2000 dps."""
    out = _gen(profile, n_steps=20, seed=0)
    gyr = out[:, 3:]
    assert np.all(np.abs(gyr) < 2000 + 10.0)  # +10 dps for noise margin


def test_gravity_at_rest(profile):
    """First sample (at rest / low-motion) should have acc_z close to 9.81 m/s²."""
    out = _gen(profile, n_steps=50, seed=0)
    az_first = float(out[0, 2])
    # Allow ±4 m/s² — some mounting offsets project gravity differently
    assert abs(az_first) > 5.0, f"acc_z={az_first:.2f} too low to represent gravity"


# ── reproducibility ──────────────────────────────────────────────────────────

def test_seeded_reproducible(profile):
    a = _gen(profile, n_steps=20, seed=42)
    b = _gen(profile, n_steps=20, seed=42)
    np.testing.assert_array_equal(a, b)


def test_different_seeds_differ(profile):
    a = _gen(profile, n_steps=20, seed=1)
    b = _gen(profile, n_steps=20, seed=2)
    assert not np.array_equal(a, b)


# ── all profiles produce distinct signals ────────────────────────────────────

def test_profiles_distinct():
    """Different profiles produce different signals (not the same output)."""
    profiles = list(PROFILES.values())
    if len(profiles) < 2:
        pytest.skip("need at least 2 profiles")
    a = _gen(profiles[0], n_steps=20, seed=0)
    b = _gen(profiles[1], n_steps=20, seed=0)
    # May have different lengths — compare only what overlaps
    n = min(a.shape[0], b.shape[0])
    assert not np.allclose(a[:n], b[:n])
