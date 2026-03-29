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

All amendments are maintained in [`docs/gaitsense_code/amendments.md`](docs/gaitsense_code/amendments.md). Amendments 1–15 are currently ratified. New amendments are added to that file through the Amendment Ratification Process below.

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
| **Signal Plotting** | Generate and save signal plots per Amendment 11 | Execute the standard 3-panel plot template from Appendix C; save to `docs/executive_branch_document/plots/` |
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

All rulings are maintained in [`docs/gaitsense_code/case_law.md`](docs/gaitsense_code/case_law.md). Five precedents are currently recorded. New rulings are appended to that file by the prevailing attorney immediately after each hearing, before any implementation begins.

---

## Appendix A — Stage Definitions and Exit Criteria

*Operational content lives in [`docs/executive_branch_document/`](docs/executive_branch_document/). See the full stage definitions including all exit criteria with confirmation records dated 2026-03-27 and 2026-03-28 in that folder, or `main:CLAUDE.md` Appendix A.*

---

## Appendix B — Simulation Infrastructure Reference

*Operational content lives in [`docs/executive_branch_document/`](docs/executive_branch_document/). See the seven-layer pipeline, boundary table, Renode test template, and invariant infrastructure documentation there, or `main:CLAUDE.md` Appendix B.*

---

## Appendix C — Signal Plot Template and Review Log

*Operational content lives in [`docs/executive_branch_document/`](docs/executive_branch_document/). See the standard three-panel signal check template and confirmed plot review entries there. Signal plot images are in [`docs/executive_branch_document/plots/`](docs/executive_branch_document/plots/).*

---

## Appendix D — Agentic Co-Design Flow

*Operational content lives in [`docs/executive_branch_document/`](docs/executive_branch_document/). See the full stage-by-stage agent/human responsibility table and decision gates there, or `main:CLAUDE.md` Appendix D.*

---

## Appendix E — HW-SW Co-Design Equivalence Map

*Operational content lives in [`docs/executive_branch_document/`](docs/executive_branch_document/). See the git/software development to hardware co-design equivalence table there, or `main:CLAUDE.md` Appendix E.*

---

## Appendix F — Measurement Philosophy Reference

*Operational content lives in [`docs/executive_branch_document/`](docs/executive_branch_document/). See the derivation chain, three-primitive enforcement rules, and calibration documentation requirements there, or `main:CLAUDE.md` Appendix F.*

---

## The Mission

The goal is not to have the receiving engineer use Claude Code or any AI agent. The goal is that a stubborn old-school hardware fanatic can pick up this work, read the docs, run the simulation, flash the firmware, and independently replicate everything that Claude Code and the developer achieved together — using nothing but a terminal, a compiler, and their own hands.
