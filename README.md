# GaitSense — Ankle Gait Analysis Wearable

Single-ankle IMU wearable for detecting walking pattern asymmetry (Symmetry Index).
Hardware: Seeed XIAO nRF52840 Sense — nRF52840 Cortex-M4F + LSM6DS3TR-C 6-DOF IMU + BLE 5.0.

**Total cost:** ~$45–50. No RTOS expertise required to run the simulator. No hardware required to validate the algorithm.

---

## Table of Contents

1. [Quick Start — Simulator Only (no hardware)](#1-quick-start--simulator-only-no-hardware)
2. [Firmware Build](#2-firmware-build)
3. [Unit Tests](#3-unit-tests)
4. [Digital Twin UI](#4-digital-twin-ui)
5. [Hardware Deployment](#5-hardware-deployment)
6. [Project Structure](#6-project-structure)
7. [Known Bugs and Resolutions](#7-known-bugs-and-resolutions)
8. [Why This Approach Works](#8-why-this-approach-works)
9. [BOMs](#9-boms)

---

## 1. Quick Start — Simulator Only (no hardware)

Run the full digital twin pipeline on any laptop. No XIAO board, no Renode, no embedded toolchain needed.

```bash
# Clone and enter
git clone <repo-url> gait_device
cd gait_device

# Install Python dependencies
pip install numpy scipy streamlit plotly bleak pyserial pytest pandas pyarrow

# Launch the Digital Twin UI
streamlit run simulator/app.py
```

Open http://localhost:8501 in your browser. Select a walker profile, click **Run Simulation**.

**What you can do without hardware:**
- Simulate 4 terrain profiles (flat, poor device fit, stairs, inclined surface)
- Toggle **"Simulate gait asymmetry (SI ≈ 25%)"** to inject a clinically significant asymmetry and verify detection
- Toggle **"Show algorithm comparison"** to overlay the original dual-confirmation algorithm (dashed) against the terrain-aware algorithm (solid) — the stair profile shows the original algorithm's failure mode
- Vary step count and random seed for reproducibility

---

## 2. Firmware Build

### Prerequisites

```bash
pip install platformio
```

PlatformIO will download the nRF Connect SDK and arm-zephyr-eabi GCC toolchain on first build (~2–3 GB, takes several minutes).

---

### 2a. Simulation build — for Renode digital twin (primary validated path)

> **Important:** PlatformIO's `pio run` command alone does not link the application code into the final ELF. A two-step ninja invocation is required (see [BUG-005](#bug-005-platformio-elf-omits-app-code--two-step-ninja-fix)). This is the only confirmed working build procedure.

```bash
# Step 1 — configure and generate build system
pio run -e xiaoble_sense_sim

# Step 2 — enter the build directory and build in the correct order
cd .pio/build/xiaoble_sense_sim
touch build.ninja                        # force CMake to skip re-generation
ninja app/libapp.a && ninja zephyr/zephyr.elf

# Step back to repo root
cd ../../..
```

**Output ELF:** `.pio/build/xiaoble_sense_sim/zephyr/zephyr.elf`

Expected sizes (from confirmed build 2026-03-27):
- Flash: ~37.4 KB / 1 MB (3.6%)
- SRAM: ~118 KB / 256 KB (45.2%)

If the sizes deviate significantly, the app code may not have linked. Re-run the two-step procedure.

---

### 2b. Production build — for flashing to physical hardware (BLE export)

```bash
pio run -e xiaoble_sense
```

This build enables BLE GATT export. Snapshots are delivered as GATT notifications. Use `host_tool/download_session.py` to download sessions over BLE.

> **Note:** The production build (`xiaoble_sense`) has not been separately validated on hardware as of the last simulation session (2026-03-28). The simulation build (`xiaoble_sense_sim`) is the fully validated path. For hardware bring-up, build `xiaoble_sense` but cross-check behaviour against the simulation predictions in [CLAUDE.md](CLAUDE.md).

---

### 2c. CONFIG_GAIT_UART_EXPORT — Renode binary export flag

The simulation environment cannot run BLE. A build flag activates a UART binary dump in place of the GATT service:

```bash
# Sim build with binary UART export (used internally by Renode bridge)
pio run -e xiaoble_sense_sim   # prj_sim.conf sets CONFIG_GAIT_UART_EXPORT=y
```

**What changes with `CONFIG_GAIT_UART_EXPORT=y`:**

`ble_gait_svc.c` is excluded. At session end, `session_mgr.c` calls `uart_export_snapshots()` which emits:

```
BLE_BINARY_START
<hex-encoded rolling_snapshot_t structs, one per line, 36 hex chars each>
BLE_BINARY_END
SESSION_END steps=N
```

`rolling_snapshot_t` struct layout (18 bytes — **not 20**, see [BUG-012](#bug-012-rolling_snapshot_t-struct-size-comment-wrong)):

```c
typedef struct {
    uint32_t anchor_step_index;   // 4 bytes
    uint32_t anchor_ts_ms;        // 4 bytes
    uint16_t si_stance_x10;       // 2 bytes  (value × 10, e.g. 123 = 12.3%)
    uint16_t si_swing_x10;        // 2 bytes
    uint16_t si_peak_angvel_x10;  // 2 bytes
    uint16_t mean_cadence_x10;    // 2 bytes
    uint8_t  step_count;          // 1 byte
    uint8_t  flags;               // 1 byte  (0x01=walking, 0x02=running)
} rolling_snapshot_t;             // total: 18 bytes
```

Python unpack (in `simulator/signal_analysis.py`):
```python
SNAPSHOT_STRUCT = struct.Struct("<IIHHHHBB")   # 18 bytes
```

**Do not flash `CONFIG_GAIT_UART_EXPORT=y` firmware to a real device.** It disables BLE entirely.

---

## 3. Unit Tests

### Python simulator tests

```bash
pytest simulator/tests/
```

Expected: **151 tests, all pass**.

### Firmware native tests (no hardware, no Renode)

The native test suite uses plain `assert()`, not Unity — so `pio test -e native` does **not** discover them automatically. Compile and run directly:

```bash
# From repo root
gcc -DUNIT_TEST \
    -I test/native/stubs \
    -I src/gait \
    test/native/test_step_detector.c src/gait/step_detector.c \
    -lm -o /tmp/test_step_detector && /tmp/test_step_detector

gcc -DUNIT_TEST \
    -I test/native/stubs \
    -I src/gait \
    test/native/test_rolling_window.c src/gait/rolling_window.c \
    -lm -o /tmp/test_rolling_window && /tmp/test_rolling_window

gcc -DUNIT_TEST \
    -I test/native/stubs \
    -I src/gait \
    test/native/test_foot_angle.c src/gait/foot_angle.c \
    -lm -o /tmp/test_foot_angle && /tmp/test_foot_angle
```

Expected: 3 tests per suite, all pass. The stub at `test/native/stubs/logging/log.h` defines `#define printk printf` so the firmware logging calls compile against the host GCC.

---

## 4. Digital Twin UI

```bash
streamlit run simulator/app.py
```

Four panels:
1. **Symmetry Index Over Time** — all 4 walker profiles overlaid against the 10% clinical threshold
2. **Algorithm Comparison** *(toggle)* — terrain-aware (solid) vs original dual-confirmation (dashed)
3. **Raw Sensor Signal** — acc_z and gyr_y for the selected profile with detected step markers
4. **Gait Phase Timing** — stance/swing duration bars per step; orange = mounting alert
5. **Profile Summary** — biomechanical parameters and detection statistics

### Renode path (requires firmware ELF)

If Renode ≥ 1.15 is installed and a firmware ELF has been built, the "Validate on embedded firmware" toggle appears in the sidebar. This runs the real C firmware on a virtual nRF52840 instead of the Python algorithm model.

```bash
# Install Renode (macOS)
brew install --cask renode

# Build firmware (see Section 2a), then launch UI
streamlit run simulator/app.py
```

---

## 5. Hardware Deployment

> **Stage gate:** Do not proceed to hardware until all simulation exit criteria in [CLAUDE.md](CLAUDE.md) Stage 3 are confirmed met. As of 2026-03-28, Stage 3 is complete. Stage 4 (edge cases) is open.

### 5a. Flash firmware

**Option A — drag-and-drop (no tools required):**
1. Double-press the XIAO reset button → it appears as a USB mass storage device (`XIAO-SENSE`)
2. Copy `.pio/build/xiaoble_sense/zephyr/zephyr.uf2` to the drive
3. Device reboots automatically

**Option B — nrfjprog via J-Link (recommended for bring-up):**
```bash
nrfjprog --program .pio/build/xiaoble_sense/zephyr/zephyr.elf --sectorerase
nrfjprog --reset
```

### 5b. Bench bring-up checklist

Run these checks before attaching the device to a subject. Each item maps to a simulation prediction.

| Step | What to check | Expected | How to check |
|------|--------------|----------|--------------|
| 1 | WHO_AM_I register | `0x6A` on I2C | RTT log line: `imu: WHO_AM_I=0x6A` at boot |
| 2 | FIFO watermark interval | ~154 ms | RTT timestamps between `imu_reader: batch` lines: 32 samples ÷ 208 Hz = 153.8 ms |
| 3 | Calibration | acc_z ≈ 9.81 m/s², gyro bias < 10 mdps/axis | Stand still 2 s after boot; check RTT calibration log |
| 4 | Step count | ≥ 98/100 steps | Walk exactly 100 steps; BLE session summary `total_steps` |
| 5 | Symmetry Index (healthy) | SI < 5% | Natural walking baseline; BLE snapshot SI values |
| 6 | Symmetry Index (lift test) | SI 8–15% | Place 10 mm lift under one heel; walk 100 steps |
| 7 | Sleep current | ≤ 5 μA | Nordic PPK2 between battery and device during idle |
| 8 | Active current | ≤ 1.5 mA | Nordic PPK2 during a walking session |

### 5c. Download a session (BLE)

```bash
pip install bleak
python host_tool/download_session.py --output session_001.csv
```

The tool connects to the first GaitSense device found, subscribes to snapshot notifications, writes `anchor_step`, `si_stance`, `si_swing`, `cadence` columns to CSV.

---

## 6. Project Structure

```
gait_device/
├── CLAUDE.md                    # Dev philosophy, stage exit criteria, bug hunt log
├── README.md                    # This file — human deployment guide
├── platformio.ini               # Build environments (xiaoble_sense, xiaoble_sense_sim, native)
├── prj.conf                     # Zephyr Kconfig — production build
├── prj_sim.conf                 # Zephyr Kconfig — simulation build (CONFIG_GAIT_UART_EXPORT=y)
├── CMakeLists.txt
├── src/
│   ├── main.c
│   ├── imu/
│   │   ├── imu_reader.c/h       # LSM6DS3 FIFO watermark trigger, 32-sample batch read
│   │   └── calibration.c/h      # Static bias removal, NVS persistence
│   ├── gait/
│   │   ├── gait_engine.c/h      # Pipeline orchestrator: IMU → step → phase → window
│   │   ├── step_detector.c/h    # Terrain-aware step detector (Option C, gyr push-off primary)
│   │   ├── phase_segmenter.c/h  # 5-state FSM: IDLE→LOADING→MID→TERMINAL→SWING
│   │   ├── foot_angle.c/h       # Complementary filter (gyro 98% / accel 2%)
│   │   └── rolling_window.c/h   # 200-step circular buffer, snapshot every 10 steps
│   ├── session/
│   │   ├── session_mgr.c/h      # Button debounce, LED state machine, session lifecycle
│   │   └── snapshot_buffer.c/h  # RAM ring buffer (5500 snapshots); optional W25Q16 fallback
│   └── ble/
│       └── ble_gait_svc.c/h     # Custom GATT service (128-bit UUID), snapshot notifications
├── simulator/
│   ├── walker_model.py          # WalkerProfile dataclass + generate_imu_sequence() — 4 terrain profiles
│   ├── imu_model.py             # Physical units → LSM6DS3 FIFO byte format (quantise + pack)
│   ├── gait_algorithm.py        # Pure-Python firmware mirror; use_legacy flag for comparison
│   ├── terrain_aware_step_detector.py  # Option C detector (Python reference implementation)
│   ├── signal_analysis.py       # UART log parser → StepEvent, SnapshotEvent, SessionEndEvent
│   ├── pipeline.py              # Orchestrator: Python path and Renode path share PipelineResult
│   ├── renode_bridge.py         # Launch Renode, feed IMU stub, drain UART, return typed events
│   └── app.py                   # Streamlit UI — 5 panels, pathological toggle, algo comparison
├── renode/
│   ├── gait_device.resc         # Renode scenario: load ELF, inject stationary samples, run
│   ├── gait_nrf52840.repl       # Platform: nRF52840 + LSM6DS3 I2C stub + GPIO INT1
│   ├── sim_imu_stub.py          # LSM6DS3TR-C I2C emulation; file-based FIFO index
│   └── sim_uart_stub.py         # UARTE0 DMA capture; TXSTOPPED semaphore fix
├── test/
│   └── native/
│       ├── test_step_detector.c # 3 tests: detect, miss, adaptive threshold
│       ├── test_rolling_window.c # 5 tests: SI=0, SI alternating, window wrap, cadence, prior seed
│       └── test_foot_angle.c    # 3 tests: static angle, drift 1s, reset
├── scripts/
│   ├── test_flat_only.py        # Renode: flat walker 100 steps → PASS
│   ├── test_stairs_100.py       # Renode: stair walker 100 steps → PASS (was 0/100 pre-fix)
│   └── test_slope_100.py        # Renode: slope walker 100 steps → PASS
├── host_tool/
│   └── download_session.py      # BLE session download → CSV
└── docs/
    ├── hw_bom.md                # Hardware bill of materials (~$45–50)
    ├── sw_bom.md                # Software bill of materials (all open-source except SEGGER tools)
    ├── handoff.md               # Stage 4/5 handoff checklist for physical validator
    ├── bug_receipt.md           # Permanent bug record (symptom, root cause, fix, files)
    └── algorithm_hunting_stair_walker.md  # Full hunting procedure for BUG-010
```

---

## 7. Known Bugs and Resolutions

All bugs discovered during simulation are resolved before hardware handoff. The table below is the complete record. See [docs/bug_receipt.md](docs/bug_receipt.md) for full symptom → root cause → fix detail on each.

### Summary

| ID | Category | Status | Title |
|----|----------|--------|-------|
| BUG-001 | Sim Infrastructure | RESOLVED | IronPython global state exhausts after 5 samples |
| BUG-002 | Gait Algorithm | RESOLVED | LOADING→MID_STANCE terrain gate broken for stairs (acc_mag assumption) |
| BUG-003 | Sim Infrastructure | RESOLVED | Python.PythonPeripheral has no sysbus memory access API |
| BUG-004 | Sim Infrastructure | SUPERSEDED | nRF UARTE EVENTS_TXSTOPPED write-only (replaced by BUG-006) |
| BUG-005 | Build / Dependencies | RESOLVED | PlatformIO ELF omits app code — two-step ninja required |
| BUG-006 | Sim Infrastructure | RESOLVED | Post-kernel uart_poll_out blocks on ENDTX semaphore |
| BUG-007 | Sim Infrastructure | RESOLVED | imu_reader_get ACK written after blocking printk |
| BUG-008 | Bare-Metal C Sim | RESOLVED | Duplicate SNAPSHOT lines: LOG_INF + printk both matched by parser |
| BUG-009 | Gait Algorithm | RESOLVED | Phase segmenter: cadence never injected + LP cold start + convolution artefact |
| BUG-010 | Gait Algorithm | RESOLVED | Stair walker: 0/100 steps detected — dual-confirmation timing mismatch |
| BUG-011 | Gait Algorithm | RESOLVED | cadence_spm=0 in all rolling_window records |
| BUG-012 | Bare-Metal C Sim | RESOLVED | rolling_snapshot_t struct comment wrong (20 bytes stated, 18 bytes actual) |
| BUG-013 | Bare-Metal C Sim | RESOLVED | VABS.F32 broken in Renode 1.16.1 — SI silently zeroed for all asymmetric walkers |

---

### Critical bugs for hardware validator to know

#### BUG-005: PlatformIO ELF omits app code — two-step ninja fix

**Symptom:** `pio run -e xiaoble_sense_sim` completes without error but the generated `zephyr.elf` contains only the Zephyr kernel — all `src/` application files are missing. Firmware boots but detects 0 steps and emits no SNAPSHOT lines.

**Root cause:** PlatformIO's CMake invocation links against a pre-built stub `app/libapp.a` rather than rebuilding it from sources. The stub is empty on a clean build.

**Fix:** Two-step ninja build (see [Section 2a](#2a-simulation-build--for-renode-digital-twin-primary-validated-path)):
```bash
pio run -e xiaoble_sense_sim
cd .pio/build/xiaoble_sense_sim && touch build.ninja
ninja app/libapp.a && ninja zephyr/zephyr.elf
```

**How to verify the fix worked:** ELF flash size should be ~37.4 KB. If it is < 5 KB, the app code is missing.

---

#### BUG-010: Stair walker — 0/100 steps detected (terrain algorithm failure)

**Symptom:** All 4 walker profiles detect 100/100 steps on flat, slope, and poor fit. Stair walker detects 0 steps.

**Root cause:** The original dual-confirmation step detector requires an acc_filt peak and a gyr_y zero-crossing within 40 ms of each other. On flat ground these are co-incident (heel-strike drives both). On stairs, forefoot/midfoot contact separates them by 135 ms — the step is always rejected on timing.

**Fix:** Option C terrain-aware detector — push-off plantar-flexion burst (gyr_y_hp > 30 dps) becomes the primary trigger; acc_filt > adaptive threshold since last step is the confirmation. An 8-entry ring buffer stores rejected acc_filt crossings so the retrospective heel-strike timestamp is recovered. Push-off is biomechanically universal across all terrains.

**Files changed:** `src/gait/step_detector.c`, `simulator/terrain_aware_step_detector.py`

**Verified:** All 4 profiles 100/100 steps in bare-metal Cortex-M4F simulation.

---

#### BUG-013: VABS.F32 broken in Renode 1.16.1 — SI silently zeroed

**Symptom:** Pathological walker (true SI = 25%) reports SI = 0.0% across all 9 snapshots in Renode. Healthy walkers unaffected (correct answer is 0% regardless).

**Root cause:** `compute_si_x10()` in `rolling_window.c` calls `fabsf(m_odd - m_even)`. The ARM FPU instruction `VABS.F32` returns the wrong result (~0) in Renode 1.16.1 when the input is a computed FPU-register value. Same class of emulator bug as the previously documented `VSQRT.F32` failure in `step_detector.c`.

**Why this matters:** The SI output is the only clinical signal the device produces. A silently zeroed SI means the device reports "perfect symmetry" for every patient regardless of actual gait asymmetry — a dangerous false negative that would have shipped to hardware undetected without the pathological walker test.

**Fix:** Replaced `fabsf()` with `(diff >= 0.0f) ? diff : -diff` in `compute_si_x10()`. Compiles to VCMP+branch, avoids VABS.F32 entirely.

**File changed:** `src/gait/rolling_window.c:compute_si_x10()`

**Verified:**
- Healthy mode: all 4 profiles SI < 5% (below 10% clinical threshold) ✓
- Pathological mode (true SI = 25%): Flat 17.2%, Bad wear 23.8%, Stairs 19.3%, Slope 22.6% — all above 10% clinical threshold ✓

---

#### BUG-012: rolling_snapshot_t struct size comment wrong (20 bytes stated, 18 bytes actual)

**Symptom:** `parse_binary_export_log()` finds 0 binary snapshots even though `BLE_BINARY_START` is present in the UART log.

**Root cause:** Comment in `rolling_window.h` said `/* 20 bytes */`. Actual layout (4+4+2+2+2+2+1+1) = 18 bytes. The hex line filter in `signal_analysis.py` was checking `len(line) == 40` (20 × 2 hex chars) instead of `len(line) == 36` (18 × 2).

**Fix:** Corrected comment in `rolling_window.h`; changed filter to `len(line) == _SNAPSHOT_STRUCT_SIZE * 2`.

**Impact on hardware:** The production BLE path sends the raw struct over GATT — any host tool must unpack with `struct.Struct("<IIHHHHBb")` (18 bytes), **not** 20 bytes.

---

### Remaining open work before hardware (Stage 4)

| Item | Description |
|------|-------------|
| Edge case tests | Zero-step session, FIFO overflow, device flipped upside-down, BLE disconnect mid-export |
| Robot Framework suite | `robot renode/robot/gait_test.robot` — automated Renode regression suite |
| Power model hardware verify | Nordic PPK2 confirmation of ≤5 μA sleep / ≤1.5 mA active (simulation predicts: sleep 5 μA, active 1.1 mA, runtime 344 days on 100 mAh) |

---

## 8. Why This Approach Works

This project was built from zero to a validated embedded gait algorithm — including discovery and fix of a critical clinical safety bug (BUG-013) — without fabricating any hardware.

The key structural principle: **every signal the firmware sees is derived from three first-order physical quantities** (vertical oscillation, cadence, step length), not injected as raw axis values. This means the simulation is a physics test, not a signal playback. When the stair walker produced 0 detected steps, the signal plots immediately showed the biomechanical reason — a 135 ms timing gap that breaks a 40 ms window assumption. No hardware was needed to make this visible.

The secondary principle: **the firmware ELF that runs in Renode is the same binary that gets flashed to the XIAO.** There is no mock, no stub, no model of the algorithm. If a failure mode appears in simulation, it will appear on hardware. If it is resolved in simulation, it is resolved on hardware.

BUG-013 is the proof: a silently-zeroed SI computation that would have shipped as a device reporting "perfect symmetry" for every patient was caught by running a single pathological walker (25% true SI) through the firmware on a virtual Cortex-M4F. No IMU. No patient. No hospital corridor.

---

## 9. BOMs

- [Hardware BOM](docs/hw_bom.md) — ~$45–50, Seeed XIAO nRF52840 Sense + perfboard assembly
- [Software BOM](docs/sw_bom.md) — full open-source stack; SEGGER tools free for non-commercial use
