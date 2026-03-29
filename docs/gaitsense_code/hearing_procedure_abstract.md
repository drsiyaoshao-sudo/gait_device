# GaitSense Judicial Hearing — Procedural Abstract

**Purpose:** A worked example of the full seven-step Judicial Hearing procedure for use as a procedural reference by future agents and human engineers. This document captures the hearing on *Dual-Confirmation Architecture vs Terrain-Aware Push-Off Primary* (2026-03-29) as a template, not a technical ruling. The ruling itself is recorded in [`case_law.md`](case_law.md).

---

## What a Hearing Is For

A Judicial Hearing activates when two or more amendments mandate incompatible actions, or when no amendment directly addresses a situation. It is not a design review, a code review, or a planning meeting. It is an evidence-bounded decision procedure with defined roles and a binding outcome.

The three roles are fixed:
- **The Justice** — the human. Presides, asks one clarifying question per position, rules. Never argues.
- **The Attorneys** — AI agents. Argue assigned positions. Do not volunteer verdicts. Do not switch sides mid-argument.
- **The Record** — written to `case_law.md` by the prevailing attorney before any implementation begins.

---

## Step-by-Step Procedure — Annotated With This Hearing's Execution

---

### Step 1 — Declaration

**The Justice declares the hearing in one sentence**, naming the conflict and both competing positions.

> *"I am declaring a hearing on: Stair Walker Step Detection Algorithm Selection. The competing positions are: Position A — retain and tune the dual-confirmation gate (acc_filt peak + gyr_y zero-crossing within 40ms window) and Position C — replace with terrain-aware push-off primary detector. The Justice presides."*

**What makes a valid declaration:**
- Names the conflict, not a preference
- States both positions symmetrically — neither is framed as the default
- Does not pre-load evidence or signal a preferred outcome

---

### Step 2 — Assignment

**The Justice assigns one attorney to each position.** If only one agent is available, it argues Position A in full before arguing Position B — no cross-contamination between arguments.

In this hearing: two Attorney-A agent instances were launched in parallel, one assigned Position A and one assigned Position C. Parallel assignment is preferred when available — it eliminates any possibility of the second argument being shaped by awareness of the first.

**Operational note:** Each attorney instance reads the relevant constitutional files (`amendments.md`, `case_law.md`) and codebase files independently before constructing its argument. This is not optional — an attorney that argues from memory rather than from the current record is out of compliance with the Benjamin Franklin Principle.

---

### Step 3 — Argument, Position A

**The assigned attorney presents four elements, in order:**

1. Which amendment is invoked — exact number and title
2. Which precedent supports this position — case name and date
3. What physical or clinical outcome this position protects
4. What the consequences of the opposing position would be in physical terms

**From this hearing — Position A (retain dual-confirmation):**

- *Amendment invoked:* Amendment 13 (Calibration Discipline) — the 40ms window is a physically derivable constant, not an arbitrary value. The formula `stance_frac × (60000 / cadence_spm) × 0.12` yields 41ms for flat and 128ms for stairs.
- *Precedent:* The Terrain Gate Case (2026-03-27) — establishes the standard that a gate must justify terrain-invariance from a walking primitive. Position A argued this standard could be met by the derived window formula.
- *Clinical outcome protected:* Heel-strike timestamp fires at the correct moment in stance (gyr_y zero-crossing), preserving phase_segmenter timing accuracy. Position C fires at push-off and infers heel-strike retrospectively — introducing a stance-duration error in the ring buffer fallback path.
- *Consequences of Position C:* Sequential dependency chain (push-off → acc_filt confirmation → ring buffer lookup) has higher compounded failure probability than parallel co-occurrence. Ring buffer fallback fires at push-off timestamp, injecting up to 557ms error into phase_segmenter on stairs.

---

### Step 4 — Argument, Position C

**The opposing attorney presents the same four elements.**

**From this hearing — Position C (terrain-aware push-off primary):**

- *Amendment invoked:* Article I (Physics First, unconditional) + Amendment 2 (Three Primitives) — push-off gyr_y_hp derives from cadence and step_length: `peak_angvel = (100 + 65 × walking_speed) × slope_factor`. The 40ms window derives from no walking primitive — it encodes flat-ground heel-strike co-incidence.
- *Precedent:* The Stair Walker Case (2026-03-27) — the dual-confirmation gate was already ruled unconstitutional. The Algorithm Comparison Case (2026-03-28) — Option C was already ruled accepted after Options A and B produced 0/100 on stairs.
- *Clinical outcome protected:* A patient ascending stairs with true SI = 25% receives a measured SI (within 6.3% of stance duration error — sub-threshold for the 10% clinical boundary). Under Position A, that patient receives undefined SI output (0/5 steps fire).
- *Consequences of Position A:* 0/100 stair step detection is not degraded accuracy — it is total failure producing undefined SI. Enacting Position A would require explicitly overruling The Stair Walker Case precedent, which requires a new hearing under CLAUDE.md Section 5.

---

### Step 5 — Deliberation (Justice's Clarifying Question)

**The Justice may ask each attorney one clarifying question.** The attorney answers only the question asked.

In this hearing, the Justice requested additional physical evidence rather than a verbal clarification:

> *"I need more evidence of the shape of the IMU data to determine whether acc_filt peak thresholds are degraded on the stair walker case."*

This triggered a **Bureaucracy Signal Plotting Standing Order** mid-hearing. The plotter agent was dispatched to generate `stair_vs_flat_imu_diagnostic.png` — a 4-panel comparison of acc_z, acc_filt, gyr_y, and gyr_y_hp for flat and stair profiles across 10 steps.

**Key finding returned:** acc_filt peaks on stairs are NOT degraded — they are 57.6% higher than flat (21.4 vs 13.6 m/s²). Position A's ring buffer fallback risk was not supported by the signal evidence.

A second targeted plot was then requested:

> *"Can you point out the missing zero-crossing in the figure?"*

The plotter agent generated `stair_step2_missing_zerocross.png` — a zoomed 2-panel plot of Steps 1–3 on stairs with annotated zero-crossing detection windows. This confirmed that on Step 2, gyr_y rises to ~160 dps and returns toward zero but does not cross within the 200ms search window, because gyr_y from the previous step's push-off bleeds into Step 2's window. The confirmation event is absent — not delayed — making window widening insufficient.

**Procedural note on mid-hearing evidence generation:** This is encouraged and constitutional. The Benjamin Franklin Principle requires rulings to cite physical evidence. If the existing record does not contain sufficient evidence, the Justice requests it. A Bureaucracy Standing Order (Signal Plotting) executes immediately — no Bill or Amendment vote is required to generate diagnostic plots.

---

### Step 6 — Ruling

**The Justice announces:**
1. Which position prevails
2. The governing physical/empirical basis (Benjamin Franklin Principle)
3. The ultimate patient/hardware outcome protected (Thomas Jefferson Principle)
4. Any conditions or constraints on application

**From this hearing:**

> *"Position A poses a fundamental error that conflicts with the Franklin principle — physics first. Stair walker's walking mechanics differ from flat walker (longer than 40ms toe-to-heel striking time and almost single push-off pattern), and will violate the Jefferson principle that maximizes the good outcome of the device. I rule in favor of Position C."*

**Benjamin Franklin basis:** The IMU diagnostic confirmed that the ~100ms timing gap between acc_filt peak and gyr_y zero-crossing on stairs is structural — caused by sigmoid toe-roll loading geometry, not a miscalibrated constant. The missing gyr_y zero-crossing on Step 2 further confirmed that the confirmation event itself is unreliable on stairs independent of window width.

**Thomas Jefferson basis:** Position A produces undefined SI output for a stair-ascending patient with genuine gait asymmetry. Position C produces a measured SI accurate to within 6.3% of stance duration — below the 10% clinical threshold.

---

### Step 7 — Recording

**The prevailing attorney records the ruling in `case_law.md` before any implementation begins.** The record uses the standard case template and includes:
- Competing positions
- Physical/empirical basis (citing specific measurements, not arguments)
- Ruling text
- Precedent effect (what future situations this governs)
- Files changed (or confirmed unchanged)

In this hearing, the ruling was recorded as **The Dual-Confirmation Architecture Case (2026-03-29)** in `case_law.md`. The diagnostic plots and the evidence script (`diagnostic_imu_analysis.py`) were committed to the repository as part of the case record.

**The commit message is part of the record.** It names the ruling, the Justice's stated basis, and the new precedent effect.

---

## Procedural Lessons From This Hearing

**1. Launch attorneys in parallel when possible.**
Both attorneys read the same files and built their arguments independently. Neither argument was shaped by awareness of the other. This is the only way to ensure symmetric evidence quality.

**2. Mid-hearing evidence requests are normal and constitutional.**
The Justice requested two plots during deliberation. Neither required a Bill. The Bureaucracy executed immediately. A hearing that pauses for evidence collection is working correctly — a hearing that rules without sufficient evidence is not.

**3. The evidence refuted the attorney, not the other way around.**
Position A's strongest claim (ring buffer fallback risk from degraded acc_filt peaks) was eliminated by the diagnostic data showing stair peaks are 57.6% *higher* than flat. No amount of argument would have resolved this — only the measurement could. This is the Benjamin Franklin Principle in operation.

**4. A missing event is different from a delayed event.**
The Step 2 zero-crossing was not late — it was absent. This distinction is what made window widening constitutionally insufficient: you cannot widen a window to capture an event that does not occur. The zoomed plot made this visually unambiguous in a way that the timing table alone did not.

**5. Existing case law shortened the hearing.**
The Stair Walker Case (2026-03-27) had already ruled the dual-confirmation architecture unconstitutional. Position C's attorney cited this directly. The Justice did not need to re-derive the ruling from first principles — only to confirm that the new evidence was consistent with the existing precedent. Case law compounds across hearings.

**6. The ruling took one sentence.**
The Justice's ruling was concise and physically grounded. It named the biomechanical difference (longer toe-to-heel striking time, single push-off pattern), cited both constitutional principles, and named the prevailing position. A ruling that requires a paragraph of reasoning to establish its physical basis is a sign that the evidence package was insufficient before the hearing began.

---

## Checklist for Future Hearings

Before declaring a hearing, confirm:
- [ ] The conflict is between two amendments or an amendment and an Article — not a preference or opinion
- [ ] Both positions can be stated symmetrically in one sentence each
- [ ] Relevant case law has been read — an existing precedent may resolve the conflict without a hearing

During the hearing:
- [ ] Attorneys are assigned, not self-selected
- [ ] Each attorney reads `amendments.md` and `case_law.md` before constructing argument
- [ ] Both arguments present all four required elements
- [ ] If evidence is insufficient, pause and dispatch a Bureaucracy Standing Order — do not rule on argument alone
- [ ] Justice asks at most one clarifying question per position

After the ruling:
- [ ] Ruling is recorded in `case_law.md` before any implementation begins
- [ ] Diagnostic plots and evidence scripts are committed to the repository
- [ ] Commit message names the case, the basis, and the new precedent effect
- [ ] No implementation proceeds until the case record is committed and pushed
