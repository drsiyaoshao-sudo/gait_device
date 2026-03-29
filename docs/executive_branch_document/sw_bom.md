# Software Bill of Materials — Ankle Gait Analysis Wearable

---

## Firmware Stack

| Component | Version / Source | License | Purpose |
|-----------|-----------------|---------|---------|
| PlatformIO Core | ≥ 6.1 | Apache 2.0 | Build system, dependency management, `pio run / test / simulate` |
| nordicnrf52 PlatformIO platform | latest | Apache 2.0 | nRF52840 board support package; integrates Zephyr SDK and nRF Connect toolchain |
| Zephyr RTOS | ≥ 3.5 (via nRF Connect SDK 2.5+) | Apache 2.0 | RTOS kernel, scheduler, IPC primitives (`k_msgq`, `k_sem`, `k_mutex`), power management |
| LSM6DSO Zephyr in-tree driver | Zephyr 3.5+ | Apache 2.0 | LSM6DS3TR-C FIFO watermark trigger + batch read via `SENSOR_TRIG_FIFO_WATERMARK`; enabled with `CONFIG_LSM6DSO=y` |
| Zephyr BT stack (NimBLE / SoftDevice) | in-tree | Apache 2.0 | BLE 5.0 GATT peripheral; custom 128-bit UUID service for snapshot export |
| Zephyr NVS | in-tree | Apache 2.0 | Non-volatile storage for IMU calibration bias across reboots |
| Zephyr Ring Buffer | in-tree | Apache 2.0 | `k_msgq imu_sample_queue` between `imu_thread` and `gait_thread` |
| Zephyr PM (Power Management) | in-tree | Apache 2.0 | System idle / deep sleep between FIFO drain cycles; target 5 μA deep sleep |
| Zephyr Sensor API | in-tree | Apache 2.0 | Abstraction over `sensor_sample_fetch` / `sensor_channel_get`; used for FIFO bulk reads |
| SEGGER RTT | bundled with J-Link SDK | SEGGER (free for non-commercial) | Low-latency `SEGGER_RTT_printf` over SWD; replaces UART for `printk` in production firmware |
| SEGGER SystemView | standalone desktop app | SEGGER (free) | Thread timeline, ISR firing intervals, preemption trace — requires J-Link EDU Mini |
| arm-zephyr-eabi GCC | ≥ 12.2 (bundled in nRF Connect SDK) | GPL-3.0 with runtime exception | Cortex-M4F cross-compiler with FPU support (`-mfpu=fpv4-sp-d16 -mfloat-abi=hard`) |
| nrfjprog | ≥ 10.20 (Nordic CLI tools) | Nordic proprietary (free) | Optional: SWD flash and reset via J-Link; alternative to drag-and-drop `.uf2` |

### Key Kconfig Flags (`prj.conf`)

```kconfig
CONFIG_I2C=y
CONFIG_BT=y
CONFIG_BT_PERIPHERAL=y
CONFIG_RING_BUFFER=y
CONFIG_FPU=y
CONFIG_FPU_SHARING=y
CONFIG_PM=y
CONFIG_NVS=y
CONFIG_SENSOR=y
CONFIG_LSM6DSO=y
CONFIG_LSM6DSO_TRIGGER_GLOBAL_THREAD=y
CONFIG_SEGGER_RTT=y                    # optional, requires J-Link
CONFIG_SEGGER_SYSTEMVIEW=y             # optional, requires J-Link + SystemView app
```

---

## Simulation Stack

| Component | Version | License | Purpose |
|-----------|---------|---------|---------|
| Renode | ≥ 1.15 | MIT | Full-system nRF52840 simulator; loads actual firmware `.elf`, simulates Cortex-M4F core + nRF52840 peripherals + LSM6DS3 I2C stub |
| Robot Framework | ≥ 7.0 | Apache 2.0 | Automated integration test runner (`gait_test.robot`); orchestrates PlatformIO build → Renode simulate → assert UART output |
| Python | ≥ 3.11 | PSF | Simulator engine, walker model, Renode telnet bridge, host BLE tool |
| NumPy | ≥ 1.26 | BSD-3-Clause | IMU signal generation (sinusoidal heel-strike impulses, swing arcs), array operations, noise injection |
| SciPy | ≥ 1.12 | BSD-3-Clause | Butterworth IIR filter design (`scipy.signal.butter` / `sosfilt`) for step detector validation; rotation matrix for mounting offset |
| Streamlit | ≥ 1.32 | Apache 2.0 | Browser-based Digital Twin Simulator UI (`streamlit run simulator/app.py`); profile selector, parameter sliders, chart rendering |
| Plotly | ≥ 5.20 | MIT | Interactive IMU signal plot (acc_z, gyr_y + step markers), SI time-series (detected vs ground truth), phase Gantt chart |
| bleak | ≥ 0.21 | MIT | Cross-platform BLE central (asyncio); used in `host_tool/download_session.py` to connect to device and pull snapshot notifications |
| pyserial | ≥ 3.5 | BSD-3-Clause | UART logging fallback when J-Link / RTT not available |
| pytest | ≥ 8.0 | MIT | Python-side unit tests for `walker_model.py`, `signal_analysis.py`, Renode bridge mock |

### Renode Platform File Summary (`renode/gait_nrf52840.repl`)

| Peripheral | Renode Model | Notes |
|-----------|-------------|-------|
| nRF52840 Cortex-M4F | `CPU.CortexM` (built-in) | Loads firmware ELF; FPU emulated |
| UART0 | `UART.NRF52840_UART` | Captures `printk` / RTT-via-UART output; Robot Framework asserts on lines |
| I2C0 + LSM6DS3 stub | Custom Python peripheral | Responds to WHO_AM_I (0x6A); `FeedSample` command injects FIFO data |
| GPIO (INT1) | `GPIOPort.NRF52840_GPIO` | Asserts watermark interrupt from I2C stub after each batch |
| Flash (1MB) | `Memory.MappedMemory` | Firmware code + NVS partition |
| RAM (256KB) | `Memory.MappedMemory` | Stack + heap + snapshot buffer |

---

## Host Analysis Tool

| Component | Version | License | Purpose |
|-----------|---------|---------|---------|
| bleak | ≥ 0.21 | MIT | BLE connection; subscribes to Step Data Transfer notifications, writes to Control Point |
| Plotly / Dash | ≥ 5.20 | MIT | Post-session SI time-series visualization; optional interactive dashboard for clinical review |
| pandas | ≥ 2.1 | BSD-3-Clause | Snapshot struct unpacking (`struct.unpack`), DataFrame for SI trend, CSV / Parquet export |
| pyarrow | ≥ 14.0 | Apache 2.0 | Optional: Parquet serialization for long-term session dataset storage |

### Host Tool Snapshot Protocol

Binary transfer (not JSON) — 5 × `step_record_t` per BLE notification at ATT MTU 247:

```
Notification header (4 bytes):
  uint16_t  seq_num         // monotonic notification counter
  uint16_t  records_in_pkt  // 1–5

Per record (48 bytes), packed:
  uint32_t  step_index
  uint32_t  heel_strike_ts_ms
  uint16_t  step_duration_ms
  uint16_t  stance_duration_ms
  uint16_t  swing_duration_ms
  int16_t   foot_angle_ic_cdeg
  int16_t   foot_angle_to_cdeg
  int16_t   peak_ang_vel_dps
  uint8_t   cadence_spm
  uint8_t   flags
  uint8_t   reserved[8]
```

1000 steps → 200 notifications → ~1.5 s transfer at 7.5 ms connection interval.

---

## Digital Twin Simulator — Component Detail

| Module | File | Dependencies | Purpose |
|--------|------|-------------|---------|
| Walker model | `simulator/walker_model.py` | NumPy, SciPy | `WalkerProfile` dataclass + `generate_imu_sequence()`; outputs `(N, 6)` array `[ax, ay, az, gx, gy, gz]` at 208 Hz |
| Renode bridge | `simulator/renode_bridge.py` | subprocess, socket | Launches Renode headless, feeds LSM6DS3 FIFO stub, drains UART event stream |
| Signal analysis | `simulator/signal_analysis.py` | NumPy, pandas | Parses UART step-event and snapshot-binary lines from Renode; reconstructs SI time series |
| UI entry point | `simulator/app.py` | Streamlit, Plotly | Profile selector, parameter sliders, "Run Simulation" button, 3-panel chart layout |
| Profile library | `simulator/profiles/*.json` | — | Serialized `WalkerProfile` parameters; grows as clinical data collected |
| Simulation results | `simulator/datasets/simulation_results/` | — | Saved runs: input profile + firmware output → labeled ground-truth dataset for future ML |

### Built-in Walker Profiles

| Profile | Cadence (spm) | True SI Stance (%) | Modeled Condition |
|---------|---------------|-------------------|------------------|
| `normal` | 100 | 3 | Healthy adult, flat ground |
| `runner` | 170 | 5 | Recreational runner, mid-foot strike |
| `post_acl` | 85 | 22 | Post-ACL reconstruction, right-side offloading |
| `elderly` | 75 | 8 | Elderly shuffler, reduced push-off |
| `hemiplegic` | 65 | 35 | Post-stroke hemiplegia, severe temporal asymmetry |

---

## Development Tools

| Tool | Version | Purpose |
|------|---------|---------|
| PlatformIO IDE (VS Code extension) | latest | Unified build (`pio run`), flash (`pio run -t upload`), monitor (`pio device monitor`), test (`pio test`) |
| VS Code | ≥ 1.85 | Editor with PlatformIO + Cortex-Debug extensions |
| Cortex-Debug (VS Code extension) | ≥ 1.12 | GDB-over-J-Link debug sessions with RTOS thread awareness (Zephyr RTOS plugin) |
| nRF Connect for Desktop | ≥ 4.4 | BLE scanner (GATT attribute browser); verify custom service UUIDs and characteristic reads during dev |
| nRF Sniffer for Bluetooth LE | ≥ 4.1 | Wireshark plugin; captures raw BLE packets on 2.4 GHz; verifies MTU negotiation, connection interval, notification flow |
| Wireshark | ≥ 4.0 | BLE packet capture display; used alongside nRF Sniffer |
| SEGGER J-Link EDU Mini | hardware + software | SWD flash, RTT, SystemView — see HW BOM |
| Git | ≥ 2.40 | Version control |
| Docker | optional | Reproducible build environment: Renode + nRF Connect SDK + PlatformIO in one container |

---

## Python Environment Setup

```bash
# Firmware simulation + host tool
pip install numpy scipy streamlit plotly bleak pyserial pytest pandas pyarrow

# Robot Framework (Renode integration tests)
pip install robotframework

# Run Digital Twin Simulator
streamlit run simulator/app.py

# Run Python unit tests
pytest simulator/tests/

# Run Robot Framework integration tests (requires Renode in PATH)
robot renode/robot/gait_test.robot
```

---

## PlatformIO Configuration Summary

```ini
; platformio.ini

[env:xiaoble_sense]
platform      = nordicnrf52
board         = xiaoble_sense        ; Seeed XIAO nRF52840 Sense
framework     = zephyr
build_flags   = -DCONFIG_FPU=y
monitor_speed = 115200
extra_scripts = scripts/renode_simulate.py   ; hooks 'pio run -t simulate'

[env:native]
platform       = native
test_build_src = yes
build_flags    = -DUNIT_TEST -std=c11
; Algorithm modules (step_detector, metrics, rolling_window) compile on host
; for fast unit testing — no hardware required
```

**Build targets:**

| Command | Action |
|---------|--------|
| `pio run -e xiaoble_sense` | Build firmware ELF + UF2 for XIAO Sense |
| `pio run -t upload` | Flash via USB-C (UF2 drag-and-drop via nRF52840 bootloader) |
| `pio run -t simulate` | Build + launch Renode with `gait_device.resc` |
| `pio test -e native` | Run host-side unit tests (step detector, SI computation) |
| `west build -b native_posix tests/gait_unit` | Zephyr ztest suite on native_posix (Zephyr test runner) |

---

## Licensing Summary

All firmware dependencies are **Apache 2.0** or equivalent permissive licenses — no GPL contamination in the firmware binary. Simulation/host tools are all permissive (MIT, BSD, Apache 2.0). SEGGER RTT/SystemView are free for non-commercial use; a commercial license is required for production sale.

| Layer | Most restrictive license | Commercial concern? |
|-------|------------------------|---------------------|
| Firmware | Apache 2.0 (Zephyr) | No |
| Simulation engine | MIT (Renode) | No |
| Host tool | MIT (bleak, Plotly) | No |
| Debug tools | SEGGER (free for non-commercial) | Yes — license for commercial production |
