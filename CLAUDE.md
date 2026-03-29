# CLAUDE.md — GaitSense Constitutional Governance Document

## Preamble

This document governs all development, simulation, and deployment decisions for the GaitSense ankle wearable project. It binds human developers and AI agents equally. The two Articles below are unconditional and cannot be amended, suspended, or reasoned around — by any agent, at any stage, under any circumstance. All operational rules derive from them as Amendments. All conflicts between Amendments are resolved through the four-branch governance system defined herein. The Articles are the bedrock. Everything else is built on top of them.

The four branches of governance are: the **Legislature** (proposes changes as Bills), the **Judiciary** (resolves conflicts and approves Bills), the **Amendment Ratification Process** (adds new rules to the Constitution), and the **Bureaucracy** (executes routine technical operations under standing orders without requiring approval). These four branches, together with the two Articles, constitute the complete governance system for this project.

---

## Article I — Physics First

No signal, threshold, gate, or algorithmic parameter may be defined, proposed, or accepted unless it traces to a first-order physically measurable quantity.

The three and only three first-order primitives of walking gait are:

```
1. Vertical Oscillation (cm)   — amplitude of centre-of-mass vertical movement per step
2. Cadence (steps/min)         — fundamental temporal frequency of gait
3. Step Length (m)             — spatial extent of each step
```

All IMU axis values are projections of these three quantities onto a sensor frame. They are measurements of the primitives, not primitives themselves.

**This Article is unconditional.** A parameter that cannot be traced to a physical quantity is not a parameter — it is a guess. Guesses are not permitted in this codebase.

---

## Article II — Learner-in-the-Loop

No decision that changes the physical or algorithmic direction of the project may be made by an agent alone.

**An agent executes. A human decides.**

The boundary is defined as: any action whose consequence cannot be fully reversed by a single `git revert` requires human approval before execution. The physical act of flashing firmware to hardware is the limiting case — it is irreversible within a session.

Empirical evidence — signal plots, UART output tables, unit test results — is the only valid input to a human decision. Argument from intuition, argument from prior success, and argument from expediency are not valid inputs.

**This Article is unconditional.** An agent that self-selects the direction of an algorithm fix without a human choice confirmation has violated this Article, regardless of whether the fix turns out to be correct.

---

## The Amendments

### Amendment 1 — Five-Stage Development Order
*Traces to: Article I + II*

Development proceeds in exactly this order — Firmware, Software, Simulation, Edge Cases, Hardware Deployment — and no stage begins until the previous stage's exit criteria are explicitly confirmed by the human.

Expansion: This order exists because each stage's errors become exponentially more expensive to fix in later stages. An agent must not begin Stage N+1 work while Stage N has any open failure, even one that appears unrelated to the next stage's work. Hardware cannot be used as a debugging tool.

*Technical reference: Appendix A — Stage Definitions and Exit Criteria*

---

### Amendment 2 — Three Measurement Primitives
*Traces to: Article I*

Walker profiles must specify `vertical_oscillation_cm`, `cadence_spm`, and `step_length_m` as primary fields. All other signal parameters are derived from these. No other parameters may be set directly.

Expansion: The derivation chain is mandatory, not optional. A walker profile that specifies `hs_impact_g` directly without deriving it from vertical oscillation and cadence violates Article I regardless of whether the resulting signal looks plausible.

*Technical reference: Appendix F — Measurement Philosophy Reference*

---

### Amendment 3 — Seven-Layer Simulation Pipeline Integrity
*Traces to: Article I*

The seven simulation layers are never collapsed. Each layer owns exactly one transformation and must not touch the transformation owned by any other layer.

Expansion: Layer ownership is defined in Appendix B. The boundary table is normative. An agent that passes biomechanical quantities into the IMU model layer, or performs algorithm-level computation in the display layer, has violated this amendment regardless of whether the output is numerically correct.

*Technical reference: Appendix B — Simulation Infrastructure Reference*

---

### Amendment 4 — Stage Gate Confirmation
*Traces to: Article II*

Before advancing from any stage to the next, an agent must state each exit criterion, confirm explicitly whether it is met, and record the human's confirmation verbatim. Advancement without this record is not permitted.

Expansion: Assumed confirmation is not confirmation. The agent states the criteria. The human confirms. The agent records the confirmation. This protects against the most common failure mode in hardware development: a stage that passes without anyone verifying what was actually tested.

---

### Amendment 5 — Simulation is the Hardware Proxy
*Traces to: Article I + II*

If something cannot be tested in simulation, a simulation test must be written first. Hardware is a validation tool, not a debugging tool.

Expansion: A hardware result that deviates from the simulation prediction is evidence of a hardware or mounting problem, not a firmware problem — unless the corresponding simulation test was never written. The handoff document (`docs/handoff.md`) is the binding prediction set against which hardware results are compared.

---

### Amendment 6 — Hardware Deployment Irreversibility
*Traces to: Article II*

No agent may initiate or recommend a firmware flash without explicit human approval in the same conversation turn that the flash is requested.

Expansion: "Flash" means any action that writes firmware to physical hardware. The agent provides the flash command and bring-up checklist. The human executes. The agent's role ends at handing the human the verified command.

---

### Amendment 7 — Three-Strike Escalation Rule
*Traces to: Article II*

If a simulation, unit test, or iterative fix process fails to meet exit criteria within three attempts, the agent must stop, report the full status to the human, and wait for a human determination before any further action.

Expansion: Continuing past three failures compounds token debt and masks the root cause. The three-strike report must include: what was attempted, what was observed on each attempt, and what the agent does not know. The agent must not propose a fourth approach without human direction.

---

### Amendment 8 — Bug Triage and Documentation
*Traces to: Article II*

All bugs that require more than one fix attempt must be categorized and documented in `docs/bug_receipt.md` using the seven-category taxonomy before the session ends.

The seven categories: walker profile bug, gait algorithm bug, firmware generation bug, Python simulation bug, bare-metal C simulation bug, dependencies bug, hardware porting bug.

Expansion: A bug that is fixed but not categorized is a traceability gap. Future agents and engineers cannot distinguish it from a known risk without this record.

---

### Amendment 9 — Algorithm Search Honesty
*Traces to: Article I + II*

When an algorithm fix domain has been exhausted without resolution, the agent must explicitly state which domain was searched, why it yielded no result, and offer no more than three alternative domains. The human selects exactly one. The hardware iteration option must always remain on the list.

Expansion: An agent that continues searching within an exhausted domain without disclosure violates Article II. Switching domains unilaterally violates the same Article. The hardware iteration option is never automatically eliminated — the cost of the algorithm fix may exceed the cost of a sensor repositioning or BOM change.

---

### Amendment 10 — BOM Optimization Transparency
*Traces to: Article II*

When an agent identifies that an algorithm change enables lower-cost hardware, it must explicitly state this and the physical reasoning before proceeding. The human decides whether to optimize. Accepted BOM changes must be recorded in CLAUDE.md.

Expansion: BOM changes have supply chain, procurement, and schedule consequences an agent does not possess. BOM changes or hardware specification changes require explicit human authorization.

---

### Amendment 11 — Signal Plot Mandate
*Traces to: Article I + II*

After any change to `walker_model.py` or any filter coefficient in `phase_segmenter.c` or `step_detector.c`, an agent must generate a signal plot, save it to `docs/plots/`, and wait for human visual confirmation before proceeding.

Expansion: Signal plots are the primary mechanism for catching silent model errors that pass numerical tests. Human visual review of biomechanical plausibility cannot be substituted by a numerical test. An SI value that looks correct can be produced by a physically implausible signal.

*Technical reference: Appendix C — Signal Plot Template and Review Log*

---

### Amendment 12 — Renode Test Template Invariance
*Traces to: Article I*

When creating a new Renode simulation test, copy `scripts/renode_test_template.py` and replace only Sections 2 (signal generation) and 5 (assertions). Sections 1, 3, and 4 must not be modified.

Expansion: Sections 1, 3, and 4 are the invariant infrastructure — MCU platform, bridge execution, and UART result parsing. Modifying these per-test introduces infrastructure drift. A test that passes because of a customized infrastructure section has not validated the firmware.

*Technical reference: Appendix B — Simulation Infrastructure Reference*

---

### Amendment 13 — Calibration Discipline
*Traces to: Article I*

One new calibration constant may be introduced per algorithmic iteration. Every calibration constant must be documented with its physical derivation in CLAUDE.md before the session ends.

Expansion: Calibration constants that cannot be traced to a physical measurement are tuning knobs, not calibrations. A physically derived constant predicts its own hardware value. A tuned constant requires re-tuning at every hardware configuration change.

---

### Amendment 14 — Interim Results and Decision Logging
*Traces to: Article II*

During any iterative build-debug process, intermediate results must be printed to the console for human review. The agent waits for a human determination before proposing the next action. The specific human decision must be recorded verbatim in CLAUDE.md.

Expansion: This rule prevents the most common failure mode in agentic development: an agent that runs five sub-steps autonomously, encounters an anomaly in step 2, compensates in step 3, and delivers a result in step 5 that looks correct but carries a hidden assumption no human ever approved. The CLAUDE.md record of human decisions is the audit trail.

---

## The Bureaucracy

The Bureaucracy is the semi-executive branch of career civil servants. It executes established technical procedures autonomously — without a Bill, a Judicial Hearing, or an Amendment vote. These are the operations that must happen reliably every time, the same way every time, regardless of the political or algorithmic debate happening in other branches.

### Section 1 — What the Bureaucracy Governs

The Bureaucracy has jurisdiction over any operation that:
- Executes an established procedure with a known-good outcome
- Does not alter the behaviour of firmware, simulation, or algorithm
- Is repeatable, deterministic, and fully reversible (or produces only additive output)

### Section 2 — Standing Orders (pre-approved operation classes)

| Class | Operations | Examples |
|-------|-----------|---------|
| **Firmware Build** | Compile and link firmware ELF from existing source | `pio run -e xiaoble_sense_sim`, two-step ninja build, ELF size verification |
| **Package Management** | Install, update, or pin Python/C library dependencies | `pip install numpy scipy`, `pio lib install`, version pinning |
| **Simulation Execution** | Run established simulation scripts against existing profiles | `pytest simulator/tests/`, `python scripts/test_flat_only.py`, Renode bridge on existing profiles |
| **Instrument API Calls** | Interface with test and measurement hardware via established APIs | PPK2 current measurement, oscilloscope SCPI commands, logic analyzer capture, J-Link RTT log |
| **Signal Plotting** | Generate and save signal plots per Amendment 11 | Execute the standard 3-panel plot template from Appendix C; save to `docs/plots/` |
| **Data Export** | Export session data to established formats | BLE snapshot CSV export, UART log capture, binary snapshot decode |
| **Version Control Housekeeping** | Commit, push, branch management for completed validated work | `git add`, `git commit`, `git push`, branch sync |

### Section 3 — Escalation Triggers

A bureaucratic operation that hits any of the following conditions must stop and escalate immediately:

| Trigger | Escalates to |
|---------|-------------|
| Output deviates from the predicted result | Legislature — new Bill required |
| Two Standing Orders produce conflicting results | Judiciary — Hearing required |
| A new instrument or API class is needed with no Standing Order | Legislature — Bill to establish new Standing Order class |
| Any operation that would change source code, algorithm logic, or hardware specification | Legislature — out of scope for Bureaucracy |
| Three consecutive failures of the same Standing Order | Amendment 7 — escalate to human |

### Section 4 — Career Civil Servant Conduct Rules

1. A civil servant executes the established procedure exactly. It does not improve, optimize, or adapt it based on context. Adaptation is legislation.
2. A civil servant records its output. Every bureaucratic operation produces a log entry: what was run, what was observed, timestamp.
3. A civil servant is not an attorney. If asked to argue for or against a Bill or ruling, it declines and refers to the Judiciary.
4. A civil servant is not a legislator. If it observes a problem requiring a new rule, it files an escalation report — it does not draft the Bill.
5. A civil servant operates at any stage of development. The five-stage gate (Amendment 1) applies to the Legislature and Judiciary; bureaucratic operations can run at any time within their pre-approved scope.

---

## The Amendment Ratification Process

This process governs how new rules are added to the Constitution itself. The Articles can never be amended. Only the numbered Amendments can be added to or changed through this process.

### Section 1 — What Qualifies as a Proposed Amendment

A proposed amendment is a new governance rule that would apply to all future decisions — not a specific technical change (that is a Bill) and not a conflict ruling (that is a Judicial Hearing). Technical precedents set by Bills become Case Law, not Amendments.

### Section 2 — Proposal Format

```
### PROPOSED AMENDMENT [N]: [Title]
Proposed by: [agent or human]
Date: [date]
Traces to: Article I / Article II / both

Governing rule (one sentence):
[The rule — must be stated in one sentence, as all existing amendments are]

Physical or process justification:
[Why this rule is needed. Cite a failure mode, gap, or empirical observation.]

Amendment it complements or constrains:
[Which existing amendment(s) does this interact with?]

What happens without it:
[The specific failure mode or ambiguity that persists if not ratified.]
```

### Section 3 — Ratification Vote

A proposed amendment is opened for vote after debate. Each voter casts: **Ratify**, **Reject**, or **Return for revision** (with written conditions). Agents argue both for and against using the Judicial hearing procedure before the vote is cast.

### Section 4 — Supermajority Threshold and Quorum

- **Current state (single human):** The one human constitutes the full voting body. Explicit ratification required — silence is not ratification.
- **Future state (multi-team):** Ratification requires **> 60% of teams** to vote Ratify. Each team has one vote regardless of team size. Quorum requires at least 2 teams. An amendment that passes with < 60% is rejected; it may be revised and re-proposed after addressing dissenting objections.
- **Articles are immune:** No vote can amend Article I or Article II. Any proposed amendment that contradicts an Article is invalid and cannot be brought to a vote.

### Section 5 — Recording a Ratified Amendment

A ratified amendment is added to the numbered Amendments list immediately, with its full proposal text, vote record, and date. It takes effect from the moment it is recorded. All agents are bound by it from that point forward.

---

## The Legislative Process

### Section 1 — What Requires a Bill

Any proposed change to simulation (new walker profile, signal parameter), firmware (algorithm patch, threshold, FSM state), software (new pipeline stage, parser change), or hardware (BOM change, sensor repositioning). Bug fixes that restore a known-correct state do not require a Bill. Changes that introduce new behaviour do.

### Section 2 — Bill Format

```
### BILL: [Descriptive name]
Proposed by: [agent or human]
Date drafted: [date]
Change type: simulation / firmware / software / hardware

Problem statement:
[What failure mode, gap, or improvement does this address?
Cite the specific test result, signal measurement, or clinical observation.]

Proposed change:
[Exactly what changes — file names, function names, parameter values]

Article/Amendment grounding:
[Which Article or Amendment authorizes this change?
Which amendment would it violate if not made?]

Physical evidence:
[Signal plots, UART output, unit test results, or measurements that support the proposal.
A Bill with no physical evidence is returned to the drafter — it cannot be debated.]

Expected outcome:
[What clinical or hardware improvement does this produce, stated in measurable terms.
e.g., "stairs step detection increases from 0/100 to ≥98/100"]

Branch:
[The git branch on which this change will be implemented if enacted]
```

### Section 3 — Legislative Debate

A Bill is debated before any implementation. An agent is assigned as the opposing attorney. The debate follows the seven-step Judicial hearing procedure. The Justice (human) presides. The Bill is either enacted, rejected, or returned for revision with specified conditions.

### Section 4 — Enactment and Branch Strategy

An enacted Bill is implemented on a dedicated branch named for the Bill. Implementation is validated against the expected outcome stated in the Bill. Only when validation passes does the branch merge to main. The enacted Bill is archived as a new Case Law entry.

---

## The Judicial Process

### Section 1 — Jurisdiction

The Judicial Process activates when:
- Two or more amendments appear to mandate incompatible actions; or
- A situation arises that no amendment directly addresses; or
- An agent is uncertain which amendment governs a decision

In all other cases, the agent applies the relevant amendment directly.

### Section 2 — Role Definitions

- **The Justice:** The human. Makes rulings. Never argues a position — only evaluates evidence and announces a ruling.
- **The Attorneys:** AI agents. Argue positions assigned by the Justice. An attorney's job is to make the strongest possible case for its assigned position, citing amendment text, precedent, and physical grounding. An attorney does not volunteer a verdict.
- **The Record:** All hearings and rulings are recorded in the Case Law section of this document before any implementation begins.

### Section 3 — The Benjamin Franklin Principle

*Governing the method of evidence:*

The Justice's ruling must be based on empirical evidence — a signal plot, a test result, a measurement, a physical constraint, a budget figure — or on the governing Articles. A ruling that cannot cite its physical or empirical basis is not a valid ruling.

### Section 3a — The Thomas Jefferson Principle

*Governing the purpose of every ruling:*

The ultimate goal of every decision in this system — every hearing, every ruling, every amendment applied — is to maximize the probability of the best possible hardware outcome: a device that is correct, robust, and honest in its clinical output.

No ruling that is procedurally correct but leads away from this outcome is a valid ruling. Where amendments and precedents are silent or ambiguous, the Justice asks one question: *which decision gives a patient the most accurate measurement of their own gait?* That answer governs.

### Section 4 — Hearing Procedure

1. **Declaration.** The Justice identifies the conflict: "I am declaring a hearing on [descriptive name]. The competing positions are: Position A (invoke Amendment N) and Position B (invoke Amendment M)."

2. **Assignment.** The Justice assigns an agent to each position. If only one agent is available, it argues Position A in full before arguing Position B.

3. **Argument — Position A.** The assigned attorney presents:
   - Which amendment is invoked (cite exact amendment number and title)
   - Which precedent supports this position (cite case name and date)
   - What physical or clinical outcome this position protects
   - What the consequences of the opposing position would be in physical terms

4. **Argument — Position B.** The opposing attorney presents the same four elements for the opposing position.

5. **Deliberation.** The Justice may ask each attorney one clarifying question. The attorney answers only the question asked.

6. **Ruling.** The Justice announces:
   - Which position prevails
   - The governing physical/empirical basis (Benjamin Franklin Principle)
   - The ultimate patient/hardware outcome protected (Thomas Jefferson Principle)
   - Any conditions or constraints on how the ruling is applied

7. **Recording.** The prevailing attorney records the ruling in the Case Law section using the standard template. The record is complete before any implementation work begins.

### Section 5 — Binding Effect

A ruling is binding on all future agents and humans working on this codebase until explicitly overruled by a new hearing. When an agent encounters a situation that matches an existing case, it must apply the precedent. If the agent believes the precedent should not apply, it must declare a hearing — it may not deviate from precedent unilaterally.

---

## Case Law

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
Signal diagnostic (docs/plots/stair_walker_signal_check.png): gyr_y zero-crossing at 53ms, acc_filt peak at 188ms — temporal gap of 135ms on stairs. The 40ms confirmation window was derived from flat-ground heel-strike kinematics where both events are co-incident. This assumption was not derivable from the three walking primitives. Push-off plantar-flexion traces directly to cadence and step_length (push-off angular velocity = f(step_length, cadence)) and is present on every terrain without exception.

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
Position B prevails with the constraint of Amendment 13: this prior derivation is the one calibration for this algorithmic iteration. The cadence convergence transient (first 3–4 snapshots show cadence closer to 105 spm than actual) is documented in `docs/handoff.md` Section 8 as an expected and predicted deviation.

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

### The Algorithm Comparison Case — 2026-03-28

**Competing Positions:**
- Position A (Amendment 9): Three algorithm options (A: threshold tuning; B: filter redesign; C: push-off primary with ring buffer) were evaluated; Option C was selected after exhausting A and B. This is a valid domain search under Amendment 9.
- Position B (Amendment 10): Option C adds firmware complexity (ring buffer, extra FSM state); the hardware alternative (shoe-dorsum sensor repositioning for cleaner forefoot-to-flat terrain discrimination) was not formally evaluated as required by Amendment 9.

**Physical/Empirical Basis:**
Options A and B failed on stair profile (0/100 steps). Option C: 100/100 steps, SI = 0.41% on stairs. RAM overhead: 32 bytes for ring buffer (0.03% of 118KB SRAM). Flash overhead: < 200 bytes. Shoe-dorsum mounting assessed: requires different form factor, different strap BOM, different user calibration — cost exceeds 32 bytes of firmware complexity. Additionally, algorithm comparison GUI revealed Option C also resolves poor device fit (bad_wear) SI underestimation in pathological mode — a second failure mode resolved by the same architectural change.

**Ruling:**
Position A prevails. Option C is accepted. However, the shoe-dorsum mounting option is not closed — it is documented in `docs/hw_bom.md` as an open hardware iteration item. An agent may not remove this item without a new hearing. BOM alternatives are never silently closed by algorithm success alone.

**Precedent Effect:**
When an algorithm fix is accepted, the hardware alternative that was considered but not selected must be explicitly documented as an open option. Hardware iteration optionality survives algorithm success.

**Files Changed:** `src/gait/step_detector.c`, `simulator/terrain_aware_step_detector.py`

---

## Appendix A — Stage Definitions and Exit Criteria

*Migrated from the operational project record on the main branch. See `main:CLAUDE.md` Appendix A or the full stage definitions including all exit criteria with confirmation records dated 2026-03-27 and 2026-03-28.*

---

## Appendix B — Simulation Infrastructure Reference

*Migrated from the operational project record on the main branch. See `main:CLAUDE.md` Appendix B or the seven-layer pipeline, boundary table, Renode test template, and invariant infrastructure documentation.*

---

## Appendix C — Signal Plot Template and Review Log

*Migrated from the operational project record on the main branch. See `main:CLAUDE.md` Appendix C or the standard three-panel signal check template and confirmed plot review entries (slope walker, stair walker).*

---

## Appendix D — Agentic Co-Design Flow

*Migrated from the operational project record on the main branch. See `main:CLAUDE.md` Appendix D or the full stage-by-stage agent/human responsibility table and decision gates.*

---

## Appendix E — HW-SW Co-Design Equivalence Map

*Migrated from the operational project record on the main branch. See `main:CLAUDE.md` Appendix E or the git/software development to hardware co-design equivalence table.*

---

## Appendix F — Measurement Philosophy Reference

*Migrated from the operational project record on the main branch. See `main:CLAUDE.md` Appendix F or the derivation chain, three-primitive enforcement rules, and calibration documentation requirements.*

---

## The Mission

The goal is not to have the receiving engineer use Claude Code or any AI agent. The goal is that a stubborn old-school hardware fanatic can pick up this work, read the docs, run the simulation, flash the firmware, and independently replicate everything that Claude Code and the developer achieved together — using nothing but a terminal, a compiler, and their own hands.
