# Algorithm Hunting — Stair Walker Step Detection Fix

**Date:** 2026-03-27
**Stage:** 2 (Python signal-level validation complete)
**Status:** Python patch validated. Awaiting human sign-off before C port.

---

## 1. Failure Mode Statement

The standard gait algorithm (`step_detector.c`) detects **0/100 steps** on the stair walker profile.
Signal amplitude is NOT the problem — `acc_filt` peaks at **7.44 m/s²** (above the 5.0 m/s² threshold).
**427 acc peaks fired and timed out** waiting for gyro confirmation.

This was confirmed by three independent methods:
- Renode firmware simulation (actual ELF on virtual nRF52840): **0/50 steps**
- Python signal-level standard pipeline (`run_standard_stairs.py`): **0/100 steps, 427 timeouts**
- Signal diagnostic plot (`docs/plots/stair_walker_signal_check.png`)

---

## 2. Root Cause — Dual-Confirmation Timing Mismatch

The step detector uses a dual-confirmation gate:

```
step valid = acc_filt exceeds threshold  AND  gyr_y sign flip within GYR_CONFIRM_MS (40ms)
```

### Biomechanical assumption (design basis)
Heel-strike simultaneously:
1. Drives a vertical deceleration impulse → `acc_filt` spike
2. Arrests plantar-flexion → `gyr_y` sign reversal (negative dorsiflexion → positive rebound)

On flat ground these two events are co-incident (~19ms separation), well within 40ms.

### How stairs breaks the assumption
Stair climbing uses a **forefoot/midfoot strike** (foot pre-dorsiflexed at contact):

| Event | Flat walker | Stair walker |
|---|---|---|
| `acc_filt` peak phase | 0.026 (15ms) | 0.164 (141ms) |
| `gyr_y` zero-crossing phase | 0.017 (10ms) | 0.017 (14ms) |
| Temporal gap | **19ms → PASS** | **126ms → TIMEOUT** |
| Verdict | Step confirmed | Step rejected |

The gyro crossing fires early (foot plants pre-dorsiflexed), then the acc_filt peak builds slowly (sigmoid loading from body weight). By the time acc_filt peaks, the gyro confirmation window has long expired.

---

## 3. Algorithm Hunting Procedure

### Step 1 — Signal observation

Generated `docs/plots/gyr_emd_terrain_comparison.png` showing all 4 walkers phase-normalised:

**Key observation (human):** *"The width of the signals in Panel 2 (HP-filtered gyr_y) are pretty consistent — this is a good sign."*

This confirmed that HP-filtering gyr_y removes terrain-specific posture drift while preserving the step-cycle oscillation morphology. The push-off burst (phase ~0.75) is present and consistently shaped across all terrains, including stairs.

### Step 2 — EMD framing

The signal has two separable modes:

```
raw gyr_y = IMF1 (step-cycle oscillation: dorsiflexion → push-off)
           + IMF2 (terrain posture drift: slow inter-step variation)
```

HP filter at 0.5 Hz approximates EMD extraction of IMF1. The push-off zero-crossing of IMF1 occurs at **consistent phase (~0.75) regardless of terrain**.

### Step 3 — Algorithm inversion hypothesis

**Old (acc-primary):**
```
acc_filt threshold → open 40ms window → wait for gyr_y zero-crossing
```

**New (gyr_y-primary):**
```
gyr_y_hp push-off event → verify acc_filt exceeded threshold since last step
```

Push-off is universal — no terrain allows walking without plantar-flexion. The confirmation window becomes the full step period rather than 40ms.

### Step 4 — Feature selection

Two candidate gyr_y features for push-off detection:

| Feature | Rebound (phase 0.10) | Push-off (phase 0.75) |
|---|---|---|
| Mechanism | Small positive rebound after initial dorsiflexion | Full plantar-flexion at stance end |
| Peak amplitude (stairs) | +14 dps (peak × 0.05) | +280 dps (peak × 1.0) |
| Ratio | 1× | **20×** |

**Zero-crossing approach rejected**: swing phase from previous step extends the "negative duration" to ~355ms for stairs, making duration-based gates terrain-coupled and unreliable.

**Push-off amplitude threshold chosen**: require `gyr_y_hp > GYR_PUSHOFF_THRESH_DPS (30 dps)` before the falling edge is counted. Physical grounding:
- Minimum push-off velocity: `100 + 65 × v_min = 106 dps` at v = 0.1 m/s
- Phase-0.10 rebound: 9–14 dps across all profiles → always below 30 dps → blocked
- Push-off burst: 185–280 dps across all profiles → always above 30 dps → detected

---

## 4. Python Validation Results

**File:** `simulator/terrain_aware_step_detector.py`
**Tests:** `simulator/tests/test_terrain_aware_detector.py` — **10/10 pass**

### Step count (target 100 ±5)

| Profile | Standard algo | Terrain-aware | Pass? |
|---|---|---|---|
| Flat | 100 | 100 | ✓ |
| Bad wear | 100 | 100 | ✓ |
| Slope (10°) | 100 | 100 | ✓ |
| **Stairs** | **0** | **100** | **✓ (was ✗)** |

### Symmetry Index — interval method (target < 3%)

| Profile | Standard SI | Terrain-aware SI | Pass? |
|---|---|---|---|
| Flat | 0.02% | 0.09% | ✓ |
| Bad wear | 0.02% | 0.09% | ✓ |
| Slope (10°) | 0.82% | 1.24% | ✓ |
| **Stairs** | **n/a** | **0.69%** | **✓ (was n/a)** |

**Note:** Terrain-aware SI is slightly higher than standard for flat/slope/bad_wear. Expected behaviour — push-off detection timestamps the end of stance rather than the start, introducing a small fixed offset between odd/even step timestamps. The offset is symmetric and consistent, so SI remains near 0%.

**Comparison plot:** `docs/plots/si_comparison_standard_vs_terrain.png`

---

## 5. Algorithm Change Summary

### Parameters changed

| Parameter | Old value | New value | Physical basis |
|---|---|---|---|
| Primary trigger | `acc_filt > threshold` | `gyr_y_hp > 30 dps` (push-off) | Push-off angular velocity floor |
| Confirmation | `gyr_y` sign flip within 40ms | `acc_filt > threshold` since last step | Acc exceeds threshold during any loading phase |
| Confirmation window | 40ms (fixed) | Full step period (terrain-agnostic) | Step period derived from cadence |
| `gyr_y` filter | Raw | HP-filtered at 0.5 Hz | EMD terrain component removal |

### What is preserved
- Same `acc_filt` filter chain (HP 0.5 Hz → LP 15 Hz adaptive)
- Same adaptive threshold (8-step peak history, seed 10 m/s²)
- Same minimum step interval (250ms / 240 spm max cadence)
- Same cadence tracking

### What changes
- Step timestamp is now at **push-off** (end of stance) rather than heel-strike (start of stance)
- This does not affect SI computation — SI uses inter-step intervals, which are measured push-off to push-off consistently

---

## 6. Fix Domains Considered and Rejected

| Domain | Considered | Outcome |
|---|---|---|
| Feature Extraction — drop gyro gate entirely | Rejected early | Loses false-positive rejection on non-locomotion vibration |
| Zero-crossing with duration gate | Attempted | Swing phase extends negative duration, makes gate terrain-coupled |
| Terrain Classification — widen gate conditionally | Not attempted | Requires classifier upstream; higher complexity |
| Hardware Change — shin IMU | Not attempted | BOM change; human selection required |
| **Push-off amplitude threshold (chosen)** | Implemented | Clean physical separator; 20× amplitude ratio; terrain-agnostic |

---

## 7. Critical Architectural Finding — Push-Off Detection Breaks Phase Segmenter Contract

**Discovered:** 2026-03-27 via `plot_swing_stance_comparison.py`
**Severity:** Blocks direct C port of `TerrainAwareStepDetector` into existing firmware without changes to `phase_segmenter.c`

### The Problem

The standard detector fires `on_heel_strike()` at the **start of stance** (acc_filt peak ≈ heel contact).
The terrain-aware detector fires at the **end of stance** (push-off burst falling edge).

`phase_segmenter.c` uses `on_heel_strike()` as its clock — it starts `PHASE_LOADING` at the callback timestamp and measures `stance_duration_ms` as the elapsed time until toe-off detection. If the callback fires at push-off instead of heel-strike, the phase segmenter computes the wrong interval:

```
Current contract:
  on_heel_strike(ts=T_hs) → PHASE_LOADING → ... → toe-off → stance = T_toeoff - T_hs

With push-off detection:
  on_heel_strike(ts=T_po[N]) → PHASE_LOADING → next push-off fires → stance = T_po[N+1] - T_po[N]
                                                                     = swing[N] + stance[N+1]
                                                                     ≈ full step period  ← WRONG
```

### Measured Impact

Numbers from `scripts/plot_swing_stance_comparison.py`:

| Profile | GT stance (ms) | GT swing (ms) | GT period (ms) | Computed "stance" if TA used | Error |
|---|---|---|---|---|---|
| Flat | 343 | 229 | 571 | 567 | +224ms (+65%) |
| Bad wear | 343 | 229 | 571 | 567 | +224ms (+65%) |
| Slope (10°) | 392 | 240 | 632 | 624 | +232ms (+59%) |
| Stairs | 557 | 300 | 857 | 852 | +295ms (+53%) |

**SI computation is unaffected** — SI uses inter-step intervals (push-off to push-off), which correctly equal the full step period regardless of which phase the detector fires at. All four profiles yield SI < 3%.

**Phase segmenter output is entirely wrong** — reported stance_duration_ms would be ~1.6–1.65× the actual stance duration for all profiles. Swing duration would be near-zero or negative.

### Step Period Accuracy (terrain-aware detector is faithful on timing)

The detector itself is accurate — detected step periods match ground truth within 5ms:

| Profile | GT period (ms) | TA detected period (ms) | Error |
|---|---|---|---|
| Flat | 571 | 567 | −4ms |
| Bad wear | 571 | 567 | −4ms |
| Slope (10°) | 632 | 624 | −8ms |
| Stairs | 857 | 852 | −5ms |

The period accuracy confirms the algorithm is detecting the right events — the issue is purely the **event contract mismatch** with `phase_segmenter.c`.

### Three Options for C Port (human must select one)

| Option | Description | Phase segmenter impact | Complexity |
|---|---|---|---|
| **A — Two-event architecture** | Add `push_off_t` event type alongside `heel_strike_t`. Step detector emits both: heel-strike detected from acc_filt peak (even if not gyro-confirmed), push-off detected from gyr_y_hp burst. Phase segmenter keeps `on_heel_strike()` contract unchanged. | None — contract preserved | Medium: new event type, dual emission |
| **B — SI-only mode for stair terrain** | Detect terrain type (low acc_z DC, slow cadence, high vertical_osc). On stair terrain: skip phase segmenter, report SI from step intervals only. On flat/slope/bad_wear: use existing standard detector unchanged. | None on non-stair. Phase seg disabled on stair. | Medium: terrain classifier needed |
| **C — Backward heel-strike inference** | After push-off fires, look back in a ring buffer for the most recent acc_filt timeout (rejected acc peak) and retroactively use its timestamp as the heel-strike event. Requires a small ring buffer of rejected peak timestamps. | Preserved — heel-strike timestamp is retroactively recovered | Low: 8-entry ring buffer, ~32 bytes RAM |

**Option C is the lowest-risk path.** The rejected acc peaks (427 of them for stairs) are already computed — we just don't store their timestamps. A small ring buffer would recover the heel-strike timing for the phase segmenter without changing the event contract or adding a terrain classifier.

### What Must NOT Be Done

Do not simply swap `step_detector.c` for `TerrainAwareStepDetector` and call `on_heel_strike()` at push-off time. This silently corrupts all phase segmenter output (stance/swing durations, foot angle at initial contact, cadence calculation) across all four terrains, not just stairs. The SI output would still look correct (because SI uses intervals), masking the corruption.

---

## 8. Procedure Enforced

Per CLAUDE.md learner-in-the-loop rules:

1. **Signal plot first** (`gyr_emd_terrain_comparison.png`) — human confirmed "consistent width in Panel 2" before any code was written
2. **Baseline confirmed independently** (`run_standard_stairs.py`) — 0 steps, 427 timeouts, before comparison plot
3. **Python implementation before C** — `TerrainAwareStepDetector` written and tested in Python
4. **Tests pass before comparison** — 10/10 unit tests green before generating comparison plot
5. **Comparison plot with verified baselines** — `si_comparison_standard_vs_terrain.png`

---

## 9. Next Steps (awaiting human sign-off)

- [ ] Human reviews `docs/plots/si_comparison_standard_vs_terrain.png`
- [ ] Human reviews `docs/plots/swing_stance_comparison.png`
- [ ] **Human selects C port option: A (two-event), B (SI-only mode), or C (backward inference)**
- [ ] Implement selected option in `src/gait/step_detector.c` (and `phase_segmenter.c` if Option A)
- [ ] Rebuild firmware ELF
- [ ] Run all 4 profiles through Renode (`test_all_profiles.py` + stairs at 100 steps)
- [ ] Confirm stairs ≥ 95/100 steps and SI < 3% in bare-metal simulation
- [ ] Confirm phase segmenter stance/swing durations within ±20ms of ground truth (all 4 profiles)
- [ ] Update `memory/bugs.md` — BUG-010 status: RESOLVED
- [ ] Commit and push

---

## 10. Files

| File | Role |
|---|---|
| `simulator/terrain_aware_step_detector.py` | Python reference implementation |
| `simulator/tests/test_terrain_aware_detector.py` | Stage 2 exit criteria tests |
| `scripts/run_standard_stairs.py` | Baseline verification (standard algo, stairs) |
| `scripts/plot_gyr_terrain_emd.py` | Signal-level EMD diagnostic plot |
| `scripts/plot_si_comparison.py` | Standard vs terrain-aware comparison plot |
| `docs/plots/gyr_emd_terrain_comparison.png` | Signal audit — all 4 walkers, HP-filtered gyr_y |
| `docs/plots/si_comparison_standard_vs_terrain.png` | SI comparison — human review checkpoint |
| `docs/plots/swing_stance_comparison.png` | Swing/stance architectural impact — phase segmenter contract |
| `docs/plots/stair_walker_signal_check.png` | Original failure mode diagnostic |
| `scripts/plot_swing_stance_comparison.py` | Generates swing/stance impact plot |
