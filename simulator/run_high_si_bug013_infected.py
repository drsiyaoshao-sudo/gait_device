"""
BUG-013 Infected ELF — Judicial Hearing Evidence Run
Profile: high_si (Walker 5 — pathological asymmetry, flat, true SI ~ 25%)
ELF: .pio/build/xiaoble_sense_sim/zephyr/zephyr.elf (freshly built 2026-04-03)
     — contains fabsf() on line 31 of rolling_window.c (BUG-013 infected source)
Seed: 42, Steps: 100

Orchestrated by: Simulation Execution Standing Order
Standing Order class: Firmware Build + Simulation Execution + Signal Plotting
"""
import sys
import os
import time
import json
import numpy as np

sys.path.insert(0, "/Users/siyaoshao/gait_device/simulator")

from walker_model import generate_imu_sequence, PROFILES
from renode_bridge import RenoneBridge

# ─── Explicit ELF: freshly built from BUG-013 infected source ────────────────
NEW_ELF = "/Users/siyaoshao/gait_device/.pio/build/xiaoble_sense_sim/zephyr/zephyr.elf"

# ─── BUG-005 guard ─────────────────────────────────────────────────────────────
print("=" * 60)
print("BUG-005 ELF Validation")
print("=" * 60)
if not os.path.exists(NEW_ELF):
    print(f"ERROR: ELF not found: {NEW_ELF}")
    sys.exit(1)
elf_size = os.path.getsize(NEW_ELF)
print(f"ELF path     : {NEW_ELF}")
print(f"ELF size     : {elf_size:,} bytes")
if elf_size < 5000:
    print("ERROR: ELF size < 5KB — BUG-005 guard triggered. Halting.")
    sys.exit(1)
print("BUG-005 guard: PASS")
print()

# ─── Step 1: Confirm profile ──────────────────────────────────────────────────
profile_key = "high_si"
profile = PROFILES[profile_key]
print("=" * 60)
print("Profile Confirmation")
print("=" * 60)
print(f"Profile      : {profile.name}")
print(f"Terrain      : {profile.terrain}")
print(f"Cadence      : {profile.cadence_spm} spm")
print(f"Stance frac  : {profile.stance_frac}")
print(f"True SI      : {profile.si_stance_true_pct}%")
print()

# ─── Step 2: Generate IMU signal ──────────────────────────────────────────────
print("Generating IMU sequence: 100 steps, seed=42 ...")
rng = np.random.default_rng(42)
samples = generate_imu_sequence(profile, n_steps=100, rng=rng)
print(f"IMU samples  : {samples.shape}  (shape: N x 6)")
print()

# ─── Step 3: Run Renode bridge with explicitly infected ELF ──────────────────
print("=" * 60)
print("Launching RenoneBridge — BUG-013 infected ELF")
print("=" * 60)

t_start = time.time()
bridge = RenoneBridge(elf_path=NEW_ELF)
steps, snapshots, session_ends = bridge.run(samples)
t_wall = time.time() - t_start

print()
print("=" * 60)
print(f"Renode run complete — wall time: {t_wall:.1f}s")
print("=" * 60)
print()

# ─── Step 4: uart-reader agent — print all UART events ───────────────────────
print("[ uart-reader ] STEP events:")
print("-" * 60)
for s in steps:
    print(f"  STEP #{s.step_index:>3}  ts={int(s.ts_ms):>6}ms  "
          f"acc={s.peak_acc_mag:>5.1f} m/s2  "
          f"gyr_y={s.peak_gyr_y:>6.1f} dps  "
          f"cadence={s.cadence_spm:>5.1f} spm")

print()
print("[ uart-reader ] SNAPSHOT events:")
print("-" * 60)
for sn in snapshots:
    print(f"  SNAPSHOT step={sn.anchor_step:>3}  "
          f"si_stance={sn.si_stance_pct:>5.1f}%  "
          f"si_swing={sn.si_swing_pct:>5.1f}%  "
          f"cadence={sn.mean_cadence_spm:>5.1f} spm")

print()
print("[ uart-reader ] SESSION_END:")
print("-" * 60)
for se in session_ends:
    print(f"  SESSION_END steps={se.total_steps}")

print()
print("[ uart-reader ] Snapshot Table (judicial evidence):")
print("-" * 60)
print(f"  {'Step':>6}  {'SI_stance%':>10}  {'SI_swing%':>9}  {'Cadence spm':>11}")
print(f"  {'------':>6}  {'----------':>10}  {'---------':>9}  {'-----------':>11}")
for sn in snapshots:
    flag = " <-- ABOVE 10% THRESHOLD" if sn.si_stance_pct > 10.0 else " <-- BUG-013: BELOW THRESHOLD"
    print(f"  {sn.anchor_step:>6}  {sn.si_stance_pct:>10.1f}  {sn.si_swing_pct:>9.1f}  {sn.mean_cadence_spm:>11.1f}{flag}")

print()
n_steps_detected = len(steps)
n_snapshots = len(snapshots)
final_si = snapshots[-1].si_stance_pct if snapshots else 0.0
final_cadence = snapshots[-1].mean_cadence_spm if snapshots else 0.0
total_reported = session_ends[0].total_steps if session_ends else 0
mean_si = sum(sn.si_stance_pct for sn in snapshots) / len(snapshots) if snapshots else 0.0

print("=" * 60)
print("Results Summary — BUG-013 INFECTED FIRMWARE:")
print(f"  ELF path       : {NEW_ELF}")
print(f"  Steps detected : {n_steps_detected} / 100")
print(f"  Snapshots      : {n_snapshots}")
print(f"  SESSION_END    : steps={total_reported}")
print(f"  Mean SI_stance : {mean_si:.1f}%")
print(f"  Final SI_stance: {final_si:.1f}%")
print(f"  Final cadence  : {final_cadence:.1f} spm")
print(f"  True SI        : 25.0%")
print(f"  VABS.F32 bug   : SI expected ~25%, REPORTED ~{mean_si:.1f}%")
print("=" * 60)

# Escalation trigger: 0 steps
if n_steps_detected == 0:
    uart_log_path = bridge.uart_log
    print("\nERROR: 0 steps detected — escalation trigger activated.")
    print("Full UART log:")
    try:
        print(uart_log_path.read_text())
    except Exception as e:
        print(f"  (could not read UART log: {e})")
    sys.exit(1)

# Write results JSON for plotter agent
results = {
    "profile": profile_key,
    "elf_path": NEW_ELF,
    "elf_size_bytes": elf_size,
    "bug013_infected": True,
    "n_steps_detected": n_steps_detected,
    "n_snapshots": n_snapshots,
    "total_reported": total_reported,
    "mean_si_stance_pct": mean_si,
    "final_si_stance_pct": final_si,
    "final_cadence_spm": final_cadence,
    "snapshots": [
        {
            "anchor_step": sn.anchor_step,
            "si_stance_pct": sn.si_stance_pct,
            "si_swing_pct": sn.si_swing_pct,
            "mean_cadence_spm": sn.mean_cadence_spm,
        }
        for sn in snapshots
    ],
}
results_path = "/tmp/high_si_bug013_infected_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults JSON written to: {results_path}")
