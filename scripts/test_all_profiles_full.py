"""
Full 4-profile validation — 100 steps each, all snapshot data printed.

For each profile prints:
  - IMU signal range
  - Step count + SESSION_END
  - Full snapshot table (step / SI_stance% / SI_swing% / cadence spm)
  - BLE binary export count (CONFIG_GAIT_UART_EXPORT)
  - Pass/fail verdict
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
from walker_model import PROFILES, generate_imu_sequence
from signal_analysis import parse_uart_log, parse_binary_export_log

RUNS = [
    ("flat",     100, 42),
    ("bad_wear", 100, 42),
    ("slope",    100, 42),
    ("stairs",   100, 42),
]

elf = detect_firmware()
if not elf:
    print("FATAL: firmware ELF not found"); sys.exit(1)

print(f"ELF   : {elf}")
print(f"Renode: {detect_renode()}")
print()

summary = []

for profile_key, n_steps, seed in RUNS:
    profile = PROFILES[profile_key]
    samples = generate_imu_sequence(profile, n_steps, rng=np.random.default_rng(seed))

    print("=" * 70)
    print(f"PROFILE : {profile.name}")
    print(f"cadence : {profile.cadence_spm} spm   "
          f"vert_osc : {profile.vertical_oscillation_cm} cm   "
          f"step_len : {profile.step_length_m} m")
    print(f"samples : {len(samples)}  ({len(samples)/208.0:.1f} s at 208 Hz)")
    print(f"acc_z   : [{samples[:,2].min():.2f}, {samples[:,2].max():.2f}] m/s²")
    print(f"gyr_y   : [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
    print()

    bridge = RenoneBridge(elf_path=elf)
    bridge._sim_failed = False
    try:
        bridge._prepare_imu_file(samples)
        bridge._start_renode()
        bridge._configure_renode()
        bridge._wait_for_session_end()
    except Exception as exc:
        bridge._sim_failed = True
        bridge._stop_renode()
        print(f"  EXCEPTION: {type(exc).__name__}: {exc}")
        summary.append((profile_key, "CRASH", 0, 0, []))
        print()
        continue

    bridge._stop_renode()
    log_text = bridge.uart_log.read_text(encoding="utf-8", errors="replace")

    steps, snaps, ends = parse_uart_log(log_text)
    binary_snaps = parse_binary_export_log(log_text)

    total = ends[0].total_steps if ends else 0
    steps_ok = abs(total - n_steps) <= 5

    print(f"Steps detected  : {len(steps)}")
    print(f"SESSION_END     : {'yes — total_steps=' + str(total) if ends else 'NOT RECEIVED'}")
    print(f"Step count      : {total}  (target {n_steps} ±5)  {'PASS' if steps_ok else 'FAIL'}")
    print(f"Binary export   : {len(binary_snaps)} snapshots from BLE_BINARY_START block")
    print()

    # Snapshot table
    print(f"Snapshots received : {len(snaps)}")
    if snaps:
        print(f"  {'Step':>5}  {'SI_stance%':>10}  {'SI_swing%':>9}  "
              f"{'Cadence spm':>11}  {'BLE bin cad':>11}")
        for i, s in enumerate(snaps):
            bin_cad = f"{binary_snaps[i].mean_cadence_spm:>11.1f}" \
                      if i < len(binary_snaps) else "          —"
            print(f"  {s.anchor_step:>5}  {s.si_stance_pct:>10.1f}  "
                  f"{s.si_swing_pct:>9.1f}  {s.mean_cadence_spm:>11.1f}  {bin_cad}")

    # Verdict
    last = snaps[-1] if snaps else None
    si_ok  = last is not None and last.si_stance_pct <= 5.0
    cad_ok = last is not None and abs(last.mean_cadence_spm - profile.cadence_spm) <= 20
    ble_ok = len(binary_snaps) == len(snaps) and len(snaps) > 0

    verdict = "PASS" if (steps_ok and si_ok and ble_ok) else "FAIL"
    print()
    print(f"Final SI_stance : {last.si_stance_pct:.1f}%  (target <5%)  "
          f"{'PASS' if si_ok else 'FAIL'}" if last else "Final SI_stance : n/a")
    print(f"Final cadence   : {last.mean_cadence_spm:.1f} spm  "
          f"(target ~{profile.cadence_spm})  {'PASS' if cad_ok else 'FAIL'}" if last else "")
    print(f"BLE export      : text={len(snaps)} binary={len(binary_snaps)}  "
          f"{'PASS' if ble_ok else 'FAIL'}")
    print(f"VERDICT         : {verdict}")
    print()

    summary.append((profile_key, verdict, total, len(snaps), snaps))

# ── Summary ───────────────────────────────────────────────────────────────────
print("=" * 70)
print("SUMMARY — all 4 profiles, 100 steps")
print("=" * 70)
print(f"  {'Profile':<12}  {'Steps':>5}  {'Snaps':>5}  "
      f"{'Final SI%':>9}  {'Cadence':>7}  {'Verdict':>7}")
for key, verdict, total, n_snaps, snaps in summary:
    profile = PROFILES[key]
    last = snaps[-1] if snaps else None
    si_str  = f"{last.si_stance_pct:.1f}%" if last else "  n/a"
    cad_str = f"{last.mean_cadence_spm:.0f}" if last else "  n/a"
    print(f"  {key:<12}  {total:>5}  {n_snaps:>5}  "
          f"{si_str:>9}  {cad_str:>7}  {verdict:>7}")
print()
all_pass = all(v == "PASS" for _, v, _, _, _ in summary)
print(f"Overall: {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
