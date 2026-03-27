"""
Stair walker — 100 steps, Renode simulation.
Validates snapshot after Option C terrain-aware detector.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
from walker_model import PROFILES, generate_imu_sequence

elf = detect_firmware()
if not elf:
    print("FATAL: firmware ELF not found"); sys.exit(1)

print(f"ELF   : {elf}")
print(f"Renode: {detect_renode()}")
print()

profile = PROFILES["stairs"]
samples = generate_imu_sequence(profile, 100, rng=np.random.default_rng(42))

print(f"Profile : {profile.name}  cadence={profile.cadence_spm} spm")
print(f"Samples : {len(samples)}  ({len(samples)/208.0:.1f}s)")
print(f"gyr_y range : [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
print()

bridge = RenoneBridge(elf_path=elf)
steps, snaps, ends = bridge.run(samples)

total = ends[0].total_steps if ends else 0
print(f"Steps detected : {len(steps)}")
print(f"SESSION_END    : {'yes — total_steps=' + str(total) if ends else 'NOT RECEIVED'}")
print(f"Step count     : {total}  (target 100 ±5)  {'PASS' if abs(total-100)<=5 else 'FAIL'}")

print(f"\nSnapshots received : {len(snaps)}")
if snaps:
    print(f"{'Step':>6}  {'SI_stance%':>10}  {'SI_swing%':>9}  {'Cadence spm':>11}")
    for s in snaps:
        print(f"{s.anchor_step:>6}  {s.si_stance_pct:>10.1f}  {s.si_swing_pct:>9.1f}  {s.mean_cadence_spm:>11.1f}")

    last = snaps[-1]
    cad_ok  = abs(last.mean_cadence_spm - profile.cadence_spm) <= 20
    si_ok   = last.si_stance_pct <= 5.0
    print(f"\nFinal snapshot cadence: {last.mean_cadence_spm:.1f} spm  "
          f"(target ~{profile.cadence_spm})  {'PASS' if cad_ok else 'FAIL'}")
    print(f"Final snapshot SI_stance: {last.si_stance_pct:.1f}%  "
          f"(target <5%)  {'PASS' if si_ok else 'FAIL'}")
