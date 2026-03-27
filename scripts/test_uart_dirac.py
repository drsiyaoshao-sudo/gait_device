"""
UART capture diagnostic — Dirac pulse signal.

Simplest possible signal: az=9.81 (flat) with a single spike at center.
Duration: 1 second (208 samples). Total with prefix: 658 samples.

Goal: verify that UART stub captures post-boot output and SESSION_END.
Check IMU stub index after run to confirm samples were consumed.
"""

import sys
import numpy as np
from pathlib import Path
import time

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware

ODR_HZ = 208.0
G      = 9.81

# ── Signal: Dirac pulse on az ───────────────────────────────────────────────
DURATION_S = 1.0
N = int(DURATION_S * ODR_HZ)   # 208 samples

samples = np.zeros((N, 6), dtype=np.float32)
samples[:, 2] = G                      # flat az = gravity
samples[N // 2, 2] = 50.0             # single spike at center

print("=" * 60)
print("UART Diagnostic — Dirac pulse (1s, single az spike)")
print("=" * 60)
print(f"  Signal     : {N} samples @ {ODR_HZ:.0f} Hz  ({DURATION_S}s)")
print(f"  az values  : {G} m/s² flat + spike of 50 m/s² at sample {N//2}")
print(f"  Total      : 450 prefix + {N} signal = {450+N} samples")
print(f"  Sim budget : ~{(450+N)/ODR_HZ + 3:.1f}s simulated")
print(f"  Renode     : {detect_renode()}")
elf = detect_firmware()
print(f"  ELF        : {elf}")
print()

if not elf:
    print("FATAL: ELF not found")
    sys.exit(1)

# ── Diagnostic paths ────────────────────────────────────────────────────────
_IMU_IDX   = Path.home() / ".gait_stub_idx.txt"
_RB_ERR    = Path.home() / ".gait_readbyte_err.txt"
_UART_LOG  = Path.home() / "gait_uart.log"
_SENTINEL  = Path.home() / "gait_uart.log.done"

# Clear diagnostics from previous run
for p in (_RB_ERR, _SENTINEL):
    p.unlink(missing_ok=True)

# ── Run ─────────────────────────────────────────────────────────────────────
bridge = RenoneBridge(elf_path=elf)
t0 = time.monotonic()

try:
    steps, snaps, ends = bridge.run(samples)
    elapsed = time.monotonic() - t0

    print(f"=== RUN COMPLETE ({elapsed:.1f}s wall time) ===")
    print(f"  Steps    : {len(steps)}")
    print(f"  Snapshots: {len(snaps)}")
    print(f"  SESSION_END: {len(ends)}")
    if ends:
        print(f"  total_steps: {ends[0].total_steps}")

except Exception as exc:
    elapsed = time.monotonic() - t0
    print(f"\n=== EXCEPTION ({elapsed:.1f}s wall time) ===")
    print(f"  {type(exc).__name__}: {exc}")

# ── Diagnostics ─────────────────────────────────────────────────────────────
print()
print("=== IMU STUB DIAGNOSTICS ===")
if _IMU_IDX.exists():
    idx_raw = _IMU_IDX.read_text().strip()
    print(f"  gait_stub_idx.txt  : {idx_raw!r}")
    try:
        idx = int(idx_raw)
        total_expected = 450 + N
        print(f"  Samples consumed   : {idx} / {total_expected}")
        if idx == 0:
            print("  WARNING: index=0 — IMU stub may not have been loaded or ran")
        elif idx < total_expected:
            print(f"  WARNING: only {idx}/{total_expected} samples consumed (session ended early?)")
        else:
            print("  OK: all samples consumed")
    except ValueError:
        print(f"  (could not parse index: {idx_raw!r})")
else:
    print("  gait_stub_idx.txt  : NOT FOUND — IMU stub did not run")

print()
print("=== UART STUB DIAGNOSTICS ===")
if _RB_ERR.exists():
    print(f"  ReadByte error     : {_RB_ERR.read_text().strip()}")
else:
    print("  ReadByte error     : none (self.GetMachine().ReadByte() OK)")

if _SENTINEL.exists():
    print(f"  SESSION_END sentinel: PRESENT (SESSION_END detected)")
else:
    print(f"  SESSION_END sentinel: ABSENT (SESSION_END not detected)")

print()
print("=== UART LOG ===")
if _UART_LOG.exists():
    raw = _UART_LOG.read_bytes()
    print(f"  Size  : {len(raw)} bytes")
    # Show printable chars
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    print(f"  Lines : {len(lines)}")
    for line in lines:
        print(f"  | {line}")
else:
    print("  NOT FOUND")
