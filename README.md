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

## Why This Digital Twin Works — The Learner-in-the-Loop Principle

This project was built in one week, from zero to a PhD-level biomechanical failure analysis, by a single developer with no prior embedded gait algorithm experience. That is not an accident of tooling. It is the result of a specific collaboration pattern that any hardware startup can replicate.

### The core problem it solves

Hardware R&D failure modes are well known: a team spends 3–6 months building firmware against a mental model of the physics, discovers on real hardware that the mental model was wrong, and restarts. The cost is not just time — it is the compounding cost of discovering a physics error at the most expensive possible point in the stack.

The standard mitigation is "simulate early." The problem is that most simulation approaches either:
- Inject raw sensor values (bypassing the physics entirely, so the simulation cannot catch physics errors)
- Mock the firmware (so the simulation cannot catch firmware errors)
- Run on a fixed test fixture (so the simulation cannot explore failure modes not already anticipated)

This project does none of those. Every signal the firmware sees is derived from three first-order physical quantities: vertical oscillation, cadence, step length. The firmware ELF runs on a virtual Cortex-M4F. The failure modes are discovered by the simulation, not programmed into it.

### What "Learner-in-the-Loop" means in practice

The developer does not need to know the answer in advance. The loop is:

```
1. Physical intuition (human)      "Stair climbing feels different — the foot lands differently"
        ↓
2. Simulator makes it precise      acc_filt peak at 188ms, gyr_y zero-crossing at 53ms
        ↓
3. Signal plot arbitrates          Neither party claims — the plot shows the 135ms separation
        ↓
4. Root cause becomes undeniable   Dual-confirmation gate assumes co-incident events; stairs split them
        ↓
5. Fix domain is physically grounded   Three options, each traceable to biomechanics or hardware
```

At no point does the developer need to know embedded C, Renode, or gait biomechanics at entry. The three-primitive constraint forces every claim to be physically grounded. The signal plots prevent "it looks right" from being accepted as evidence. The stage gate system prevents fixing one layer by breaking another.

### The concrete result from this project

BUG-010, the Stair Walker failure mode:
- **Failure**: 0/50 steps detected on stair profile in bare-metal simulation
- **Signal**: acc_filt peak = 7.44 m/s² (above 5.0 threshold) — the signal IS present
- **Root cause**: gyr_y zero-crossing occurs 135ms before the acc_filt peak; `GYR_CONFIRM_MS = 40ms`; step rejected on timing, not amplitude
- **Physical explanation**: Heel-strike places impact and ankle rotation reversal within 40ms. Forefoot/midfoot strike on stairs separates them by 135ms, breaking the dual-confirmation assumption
- **Fix options documented**: Feature Extraction / Terrain Classification / Hardware Change — each with biomechanical grounding, awaiting human selection
- **Cost**: Zero hardware fabricated. Zero PCBs ordered. Zero firmware flashed to a broken device.

This is the value proposition of the digital twin for a hardware startup: the expensive discovery (the algorithm fundamentally cannot handle stair gait as designed) happened at the simulation layer, not the hardware layer.

### How to replicate this for your own project

1. **Enforce the three-primitive rule** — never let the simulator accept raw axis values as inputs. Force every signal to derive from a physically measurable quantity. This is what makes the simulation a physics test, not a signal playback.

2. **Run real firmware on virtual hardware** — Renode + PlatformIO is the stack used here. The firmware ELF that runs in Renode is the same binary that gets flashed to the XIAO. If a failure mode appears in simulation, it will appear on hardware.

3. **Plot before you trust numbers** — SI = 0.0% is correct for a symmetric walker, but only if the underlying signals are physically plausible. The learner-in-the-loop signal plot (3-panel: acc_z, acc_x, gyr_y) is a required checkpoint after every model or filter change, not an optional audit.

4. **Document the failure, not just the fix** — the stair walker fix domain is not yet selected. That is intentional. A startup that documents "what broke and why" without immediately patching it has something more valuable than a patch: a grounded decision about which of three architectural directions to pursue (algorithm, classification, or hardware BOM).

5. **Use the stage gate as a forcing function** — the development order (Firmware → Software → Simulation → Edge Cases → Hardware) is not bureaucracy. It is the mechanism that prevents a firmware bug from being hidden by a simulator workaround, or a simulator failure from being dismissed as "we'll test on hardware."

---

## Docs

- [Hardware BOM](docs/hw_bom.md)
- [Software BOM](docs/sw_bom.md)
