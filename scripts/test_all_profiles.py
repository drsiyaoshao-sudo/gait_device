"""
Stage 3 pipeline survival test — all 4 walker profiles.

Uses step-interval SI computed from UART STEP timestamps (no SNAPSHOT needed).
Phase segmenter / rolling_window not required — step detector only.

SI formula:
    interval[N] = ts[N+1] - ts[N]
    T_odd/even  = mean interval for odd/even steps (skip first 4 warmup steps)
    SI          = 200 * |T_odd - T_even| / (T_odd + T_even)

Stage 3 criteria evaluated here:
    - total_steps within ±5 of N_STEPS  (all 4 profiles: 100)
    - SI_interval within ±3% of 0       (all walkers symmetric by design)
    - Stair walker: 100 steps PASS (Option C terrain-aware fix validated in Python)
"""

import sys
import re
import os
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
from walker_model import PROFILES, generate_imu_sequence

# ── Profile run table ─────────────────────────────────────────────────────────
RUNS = [
    ("flat",     100, 42),
    ("bad_wear", 100, 42),
    ("slope",    100, 42),
    ("stairs",   100, 42),   # 100 steps — Option C terrain-aware fix
]

# ── SI helper ─────────────────────────────────────────────────────────────────

def step_interval_si(steps_list, warmup=4):
    """Compute SI from step timestamps. Returns (T_odd, T_even, SI_pct)."""
    if len(steps_list) < warmup + 4:
        return None, None, None
    # steps_list: list of StepEvent ordered by step_index
    ts = {s.step_index: s.ts_ms for s in steps_list}
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

# ── Main loop ─────────────────────────────────────────────────────────────────

elf = detect_firmware()
if not elf:
    print("FATAL: firmware ELF not found")
    sys.exit(1)

print(f"ELF   : {elf}")
print(f"Renode: {detect_renode()}")
print()

results = []

for profile_key, n_steps, seed in RUNS:
    profile = PROFILES[profile_key]
    samples = generate_imu_sequence(profile, n_steps, rng=np.random.default_rng(seed))

    print("=" * 64)
    print(f"PROFILE: {profile.name}")
    print(f"  n_steps={n_steps}  cadence={profile.cadence_spm} spm  "
          f"samples={len(samples)}")
    print(f"  gyr_y range: [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
    print()

    bridge = RenoneBridge(elf_path=elf)
    try:
        steps, snaps, ends = bridge.run(samples)

        total = ends[0].total_steps if ends else 0
        step_pass = abs(total - n_steps) <= 5

        T_odd, T_even, si = step_interval_si(steps)
        si_pass = (si is not None) and si <= 3.0

        print(f"  Steps detected : {len(steps)}")
        print(f"  SESSION_END    : {'yes' if ends else 'NO'}")
        print(f"  total_steps    : {total}  (target {n_steps} ±5)  "
              f"{'PASS' if step_pass else 'FAIL'}")
        if si is not None:
            print(f"  SI_interval    : {si:.2f}%  "
                  f"(T_odd={T_odd:.1f}ms  T_even={T_even:.1f}ms)  "
                  f"{'PASS' if si_pass else 'FAIL'}")
        else:
            print(f"  SI_interval    : not enough steps")

        verdict = "PASS" if (step_pass and (si_pass or si is None)) else "FAIL"
        results.append((profile_key, verdict, total, si))
        print(f"  VERDICT        : {verdict}")

    except Exception as exc:
        print(f"  EXCEPTION: {type(exc).__name__}: {exc}")
        results.append((profile_key, "CRASH", 0, None))

    print()

# ── Summary ───────────────────────────────────────────────────────────────────
print("=" * 64)
print("SUMMARY")
print("=" * 64)
for key, verdict, total, si in results:
    si_str = f"SI={si:.2f}%" if si is not None else "SI=n/a"
    print(f"  {key:<12}  steps={total:<4}  {si_str:<12}  {verdict}")
print()
all_pass = all(v == "PASS" for _, v, _, _ in results)
stair = next((r for r in results if r[0] == "stairs"), None)
print(f"All profiles: {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
if stair:
    print(f"Stairs: {stair[1]}  (expected: PASS — Option C terrain-aware fix)")
