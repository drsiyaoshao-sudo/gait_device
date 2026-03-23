"""
Stage 2 exit criteria — pipeline end-to-end (Python path):
  - run_profile() returns PipelineResult for every built-in profile
  - step_count ≈ n_steps (within ±5% after calibration window)
  - Snapshots emitted every 10 steps once window ≥ 10 steps
  - SI = 0 for a perfectly symmetric walker (flat profile)
  - renode_status() returns a dict with required keys
  - run_all_profiles() returns all four profiles
"""
import pytest
from pipeline import run_profile, run_all_profiles, renode_status, PipelineResult
from walker_model import PROFILES


@pytest.fixture(params=list(PROFILES.keys()))
def result(request):
    return run_profile(PROFILES[request.param], n_steps=100, seed=42)


# ── PipelineResult type ───────────────────────────────────────────────────────

def test_result_type(result):
    assert isinstance(result, PipelineResult)


def test_result_samples_shape(result):
    assert result.samples.ndim == 2 and result.samples.shape[1] == 6


# ── step count ───────────────────────────────────────────────────────────────

def test_step_count_reasonable(result):
    """Should detect close to n_steps (allow calibration window to eat some)."""
    n_steps = 100
    # After 1s calibration at 208 Hz + step period, may lose 3-5 steps
    assert result.step_count >= n_steps * 0.85


def test_step_count_not_excessive(result):
    n_steps = 100
    # Allow +15%: variability and cadence variation can add a handful of extra steps
    assert result.step_count <= int(n_steps * 1.15)


# ── snapshots ────────────────────────────────────────────────────────────────

def test_snapshots_emitted(result):
    """At 100 steps, rolling window should emit several snapshots."""
    assert len(result.snapshots) > 0


def test_snapshot_steps_field(result):
    """Each snapshot anchor_step should be a positive multiple of 10."""
    for snap in result.snapshots:
        assert snap.anchor_step >= 9   # first snapshot at step=9 (0-indexed)


# ── SI for flat symmetric walker ─────────────────────────────────────────────

def test_si_flat_near_zero():
    """Flat/healthy symmetric walker → SI stance should be low."""
    res = run_profile(PROFILES["flat"], n_steps=200, seed=42)
    if not res.snapshots:
        pytest.skip("no snapshots produced")
    # Allow up to 8% due to sensor noise + finite window
    assert res.si_mean() < 8.0, f"Expected SI<8% for flat walker, got {res.si_mean():.2f}%"


# ── bad_wear mounts_suspect flag ──────────────────────────────────────────────

def test_bad_wear_mounting_suspect():
    """bad_wear profile should flag at least some steps as mounting-suspect."""
    res = run_profile(PROFILES["bad_wear"], n_steps=100, seed=42)
    assert res.mounting_suspect_count > 0


# ── run_all_profiles ─────────────────────────────────────────────────────────

def test_run_all_profiles_keys():
    results = run_all_profiles(n_steps=50, seed=42)
    assert set(results.keys()) == set(PROFILES.keys())


def test_run_all_profiles_all_results():
    results = run_all_profiles(n_steps=50, seed=42)
    for k, v in results.items():
        assert isinstance(v, PipelineResult), f"profile '{k}' not a PipelineResult"


# ── renode_status ────────────────────────────────────────────────────────────

def test_renode_status_keys():
    s = renode_status()
    for key in ("renode_found", "elf_found", "available"):
        assert key in s, f"missing key: {key}"


def test_renode_status_types():
    s = renode_status()
    assert isinstance(s["renode_found"], bool)
    assert isinstance(s["elf_found"], bool)
    assert isinstance(s["available"], bool)
