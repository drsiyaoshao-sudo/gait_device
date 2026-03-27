"""
Renode Simulation Test Template
================================

Covers the full pipeline: signal generation → MCU simulation → UART result collection.

ARCHITECTURE (7-layer digital twin, CLAUDE.md):
  [Section 2: Signal Generator]
      ↓  (N,6) float32 @ 208 Hz
  [RenoneBridge._prepare_imu_file()]
      ↓  prepends 450 stationary calibration samples → /tmp/gait_imu_sim.f32
  [Section 1: Renode + nRF52840 Cortex-M4F]
      sim_imu_stub.py  @ sysbus 0x400B0000  — LSM6DS3TR-C I2C register emulation
      sim_uart_stub.py @ sysbus 0x40002000  — UARTE0 capture + TXSTOPPED fix
      firmware.elf                           — actual Zephyr firmware (CONFIG_GAIT_RENODE_SIM=y)
      ↓  UART log file
  [Section 4: signal_analysis.parse_uart_log()]
      ↓  typed events
  [Section 5: Assertions / Results]

HOW TO ADAPT THIS TEMPLATE:
  1. Copy this file, rename it (e.g. test_my_signal.py)
  2. Replace SECTION 2 with your signal generation logic
  3. Replace SECTION 5 pass/fail criteria for your test
  4. Do NOT change Sections 1, 3, 4 — those are invariant infrastructure

INVARIANT SECTIONS (never change these between tests):
  Section 1: MCU platform description and peripheral stubs
  Section 3: Bridge execution (IMU file write + Renode launch + boot + wait)
  Section 4: UART log parsing (signal_analysis typed events)

Three-strike rule applies (CLAUDE.md Rule 5).
"""

import sys
import numpy as np
from pathlib import Path

# ── path setup ─────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "simulator"))

from renode_bridge import RenoneBridge, detect_renode, detect_firmware
# signal_analysis is invoked internally by bridge._parse_uart_log()

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — SIGNAL GENERATION (replace this section for each test)
# ═══════════════════════════════════════════════════════════════════════════
#
# Requirements:
#   - Return np.ndarray shape (N, 6), dtype float32
#   - Columns: [ax, ay, az, gx, gy, gz]
#   - Units: m/s² for acceleration, dps for gyro
#   - Sample rate: 208 Hz (ODR_HZ)
#   - Duration: choose N to cover your test scenario
#
# The bridge prepends 450 stationary samples (az=9.81, rest=0) automatically
# to fill the firmware's calibration window before your signal starts.
#
# Examples in this file:
#   - pure_sine_1p5hz()   : 1.5 Hz sine on az, 10 s — expects 0 steps
#   - flat_walker_100()   : PROFILES["flat"], 100 steps — expects ~100 steps, SI≈0%
#
# ─── Signal constants ───────────────────────────────────────────────────────
ODR_HZ = 208.0   # LSM6DS3TR-C output data rate (Hz) — do not change
G      = 9.81    # standard gravity (m/s²)


def generate_signal() -> np.ndarray:
    """
    *** REPLACE THIS FUNCTION ***

    Return (N, 6) float32 [ax ay az gx gy gz] in physical units.
    This is the ONLY function that changes between tests.

    Current: 1.5 Hz sine baseline — expects SESSION_END, 0 steps.
    """
    # ── sine wave: 1.5 Hz on az, 10 seconds ──────────────────────────────
    FREQ_HZ    = 1.5    # Hz
    AMPLITUDE  = 2.0    # m/s² around gravity
    DURATION_S = 10.0   # seconds

    N = int(DURATION_S * ODR_HZ)
    t = np.arange(N) / ODR_HZ

    samples = np.zeros((N, 6), dtype=np.float32)
    samples[:, 2] = G + AMPLITUDE * np.sin(2.0 * np.pi * FREQ_HZ * t)  # az
    # ax, ay, gx, gy, gz remain 0

    return samples

    # ── Alternative: walker profile (uncomment to use) ──────────────────
    # from walker_model import PROFILES, generate_imu_sequence
    # PROFILE = PROFILES["flat"]   # or "bad_wear", "slope", "stairs"
    # N_STEPS = 100
    # return generate_imu_sequence(PROFILE, N_STEPS, rng=np.random.default_rng(42))


# ── Signal metadata for printing (describe your signal here) ───────────────
SIGNAL_DESCRIPTION = "1.5 Hz sine on az — expects SESSION_END, 0 steps"


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — MCU PLATFORM (INVARIANT — do not change)
# ═══════════════════════════════════════════════════════════════════════════
#
# Hardware: XIAO nRF52840 Sense
#   MCU:         Nordic nRF52840, Cortex-M4F, 64 MHz, 256 KB SRAM, 1 MB Flash
#   IMU:         LSM6DS3TR-C (accel ±16g @ 0.488mg/LSB, gyro ±2000dps @ 70mdps/LSB)
#   Interface:   TWIM0 (I2C) @ 0x40003000, LSM6DS3 at 0x6A
#   UART:        UARTE0 @ 0x40002000 (EasyDMA, 208 Hz FIFO watermark)
#
# Renode peripherals loaded by RenoneBridge._configure_renode():
#   REPL 1:  nrf52840.repl         — base MCU (Cortex-M4F, SRAM, Flash, NVIC)
#            sim_imu_stub.py       — LSM6DS3TR-C I2C emulation at 0x400B0000
#   REPL 2:  sim_uart_stub.py      — UARTE0 replacement at 0x40002000
#              - reads:  EVENTS_TXSTOPPED=1, EVENTS_ENDTX=1 (TXSTOPPED fix)
#              - writes: captures TASKS_STARTTX DMA bytes via self.GetMachine()
#              - output: appends to ~/gait_uart.log
#              - sentinel: writes ~/gait_uart.log.done on SESSION_END
#
# Firmware:  .pio/build/xiaoble_sense_sim/firmware.elf
#   Build:   pio run -e xiaoble_sense_sim
#   Config:  prj_sim.conf (CONFIG_GAIT_RENODE_SIM=y, no BT/I2C/NVS)
#   Session: auto-starts, polls g_imu_sim_exhausted, auto-stops + prints SESSION_END
#
# (No changes needed here — RenoneBridge handles all of this)


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — BRIDGE EXECUTION (INVARIANT — do not change)
# ═══════════════════════════════════════════════════════════════════════════

def _preflight(samples: np.ndarray) -> str:
    """Print pre-flight info and return the ELF path. Exits on missing ELF."""
    print("=" * 60)
    print(f"  Signal     : {SIGNAL_DESCRIPTION}")
    print(f"  Samples    : {len(samples)} @ {ODR_HZ:.0f} Hz  "
          f"({len(samples)/ODR_HZ:.1f}s signal)")
    print(f"  az range   : [{samples[:,2].min():.2f}, {samples[:,2].max():.2f}] m/s²")
    print(f"  gyr_y range: [{samples[:,4].min():.1f}, {samples[:,4].max():.1f}] dps")
    print(f"  Renode     : {detect_renode()}")
    elf = detect_firmware()
    print(f"  ELF        : {elf}")
    print()

    if not detect_renode():
        print("FATAL: renode binary not found on PATH")
        sys.exit(1)
    if not elf:
        print("FATAL: firmware ELF not found — run: pio run -e xiaoble_sense_sim")
        sys.exit(1)
    return elf


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4 — UART RESULT COLLECTION (INVARIANT — do not change)
# ═══════════════════════════════════════════════════════════════════════════

def _print_results(bridge, steps, snaps, ends):
    """Print parsed UART results. Never modify this function."""
    print("=== UART RESULTS ===")
    print(f"  Steps detected   : {len(steps)}")
    print(f"  Snapshots        : {len(snaps)}")
    print(f"  SESSION_END count: {len(ends)}")
    if ends:
        print(f"  total_steps      : {ends[0].total_steps}")
    if steps:
        print(f"  First 5 steps:")
        for s in steps[:5]:
            print(f"    #{s.step_index:3d}  ts={s.ts_ms:.0f}ms  "
                  f"acc={s.peak_acc_mag:.1f} m/s²  "
                  f"gyr_y={s.peak_gyr_y:.1f} dps  "
                  f"cadence={s.cadence_spm:.1f} spm")
    if snaps:
        si_vals = [s.si_stance_pct for s in snaps]
        si_mean = sum(si_vals) / len(si_vals)
        print(f"  SI stance mean   : {si_mean:.1f}%  (over {len(snaps)} snapshots)")

    uart_log = bridge.uart_log
    if uart_log.exists():
        raw = uart_log.read_text(errors="replace").strip()
        lines = raw.splitlines()
        print(f"\n=== RAW UART LOG ({len(lines)} lines) ===")
        for line in lines[:40]:
            print(f"  {line}")
        if len(lines) > 40:
            print(f"  ... ({len(lines)-40} more lines)")
    else:
        print(f"\n=== UART LOG NOT FOUND at {uart_log} ===")


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5 — ASSERTIONS (replace pass/fail criteria for each test)
# ═══════════════════════════════════════════════════════════════════════════

def check_results(steps, snaps, ends) -> bool:
    """
    *** REPLACE THIS FUNCTION for each test ***

    Return True if test passes, False if it fails.
    Current: sine baseline — SESSION_END received, 0 steps.
    """
    print("=== ASSERTIONS ===")
    session_ok = len(ends) >= 1
    steps_ok   = len(steps) == 0
    print(f"  SESSION_END received : {'PASS' if session_ok else 'FAIL'}")
    print(f"  Steps == 0           : {'PASS' if steps_ok else 'FAIL'}")
    return session_ok and steps_ok

    # ── Alternative: flat walker (uncomment to use) ──────────────────────
    # N_STEPS = 100
    # total = ends[0].total_steps if ends else 0
    # step_pass = abs(total - N_STEPS) <= 5
    # si_pass = True
    # if snaps:
    #     si_mean = sum(s.si_stance_pct for s in snaps) / len(snaps)
    #     si_pass = abs(si_mean) <= 3.0
    # print(f"  Steps {total} (target {N_STEPS}±5): {'PASS' if step_pass else 'FAIL'}")
    # print(f"  SI    {si_mean:.1f}% (target 0%±3%): {'PASS' if si_pass else 'FAIL'}")
    # return step_pass and si_pass


# ═══════════════════════════════════════════════════════════════════════════
# MAIN (do not change)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("Renode Simulation Test")
    print("=" * 60)

    samples = generate_signal()
    elf     = _preflight(samples)
    bridge  = RenoneBridge(elf_path=elf)

    try:
        steps, snaps, ends = bridge.run(samples)
        _print_results(bridge, steps, snaps, ends)
        print()
        passed = check_results(steps, snaps, ends)
        print()
        if passed:
            print("RESULT: PASS")
        else:
            print("RESULT: FAIL — review output above")
            sys.exit(2)

    except Exception as exc:
        print(f"\n=== EXCEPTION ===")
        print(f"  {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        print()
        print("ACTION REQUIRED: review error, check three-strike count, document in bugs.md")
        sys.exit(2)
