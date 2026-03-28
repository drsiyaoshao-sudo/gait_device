"""
BLE export simulation — flat walker 100 steps.

Validates the CONFIG_GAIT_UART_EXPORT pipeline:
  1. Firmware emits BLE_BINARY_START / hex lines / BLE_BINARY_END before SESSION_END.
  2. parse_binary_export_log() hex-decodes and unpacks rolling_snapshot_t structs.
  3. Binary snapshot fields match the text SNAPSHOT lines parsed by parse_uart_log().

Pass criteria:
  - BLE_BINARY_START block is present in UART log.
  - Count matches number of text SNAPSHOT lines (both = 9 for 100 steps).
  - Each binary snapshot si_stance_pct within 0.1% of corresponding text snapshot.
  - Each binary snapshot mean_cadence_spm within 2 spm of corresponding text snapshot.
  - No CRC / length / unpack errors.
"""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
from walker_model import PROFILES, generate_imu_sequence
from signal_analysis import parse_uart_log, parse_binary_export_log

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
print()

bridge = RenoneBridge(elf_path=elf)

# Run simulation — reuse bridge internals to capture raw log text
bridge._sim_failed = False
try:
    bridge._prepare_imu_file(samples)
    bridge._start_renode()
    bridge._configure_renode()
    bridge._wait_for_session_end()
except Exception as e:
    bridge._sim_failed = True
    bridge._stop_renode()
    print(f"FATAL: simulation error: {e}")
    sys.exit(1)

bridge._stop_renode()

# Read raw log
log_text = bridge.uart_log.read_text(encoding="utf-8", errors="replace")

# Parse both paths
_, text_snaps, ends = parse_uart_log(log_text)
binary_snaps = parse_binary_export_log(log_text)

total = ends[0].total_steps if ends else 0
print(f"Steps detected    : {total}  (target 100 ±5)  {'PASS' if abs(total-100)<=5 else 'FAIL'}")
print(f"Text snapshots    : {len(text_snaps)}")
print(f"Binary snapshots  : {len(binary_snaps)}")
print()

# Check for binary block presence
has_binary = "BLE_BINARY_START" in log_text
print(f"BLE_BINARY_START  : {'PRESENT' if has_binary else 'MISSING'}  {'PASS' if has_binary else 'FAIL'}")
print(f"Count match       : text={len(text_snaps)} binary={len(binary_snaps)}  "
      f"{'PASS' if len(text_snaps)==len(binary_snaps) else 'FAIL'}")
print()

# Field-by-field comparison
if text_snaps and binary_snaps:
    print(f"{'Snap':>4}  {'Text SI%':>9}  {'Bin SI%':>8}  {'ΔSI%':>6}  "
          f"{'Text Cad':>9}  {'Bin Cad':>8}  {'ΔCad':>5}  {'Match':>5}")
    all_ok = True
    for i, (ts, bs) in enumerate(zip(text_snaps, binary_snaps)):
        d_si  = abs(ts.si_stance_pct - bs.si_stance_pct)
        d_cad = abs(ts.mean_cadence_spm - bs.mean_cadence_spm)
        ok = d_si <= 0.1 and d_cad <= 2.0
        all_ok = all_ok and ok
        print(f"{i:>4}  {ts.si_stance_pct:>9.1f}  {bs.si_stance_pct:>8.1f}  "
              f"{d_si:>6.2f}  {ts.mean_cadence_spm:>9.1f}  {bs.mean_cadence_spm:>8.1f}  "
              f"{d_cad:>5.1f}  {'OK' if ok else 'FAIL':>5}")
    print()
    print(f"Field comparison  : {'PASS — all snapshots match' if all_ok else 'FAIL — mismatch detected'}")
else:
    all_ok = False
    print("Field comparison  : SKIP — no snapshots to compare")

print()
# Summary verdict
count_ok  = len(text_snaps) == len(binary_snaps) and len(binary_snaps) > 0
steps_ok  = abs(total - 100) <= 5
verdict = has_binary and count_ok and steps_ok and all_ok
print(f"OVERALL: {'PASS' if verdict else 'FAIL'}")
