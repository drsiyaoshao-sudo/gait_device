"""
Pipeline orchestrator — pure Python path (default) + optional Renode path.

Two execution paths share the same PipelineResult interface:

    PythonPipeline (default, always available)
        WalkerProfile → generate_imu_sequence() → gait_algorithm.run()

    RenonePipeline (requires renode binary + firmware.elf)
        WalkerProfile → generate_imu_sequence()
                      → imu_model.quantize_to_file()
                      → Renode (firmware.elf on nRF52840 + LSM6DS3 stub)
                      → signal_analysis.parse_uart_log()

The UI (app.py) calls run_profile() / run_all_profiles() only.
It never imports from gait_algorithm or renode_bridge directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Optional

import numpy as np

from walker_model import WalkerProfile, PROFILES, generate_imu_sequence, profile_summary
from gait_algorithm import (
    StepEvent, SnapshotEvent, StepRecord,
    run as _run_algorithm,
)


# ─────────────────────────────────────────────────────────────────────────────
# PipelineResult — identical regardless of which path produced it
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    profile:    WalkerProfile
    samples:    np.ndarray          # (N, 6) calibrated float32
    via_renode: bool                # True if produced by Renode path

    steps:      list[StepEvent]
    snapshots:  list[SnapshotEvent]
    records:    list[StepRecord]    # empty when via_renode=True (firmware owns this)

    summary:    dict                # from profile_summary()

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def snapshot_si_stance(self) -> list[float]:
        return [s.si_stance_pct for s in self.snapshots]

    @property
    def snapshot_si_swing(self) -> list[float]:
        return [s.si_swing_pct for s in self.snapshots]

    @property
    def snapshot_steps(self) -> list[int]:
        return [s.anchor_step for s in self.snapshots]

    @property
    def step_ts_ms(self) -> list[float]:
        return [s.ts_ms for s in self.steps]

    @property
    def step_sample_idx(self) -> list[int]:
        """Sample index corresponding to each detected heel strike."""
        odr = 208.0
        return [int(s.ts_ms / 1000.0 * odr) for s in self.steps]

    @property
    def mounting_suspect_count(self) -> int:
        return sum(1 for r in self.records if r.mounting_suspect)

    def si_mean(self) -> float:
        v = self.snapshot_si_stance
        return sum(v) / len(v) if v else 0.0

    def si_max(self) -> float:
        v = self.snapshot_si_stance
        return max(v) if v else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Renode availability check (lazy import to avoid error if bridge not installed)
# ─────────────────────────────────────────────────────────────────────────────

def _renode_available(elf_path: Optional[str] = None) -> bool:
    """Return True only if both the renode binary and firmware ELF exist."""
    try:
        from renode_bridge import is_available
        return is_available(elf_path)
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Pure Python path
# ─────────────────────────────────────────────────────────────────────────────

def _apply_si_override(profile: WalkerProfile, si_override: Optional[float]) -> WalkerProfile:
    """Return a copy of profile with si_stance_true_pct replaced, or the original."""
    if si_override is None:
        return profile
    return replace(profile, si_stance_true_pct=si_override)


def _run_python(
    profile: WalkerProfile,
    n_steps: int,
    seed: int,
    use_legacy: bool = False,
) -> PipelineResult:
    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)
    steps, snapshots, records = _run_algorithm(samples, use_legacy=use_legacy)

    return PipelineResult(
        profile    = profile,
        samples    = samples,
        via_renode = False,
        steps      = steps,
        snapshots  = snapshots,
        records    = records,
        summary    = profile_summary(profile),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Renode path
# ─────────────────────────────────────────────────────────────────────────────

def _run_renode(
    profile:  WalkerProfile,
    n_steps:  int,
    seed:     int,
    elf_path: Optional[str],
) -> PipelineResult:
    from renode_bridge import RenoneBridge, detect_firmware, _DEFAULT_REPL, _DEFAULT_RESC

    rng     = np.random.default_rng(seed)
    samples = generate_imu_sequence(profile, n_steps, rng=rng)

    elf = elf_path or detect_firmware()
    bridge = RenoneBridge(
        elf_path  = elf,
        repl_path = _DEFAULT_REPL,
        resc_path = _DEFAULT_RESC,
    )
    steps, snapshots, session_ends = bridge.run(samples)

    return PipelineResult(
        profile    = profile,
        samples    = samples,
        via_renode = True,
        steps      = steps,
        snapshots  = snapshots,
        records    = [],        # firmware owns step records; Python path has them
        summary    = profile_summary(profile),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_profile(
    profile:     WalkerProfile,
    n_steps:     int   = 200,
    seed:        int   = 42,
    use_renode:  bool  = False,
    elf_path:    Optional[str]   = None,
    si_override: Optional[float] = None,
    use_legacy:  bool  = False,
) -> PipelineResult:
    """
    Run a single walker profile through the simulation pipeline.

    Parameters
    ----------
    profile : WalkerProfile
    n_steps : int
        Number of gait steps to simulate (excluding the 1s stationary prefix).
    seed : int
        RNG seed for reproducible noise.
    use_renode : bool
        If True, attempt to use the Renode embedded path.
        Falls back silently to the Python path if Renode or the firmware ELF
        is unavailable.
    elf_path : str | None
        Override path to firmware.elf (Renode path only).
    """
    profile = _apply_si_override(profile, si_override)
    if use_renode:
        if _renode_available(elf_path):
            try:
                return _run_renode(profile, n_steps, seed, elf_path)
            except Exception as exc:
                import warnings
                warnings.warn(
                    f"Renode run failed for profile '{profile.name}': {exc!r}. "
                    "Falling back to Python path.",
                    RuntimeWarning,
                    stacklevel=2,
                )
        # Graceful fallback: Renode not found, ELF not built, or run failed
    return _run_python(profile, n_steps, seed, use_legacy=use_legacy)


def run_all_profiles(
    n_steps:     int   = 200,
    seed:        int   = 42,
    use_renode:  bool  = False,
    elf_path:    Optional[str]   = None,
    si_override: Optional[float] = None,
    profile_keys: Optional[list] = None,
    use_legacy:  bool  = False,
) -> dict[str, PipelineResult]:
    """Run walker profiles and return results keyed by profile name.

    profile_keys: subset of PROFILES to run; defaults to all.
    si_override:  if set, overrides si_stance_true_pct on every profile.
    use_legacy:   if True, use original dual-confirmation step detector.
    """
    keys = profile_keys if profile_keys is not None else list(PROFILES.keys())
    return {
        key: run_profile(PROFILES[key], n_steps, seed, use_renode, elf_path,
                         si_override, use_legacy=use_legacy)
        for key in keys
    }


def renode_status(elf_path: Optional[str] = None) -> dict:
    """
    Return a dict describing Renode availability for the UI status panel.

    Keys: renode_found, elf_found, renode_path, elf_path, available
    """
    try:
        from renode_bridge import detect_renode, detect_firmware
        renode_path = detect_renode()
        fw_path     = detect_firmware(elf_path)
        return {
            "renode_found": bool(renode_path),
            "elf_found":    bool(fw_path),
            "renode_path":  renode_path or "",
            "elf_path":     fw_path or "",
            "available":    bool(renode_path and fw_path),
        }
    except ImportError:
        return {
            "renode_found": False,
            "elf_found":    False,
            "renode_path":  "",
            "elf_path":     "",
            "available":    False,
        }
