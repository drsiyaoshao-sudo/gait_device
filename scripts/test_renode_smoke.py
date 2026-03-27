"""
Renode Stage 3 test — Walker 1 (flat, 100 steps).

Runs the flat walker profile through the full simulation pipeline:
  walker_model → IMU stub → nRF52840 firmware in Renode → UART parser

Stage 3 exit criterion (flat):
  - total_steps within ±5 of 100
  - SI detection within ±3% of ground truth (0% for symmetric walker)

Three-strike rule: stop at attempt 3 if exit criteria not met.
"""

import sys
import os
import numpy as np
from pathlib import Path

# Allow imports from simulator/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
from walker_model import PROFILES, generate_imu_sequence

# ── Profile setup ──────────────────────────────────────────────────────────
N_STEPS  = 100
PROFILE  = PROFILES["flat"]
SEED     = 42

samples = generate_imu_sequence(PROFILE, N_STEPS, rng=np.random.default_rng(SEED))

# ── Pre-flight checks ──────────────────────────────────────────────────────
print("=" * 60)
print("[ATTEMPT 1/3] Stage 3 — Walker 1 flat, 100 steps")
print("=" * 60)
print(f"  Profile    : {PROFILE.name}")
print(f"  Cadence    : {PROFILE.cadence_spm} spm")
print(f"  Step length: {PROFILE.step_length_m} m")
print(f"  Vert osc   : {PROFILE.vertical_oscillation_cm} cm")
print(f"  Samples    : {len(samples)} @ 208 Hz")
print(f"  acc_z range: [{samples[:,2].min():.2f}, {samples[:,2].max():.2f}] m/s²")
print(f"  gyr_y range: [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
print(f"  Renode     : {detect_renode()}")
print(f"  ELF        : {detect_firmware()}")
print()

elf = detect_firmware()
if not elf:
    print("FATAL: firmware ELF not found — cannot proceed")
    sys.exit(1)

# ── Run ───────────────────────────────────────────────────────────────────
bridge = RenoneBridge(elf_path=elf)
try:
    steps, snaps, ends = bridge.run(samples)

    print("=== UART RESULTS ===")
    print(f"  Steps detected   : {len(steps)}")
    print(f"  Snapshots        : {len(snaps)}")
    print(f"  SESSION_END count: {len(ends)}")
    if ends:
        print(f"  total_steps      : {ends[0].total_steps}")
    if steps:
        print(f"  First 5 steps    :")
        for s in steps[:5]:
            print(f"    #{s.step_index:3d}  ts={s.ts_ms:.0f}ms  "
                  f"acc={s.peak_acc_mag:.1f} m/s²  "
                  f"gyr_y={s.peak_gyr_y:.1f} dps  "
                  f"cadence={s.cadence_spm:.1f} spm")

    # ── Stage 3 exit criteria check ───────────────────────────────────────
    print()
    print("=== STAGE 3 EXIT CRITERIA (flat) ===")
    total     = ends[0].total_steps if ends else 0
    step_pass = abs(total - N_STEPS) <= 5
    print(f"  total_steps : {total}  (target {N_STEPS} ±5)  {'PASS' if step_pass else 'FAIL'}")
    if snaps:
        si_vals = [s.si_stance_pct for s in snaps]
        si_mean = sum(si_vals) / len(si_vals)
        si_pass = abs(si_mean) <= 3.0
        print(f"  SI stance   : mean={si_mean:.1f}%  (target 0% ±3%)  {'PASS' if si_pass else 'FAIL'}")
    else:
        print(f"  SI stance   : no snapshots (need ≥10 steps for first snapshot)")

    print()
    # Print raw UART log for human review
    uart_log = bridge.uart_log
    if uart_log.exists():
        raw = uart_log.read_text(errors="replace").strip()
        lines = raw.splitlines()
        print(f"=== RAW UART LOG ({len(lines)} lines) ===")
        for line in lines[:60]:
            print(f"  {line}")
        if len(lines) > 60:
            print(f"  ... ({len(lines) - 60} more lines)")
    else:
        print(f"=== UART LOG NOT FOUND at {uart_log} ===")

    print()
    print("RESULT: pipeline completed without crash")

except Exception as exc:
    print(f"\n=== EXCEPTION (attempt 1/3) ===")
    print(f"  {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
    print()
    print("ACTION REQUIRED: review error above, document, determine next step")
    sys.exit(2)
