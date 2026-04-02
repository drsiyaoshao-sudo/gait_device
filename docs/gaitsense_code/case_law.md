# GaitSense Case Law

All rulings are binding on future agents and humans per the Judicial Process in CLAUDE.md. To deviate from a precedent, a new hearing must be declared — unilateral deviation is not permitted.

*Format for each case:*
```
### [CASE NAME] — [DATE]
Competing Positions: A (Amendment N) vs B (Amendment M)
Physical/Empirical Basis: [the measurement or signal that decided the case]
Ruling: [which position prevailed and the condition under which it applies]
Precedent Effect: [future situations this ruling governs]
Files Changed: [list]
```

---

### The Stair Walker Case — 2026-03-27

**Competing Positions:**
- Position A (Amendment 5): Maintain the dual-confirmation gate; it is correct for all profiles that passed validation.
- Position B (Article I): The dual-confirmation gate embeds a terrain-specific assumption not derived from any walking primitive — it must be replaced.

**Physical/Empirical Basis:**
Signal diagnostic (docs/executive_branch_document/plots/stair_walker_signal_check.png): gyr_y zero-crossing at 53ms, acc_filt peak at 188ms — temporal gap of 135ms on stairs. The 40ms confirmation window was derived from flat-ground heel-strike kinematics where both events are co-incident. This assumption was not derivable from the three walking primitives. Push-off plantar-flexion traces directly to cadence and step_length (push-off angular velocity = f(step_length, cadence)) and is present on every terrain without exception.

**Ruling:**
Position B prevails. The dual-confirmation gate is replaced by the push-off primary detector with retrospective ring-buffer heel-strike inference. Any future step detector primary trigger must be a signal feature that is biomechanically required on all terrains and derivable from at least one walking primitive.

**Precedent Effect:**
Time-gated co-occurrence windows that assume simultaneous signal events are not permitted unless the simultaneity is derived from and bounded by a walking primitive.

**Files Changed:** `src/gait/step_detector.c`, `simulator/terrain_aware_step_detector.py`

---

### The VABS.F32 Case — 2026-03-28

**Competing Positions:**
- Position A (Amendment 5): Healthy walkers passing all Stage 3 exit criteria (SI < 3%) is sufficient; the VABS.F32 discrepancy is a simulator artifact with no clinical consequence.
- Position B (Article I + Amendment 4): A failure mode is only confirmed caught if it is tested under conditions where the correct answer is non-zero. SI correctness for healthy walkers does not constitute a test of the SI computation under asymmetric input.

**Physical/Empirical Basis:**
Pathological walker test: true SI = 25% injected via ±45ms alternating stance offset. Firmware reported SI = 0.0% across all 9 snapshots on all 4 profiles despite 100/100 steps detected. DBG_SNAP diagnostic confirmed n_odd=9, n_even=10, stance_odd=482ms, stance_even=388ms — expected SI ≈ 21%, reported SI = 0.0%. Root cause: `VABS.F32` ARM FPU instruction returns ≈0 instead of |x| in Renode 1.16.1 for computed FPU-register values. `fabsf(m_odd - m_even)` was silently zeroing every SI computation where the result was non-zero.

**Ruling:**
Position B prevails. The pathological walker test (true SI = 25%, all four profiles, all above 10% clinical threshold) is now a mandatory Stage 3 exit criterion. `fabsf()` on FPU-register values is banned in this codebase; the conditional subtraction pattern `(diff >= 0.0f) ? diff : -diff` is the required replacement. Any future function that computes a quantity that could silently return a "correct-looking" zero must be validated under input conditions where the correct answer is non-zero.

**Precedent Effect:**
"No crash" is not a passing criterion. "Correct output for inputs where the correct answer is known to be non-zero" is the required criterion for any clinical-output computation.

**Files Changed:** `src/gait/rolling_window.c`

---

### The CNN Prior Seeding Case — 2026-03-28

**Competing Positions:**
- Position A (Amendment 13): Pre-filling the rolling window with synthetic records is a calibration that permanently biases the window; one calibration per algorithmic iteration must be justified.
- Position B (Article I + Amendment 5): The cold-start artifact (SI_swing = 200% at first snapshot) has a known physical cause (ring buffer ghost step from calibration period); the synthetic prior is derived from the three walking primitives at 105 spm using the physiological 60/40 stance/swing constant, not tuned empirically.

**Physical/Empirical Basis:**
Renode simulation (all 4 profiles): SI_swing = 200% at first snapshot regardless of actual asymmetry. Diagnostic: ring buffer entry from stationary calibration period produced heel-strike timestamp ≈ 4.8ms, yielding stance ≈ 1534ms (3× normal). Synthetic prior derivation: stance=343ms = 60% of 571ms step period at 105 spm. The 60/40 stance/swing split is a measured physiological constant, not a tuned value. Priors are symmetric (identical odd/even) → contribute exactly 0% SI. Priors evict naturally from the 200-entry buffer after 200 real steps.

**Ruling:**
Position B prevails with the constraint of Amendment 13: this prior derivation is the one calibration for this algorithmic iteration. The cadence convergence transient (first 3–4 snapshots show cadence closer to 105 spm than actual) is documented in `docs/executive_branch_document/handoff.md` Section 8 as an expected and predicted deviation.

**Precedent Effect:**
Synthetic priors are permitted as a cold-start mechanism if and only if: (a) prior values are derived from walking primitives using documented physiological constants; (b) priors are symmetric and contribute zero SI; (c) they evict naturally within one full window cycle; (d) the convergence transient is documented in the handoff document.

**Files Changed:** `src/gait/rolling_window.c`, `src/gait/phase_segmenter.c`

---

### The Terrain Gate Case — 2026-03-27

**Competing Positions:**
- Position A (Amendment 3): The LOADING→MID_STANCE gate references `acc_mag` which is also used in the step detector — this may be a cross-layer coupling.
- Position B (Article I): The `acc_mag` gate (`|acc_mag − 9.81| < 2.94`) was derived from flat-ground physics and must be replaced with a terrain-agnostic gate derivable from a walking primitive.

**Physical/Empirical Basis:**
Stair walker stuck permanently in LOADING phase. `acc_mag` at stair mid-stance ≈ 20 m/s² due to heel-strike impact. Gate: |20 − 9.81| = 10.2 >> 2.94 — never fires. Physical measurement: heel-strike arrest decays from 37–60 dps to near-zero in ~100ms on all terrains; early ankle rocker is 10–13 dps. The bisection point of 20 dps is terrain-invariant because it is derived from the gyr_y decay dynamics of foot-floor contact, which is governed by stance mechanics, not surface type.

**Ruling:**
Position B prevails (Article I takes precedence). Gate replaced with `|gyr_y| < 20 dps`. The VSQRT.F32 workaround was also removed because the acc_mag computation that required it is eliminated. Any phase transition gate that references a computed quantity must justify its terrain-invariance; if it cannot, it must be replaced by a raw axis gate derivable from walking primitive mechanics.

**Precedent Effect:**
Computed quantities used in phase transition gates require explicit terrain-invariance justification traceable to a walking primitive. Flat-ground-derived thresholds are not terrain-invariant by default.

**Files Changed:** `src/gait/phase_segmenter.c`

---

### The Dual-Confirmation Architecture Case — 2026-03-29

**Competing Positions:**
- Position A (Amendment 13 + Amendment 5): The 40ms co-occurrence window is a physically derivable calibration constant, not an architectural error. The correct remediation is to derive the window from `cadence_spm` and `stance_frac` as `stance_frac × (60000 / cadence_spm) × 0.12`, yielding a terrain-adaptive constant. The ring buffer fallback in Position C introduces a stance-duration timing error when no acc_filt crossing is found.
- Position C (Article I + Amendment 2 + Stair Walker Case precedent): Push-off plantar-flexion (gyr_y_hp) derives directly from cadence and step length. The 40ms window cannot derive from any walking primitive because it encodes flat-ground heel-strike co-incidence — a terrain-specific biomechanical assumption, not a primitive.

**Physical/Empirical Basis:**
IMU diagnostic plot (`docs/executive_branch_document/plots/stair_vs_flat_imu_diagnostic.png`), generated 2026-03-29 from `diagnostic_imu_analysis.py` against both profiles, 30 steps, seed=42:

- acc_filt peaks on stairs: mean 21.4 m/s² — **57.6% higher than flat** (13.6 m/s²). Peaks are not degraded; both profiles clear the 5.0 m/s² adaptive threshold with margin. Position A's ring buffer fallback risk (from missing acc_filt crossings) is not supported by the signal evidence.
- Timing gap between acc_filt peak and gyr_y zero-crossing: flat = ~19ms (4/5 steps fire the 40ms window); stairs = ~100ms (0/5 steps fire, including one step with no gyr_y zero-crossing detected at all).
- The ~100ms structural gap on stairs is not a constant calibration error — it is caused by the sigmoid toe-roll loading geometry of stair contact, which shifts the acc_filt peak rightward by the full body-weight loading interval relative to flat heel-strike. No single window constant can cover both because the two peaks occupy structurally different positions in the gait cycle.
- The missing gyr_y zero-crossing on stair Step 2 confirms that the confirmation event itself is unreliable on stairs, independent of window width. Even a widened window would not fire when the confirmation event does not occur.

**Ruling:**
Position C prevails. The Justice ruled that Position A poses a fundamental error conflicting with the Benjamin Franklin Principle (Physics First): stair walker biomechanics differ structurally from flat walker (longer toe-to-heel strike interval, near-single push-off loading pattern). The 40ms window failure is not a miscalibrated constant — it is an architectural assumption that encodes flat-ground heel-strike co-incidence and cannot be corrected by derivation without embedding a hidden terrain classifier. This violates Article I. Enacting Position A would also violate the Thomas Jefferson Principle: a patient ascending stairs with genuine gait asymmetry would receive an undefined SI output (0/5 steps fire), not an inaccurate one. Position C (terrain-aware push-off primary) is confirmed as the constitutionally required architecture.

**Precedent Effect:**
Any future proposal to restore a co-occurrence timing window as the primary step detection mechanism must first demonstrate, from physical IMU measurements, that the two co-occurring events occupy the same phase of the gait cycle across all terrain profiles under test. Simulation evidence (acc_filt and gyr_y timing tables) is the minimum required evidence for such a claim. A derivation argument alone, without measured timing data, is insufficient under the Benjamin Franklin Principle.

**Files Changed:** No new implementation — ruling confirms existing `src/gait/step_detector.c` (Option C, terrain-aware) and `simulator/terrain_aware_step_detector.py`. Diagnostic script: `diagnostic_imu_analysis.py`.

---

### The Algorithm Comparison Case — 2026-03-28

**Competing Positions:**
- Position A (Amendment 9): Three algorithm options (A: threshold tuning; B: filter redesign; C: push-off primary with ring buffer) were evaluated; Option C was selected after exhausting A and B. This is a valid domain search under Amendment 9.
- Position B (Amendment 10): Option C adds firmware complexity (ring buffer, extra FSM state); the hardware alternative (shoe-dorsum sensor repositioning for cleaner forefoot-to-flat terrain discrimination) was not formally evaluated as required by Amendment 9.

**Physical/Empirical Basis:**
Options A and B failed on stair profile (0/100 steps). Option C: 100/100 steps, SI = 0.41% on stairs. RAM overhead: 32 bytes for ring buffer (0.03% of 118KB SRAM). Flash overhead: < 200 bytes. Shoe-dorsum mounting assessed: requires different form factor, different strap BOM, different user calibration — cost exceeds 32 bytes of firmware complexity. Additionally, algorithm comparison GUI revealed Option C also resolves poor device fit (bad_wear) SI underestimation in pathological mode — a second failure mode resolved by the same architectural change.

**Ruling:**
Position A prevails. Option C is accepted. However, the shoe-dorsum mounting option is not closed — it is documented in `docs/executive_branch_document/hw_bom.md` as an open hardware iteration item. An agent may not remove this item without a new hearing. BOM alternatives are never silently closed by algorithm success alone.

**Precedent Effect:**
When an algorithm fix is accepted, the hardware alternative that was considered but not selected must be explicitly documented as an open option. Hardware iteration optionality survives algorithm success.

**Files Changed:** `src/gait/step_detector.c`, `simulator/terrain_aware_step_detector.py`

---

### The Pathological Validation Gate Case — 2026-04-02

**Competing Positions:**
- Position A (Amendment 5): Healthy walkers pass all Stage 3 exit criteria. The VABS.F32 silent-zeroing failure is a Renode 1.16.1 emulator artifact with no clinical consequence on real Cortex-M4F hardware. Stage 3 exit criteria are satisfied.
- Position B (Article I + Amendment 4): The SI computation has never been tested under input conditions where the correct answer is non-zero. A silent false negative that passes healthy validation is not validated. The Stage 3 pathological walker test mandated by The VABS.F32 Case had not been run against the patched firmware as of this hearing.

**Physical/Empirical Basis:**
The `high_si` pathological walker profile was run through Renode firmware for the first time in this codebase's history (2026-04-02). True SI injected: 25.0% (odd steps +45ms stance, even steps -45ms). Firmware reported SI across all 9 snapshots:

```
step= 9: si_stance=19.0%   step=19: si_stance=18.3%   step=29: si_stance=17.8%
step=39: si_stance=17.0%   step=49: si_stance=16.9%   step=59: si_stance=16.6%
step=69: si_stance=16.4%   step=79: si_stance=16.6%   step=89: si_stance=16.4%
```

True SI mean: 25.6%. Firmware range: 16.4–19.0%. Systematic underreporting: approximately 6–9 percentage points below true SI. All 9 snapshots were above the 10% clinical threshold (confirming the VABS.F32 conditional-subtraction fix at `rolling_window.c:30-31` works — the device no longer silently reports 0%). Steps detected: 100/100. However, the magnitude of SI reported is systematically wrong. A patient with true 25% asymmetry would receive a ~17% reading from this device.

Plot saved: `docs/executive_branch_document/plots/high_si_stance_timing.png`

**Ruling:**
Position B prevails. The Benjamin Franklin basis: Position B correctly recorded that the SI measurement is wrong — specifically, a systematic underreporting of approximately 6–9 percentage points below true SI under pathological input conditions. The Thomas Jefferson basis: Position B maximizes the performance of the final device that is best for human usage. A device that silently underreports a patient's gait asymmetry by 6–9 percentage points provides a clinically incorrect measurement and cannot be cleared for Stage 3 advancement.

The VABS.F32 conditional-subtraction fix is confirmed working (non-zero SI is now produced). However, the magnitude accuracy defect is an open finding that must be addressed before Stage 3 can close.

**Precedent Effect:**
1. The Stage 3 pathological walker test — mandated by The VABS.F32 Case — was confirmed un-run against the patched firmware as of this hearing. Amendment 4 requires it be run and human-confirmed before Stage 3 advancement. This hearing constitutes the first execution of that test.
2. The systematic SI magnitude underreporting (~6–9 percentage points below true SI at 25% injected asymmetry) is now a documented open finding. Stage 3 cannot close until this defect is addressed as a separate constitutional question — either through a Bill proposing a specific fix or through a further Judicial Hearing.
3. Any future Stage 3 gate closure requires: (a) pathological walker run through Renode with confirmed non-zero SI output above the 10% clinical threshold, AND (b) the SI magnitude accuracy defect addressed and validated under known non-zero input conditions. Passing criterion (a) alone is not sufficient for Stage 3 advancement.
4. This ruling extends The VABS.F32 Case precedent: "correct output for inputs where the correct answer is known to be non-zero" now also requires that the magnitude of the output is within a clinically acceptable tolerance of the true value — not merely that the output is non-zero.

**Files Changed:** None — ruling precedes implementation.
