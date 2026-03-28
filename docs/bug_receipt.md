# GaitSense — Bug Receipt for Project Handoff

**Prepared by:** Simulation & Firmware Team
**Date:** 2026-03-27
**Branch at handoff:** handoff-testing (based on ble-export-sim)
**Purpose:** Every bug found during simulation stages 1–3, its root cause, and the exact fix applied. Use this as a debugging reference if hardware behaviour deviates from `docs/handoff.md` predictions.

---

## How to Use This Document

Each entry follows the same structure:

- **Symptom** — what you would observe if this bug were still present
- **Root cause** — why it happened
- **Fix** — what was changed and where
- **Verification** — how it was confirmed resolved

Bugs are ordered by the stage in which they were caught. If you encounter unexpected hardware behaviour, match the symptom to an entry here before concluding the fault is new.

---

## Category Index

| Category | Bug IDs |
|---|---|
| Simulation Infrastructure | BUG-001, BUG-003, BUG-004, BUG-006, BUG-007 |
| Dependencies / Build | BUG-005 |
| Bare-Metal C Simulation | BUG-008, BUG-012 |
| Gait Algorithm | BUG-002, BUG-009, BUG-010, BUG-011 |

---

## Gait Algorithm Bugs

These bugs were in the core algorithm running on the nRF52840. They will reproduce on physical hardware if the fix is absent from the flashed ELF.

---

### BUG-010 — Stair Walker: 0 steps detected out of 100

**Category:** Gait Algorithm
**Stage caught:** Stage 3 (Renode bare-metal simulation)
**Status:** RESOLVED

**Symptom:**
Walking a stair-like profile (forefoot contact, high vertical acceleration at mid-stance) produces zero step detections. The `SESSION_END steps=0` line appears in UART output. On hardware this would appear as the LED never confirming a step and the BLE session summary reporting 0 steps.

**Root cause:**
The original step detector used dual-confirmation: `gyr_y` sign reversal at heel contact AND `acc_filt` threshold crossing within a 40ms co-occurrence window. On flat ground these two events are co-incident (<15ms apart). On stairs, forefoot contact means `gyr_y` crosses zero at 53ms while `acc_filt` peaks at 188ms — a 135ms gap that exceeds the 40ms window. Every candidate step was discarded.

Signal measurements from diagnostic plot:

| Signal | Flat walker | Stair walker |
|---|---|---|
| gyr_y zero-crossing | 34ms after stance start | 53ms after stance start |
| acc_filt peak | 572ms after stance start | 188ms after stance start |
| Temporal gap | 538ms (within window) | **135ms (exceeds 40ms window)** |

**Fix (Push-Off Primary with Retrospective Heel-Strike Inference):**

Algorithm inversion in `src/gait/step_detector.c`:
1. Primary trigger: `gyr_y_hp > 30 dps` (push-off burst). Push-off plantar-flexion is biomechanically universal — no terrain allows walking without it.
2. Confirmation: `acc_filt > adaptive_threshold` since the last confirmed step (not time-gated).
3. Heel-strike inference: an 8-entry ring buffer (~32 bytes RAM) stores rejected `acc_filt` threshold crossings since the last step. On confirmed push-off, the oldest ring entry is used as the retrospective heel-strike timestamp → `phase_segmenter` receives physically correct stance start timing.

**Verification:**
Renode bare-metal, 100 steps per profile:

| Profile | Before fix | After fix | SI |
|---|---|---|---|
| Flat | 100/100 | 100/100 | 0.04% |
| Bad wear | 100/100 | 100/100 | 0.04% |
| Slope 10° | 100/100 | 100/100 | 0.84% |
| **Stairs** | **0/100** | **100/100** | **0.41%** |

**Files changed:** `src/gait/step_detector.c`

---

### BUG-002 — LOADING→MID_STANCE phase gate fails on stairs

**Category:** Gait Algorithm
**Stage caught:** Stage 3 (Renode bare-metal simulation)
**Status:** RESOLVED

**Symptom:**
Stair walker step 0 is stuck in `LOADING` phase and never completes a gait cycle. First snapshot shows `SI_swing = 200%` (a convolution artifact from missing the even-side reference of step 0). On hardware this would manifest as the first ~10 steps producing wildly incorrect SI values.

**Root cause:**
The `LOADING → MID_STANCE` transition condition required:

```c
acc_z_lp > 0.85 * 9.81  AND  fabsf(acc_mag - 9.81) < 2.94
```

The second gate assumes `acc_mag ≈ 9.81 m/s²` at mid-stance (valid on flat ground). On stairs, heel-strike impact drives `acc_mag ≈ 20 m/s²`. The gate `|20 - 9.81| = 10.2 >> 2.94` never fires. The phase segmenter is permanently stuck in `LOADING`.

**Fix:**
Replaced the `acc_mag` gate with a gyroscope-based terrain-agnostic gate:

```c
fabsf(gyr_y) < 20.0f  /* dps */
```

Physical derivation: heel-strike arrest decays from 37–60 dps to near-zero in ~100ms on all terrains. Early ankle rocker is 10–13 dps. The 20 dps threshold bisects them — terrain-independent. The `sim_sqrtf` Renode VSQRT.F32 workaround in `phase_segmenter.c` was also removed entirely as `acc_mag` is no longer computed.

**Verification:**
All 4 profiles cycle correctly. Step 0 included in rolling window (anchor=9, not 10). `SI_swing = 0.0%` at first snapshot for all profiles.

**Files changed:** `src/gait/phase_segmenter.c`

---

### BUG-009 — Rolling window cold start: SI_swing = 200% at first snapshot

**Category:** Gait Algorithm
**Stage caught:** Stage 3 (Renode bare-metal simulation)
**Status:** RESOLVED

**Symptom:**
Regardless of walker profile, the very first snapshot (anchor_step=9) always reports `SI_swing = 200%`. All subsequent snapshots are correct. On hardware this means the first ~20 seconds of a session will always show a pathological asymmetry reading that clears on its own — potentially alarming a user or falsely triggering a flag.

**Root cause:**
Two compounding cold-start effects:

1. **Ring buffer ghost step:** The terrain-aware step detector ring buffer retains `acc_filt` peaks from the stationary calibration period. Step 0 receives a heel-strike timestamp of ~4.8ms (essentially t=0), yielding a stance duration of ~1534ms (3× normal). This creates an extreme outlier in the even-step distribution of the first 10-step window.

2. **LP filter cold start:** `acc_z_lp_prev` initialised to 0 via `memset`. First real sample sees `acc_z_lp = 0.5×0 + 0.5×acc_z` instead of the gravity baseline. Combined with the ghost step, the first snapshot has a corrupted odd/even swing balance.

**Fix (CNN same-padding analogy):**

Two changes:

1. `rolling_window_init()` in `src/gait/rolling_window.c`: pre-fill the circular window with 9 synthetic flat-walk records as neutral priors:
   - stance=343ms, swing=229ms, cadence=105 spm (derived from 60/40 stance/swing split at 105 spm)
   - Records use `step_index` 0–8, `flags=0x01`
   - Priors evict naturally as real steps fill the buffer (gone after 200 real steps — no permanent effect)

2. `phase_segmenter_init()` in `src/gait/phase_segmenter.c`: seed `acc_z_lp_prev = 9.81f` (gravity baseline) instead of 0.

**Effect:** First snapshot window = 9 synthetic neutral priors + 10 real steps. SI_swing artifact eliminated. Cadence converges from 105 spm prior toward real cadence over first 3–4 snapshots.

**Verification:** `SI_swing = 0.0%` at all 9 snapshots for all 4 profiles.

**Files changed:** `src/gait/rolling_window.c`, `src/gait/phase_segmenter.c`

---

### BUG-011 — cadence_spm = 0 in all rolling_window records

**Category:** Gait Algorithm
**Stage caught:** Stage 3 (Renode bare-metal simulation)
**Status:** RESOLVED

**Symptom:**
Every `SNAPSHOT` UART line shows `cadence=0 spm`. `mean_cadence_x10 = 0` in all snapshot structs. `is_running` is always false. On hardware this means the BLE cadence field in every GATT notification would be zero regardless of actual walking speed.

**Root cause:**
`phase_segmenter_on_heel_strike()` never sets `ps.cur.cadence_spm`. The `heel_strike_t` struct has no cadence field. The only source of cadence data is `step_detector_cadence_spm()` — this function was never called anywhere in the pipeline that feeds `rolling_window_add_step()`.

**Fix:**
In `src/gait/gait_engine.c`, function `on_step_record()`:
```c
step_record_t rec = *raw_rec;                         // copy
rec.cadence_spm = (uint8_t)MIN(                       // inject cadence
    step_detector_cadence_spm(), 255);
rolling_window_add_step(&rec);                        // pass corrected record
```

**Verification:**
All 4 profiles show correct cadence in snapshots:
- Flat: 104 spm (target 105)
- Slope: 95 spm (target 95)
- Stairs: 72 spm (target 70)

**Files changed:** `src/gait/gait_engine.c`

---

## Bare-Metal C Simulation Bugs

These bugs were in the simulation infrastructure (Renode scripts and Python parsers) and do not affect the flashed firmware. They are documented here because they could re-emerge if the simulation pipeline is re-run or extended.

---

### BUG-008 — Duplicate SNAPSHOT lines in UART log (18 snapshots instead of 9)

**Category:** Bare-Metal C Simulation
**Stage caught:** Stage 3 (Renode bare-metal simulation)
**Status:** RESOLVED

**Symptom:**
A 100-step run produces 18 snapshot events instead of 9. Each anchor step appears twice — once with correct cadence, once with cadence=0. The SI values from the duplicate set are usually wrong (the zero-cadence copy). `parse_uart_log()` returns double the expected snapshot count.

**Root cause:**
`emit_snapshot()` in `src/gait/rolling_window.c` emitted both `LOG_INF("SNAPSHOT…")` and `printk("SNAPSHOT…")`. In the Renode simulation build, `CONFIG_LOG=n` does NOT silence `LOG_INF` — it still fires. `signal_analysis.py` uses `.search()` (not `.match()`), so it matches `SNAPSHOT` anywhere in a log-prefixed string. Two events per snapshot anchor step.

**Fix:**
Removed `LOG_INF` from `emit_snapshot()`. Only `printk` remains.

```c
/* emit_snapshot() — printk only; LOG_INF is NOT silent under CONFIG_LOG=n
 * in the Renode sim build (the Zephyr log backend still fires). */
printk("SNAPSHOT step=%u si_stance=%.1f%% si_swing=%.1f%% cadence=%.1f spm\n",
       ...);
```

**Verification:** 9 snapshots per 100-step run. No duplicates across all 4 profiles.

**Files changed:** `src/gait/rolling_window.c`

---

### BUG-012 — rolling_snapshot_t struct size comment wrong (20 bytes stated, 18 bytes actual)

**Category:** Bare-Metal C Simulation
**Stage caught:** Stage 3, BLE export sub-task (session 3)
**Status:** RESOLVED

**Symptom:**
`parse_binary_export_log()` returns 0 binary snapshots even though `BLE_BINARY_START` is present in the UART log. The hex lines are present but filtered out. No error is raised — the export silently returns empty.

**Root cause:**
The comment in `rolling_window.h` read `/* 20 bytes */`. The actual struct layout:

```
uint32_t anchor_step_index   4 bytes
uint32_t anchor_ts_ms        4 bytes
uint16_t si_stance_x10       2 bytes
uint16_t si_swing_x10        2 bytes
uint16_t si_peak_angvel_x10  2 bytes
uint16_t mean_cadence_x10    2 bytes
uint8_t  step_count          1 byte
uint8_t  flags               1 byte
Total:                       18 bytes
```

The original Python filter was written from the incorrect comment:
```python
elif in_export and len(line) == 40:   # WRONG — 20 * 2
```
Every 36-character hex line was rejected.

**Fix:**
1. `simulator/signal_analysis.py`: changed filter to use the computed constant:
```python
elif in_export and len(line) == _SNAPSHOT_STRUCT_SIZE * 2:  # 36
```
2. `src/gait/rolling_window.h`: corrected comment:
```c
} rolling_snapshot_t;  /* 18 bytes: 4+4+2+2+2+2+1+1 */
```

Also corrected the module docstring in `signal_analysis.py` which stated "20 bytes each" and used `struct("…Bb")` — note the struct format `<IIHHHHBb` is 18 bytes (the `b` is signed int8, not a padding byte).

**Verification:** All 4 profiles: 9/9 binary snapshots match text snapshots. ΔSI = 0.00%.

**Files changed:** `simulator/signal_analysis.py`, `src/gait/rolling_window.h`

---

## Simulation Infrastructure Bugs

These bugs were in the Renode peripheral scripts. They do not affect the flashed firmware. They are documented because the simulation pipeline must work for future edge-case validation (Stage 4) and hardware-correlated re-runs.

---

### BUG-001 — IronPython global state exhausts after 5 IMU samples

**Category:** Simulation Infrastructure
**Stage caught:** Stage 3 (early Renode bring-up)
**Status:** RESOLVED

**Symptom:**
IMU simulation stalls after 5 samples. Renode sim hangs waiting for the next FIFO watermark interrupt that never fires.

**Root cause:**
`sim_imu_stub.py` maintained an in-memory list for the sample index. IronPython (the Renode scripting engine) does not persist global state reliably between peripheral callback invocations after the first few calls.

**Fix:**
Replaced in-memory index with a file-based index. The index is written and read from a temp file. `_write_idx()` uses explicit `f.close()` to force filesystem flush.

**Files changed:** `renode/sim_imu_stub.py`

---

### BUG-003 — Python.PythonPeripheral has no sysbus memory access API

**Category:** Simulation Infrastructure
**Stage caught:** Stage 3 (UART stub development)
**Status:** RESOLVED

**Symptom:**
`sim_uart_stub.py` could not read DMA memory to capture UART bytes. AttributeError on `self.sysbus.ReadByte()`.

**Root cause:**
The Renode Python peripheral API does not expose `sysbus` directly as an attribute.

**Fix:**
Use the inherited `IPeripheral` method chain:
```python
self.GetMachine().SystemBus.ReadByte(ptr + i)
```

**Files changed:** `renode/sim_uart_stub.py`

---

### BUG-004 — nRF UARTE EVENTS_TXSTOPPED is write-only (SUPERSEDED by BUG-006)

**Category:** Simulation Infrastructure
**Stage caught:** Stage 3 (UART stub development)
**Status:** SUPERSEDED

**Note:** An attempt to signal TX completion by writing `EVENTS_TXSTOPPED` via the register map failed because the register is write-only in Renode's nRF52840 model. This approach was abandoned. See BUG-006 for the working solution.

---

### BUG-006 — Post-kernel uart_poll_out blocks indefinitely on tx_done_sem

**Category:** Simulation Infrastructure
**Stage caught:** Stage 3 (UART stub development)
**Status:** RESOLVED

**Symptom:**
Renode simulation hangs at the first `printk()` or `uart_poll_out()` call. The firmware is waiting for a TX-complete semaphore that is never signalled. Sim timeout.

**Root cause:**
Zephyr's nRF UARTE driver (post-kernel init) uses `tx_done_sem` to gate `uart_poll_out`. After kernel init, the driver requires `TASKS_STARTTX` to be acknowledged by the peripheral, which in a real nRF52840 fires `EVENTS_ENDTX`. The Renode model does not auto-fire `EVENTS_ENDTX`.

**Fix:**
In `sim_uart_stub.py`, install a memory watchpoint on `TASKS_STARTTX` writes. On trigger, directly write bit 2 of `NVIC_ISPR0` (0xE000E200) to fire the UARTE interrupt, which unblocks `tx_done_sem`.

```python
machine.SystemBus.AddWatchpointHook(TASKS_STARTTX_ADDR, ...,
    lambda: machine.SystemBus.WriteDoubleWord(0xE000E200, 1 << 2))
```

**Files changed:** `renode/sim_uart_stub.py`

---

### BUG-007 — imu_reader_get ACK written after blocking printk

**Category:** Simulation Infrastructure
**Stage caught:** Stage 3 (initial Renode run)
**Status:** RESOLVED

**Symptom:**
Renode deadlocks on the first FIFO watermark batch. The IMU stub is waiting for the firmware to ACK the sample read before advancing the index, but the firmware is blocked inside a `printk()` (which itself is waiting for UART TX complete — see BUG-006). Circular dependency.

**Root cause:**
In `src/drivers/imu_sim_reader.c`, the ACK write to the IMU stub's ACK register was placed after the diagnostic `printk()` call. The `printk()` blocked on TX semaphore; the IMU stub was blocked waiting for ACK; the TX semaphore would only unblock after the next FIFO watermark; the next FIFO watermark would only fire after ACK. Deadlock.

**Fix:**
Moved the ACK write to before the `printk()` in `imu_sim_reader.c`.

**Files changed:** `src/drivers/imu_sim_reader.c`

---

## Dependencies / Build Bugs

---

### BUG-005 — PlatformIO firmware.elf omits application code

**Category:** Dependencies / Build
**Stage caught:** Stage 3 (first Renode ELF load)
**Status:** RESOLVED (workaround)

**Symptom:**
`pio run -e xiaoble_sense_sim` completes without error but the resulting ELF contains only Zephyr OS startup code — all `src/gait/*.c` files are absent. Renode loads the ELF and the firmware boots but no step events are ever emitted.

**Root cause:**
PlatformIO's CMake integration for Zephyr generates `app/libapp.a` as a separate link target but does not include it in its own top-level link step when called via `pio run`. The Zephyr CMake system knows about it but PlatformIO's wrapper does not trigger the correct ninja target sequence.

**Fix (two-step ninja build — must be used every time):**
```bash
pio run -e xiaoble_sense_sim
cd .pio/build/xiaoble_sense_sim
touch build.ninja          # force ninja to re-evaluate targets
ninja app/libapp.a
ninja zephyr/zephyr.elf
cd ../../../
```

Expected ELF: `.pio/build/xiaoble_sense_sim/zephyr/zephyr.elf`
Expected size: Flash ≈ 37.4 KB, SRAM ≈ 118 KB

**Important:** If `pio run` and then `ninja` are not run in this order, the ELF will silently produce 0 steps. There is no build error. The only indication is `SESSION_END steps=0` in UART output.

**Files changed:** None (procedure only). Automation script: `scripts/link_app_lib.py` (recommended future work — not yet implemented).

---

## Summary Table

| ID | Category | Title | Key file(s) changed |
|---|---|---|---|
| BUG-010 | Gait Algorithm | Stair walker: 0/100 steps — dual-confirmation timing mismatch | `step_detector.c` |
| BUG-002 | Gait Algorithm | LOADING→MID_STANCE gate: acc_mag assumption broken on stairs | `phase_segmenter.c` |
| BUG-009 | Gait Algorithm | Cold start: SI_swing=200% at first snapshot | `rolling_window.c`, `phase_segmenter.c` |
| BUG-011 | Gait Algorithm | cadence_spm=0 in all rolling_window records | `gait_engine.c` |
| BUG-008 | Bare-Metal C Sim | Duplicate SNAPSHOT lines: LOG_INF + printk both matched | `rolling_window.c` |
| BUG-012 | Bare-Metal C Sim | rolling_snapshot_t struct size comment wrong (20→18 bytes) | `signal_analysis.py`, `rolling_window.h` |
| BUG-001 | Sim Infra | IronPython global state exhausts after 5 samples | `sim_imu_stub.py` |
| BUG-003 | Sim Infra | Python.PythonPeripheral no sysbus memory access API | `sim_uart_stub.py` |
| BUG-004 | Sim Infra | nRF UARTE EVENTS_TXSTOPPED write-only (superseded) | — |
| BUG-006 | Sim Infra | uart_poll_out blocks on tx_done_sem indefinitely | `sim_uart_stub.py` |
| BUG-007 | Sim Infra | imu_reader ACK written after blocking printk (deadlock) | `imu_sim_reader.c` |
| BUG-005 | Dependencies | PlatformIO ELF omits app code — ninja two-step required | procedure only |

---

## Hardware Porting Watch List

The following issues have NOT been seen in simulation but are predicted based on the simulation-to-hardware transition. They are not bugs yet — they are risk items to check during Stage 5 bring-up.

| Risk | Predicted symptom | Check |
|---|---|---|
| Button pin P0.27 not exposed on standalone XIAO | Button press never registered; session never starts | Update `boards/xiao_ble_sense.overlay` to an exposed XIAO pad (e.g. P0.02) |
| Calibration bias on hardware vs simulation | acc_z baseline not 9.81 at rest, cadence offset | Run 2s static calibration, verify NVS write via RTT |
| IMU I2C address conflict | WHO_AM_I read fails (expected 0x6A) | Confirm `CONFIG_LSM6DS3_I2C_ADDR=0x6A` matches PCB pull-up state |
| BLE MTU negotiation mismatch | Snapshot GATT notifications truncated | Verify `CONFIG_BT_L2CAP_TX_MTU` ≥ snapshot struct size |
| LiPo connector polarity | Device does not power on or immediate voltage rail collapse | Check JST-PH 2-pin polarity before first power-on |
