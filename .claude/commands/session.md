Run a full GaitSense development session from toolchain lock through hardware clinical validation.

Usage: /session [stage]

Stages:
  status   — read constitutional record, print current stage and open gates
  0        — Stage 0: HIL Toolchain Lock  ← START HERE on any new session or new hardware
  1        — Stage 1: Firmware Simulation (Renode, 4 profiles)
  2        — Stage 2: Algorithm Firmware (Arduino, USB validation)
  3        — Stage 3: BLE Pipeline (wireless path, laptop console)
  4        — Stage 4: Clinical Hardware Validation (ankle strap, walk tests, SI)

If no stage given, run status first, then ask Justice which stage to begin.

---

## Design Principle — HIL First

**Hardware-in-the-loop must be the first gate, not the last.**

Every session begins with Stage 0 (HIL Toolchain Lock) before any simulation or algorithm
work begins. The reason: toolchain failures (wrong board variant, UF2 offset mismatch,
USB cable, BLE scan name truncation) take hours to debug when discovered at the end.
Discovered at the beginning, they take 10 minutes.

Stage 0 is cheap. Stage 0 failure discovered at Stage 3 is expensive.
Article II (irreversibility) does not apply to Stage 0 — counter flashing is trivially reversible.

---

## Session Initialisation (always runs first)

**Step 0a — Toolchain config check:**
Read `docs/toolchain_config.md` before anything else. If the file is missing or
lock status is not LOCKED: stop and print:
  "Toolchain config missing or unlocked. Run /toolchain init (new project) or
   /toolchain lock (Stage 0 complete) before starting a session."

Print the active toolchain summary from the config (hardware, FQBN, flash method, BLE receiver).
If any blocked toolchain appears in the config's active slot: stop and report the conflict
before proceeding.

**Step 0b — Package check:**
Invoke `package-manager` to verify required Python packages:
`bleak`, `pyserial`, `numpy`, `scipy`, `matplotlib`, and any packages in `requirements.txt`.
Do not proceed to constitutional record print until package-manager reports clean.

Print session header from constitutional record:

```
══════════════════════════════════════════════════════════════════
  GAITSENSE SESSION — $(date)
══════════════════════════════════════════════════════════════════
  Constitutional record:
    Amendments: [N] ratified  — most recent: [title]
    Case law:   [N] precedents recorded

  Stage status:
    Stage 0 — HIL Toolchain Lock:         [CLOSED / OPEN / NOT STARTED]
    Stage 1 — Firmware Simulation:        [CLOSED / OPEN / NOT STARTED]
    Stage 2 — Algorithm Firmware (USB):   [CLOSED / OPEN / NOT STARTED]
    Stage 3 — BLE Pipeline:               [CLOSED / OPEN / NOT STARTED]
    Stage 4 — Clinical Validation:        [CLOSED / OPEN / NOT STARTED]

  Active toolchain (Amendment 17):
    Firmware:  Arduino CLI — Seeeduino:nrf52:xiaonRF52840Sense
    Flash:     Sparse UF2 — double-tap RST → /Volumes/XIAO-SENSE/
    Serial:    screen /dev/tty.usbmodem* 115200  OR  pio device monitor
    BLE:       python3.11 scripts/ble_console.py  (bleak, NUS TX UUID)
    Blocked:   Zephyr + PlatformIO (Amendment 16, 2026-04-10)

  Agent roster:
    Judiciary:    judicial-clerk  attorney-A  attorney-B
    Simulation:   simulator-operator  plotter  uart-reader
    Bureaucracy:  package-manager  stage-compactor

  Skills:
    /session [stage]           — this orchestrator
    /hear "<name>" A vs B      — judicial hearing
    /plot-evidence <type>      — evidence collection
    /plot-profile <profile>    — signal diagnostic plot
══════════════════════════════════════════════════════════════════
```

---

## Stage 0 — HIL Toolchain Lock

**Purpose:** Prove the full flash → run → observe loop works before any algorithm work begins.
**Agents:** package-manager (already ran), uart-reader
**Estimated time:** 10–15 minutes per smoke test

This stage implements Amendment 16 (Smoke Test Order). All four tests must pass in sequence.
A failure at any step blocks further stages — do not skip ahead.

### Test 0.1 — USB Counter

**Flash:** `arduino/ble_counter_test/ble_counter_test.ino`

Build and flash:
```bash
arduino-cli compile --fqbn Seeeduino:nrf52:xiaonRF52840Sense arduino/ble_counter_test
# Build sparse UF2, double-tap RST, copy to /Volumes/XIAO-SENSE/
```

Monitor via uart-reader:
```bash
screen /dev/tty.usbmodem* 115200
```

Expected output (1 line/sec):
```
counter=1
counter=2
counter=3
```

**Pass criteria:**
- [ ] Counter increments without reset for ≥ 10 lines
- [ ] No garbage on serial line

**Failure modes:**
- Blank output: USB-C cable is charge-only; try another cable
- Garbage: baud rate mismatch or wrong board variant (must be Sense, not standard)
- Resets: SoftDevice not flashed; rebuild sparse UF2 including sd_bl.bin at 0x1000

[GATE 0.1] Pass → continue. Fail → diagnose before proceeding. Three failures → /hear before new approach.

---

### Test 0.2 — USB IMU

**Flash:** `arduino/imu_smoke_test/xiao_imu_test.ino`

Expected output (~10 lines/sec):
```
ax:0.12 ay:-0.04 az:9.81 gx:0.02 gy:-0.01 gz:0.00
```

**Pass criteria:**
- [ ] `az ≈ ±9.8 m/s²` when board flat (gravity on Z)
- [ ] `gx/gy/gz ≈ 0 dps` when still
- [ ] Values stream continuously; no freeze

**Failure modes:**
- `IMU FAILED` then halt: wrong XIAO variant (non-Sense), or P1.08 power pin not asserted
- Values all zero: I2C not responding at 0x6A; check board is Sense variant
- `az ≈ 1.0` (not 9.81): readFloatAccelX() returns g not m/s² — confirm firmware multiplies by 9.81f

[GATE 0.2] Pass → continue.

---

### Test 0.3 — USB Gait Algorithm

**Flash:** `arduino/gait_algo_test/gait_algo_test.ino`

Walk or swing the board. Expected per-step output:
```
STEP #1 stance=401ms swing=482ms cadence=75spm si=0.0%
STEP #2 stance=286ms swing=340ms cadence=92spm si=4.8%
```

**Pass criteria:**
- [ ] Steps detected within 5 swings of motion
- [ ] Cadence 60–130 spm (normal walking range)
- [ ] SI changes between steps (non-zero after step 2)
- [ ] No firmware resets

**Failure modes:**
- No steps detected: push-off `gyr_y` not exceeding 30 dps threshold; swing harder or check IMU axis orientation
- Cadence = 0 or 255: cadence overflow; check `step_detector_cadence_spm()` return type
- SI always 0.0%: BUG-013 present — verify `rolling_window.cpp` uses `(diff >= 0.0f) ? diff : -diff` not `fabsf()`

[GATE 0.3] Pass → continue.

---

### Test 0.4 — BLE Gait Algorithm

**Flash:** `arduino/ble_gait/ble_gait.ino`

On laptop:
```bash
python3.11 scripts/ble_console.py
```

Expected scan and connect:
```
Scanning for 'GaitS*'...
Found: GaitS [<address>]
Connecting...
Connected. Subscribing to NUS TX...
--- GaitSense output ---
```

Walk or swing. Expected output:
```
STEP#1 st=401 sw=482 cd=75 si=0.0%
STEP#2 st=286 sw=340 cd=92 si=4.8%
SNAP#9 si=2.1% sw=1.8% cd=88
```

**Pass criteria:**
- [ ] Device found within 15 s scan
- [ ] STEP# lines arrive within 5 swings of motion
- [ ] SNAP# lines appear after every 10 steps
- [ ] Line-buffered output — no truncated mid-line fragments

**Failure modes:**
- Not found in scan: board not advertising; check Serial output for "GaitS advertising" at boot
- Connected but no data: `bleuart.write()` is guarded by `Bluefruit.connected()` check — remove guard (write unconditionally)
- Truncated lines: format string > 48 chars exceeds BLE MTU; shorten format string
- `bleak` ImportError: `python3.11 -m pip install bleak` (system Python 3.9 does not have it)

[GATE 0.4] **Stage 0 CLOSED** — toolchain confirmed end-to-end.

**[JUSTICE GATE S0]** All four tests pass → invoke `stage-compactor` to close Stage 0.

---

## Stage 1 — Firmware Simulation

**Purpose:** Validate algorithm correctness on all 4 terrain profiles using the Renode bare-metal simulation.
**Agents:** simulator-operator → uart-reader → plotter
**Entry condition:** Stage 0 closed.

### Pipeline

```
For each profile in [flat, bad_wear, stairs, slope]:
    simulator-operator → uart-reader (UART log) → plotter (signal plot)
    → print: step count, SI_stance, SI_swing, cadence per profile

Pathological check (Amendment 15):
    simulator-operator (si_true=25%) → SI > 10% required on all 4 profiles
```

Invoke simulator-operator once per profile. Do not batch all four — run sequentially so
UART evidence is available for each before the next begins.

```bash
# Each profile
python scripts/test_flat_only.py
python scripts/test_stairs_100.py
python scripts/test_slope_100.py
# bad_wear profile uses flat with 20° mount offset

# Full 4-profile table
python scripts/test_all_profiles_full.py

# Pathological validation
python scripts/test_all_profiles_full.py --pathological
```

Signal plots (Amendment 11 — mandatory):
```bash
/plot-profile flat
/plot-profile stairs
/plot-profile bad_wear
/plot-profile slope
```

### Exit criteria
- [ ] All 4 healthy profiles: ≥ 98/100 steps, SI_stance < 10%
- [ ] Pathological: SI_stance > 10% on all 4 profiles
- [ ] All 4 signal plots reviewed by Justice (Amendment 11)
- [ ] No new bugs vs `docs/executive_branch_document/bug_receipt.md`

**[JUSTICE GATE S1]** Criteria met → invoke `stage-compactor` to close Stage 1.

---

## Stage 2 — Algorithm Firmware (Arduino USB)

**Purpose:** Run the same algorithm on real hardware over USB serial. Cross-validates that
the Arduino port produces results consistent with the Renode simulation.
**Entry condition:** Stage 1 closed.

### Pipeline

```
1. Build and flash arduino/ble_gait/ble_gait.ino (USB monitoring path)
   → pio device monitor or screen — capture STEP# and SNAP# lines

2. Walk 50 steps on flat ground
   → compare cadence, SI_stance against Renode Stage 1 prediction

3. Walk 50 steps with 10 mm heel lift (one foot)
   → SI_stance must increase ≥ 5% vs baseline (sensitivity test)
```

Tolerance for hardware vs Renode (Amendment 5):
- Cadence: within ±5 spm
- SI_stance: within ±6.3% of Renode prediction (derived from Amendment 15 statistical derivation)

### Exit criteria
- [ ] Step count ≥ 98/100 on flat ground
- [ ] Cadence within ±5 spm of expected
- [ ] SI_stance < 5% on symmetric walking
- [ ] SI_stance increases ≥ 5% with 10 mm heel lift
- [ ] No firmware resets in ≥ 10 min continuous session

**[JUSTICE GATE S2]** Criteria met → invoke `stage-compactor` to close Stage 2.

---

## Stage 3 — BLE Pipeline

**Purpose:** Validate wireless path — same data as Stage 2, received on laptop over BLE NUS.
Confirms MTU, fragmentation handling, and line-buffer integrity under real walking conditions.
**Entry condition:** Stage 2 closed.

### Pipeline

```
1. Confirm ble_console.py connects and streams clean STEP#/SNAP# lines
   → repeat Stage 2 walk tests, this time reading from BLE not USB

2. BLE stress test:
   - Walk 200 steps continuous
   - Count STEP# lines received vs expected
   - Packet loss = (expected - received) / expected × 100%
   - Target: < 2% packet loss at ≤ 5 m range
```

```bash
python3.11 scripts/ble_console.py | tee /tmp/ble_session_$(date +%Y%m%d_%H%M%S).log
```

### Exit criteria
- [ ] 200-step session: packet loss < 2%
- [ ] SNAP# lines arrive every 10 steps with no gaps
- [ ] SI matches USB path within ±1% (same physical motion, different transport)
- [ ] No spontaneous BLE disconnects in ≥ 5 min session

**[JUSTICE GATE S3]** Criteria met → invoke `stage-compactor` to close Stage 3.

---

## Stage 4 — Clinical Hardware Validation

**Purpose:** Validate clinical measurement accuracy. Real human, real ankle, real walking.
This is the Article II irreversibility gate for clinical decisions.
**Entry condition:** Stages 0–3 all closed.

### Pre-flight (Article II)

Before any clinical data collection:
- Justice reviews Stage 3 BLE evidence
- Justice confirms hardware is ready for ankle mounting
- **JUSTICE APPROVES CLINICAL VALIDATION** — this is a hard gate, no agent self-selects

### Assembly checklist
- [ ] Enclosure is rigid TPU Shore A ≥ 90 (no soft silicone — attenuates heel-strike signal)
- [ ] Mounted over lateral malleolus — USB-C port faces posterior (toward heel)
- [ ] Strap is tight, no rotation under simulated vibration
- [ ] BLE chip antenna faces laterally (away from body)

### Calibration
Subject stands still 2 s after mounting. Firmware runs 400-sample calibration window.
Do not walk during this window.

### Walk protocol

**Run 1 — Baseline symmetric**
- Flat ground, comfortable walking pace, ≥ 100 steps
- Expected: SI_stance < 5%, cadence 85–110 spm

**Run 2 — Heel lift sensitivity**
- Flat ground, 10 mm lift under one heel, ≥ 100 steps
- Expected: SI_stance increases ≥ 5% vs Run 1

**Run 3 — Cadence range**
- Flat ground, slow walk then fast walk in same session
- Expected: cadence tracks actual pace, smooth convergence (no step loss)

**Run 4 — BLE range**
- Walk up to 10 m from laptop
- Expected: < 2% packet loss at 10 m (open space)

### Results table (fill in during validation)

| Run | Steps | SI_stance% | SI_swing% | Cadence spm | Pass? |
|-----|-------|-----------|----------|------------|-------|
| 1 — Baseline | | | | | |
| 2 — Heel lift | | | | | |
| 3 — Cadence range | | | | | |
| 4 — BLE range | | | | | |

### Deviations
Any result outside tolerance → cross-reference `docs/executive_branch_document/bug_receipt.md` first.
Unexplained deviation → `/hear` before any firmware change.

### Exit criteria
- [ ] Run 1: SI_stance < 5%, cadence 85–110 spm
- [ ] Run 2: SI_stance increases ≥ 5% vs Run 1
- [ ] Run 3: cadence tracks pace with no step loss
- [ ] Run 4: BLE range ≥ 10 m, < 2% packet loss
- [ ] All deviations explained and recorded in case_law.md

**[JUSTICE GATE S4 — FINAL]** Criteria met → invoke `stage-compactor` to close Stage 4.
Constitutional method validated end-to-end on physical hardware.

---

## Full Pipeline Map

```
  /session
      │
      ├── [SESSION INIT] package-manager · constitutional record · stage status
      │
      ├── Stage 0 ── HIL Toolchain Lock  ← FIRST — before any algorithm work
      │               counter → IMU → algo (USB) → algo (BLE)
      │               uart-reader × 4 smoke tests
      │               [GATE S0] → stage-compactor
      │               ↑ If this fails, nothing else is valid
      │
      ├── Stage 1 ── Firmware Simulation
      │               simulator-operator × 4 profiles (sequential)
      │               uart-reader · plotter
      │               /plot-profile × 4 (Amendment 11)
      │               [GATE S1] → stage-compactor
      │
      ├── Stage 2 ── Algorithm Firmware (USB)
      │               flash ble_gait.ino · uart-reader
      │               50-step flat · 50-step heel lift
      │               [GATE S2] → stage-compactor
      │
      ├── Stage 3 ── BLE Pipeline
      │               ble_console.py · 200-step stress test
      │               packet loss < 2%
      │               [GATE S3] → stage-compactor
      │
      └── Stage 4 ── Clinical Hardware Validation
                      [JUSTICE APPROVES — Article II]
                      ankle mount · 4 walk runs · results table
                      deviations → /hear before any fix
                      [GATE S4 FINAL] → stage-compactor
```

---

## Constitutional References

- Article I: all signal thresholds trace to physical primitives (gyr_y > 30 dps = push-off, not a guess)
- Article II: no clinical decision without Justice approval; hardware flash is the irreversibility gate
- Amendment 1: five-stage development order (Stage 0 added by Amendment 16 practice)
- Amendment 5: simulation is the hardware proxy — Stage 2 deviations from Stage 1 are hardware problems, not firmware problems
- Amendment 6: flash irreversibility — Stage 0 smoke tests bypass this (counter is trivially reversible)
- Amendment 7: three-strike escalation — three failures at any gate → /hear before new approach
- Amendment 11: signal plots mandatory after any walker_model or algorithm change
- Amendment 16: smoke test order (counter → sensor → algo USB → algo BLE) — Stage 0 encodes this
- Amendment 17: toolchain alignment — Arduino CLI + sparse UF2 is active; Zephyr is blocked

Now parse "$ARGUMENTS":
  If a stage number (0–4) or keyword (status) is given, run that stage only.
  If no argument: run session initialisation, print stage status, ask Justice which stage to begin.
