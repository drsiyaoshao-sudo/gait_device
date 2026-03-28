# GaitSense — Hardware Handoff Document

**Prepared by:** Simulation & Firmware Team
**Date:** 2026-03-27
**Branch:** ble-export-sim → handoff-testing
**Target recipient:** Engineer with medium-level embedded knowledge (nRF52840 / Zephyr familiarity assumed; gait algorithm internals documented here)

---

## Purpose

This document is the single-source handoff package for physical bring-up of the GaitSense ankle wearable. Everything in it traces back to simulation that was run before this document was written. You are not debugging an algorithm — you are verifying that physical hardware matches a simulation that has already been validated on a virtual Cortex-M4F running the exact same ELF binary you will flash.

If physical results deviate significantly from the simulation predictions in this document, that is a hardware or mounting problem, not a firmware problem.

---

## 1. Algorithm Overview — What the Firmware Does

### 1.1 What Is Being Measured

**Symmetry Index (SI)** — the percentage difference between left and right leg timing:

```
SI = 200 × |M_odd - M_even| / (M_odd + M_even)   [%]
```

`M_odd` = mean stance (or swing) duration for odd-numbered steps (one foot).
`M_even` = mean for even steps (other foot).

SI = 0% → perfectly symmetric. SI > 5% is clinically significant. A single ankle placement alternates odd/even steps between legs.

### 1.2 Signal Pipeline

```
IMU @ 208 Hz  (acc_x, acc_y, acc_z, gyr_x, gyr_y, gyr_z)
    │
    ▼  step_detector.c         Finds each heel strike timestamp
    │  → heel_strike_t: {ts_ms, step_index, peak_acc_mag, peak_gyr_y}
    │
    ▼  phase_segmenter.c       Tracks LOADING→MID_STANCE→TERMINAL→TOE_OFF→SWING
    │  → step_record_t: {stance_ms, swing_ms, cadence_spm, foot_angle}
    │
    ▼  rolling_window.c        200-step circular buffer, snapshot every 10 steps
    │  → rolling_snapshot_t: {si_stance_x10, si_swing_x10, mean_cadence_x10, ...}
    │
    ▼  snapshot_buffer.c       5500 × 18-byte RAM ring buffer
    │
    ▼  ble_gait_svc.c          GATT export on CTRL_EXPORT command
```

### 1.3 Step Detector: Push-Off Primary with Retrospective Heel-Strike Inference

This is the most important algorithm decision. It was redesigned after simulation discovered a complete failure on stair terrain (0/100 steps detected with the original design).

**Why the original design failed on stairs:**

The original detector used a dual-confirmation gate:
1. `acc_filt` (filtered acceleration magnitude) > adaptive threshold → heel-strike candidate
2. Within 40 ms: `gyr_y` crosses zero → step confirmed

On flat ground this works because heel contact simultaneously creates an acceleration impulse AND arrests plantar-flexion — both events within 5–15 ms.

On stairs, the foot contacts at forefoot/midfoot. Weight transfers slowly: `acc_filt` peaks at 188 ms into stance. The `gyr_y` zero-crossing happens at 53 ms (forefoot contact). The 135 ms gap exceeds the 40 ms window. Every step is rejected — 0/100 steps.

```
FLAT GROUND                           STAIRS

 acc_filt                              acc_filt
    │ ▄▄▄                                │              ▄▄
    │▄   ▄                               │          ▄▄▄▄
    │     ▄▄                             │       ▄▄▄
────┼──────────► t                  ─────┼───────────────► t
    0  5ms peak                          0  53ms  188ms peak
                                                  ↑ peak at 188ms
 gyr_y zero-cross at ~5ms                gyr_y zero-cross at 53ms
 → gap ≈ 5ms  << 40ms window             → gap ≈ 135ms >> 40ms window
 → CONFIRMED                             → REJECTED ← original bug
```

**The physical principle that fixes it:**

Push-off (plantar-flexion) is biomechanically universal. Every terrain — flat, slope, stairs — requires lifting the foot off the ground. Push-off always produces a strong `gyr_y` burst. The minimum push-off burst at slow walking is ~100 dps. The early-stance rebound artifact peaks at only 9–14 dps — well below the 30 dps detection threshold, so it cannot cause false triggers.

**How the current step detector works:**

```
Each 208 Hz sample:

STEP 1 — FILTER CHAIN (unchanged from original design)
  acc_mag = √(ax² + ay² + az²)
  acc_filt = LP(15 Hz) ← HP(0.5 Hz) ← acc_mag     impact energy, DC-removed
  gyr_hp  = HP(0.5 Hz) ← gyr_y                     push-off burst, posture DC removed

STEP 2 — CONFIRMATION ACCUMULATOR (resets each stance)
  If acc_filt > adaptive_threshold:
      Set acc_above = true                            ← impact occurred this stance
      If this is the first below→above crossing:
          Push timestamp into 8-entry ring buffer     ← heel-strike candidate recorded

STEP 3 — PUSH-OFF DETECTION
  If gyr_hp > 30 dps: in_pushoff = true
  If in_pushoff AND gyr_hp falls back below 30 dps:
      → This is the falling edge of push-off — end of stance

STEP 4 — STEP CONFIRMATION (at push-off falling edge)
  Require ALL of:
      acc_above == true                               ← impact confirmed during this stance
      elapsed >= 250 ms since last step               ← refractory period (no double-counts)

STEP 5 — RETROSPECTIVE HEEL-STRIKE INFERENCE
  Find the oldest ring-buffer entry with timestamp > last_confirmed_step_ts.
  That is the first acc_filt threshold crossing since the previous push-off.
  This is the physical heel/forefoot contact moment.
  Report this as the heel_strike_ts_ms to phase_segmenter.

  Why look back? Push-off fires at the END of stance.
  Stance duration = push-off_ts − heel_strike_ts requires the START of stance.
  The 8-entry ring buffer (~32 bytes RAM) holds up to 8 contact candidates per stance.
  On all terrains, the correct candidate is always the oldest crossing since the last step.

STEP 6 — CLEANUP
  Clear ring buffer. Update adaptive threshold with this step's acc_filt peak.
  Update cadence from 4-step rolling interval average.
```

**Key thresholds (all derived from physical measurements):**

| Constant | Value | Physical derivation |
|---|---|---|
| `GYR_PUSHOFF_THRESH_DPS` | 30 dps | Minimum push-off ≈ 100 dps at v=0.1 m/s. Rebound artifact 9–14 dps. 30 dps gives 3× margin above artifact. |
| `MIN_STEP_INTERVAL_MS` | 250 ms | 250 ms = 240 spm (maximum sprint). Refractory period prevents double-counts. |
| `HS_RING_SIZE` | 8 | 8 crossings × 4 bytes = 32 bytes RAM. More than enough for one stance period. |
| Adaptive threshold | 50% of mean(last 8 peaks) | Self-calibrating to terrain and body weight. |

**Stance timing accuracy vs. true contact:**
- Flat: inferred timestamp −18 ms from true contact (acc_filt crossing slightly precedes peak)
- Stairs: −35 ms
Both are systematic offsets that cancel when computing SI from odd/even pairs. SI accuracy is unaffected.

### 1.4 Phase Segmenter: Gait Phase FSM

Transitions through 6 phases per step. Key gates:

**LOADING → MID_STANCE** (terrain-agnostic, post-BUG-002 fix):
```
acc_z_lp > 0.85 × 9.81   AND   |gyr_y| < 20 dps
```
The 20 dps threshold bisects heel-strike arrest (37–60 dps peak) and early ankle rocker (10–13 dps). Original gate used `|acc_mag − 9.81| < 2.94` which failed for stairs where `acc_mag ≈ 20 m/s²` at mid-stance.

**MID_STANCE → TERMINAL:**
```
acc_z_lp falling (derivative < 0)   AND   gyr_y < −10 dps   for ≥ 5 ms
```

**TERMINAL → TOE_OFF:**
```
|gyr_y| > adaptive_pushoff_threshold   OR   acc_z_lp < 2.94 m/s²
```
Push-off threshold adapts from the last 4 toe-off events (handles terrain changes).

### 1.5 Rolling Window: CNN Prior Seeding

**The cold-start problem:** At session start, the ring buffer for heel-strike inference retains residual acc_filt peaks from the static calibration period. Step 0 gets a heel-strike timestamp ≈ 4.8 ms (essentially t=0), making its stance ≈ 1534 ms — 3× normal. This corrupts the first 10-step snapshot.

**Fix:** `rolling_window_init()` pre-fills the buffer with 9 synthetic flat-walk records (analogous to CNN same-padding):
```
stance   = 343 ms   (60% of 571 ms step period at 105 spm)
swing    = 229 ms   (40%)
cadence  = 105 spm
flags    = valid
```
First real snapshot = 9 synthetic priors + 10 real steps. Synthetic records are identical for odd/even → contribute 0% SI. Evicted naturally as real steps fill the 200-entry buffer (gone after 200 real steps).

Effect: snapshot 0 SI_stance = 0.0% instead of 200%. Cadence converges from 105 spm toward real cadence over 3–4 snapshots (visible in the stairs profile below).

---

## 2. Simulation Validation Results

All results from branch `ble-export-sim`, Renode bare-metal Cortex-M4F, 2026-03-27. The ELF used here is the same binary to be flashed.

### 2.1 Four-Profile Full Pipeline

| Profile | Steps | SI_stance | SI_swing | Final cadence | BLE export | Verdict |
|---|---|---|---|---|---|---|
| Flat walk | 100/100 | 0.0% | 0.0% | 104 spm (target 105) | 9/9 ✓ | PASS |
| Bad wear (20° mount offset) | 100/100 | 0.0% | 0.0% | 104 spm | 9/9 ✓ | PASS |
| Slope 10° | 100/100 | 0.0% | 0.0% | 95 spm (target 95) | 9/9 ✓ | PASS |
| Stairs | 100/100 | 0.0% | 0.0% | 72 spm (target 70) | 9/9 ✓ | PASS |

Stairs snapshot table — cadence convergence from CNN prior:

| Snapshot | Step | SI_stance | SI_swing | Cadence spm |
|---|---|---|---|---|
| 0 | 9 | 0.0% | 0.0% | 89 ← prior seeding effect |
| 1 | 19 | 0.0% | 0.0% | 82 |
| 2 | 29 | 0.0% | 0.0% | 79 |
| 3 | 39 | 0.0% | 0.0% | 77 |
| 4 | 49 | 0.0% | 0.0% | 76 |
| 5 | 59 | 0.0% | 0.0% | 74 |
| 6 | 69 | 0.0% | 0.0% | 74 |
| 7 | 79 | 0.0% | 0.0% | 73 |
| 8 | 89 | 0.0% | 0.0% | 72 ← converged |

### 2.2 Power Budget

| Parameter | Simulated | Stage 5 target |
|---|---|---|
| Flash | 26.8 KB / 1 MB | — |
| SRAM | 115.8 KB / 256 KB | — |
| Active current | ≈ 1.1 mA | ≤ 1.5 mA |
| Sleep current | ≈ 5 µA | ≤ 5 µA |
| FIFO idle interval | 153.85 ms (32 ÷ 208 Hz) | ≈ 154 ms |
| Average (100 mAh cell) | 12.1 µA → 344 days | — |

---

## 3. Hardware Required

### 3.1 Minimum Kit

| Item | Part | Notes |
|---|---|---|
| MCU + IMU | Seeed XIAO nRF52840 Sense (102010448) | Must be **Sense** — on-board LSM6DS3TR-C |
| LiPo | 402030 3.7V 150 mAh, JST-PH 2.0mm | 100 mAh minimum |
| Perfboard | 30×40 mm FR4, 2.54mm pitch | |
| Tactile button | 6×6mm through-hole (Omron B3F-4055) | |
| LED (green) + 330Ω resistor | 3mm through-hole | External LED — see Section 4.1 note |
| 4.7kΩ resistor | 1/4W | Button pull-up if not using internal pull-up |
| Ankle strap | 25mm neoprene, Velcro | |
| USB-C cable | Data-capable | |

Full BOM: `docs/hw_bom.md`.

---

## 4. Perfboard Assembly

### 4.1 Pin Assignment Note — Read Before Soldering

The firmware's device tree overlay (`boards/xiao_ble_sense.overlay`) currently targets the **nRF52840 DK BSP** (board `nrf52840dk_nrf52840`), not a custom XIAO overlay. This means:

- **LED → P0.13**: On the nRF52840 DK this is the on-board LED1 pad. On XIAO nRF52840 Sense, P0.13 is the RED channel of the built-in RGB LED — **no external LED pad needed for initial bring-up**. The RGB LED (active-low) will serve as the status indicator on the XIAO itself.

- **Button → P0.27**: On the nRF52840 DK this is Button 0. P0.27 is not directly exposed as a labelled pad on the XIAO Sense (it is used internally for SWD CLK during programming). For standalone XIAO assembly, the device tree overlay must be updated to remap the button to an exposed pad (e.g. D0 = P0.02).

**For initial bench bring-up**, use the nRF52840 DK board — both LED and button are on the DK PCB, no perfboard needed.

**For standalone XIAO assembly**, update the overlay then solder per the diagram below.

### 4.2 Perfboard Circuit Diagram (Standalone XIAO Assembly)

After updating the overlay to use exposed XIAO pads (example: button → D0/P0.02, LED → D1/P0.03):

```
                        XIAO nRF52840 Sense
                       (top view, USB-C at top)

                        USB-C connector
                    ┌───────────────────┐
                    │  ○  RGB LED  ○    │  ← built-in, do not wire
   D0  (P0.02) ─ ──┤1               14├── VIN  (5V from USB)
   D1  (P0.03) ─ ──┤2               13├── GND  ──────────────────┐
   D2  (P0.28) ─ ──┤3               12├── 3V3  ─────────┐        │
   D3  (P0.29) ─ ──┤4               11├── D10 (P1.15)   │        │
   D4/SDA(P0.05)──┤5               10├── D9  (P1.14)   │        │
   D5/SCL(P0.04)──┤6                9├── D8  (P1.13)   │        │
   D6/TX (P1.11)──┤7                8├── D7/RX(P1.12)  │        │
                    └───────────────────┘                │        │
                            │                            │        │
                     JST-PH 2.0mm (on PCB underside)     │        │
                     ┌────────────┐                      │        │
                     │  +  BAT -  │                      │        │
                     └──┬──────┘                        │        │
                        │  LiPo 150mAh                   │        │
                        └────────────────────────────────│────────┘
                                                         │
                                         ┌───────────────┘
                                         │  3V3 rail
     BUTTON CIRCUIT (example: D0/P0.02)  │
     ─────────────────────────────────   │
                                         │
     3V3 ─────┬───── 4.7kΩ ─────────────┤
              │                          │   ← pull-up keeps D0 HIGH when open
              │                       D0 (P0.02) ← to XIAO pad 1
              │
       ┌──────┘
       │  Tactile button (6×6mm through-hole)
       │  (short-circuits D0 to GND on press → active-low trigger)
       │
      GND

     LED CIRCUIT (example: D1/P0.03)
     ────────────────────────────────
     If overlay uses active-HIGH (GPIO_ACTIVE_HIGH on D1):

                      D1 (P0.03) ── 330Ω ──┬── LED anode (+)
                                            └── LED cathode (−) ── GND

     If overlay uses active-LOW (GPIO_ACTIVE_LOW on D1):

                      3V3 ── 330Ω ──┬── LED anode (+)
                                    └── LED cathode (−) ── D1 (P0.03)
                                    (pin sinks current when driven LOW = LED on)
```

### 4.3 Perfboard Layout (Suggested)

```
  ┌──────────────────────────────────────────────────┐
  │  30×40 mm FR4 perfboard (2.54mm grid)            │
  │                                                  │
  │   ┌─────────────────────┐                        │
  │   │  XIAO nRF52840 Sense│   Solder directly      │
  │   │  (castellated pads) │   or use 2-row header   │
  │   └─────────────────────┘                        │
  │                                                  │
  │  [BTN]   [4.7k]   [LED] [330R]                   │
  │                                                  │
  │  JST-PH ──── to XIAO BAT pads (underside)        │
  └──────────────────────────────────────────────────┘
```

### 4.4 Soldering Notes

- Apply Loctite Flex 401 bead along all 4 XIAO castellated pad rows before first power-on. Walking produces repeated 5–6g shock.
- Solder joints on the button and LED should have strain-relief loops (1 mm drip loop in wire before pad) — vibration fatigues straight-wire joints.
- After assembly but before conformal coat: verify all connections with multimeter in continuity mode.
- Conformal coat (MG Chemicals 422B): apply to all exposed solder joints. Avoid USB-C port and JST connector.

---

## 5. Device Mounting

**Position:** Over the lateral malleolus (outer ankle bone).

**Coordinate frame:**
```
                         ↑ Z (away from body / dorsal)
                         │
  Posterior (heel) ←─── ─┼─ ───→ Anterior (toe direction)
                         │
                XIAO USB-C port faces POSTERIOR (toward heel)
```

**Rules:**
- Enclosure must be rigid TPU Shore A ≥ 90. Soft silicone attenuates the 5–6g heel-strike signal below the adaptive threshold — step detector will fail.
- Minimize air gap between enclosure and ankle skin. Every mm is a mechanical low-pass filter on the heel-strike transient.
- Strap must not rotate under vibration. Velcro saddle insert required.
- BLE chip antenna faces laterally (away from body) for range.

**Calibration:** subject stands still on flat ground for 2 s after mounting. Firmware runs a 400-sample calibration window at startup — do not walk during this window.

---

## 6. Bench Bring-Up Sequence

Work through in order.

### Step 1 — Continuity Check (unpowered)

- [ ] Button: continuity GND↔GPIO when pressed, open when released
- [ ] LED + resistor: correct polarity, no short to adjacent pads
- [ ] Battery JST-PH: red = positive, matches XIAO marking

### Step 2 — First Power-On (DK or XIAO)

Connect J-Link. Open RTT viewer:
```bash
JLinkRTTViewer --device nRF52840_xxAA --RTTChannel 0
```

Expected boot log:
```
<inf> calibration: No stored calibration — running calibration now
<inf> calibration: Calibration complete
```

**No RTT output:** ELF not flashed. Re-flash and verify with `nrfjprog --readback`.

### Step 3 — IMU Verification

After 2 s stationary, calibration output should show:
- `acc_z bias ≈ 0.0 m/s²` (gravity subtracted)
- `gyro bias < 10 mdps` all axes

**If calibration does not appear:** On XIAO Sense, the LSM6DS3TR-C is soldered on-board at I2C address 0x6A — no external wiring needed. Failure here means wrong XIAO variant (non-Sense) or I2C overlay mismatch.

### Step 4 — FIFO Interval Verification

In RTT log, inter-batch timestamps:
```
<inf> imu_reader: batch ts=XXXXms  n=32
<inf> imu_reader: batch ts=XXXXms  n=32
```

**Expected:** 153–155 ms between batches.
**Pass criterion:** within ±5 ms of 154 ms, consistent, no missed batches.

### Step 5 — Session Lifecycle

1. Stand still 2 s (calibration)
2. Short button press → LED blinks fast (250 ms period) = recording
3. Walk 50 steps
4. Long button press ≥ 2 s → LED slow blink (1 s) = session complete

Connect nRF Connect app, scan for `GaitSense`. Subscribe to GATT-0002, write `0x0003` to GATT-0003. Expected: 4–5 snapshot notifications for 50 steps.

---

## 7. Stage 5 Validation Checklist

Record actual results here.

### 7.1 Step Count Accuracy

Walk exactly 100 steps on flat ground. Verify `total_steps` from BLE export.

| Run | Steps walked | total_steps reported | Pass (≥ 98)? |
|---|---|---|---|
| 1 | 100 | | |
| 2 | 100 | | |

Simulation prediction: 100/100.

### 7.2 Symmetry Index — Baseline

Natural walking, flat, 100+ steps.

| Run | SI_stance% | SI_swing% | Pass (< 5%)? |
|---|---|---|---|
| 1 | | | |
| 2 | | | |

Simulation predicts < 0.1% (synthetic symmetric signal). Real hardware expect 1–4% (natural variability).

### 7.3 Symmetry Index — 10 mm Lift Sensitivity Test

Insert 10 mm lift under one heel. Walk 100+ steps.

| Condition | SI_stance% | SI_swing% |
|---|---|---|
| No lift (baseline) | | |
| 10 mm lift (right heel) | | |

Expected: SI_stance increases 8–15% with lift. No change = mounting or calibration problem.

### 7.4 Power (PPK2 Required)

| State | Measured | Target | Pass? |
|---|---|---|---|
| Deep sleep (no session) | | ≤ 5 µA | |
| Active session (walking avg) | | ≤ 1.5 mA | |

Measure active current over ≥ 30 s of walking, averaged.

### 7.5 BLE Export Integrity

Walk 200+ steps. Export:
```bash
python host_tool/download_session.py --output session.csv
```

| Metric | Result | Pass? |
|---|---|---|
| Snapshot count (≈ steps ÷ 10) | | |
| Packet loss / CRC errors | | None = pass |

### 7.6 Durability — 10-Minute Run

| Check | Result |
|---|---|
| No false session stop (button vibration trigger) | |
| `mounting_suspect` flag not set in any snapshot | |
| No firmware reset in RTT log | |
| Strap did not rotate | |

---

## 8. Expected Deviations from Simulation

| Observation | Why | Accept if |
|---|---|---|
| Snapshots 0–2 show cadence above actual | CNN prior seeding at 105 spm | Converges by snapshot 3–4 |
| SI_stance 1–4% on symmetric walking | Real gait has natural variability | < 5% |
| Cadence 1–3 spm below treadmill display | Treadmill counts strides; firmware counts individual heel strikes | < 5 spm difference |
| Active current slightly above 1.1 mA | BLE advertising not in simulation power model | ≤ 1.5 mA |
| FIFO interval ±2 ms jitter | Real crystal PPM tolerance | ≤ ±5 ms |

---

## 9. Failure Escalation

**Step count < 98/100:**
1. Is the enclosure rigid and tight against the ankle? Soft mounting attenuates heel-strike below the adaptive threshold.
2. Are push-off bursts above 30 dps? Collect RTT STEP log, check `gyr_y` column.
3. If `gyr_y` consistently < 30 dps (very slow walking or soft surface): lower `GYR_PUSHOFF_THRESH_DPS` in `step_detector.c` and re-simulate.

**SI > 5% on symmetric walking:**
1. Check `mounting_suspect` flag — if set, device rotated past 15° at mid-stance. Re-mount with tighter strap.
2. Run 10 mm lift test. If SI does not respond to the lift, calibration or mounting is the issue.
3. If SI does respond to the lift but baseline SI is high: gait asymmetry is real; not a firmware issue.

**Sleep current > 10 µA:**
1. Confirm production ELF was flashed (not sim ELF — `CONFIG_GAIT_RENODE_SIM=y` disables power management).
2. Verify BLE advertising stops after timeout — device should not advertise indefinitely.
3. Provide PPK2 waveform trace for escalation.

**BLE drops packets:**
1. Move within 2 m. Antenna faces laterally.
2. Current GATT payload: 10 snapshots × 18 bytes + 4-byte header = 184 bytes — fits MTU 247. If MTU negotiation failed, check `bt_gatt_notify` return codes in RTT.

---

## 10. Simulation Re-Run Reference

```bash
# Full 4-profile validation with snapshot tables
python scripts/test_all_profiles_full.py

# BLE binary export path
python scripts/test_ble_export.py

# Individual profiles
python scripts/test_flat_only.py
python scripts/test_slope_100.py
python scripts/test_stairs_100.py
```

Requires Renode 1.16.1 on PATH and built ELF at `.pio/build/xiaoble_sense_sim/zephyr/zephyr.elf`.

---

## 11. File Reference

| File | Contents |
|---|---|
| `docs/hw_bom.md` | Full BOM — part numbers, suppliers, prices |
| `docs/sw_bom.md` | Software dependencies and versions |
| `memory/bugs.md` | All 12 simulation bugs — root cause, fix, verified result |
| `docs/algorithm_hunting_stair_walker.md` | Stair failure mode investigation with signal plots |
| `src/gait/step_detector.c` | Push-off primary step detector with ring-buffer heel-strike inference |
| `src/gait/phase_segmenter.c` | Gait phase FSM — terrain-agnostic MID_STANCE gate |
| `src/gait/rolling_window.c` | 200-step rolling window + CNN prior seeding |
| `src/ble/ble_gait_svc.c` | BLE GATT service — snapshot export |
| `host_tool/download_session.py` | BLE host download tool |
| `scripts/test_all_profiles_full.py` | Single-command full pipeline verification |
| `boards/xiao_ble_sense.overlay` | Device tree — **update GPIO pins before standalone XIAO assembly** |
