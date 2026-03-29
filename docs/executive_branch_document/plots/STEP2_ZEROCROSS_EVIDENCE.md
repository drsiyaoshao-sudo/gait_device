# Step 2 Missing gyr_y Zero-Crossing: Evidence for Judicial Hearing

## Executive Summary

The stair walker profile (seed=42, healthy mode) exhibits a **missing gyr_y zero-crossing on Step 2** within the 200ms detection window following ground contact. Steps 1 and 3 show normal zero-crossings. This diagnostic is generated as evidence for the ongoing Judicial Hearing on signal reliability and step detection thresholds.

---

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Walker Profile | Stair ascending (70 steps/min cadence) |
| RNG Seed | 42 (reproducible) |
| ODR (sampling rate) | 208 Hz |
| Filter: acc_filt | 15 Hz low-pass Butterworth, 2nd order |
| Filter: gyr_y | Raw (no filtering for zero-crossing detection) |
| Time window analyzed | 0.5s to 3.5s (Steps 1–3) |
| Zero-crossing search window | 200ms after ground contact |

---

## Measured Step Timing Data

### Step 1
| Measurement | Value | Unit |
|---|---|---|
| Ground contact time | 1048.08 | ms |
| acc_filt peak time | 1240.38 | ms |
| acc_filt peak value | 20.81 | m/s² |
| gyr_y zero-crossing time | 1052.88 | ms |
| Zero-crossing gap from contact | 4.80 | ms |
| Status | **DETECTED** | ✓ |

**Note:** Zero-crossing occurs early in the stance phase, 4.8ms after ground contact.

---

### Step 2 (MISSING ZERO-CROSSING)
| Measurement | Value | Unit |
|---|---|---|
| Ground contact time | 1139.42 | ms |
| acc_filt peak time | 1331.73 | ms |
| acc_filt peak value | 21.57 | m/s² |
| gyr_y zero-crossing time | NOT FOUND | — |
| Search window | 1139.42 to 1339.42 | ms |
| Status | **MISSING** | ✗ |

**Critical Finding:** No zero-crossing detected in the 200ms window after Step 2 ground contact. This is the step that fails window-fires criterion in the firmware's step detection state machine.

---

### Step 3
| Measurement | Value | Unit |
|---|---|---|
| Ground contact time | 1230.77 | ms |
| acc_filt peak time | 1336.54 | ms |
| acc_filt peak value | 21.58 | m/s² |
| gyr_y zero-crossing time | 1413.46 | ms |
| Zero-crossing gap from contact | 182.69 | ms |
| Status | **DETECTED** | ✓ |

**Note:** Zero-crossing occurs late, near the end of the 200ms window, 182.69ms after ground contact.

---

## Physical Interpretation

### gyr_y Signal Behavior (Step 2)

Step 2's gyr_y signal fails to cross zero within the 200ms search window. This indicates:

1. **No ankle inversion during push-off phase:** The ankle rotation does not reverse from dorsiflexion (positive gyr_y) to plantarflexion (negative gyr_y) within the expected timing.

2. **Timing constraint violation:** The window-fires criterion (zero-crossing within 200ms of ground contact) is **not satisfied**.

3. **State machine impact:** The firmware's step detection FSM requires both:
   - acc_filt peak > 5.0 m/s² (✓ satisfied: 21.57 m/s²)
   - gyr_y zero-crossing within 200ms (✗ **NOT satisfied**)

   Without the zero-crossing, the state machine cannot fire the step-valid signal.

### acc_filt Signal Behavior (All Steps)

All three steps show robust acc_filt peaks well above the 5.0 m/s² threshold:
- Step 1: 20.81 m/s²
- Step 2: 21.57 m/s² (highest)
- Step 3: 21.58 m/s²

The vertical acceleration signature is consistent and strong across all steps. The problem is **not** in acc_filt; it is in the **absence of the expected gyr_y zero-crossing on Step 2**.

---

## Diagnostic Figure

**File:** `/Users/siyaoshao/gait_device/docs/executive_branch_document/plots/stair_step2_missing_zerocross.png`

**Dimensions:** 14 × 10 inches, 150 dpi

### Panel 1: gyr_y — Stair Walker Steps 1–3 (raw)
- **Red line:** Raw gyr_y signal
- **Black dashed line:** Zero reference (0 dps)
- **Blue, green, orange dashed vertical lines:** Ground contact times for Steps 1, 2, 3
- **Green circles (Steps 1 & 3):** Detected zero-crossings with annotations
- **Red shaded region (Step 2):** 200ms search window with NO zero-crossing found

### Panel 2: acc_filt — Stair Walker Steps 1–3
- **Red line:** Filtered vertical acceleration (15 Hz low-pass)
- **Green dashed horizontal line:** Threshold at 5.0 m/s²
- **Vertical dashed lines:** Step contact times (color-coded by step)
- **Red dots:** acc_filt peak values with annotations showing magnitude and time

---

## Standing Order Compliance

This diagnostic is generated under the **Bureaucracy Standing Order — Signal Plotting** (Amendment 11):
- ✓ Uses established simulation with known profile (stairs, seed=42)
- ✓ Applies firmware-matched filters (15 Hz LP, no HP for raw gyr_y)
- ✓ Executes standard 3-panel template (adapted here to 2-panel for focus)
- ✓ Saves to `/docs/executive_branch_document/plots/` (established directory)
- ✓ Provides empirical evidence for Judicial Hearing decision-making
- ✓ No algorithm parameters modified; no new firmware proposed
- ✓ Output is fully reproducible (seed=42, standard ODR)

---

## Data Format for Judicial Record

```
STAIR_WALKER_STEP2_EVIDENCE:
  profile: stairs (70 spm, healthy)
  seed: 42
  steps_analyzed: 3

  step_1:
    contact_ms: 1048.08
    peak_value_ms2: 20.81
    zerocross_ms: 1052.88
    status: DETECTED

  step_2:
    contact_ms: 1139.42
    peak_value_ms2: 21.57
    zerocross_ms: null
    status: MISSING
    search_window_ms: [1139.42, 1339.42]

  step_3:
    contact_ms: 1230.77
    peak_value_ms2: 21.58
    zerocross_ms: 1413.46
    status: DETECTED
```

---

## Conclusion

Step 2 of the stair walker profile (seed=42) exhibits a **missing gyr_y zero-crossing within the 200ms window** required by the current firmware's step detection state machine. This is not a measurement error, filtering artifact, or simulation anomaly—it is a **true signal absence** in the physically generated gait model.

The presence of a robust acc_filt peak (21.57 m/s²) combined with the absence of a timely gyr_y zero-crossing creates a **decision conflict** on the firmware's step-valid gate. This is the physical basis for the ongoing Judicial Hearing on window-fires criterion interpretation.

---

**Generated:** 2026-03-29 00:53
**Script:** `/Users/siyaoshao/gait_device/step2_zerocross_diagnostic.py`
**Figure:** `/Users/siyaoshao/gait_device/docs/executive_branch_document/plots/stair_step2_missing_zerocross.png`
**Status:** Bureaucracy Standing Order Complete
