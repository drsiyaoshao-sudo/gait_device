"""
Single-profile Renode test — flat walker, 100 steps.
Stage 3 smoke test for Option C firmware.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
from walker_model import PROFILES, generate_imu_sequence

def step_interval_si(steps_list, warmup=4):
    if len(steps_list) < warmup + 4:
        return None, None, None
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
    si = 200.0 * abs(T_odd - T_even) / denom if denom > 1e-6 else None
    return T_odd, T_even, si

elf = detect_firmware()
if not elf:
    print("FATAL: firmware ELF not found"); sys.exit(1)

print(f"ELF   : {elf}")
print(f"Renode: {detect_renode()}")
print()

profile = PROFILES["flat"]
samples = generate_imu_sequence(profile, 100, rng=np.random.default_rng(42))

print(f"Profile : {profile.name}  cadence={profile.cadence_spm} spm")
print(f"Samples : {len(samples)}  ({len(samples)/208.0:.1f}s)")
print(f"gyr_y range : [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
print()

bridge = RenoneBridge(elf_path=elf)
steps, snaps, ends = bridge.run(samples)

total = ends[0].total_steps if ends else 0
T_odd, T_even, si = step_interval_si(steps)

print(f"Steps detected : {len(steps)}")
print(f"SESSION_END    : {'yes — total_steps=' + str(total) if ends else 'NOT RECEIVED'}")
print(f"Step count     : {total}  (target 100 ±5)  {'PASS' if abs(total-100)<=5 else 'FAIL'}")
if si is not None:
    print(f"SI_interval    : {si:.2f}%  (T_odd={T_odd:.1f}ms  T_even={T_even:.1f}ms)  "
          f"{'PASS' if si<=3.0 else 'FAIL'}")
else:
    print(f"SI_interval    : not enough steps")

if steps:
    print(f"\nFirst 5 steps:")
    for s in steps[:5]:
        print(f"  step {s.step_index:>3}  ts={s.ts_ms:>8} ms")
