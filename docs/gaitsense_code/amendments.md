# GaitSense Amendments

All amendments derive from Article I (Physics First) and/or Article II (Learner-in-the-Loop) in CLAUDE.md. The governing Articles are unconditional and cannot be amended. New amendments are added through the Amendment Ratification Process defined in CLAUDE.md.

---

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

Expansion: A hardware result that deviates from the simulation prediction is evidence of a hardware or mounting problem, not a firmware problem — unless the corresponding simulation test was never written. The handoff document (`docs/executive_branch_document/handoff.md`) is the binding prediction set against which hardware results are compared.

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

All bugs that require more than one fix attempt must be categorized and documented in `docs/executive_branch_document/bug_receipt.md` using the seven-category taxonomy before the session ends.

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

When an agent identifies that an algorithm change enables lower-cost hardware, it must explicitly state this and the physical reasoning before proceeding. The human decides whether to optimize. Accepted BOM changes must be recorded using versioning of BOMs.

Expansion: BOM changes have supply chain, procurement, and schedule consequences an agent does not possess. BOM changes or hardware specification changes require explicit human authorization.

---

### Amendment 11 — Signal Plot Mandate
*Traces to: Article I + II*

After any change to `walker_model.py` or any filter coefficient in `phase_segmenter.c` or `step_detector.c`, an agent must generate a signal plot, save it to `docs/executive_branch_document/plots/`, and wait for human visual confirmation before proceeding.

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

During any iterative build-debug process, intermediate results must be printed to the console for human review. The agent waits for a human determination before proposing the next action. The specific human decision must be recorded verbatim in bug receipt and project memory files.

Expansion: This rule prevents the most common failure mode in agentic development: an agent that runs five sub-steps autonomously, encounters an anomaly in step 2, compensates in step 3, and delivers a result in step 5 that looks correct but carries a hidden assumption no human ever approved. The record of human decisions is the audit trail.

---

### Amendment 15 — Statistical Derivation Documentation
*Traces to: Article I*
*Ratified: 2026-03-29. Proposed by: Claude Sonnet 4.6. Ratified by: sole human engineer.*

Any constant that cannot be derived algebraically from the three walking primitives but is instead derived from a population distribution of one or more primitives must document: the distribution (μ, σ), the sigma bound applied, and any population explicitly excluded from the bound.

Expansion: This amendment closes the gap between Amendment 13 (algebraically derived constants) and constants derived from population statistics of walking primitives. A constant derived from the cadence distribution still traces to Article I — but the statistical path must be made explicit. The failure mode without this rule: statistically derived constants accumulate as undocumented magic numbers that pass Article I review because a primitive is nominally involved, but carry no derivation that predicts their correct value when the target population changes (paediatric, geriatric, athletic). The required documentation format is:

```
/* CONSTANT_NAME — statistically derived from [primitive].
 * Population: [description], distribution ~ N(μ, σ²) [units]
 * Bound: [N]σ upper/lower tail → [value] [units] → CONSTANT = [value]
 * Excluded population: [any explicitly out-of-scope group and why]
 * Traces to: [primitive] (Article I). */
```

First application: `MIN_STEP_INTERVAL_MS = 250` in `src/gait/step_detector.c`.
Human ambulation cadence ~ N(130, 30²) spm across walking + running population.
2.5σ upper tail: 205 spm → minimum step period 293 ms → 250 ms with margin.
Excluded: running downhill (>210 spm, out of scope for SI measurement device).
