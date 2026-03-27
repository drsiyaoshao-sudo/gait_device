"""
Renode Stage 3 sine wave baseline test.

Injects a pure 1.5 Hz sine on the az axis — no heel-strike morphology.
Expected result: SESSION_END received, 0 steps detected.

This test validates that:
  1. The Renode bridge boots and runs without crash
  2. uart0 CreateFileBackend captures UART output
  3. The TXSTOPPED watchpoint keeps TX unblocked
  4. The gait algorithm correctly produces 0 steps for non-step input

Three-strike rule applies (CLAUDE.md Rule 5).
"""

import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware

# ── Sine wave generation ───────────────────────────────────────────────────
ODR_HZ     = 208.0          # sensor output data rate
FREQ_HZ    = 1.5            # sine frequency
AMPLITUDE  = 2.0            # m/s² — oscillation amplitude around gravity
DURATION_S = 10.0           # seconds of walking signal (after stationary prefix)
G          = 9.81

N = int(DURATION_S * ODR_HZ)   # 2080 samples
t = np.arange(N) / ODR_HZ

# Pure 1.5 Hz sine on az, everything else zero
samples = np.zeros((N, 6), dtype=np.float32)
samples[:, 2] = G + AMPLITUDE * np.sin(2.0 * np.pi * FREQ_HZ * t)   # az

# ── Pre-flight ─────────────────────────────────────────────────────────────
print("=" * 60)
print("[ATTEMPT 1/3]  Sine wave baseline — expect SESSION_END, 0 steps")
print("=" * 60)
print(f"  Frequency  : {FREQ_HZ} Hz")
print(f"  Amplitude  : ±{AMPLITUDE} m/s² on az")
print(f"  Duration   : {DURATION_S}s  ({N} samples @ {ODR_HZ:.0f} Hz)")
print(f"  az range   : [{samples[:,2].min():.2f}, {samples[:,2].max():.2f}] m/s²")
print(f"  Renode     : {detect_renode()}")
print(f"  ELF        : {detect_firmware()}")
print()

elf = detect_firmware()
if not elf:
    print("FATAL: firmware ELF not found")
    sys.exit(1)

# ── Run ────────────────────────────────────────────────────────────────────
bridge = RenoneBridge(elf_path=elf)
try:
    steps, snaps, ends = bridge.run(samples)

    print("=== UART RESULTS ===")
    print(f"  Steps detected   : {len(steps)}  (expected 0)")
    print(f"  Snapshots        : {len(snaps)}")
    print(f"  SESSION_END count: {len(ends)}")
    if ends:
        print(f"  total_steps      : {ends[0].total_steps}  (expected 0)")

    uart_log = bridge.uart_log
    if uart_log.exists():
        raw = uart_log.read_text(errors="replace").strip()
        lines = raw.splitlines()
        print(f"\n=== RAW UART LOG ({len(lines)} lines) ===")
        for line in lines[:30]:
            print(f"  {line}")
        if len(lines) > 30:
            print(f"  ... ({len(lines)-30} more lines)")
    else:
        print(f"\n=== UART LOG NOT FOUND at {uart_log} ===")

    print()
    session_ok = len(ends) >= 1
    steps_ok   = len(steps) == 0
    print(f"  SESSION_END received : {'PASS' if session_ok else 'FAIL'}")
    print(f"  Steps == 0           : {'PASS' if steps_ok else 'FAIL'}")
    print()
    if session_ok and steps_ok:
        print("RESULT: PASS — sine baseline confirmed")
    else:
        print("RESULT: FAIL — review output above")
        sys.exit(2)

except Exception as exc:
    print(f"\n=== EXCEPTION (attempt 1/3) ===")
    print(f"  {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
    print()
    print("ACTION REQUIRED: review error above, document, determine next step")
    sys.exit(2)
