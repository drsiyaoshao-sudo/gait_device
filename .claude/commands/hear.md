Declare and run a Judicial Hearing under the GaitSense Constitutional Governance system.

Usage: /hear "<hearing name>" <position-A-description> vs <position-B-description>

Examples:
  /hear "BLE MTU vs USB CDC as primary debug path" "BLE NUS primary — matches production path" vs "USB CDC primary — deterministic, no fragmentation"
  /hear "Arduino vs Zephyr re-evaluation" "unblock Zephyr — new overlay evidence" vs "keep Arduino — Amendment 16 block stands"
  /hear "SI computation fabsf workaround" "remove BUG-013 workaround on real hardware" vs "keep workaround — compiler optimisation risk persists"

If no arguments given, print this usage and the 7-step procedure below, then stop.

---

## Step 1 — Warm the courtroom

Invoke the judicial-clerk agent immediately. It will:
- Verify agent roster (attorney-A, attorney-B, simulator-operator, plotter, uart-reader)
- Print COURTROOM READY before any argument begins

Do not proceed past Step 1 until judicial-clerk prints COURTROOM READY.

---

## Step 2 — Print hearing declaration

Print the following with the hearing name and positions filled in:

```
══════════════════════════════════════════════════════════════
JUDICIAL HEARING DECLARED
Hearing: <hearing name>
Position A: <position-A-description>
Position B: <position-B-description>

Constitutional grounding to check before arguing:
  docs/gaitsense_code/amendments.md       — all ratified amendments (1–17)
  docs/gaitsense_code/case_law.md         — all recorded precedents
  docs/toolchain_config.md               — active toolchain, blocked tools, pin map, repo registry
  CLAUDE.md Judicial Process §3–4         — Benjamin Franklin + Thomas Jefferson principles

Evidence commands available during this hearing:
  /plot-evidence signal <profile>         — IMU signal plot
  /plot-evidence sim <profile>            — full simulation evidence (UART + signal)
  /plot-evidence uart <log_path>          — UART session output from Renode log
══════════════════════════════════════════════════════════════
```

---

## Step 3 — Assign attorneys and launch arguments (parallel)

Assign Attorney-A to Position A and Attorney-B to Position B (or reverse — assignment is random).
Launch both attorney agents in parallel. Each must:
1. Read `docs/gaitsense_code/amendments.md`
2. Read `docs/gaitsense_code/case_law.md`
3. Read any source files directly relevant to their position
4. Present all four required argument elements:
   - Amendment(s) invoked (exact number and title)
   - Precedent (case name and date, or explicit statement of none)
   - Physical/clinical outcome protected
   - Consequences of opposing position in physical terms

---

## Step 4 — Evidence collection (if Justice requests it)

Use /plot-evidence to generate requested evidence. Evidence commands run as Bureaucracy
Standing Orders — no Bill or hearing required. The Justice may request evidence at any
point between Step 3 and Step 6.

---

## Step 5 — Clarifying questions (Justice only)

The Justice may ask each attorney one clarifying question. The attorney answers only
the question asked. Print each Q&A clearly labelled:
  JUSTICE → ATTORNEY-A: <question>
  ATTORNEY-A: <answer>

---

## Step 6 — Ruling

The Justice announces:
- Which position prevails
- The governing physical/empirical basis (Benjamin Franklin Principle)
- The ultimate patient/hardware outcome protected (Thomas Jefferson Principle)
- Any conditions or constraints on how the ruling is applied

---

## Step 7 — Record to case law

The prevailing attorney writes the ruling to `docs/gaitsense_code/case_law.md`
using the standard case law template. The record must be complete before any
implementation work begins. This is a hard gate — implementation cannot start
until the ruling is recorded.

Standard case law entry format:
```
### Case [N]: [Hearing Name]
**Date:** [date]
**Positions:** A — [description] | B — [description]
**Prevailing position:** [A or B]
**Justice's ruling:** [ruling text]
**Physical/empirical basis:** [evidence cited]
**Patient outcome protected:** [Thomas Jefferson statement]
**Conditions:** [any constraints on application]
**Enacted bill (if any):** [bill name, or "none"]
**Implementation branch:** [branch name, or "none"]
```

---

## Nested Hearing Protocol

If a nested hearing must be declared during argument (Step 3–5):
1. Pause the current hearing — print PARENT HEARING PAUSED
2. Complete the nested hearing fully (Steps 1–7)
3. Resume parent hearing — print PARENT HEARING RESUMED
4. The child ruling is new evidence for the parent hearing; do not re-debate it

---

## Constitutional References

This command implements CLAUDE.md Judicial Process §1–5.
- §1 Jurisdiction: conflict between amendments, unaddressed situation, agent uncertainty
- §2 Roles: Justice (human), Attorneys (AI), Record (case_law.md)
- §3 Benjamin Franklin Principle: empirical evidence only
- §3a Thomas Jefferson Principle: best patient/hardware outcome governs
- §4 Hearing Procedure: the 7 steps above
- §5 Binding Effect: ruling governs all future agents until explicitly overruled

Now invoke the judicial-clerk agent, then print the hearing declaration with "$ARGUMENTS" parsed as:
  First quoted string = hearing name
  Text after first "vs" = position B description
  Text between hearing name and "vs" = position A description
If parsing fails, print usage and stop.
