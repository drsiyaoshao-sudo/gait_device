# GaitSense — Ankle Gait Analysis Wearable

Single-ankle IMU device for detecting walking pattern asymmetry.
Hardware: Seeed XIAO nRF52840 Sense (nRF52840 + LSM6DS3TR-C + BLE 5.0).

---

## Quick Start

```bash
# Install Python dependencies
pip install numpy scipy streamlit plotly bleak pyserial pytest pandas pyarrow robotframework

# Build firmware
pio run -e xiaoble_sense

# Run simulation (no hardware needed)
pio run -t simulate

# Launch Digital Twin UI
streamlit run simulator/app.py

# Run unit tests (host-side, no hardware)
pio test -e native
```

---

## Project Structure

```
gait_device/
├── CLAUDE.md                    # Dev philosophy, pipeline, stage exit criteria
├── README.md                    # This file
├── platformio.ini               # PlatformIO build environments
├── prj.conf                     # Zephyr Kconfig
├── CMakeLists.txt
├── boards/
│   └── xiao_ble_sense.overlay   # LSM6DSO on I2C0, button, LED
├── src/
│   ├── main.c
│   ├── imu/
│   │   ├── imu_reader.c/h       # FIFO watermark trigger + batch read
│   │   └── calibration.c/h      # Static bias, NVS persistence
│   ├── gait/
│   │   ├── gait_engine.c/h      # Pipeline orchestration
│   │   ├── step_detector.c/h    # Adaptive LP filter + HS FSM
│   │   ├── phase_segmenter.c/h  # Gait phase FSM
│   │   ├── foot_angle.c/h       # Complementary filter
│   │   └── rolling_window.c/h   # 200-step buffer + snapshot every 10 steps
│   ├── session/
│   │   ├── session_mgr.c/h      # Button debounce, LED, session lifecycle
│   │   └── snapshot_buffer.c/h  # RAM ring buffer (5500 snapshots)
│   └── ble/
│       └── ble_gait_svc.c/h     # Custom GATT service + snapshot export
├── simulator/
│   ├── walker_model.py          # Biomechanical signal generator (4 terrain profiles)
│   ├── imu_model.py             # Physical units → LSM6DS3 FIFO byte format
│   ├── signal_analysis.py       # UART log parser → typed events
│   └── app.py                   # Streamlit UI
├── renode/
│   ├── gait_device.resc         # Renode scenario script
│   ├── gait_nrf52840.repl       # Platform: nRF52840 + LSM6DS3 stub
│   └── robot/
│       ├── gait_test.robot      # Robot Framework integration tests
│       └── imu_feeder.py        # Inject IMU samples via Renode Python API
├── test/
│   └── native/
│       ├── test_step_detector.c
│       ├── test_rolling_window.c
│       └── test_foot_angle.c
├── host_tool/
│   └── download_session.py      # BLE snapshot download (real hardware)
└── docs/
    ├── hw_bom.md
    └── sw_bom.md
```

---

## Firmware Build Variants

### Production build (BLE export)
```bash
pio run -e xiaoble_sense
```
Snapshots exported via custom GATT service. Use `host_tool/download_session.py` to download.

### Simulation build (UART export)
```bash
pio run -e xiaoble_sense -- -DCONFIG_GAIT_UART_EXPORT=y
```

**What changes with `CONFIG_GAIT_UART_EXPORT=y`:**

`ble_gait_svc.c` is **excluded** from the build. In its place, a UART dump loop
in `session_mgr.c` activates at session end and writes all `rolling_snapshot_t`
structs as raw binary over UART0, preceded by a 4-byte magic header `0xGA1T0001`
and a 4-byte count.

This flag exists **only for Renode simulation**. It must never be flashed to hardware
because it disables BLE entirely. The production BLE path is the only valid export
mechanism for physical devices.

```c
/* session_mgr.c — excerpt showing the conditional */
#ifdef CONFIG_GAIT_UART_EXPORT
    /* Simulation path: dump snapshots as binary over UART */
    uart_export_snapshots();
#else
    /* Production path: BLE GATT export */
    ble_gait_svc_notify_status(SESSION_COMPLETE);
#endif
```

Format of UART binary dump:
```
[4 bytes] magic   : 0x47 0x41 0x31 0x54  ("GA1T")
[4 bytes] count   : uint32_t little-endian, number of snapshots
[N × 20 bytes]    : rolling_snapshot_t structs, packed, little-endian
```

Python unpack (in `signal_analysis.py`):
```python
SNAPSHOT_STRUCT = struct.Struct("<IIHHHHBb")   # 20 bytes
```

---

## Development Order (enforced — see CLAUDE.md)

```
1. Firmware  →  2. Software  →  3. Simulation  →  4. Edge Cases  →  5. Hardware
```

Every stage requires explicit sign-off before the next begins.

---

## Docs

- [Hardware BOM](docs/hw_bom.md)
- [Software BOM](docs/sw_bom.md)
