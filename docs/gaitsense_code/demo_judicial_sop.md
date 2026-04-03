# Demo SOP — Judicial Session Recording
## Subject: BUG-013 (VABS.F32 Silent SI Zeroing)

**Purpose:** Step-by-step recording guide for a live demo of the GaitSense
judicial hearing process using BUG-013 as the case study. Single terminal
session — Justice runs Claude Code and dispatches agents sequentially.

---

## Why BUG-013

- **Dramatic UART evidence:** all 9 snapshots show `si_stance=0.0%` with true SI=25%
- **Clear clinical stakes:** dangerous false negative — device reports "perfect symmetry" for every asymmetric patient
- **Two genuinely defensible positions:** "it's a sim artifact" vs "silent false negative must be tested"
- **Known outcome:** ruling already in `case_law.md` (VABS.F32 Case, 2026-03-28)

---

## Step 0 — Start the demo

```bash
cd /Users/siyaoshao/gait_device
bash demo_start.sh
claude
```

Then call the judicial-clerk agent to warm up all bureaucratic and attorney agents.

---

## Step 1 — Justice Declares (Pane 4)

Type into the main Claude Code session:

```
I am declaring a Judicial Hearing on BUG-013: VABS.F32 silent SI zeroing.

Competing positions:
- Position A (Amendment 5): Healthy walkers pass all Stage 3 exit criteria.
  VABS.F32 is a Renode 1.16.1 emulator artifact with no clinical consequence
  on real Cortex-M4F hardware.
- Position B (Article I + Amendment 4): The SI computation has never been
  tested under input conditions where the correct answer is non-zero.
  A silent false negative that passes healthy validation is not validated.

The Justice presides. Assign Attorney-A to Position A, Attorney-B to Position B.
```

---

## Step 2 — Assign Attorneys (Pane 4 dispatches Panes 1 and 2)

Launch Attorney-A and Attorney-B in parallel.

**Attorney-A initialization prompt (paste into Pane 1):**

```
You are Attorney-A. The Justice has assigned you Position A in a Judicial
Hearing on BUG-013 (VABS.F32 silent SI zeroing).

Position A: The healthy walker validation results (all four profiles,
SI < 3%, 100/100 steps) satisfy Stage 3 exit criteria under Amendment 5.
The VABS.F32 discrepancy is a Renode 1.16.1 emulator artifact. On real
Cortex-M4F hardware, VABS.F32 executes correctly per ARM architecture
spec. There is no clinical consequence for hardware deployment.

Read docs/gaitsense_code/amendments.md, docs/gaitsense_code/case_law.md,
and src/gait/rolling_window.c before constructing your argument.
Present all four required argument elements.
```

**Attorney-B initialization prompt (dispatch to attorney-B agent):**

```
You are Attorney-B. The Justice has assigned you Position B in a Judicial
Hearing on BUG-013 (VABS.F32 silent SI zeroing).

Position B: The SI computation has never been tested under input conditions
where the correct answer is non-zero. Healthy walkers produce SI=0%
regardless of whether VABS.F32 works correctly — the bug is undetectable
without a pathological test. A function that silently returns a
correct-looking zero on asymmetric input violates Article I (Physics First)
and Amendment 4 (Stage Gate Confirmation): a test that cannot fail is
not a test.

Read docs/gaitsense_code/amendments.md, docs/gaitsense_code/case_law.md,
and src/gait/rolling_window.c before constructing your argument.
Present all four required argument elements.
```

---

## Step 3+4 — Attorneys Argue (dispatched sequentially)

Each attorney presents:
1. Amendment invoked (exact number + title)
2. Precedent cited (case name + date)
3. Physical outcome protected
4. Consequences of opposing position in physical terms

**Do not interrupt.** Let both arguments complete before moving to Step 5.

---

## Step 5 — Justice Requests Evidence

After both arguments, dispatch the simulator-operator and uart-reader agents:

```
Show me the pathological walker UART output — all 9 snapshots.
Also generate the stance timing plot showing odd vs even stance duration.
```

**Evidence commands (run via simulator-operator or directly):**

```bash
# UART evidence: pathological mode, all 4 profiles
cd /Users/siyaoshao/gait_device
python3 -c "
import sys; sys.path.insert(0, 'simulator')
from pipeline import run_all_profiles
results = run_all_profiles(n_steps=100, si_override=25.0)
for r in results:
    print(r)
"

# Stance timing plot (existing evidence script)
python3 diagnostic_imu_analysis.py
```

**Expected UART output (decisive evidence):**
```
SNAPSHOT snap=1  si_stance=0.0%  si_swing=0.0%  cadence=104 spm
SNAPSHOT snap=2  si_stance=0.0%  si_swing=0.0%  cadence=104 spm
...
SNAPSHOT snap=9  si_stance=0.0%  si_swing=0.0%  cadence=104 spm
SESSION_END total_steps=100
─────────────────────────────────────
SUMMARY:
  Steps detected : 100
  Snapshots      : 9
  Final SI       : 0.0%   ← true SI is 25.0%
  Final cadence  : 104 spm
```

---

## Step 6 — Justice Rules (Pane 4)

After UART output and plot appear, type ruling into Pane 4:

```
Position B prevails.

Physical basis (Benjamin Franklin Principle): The UART log shows SI=0.0%
across all 9 snapshots with stance_odd=482ms and stance_even=388ms —
a 24% actual asymmetry that the computation cannot see. The function
produces a correct-looking zero for every asymmetric input. Healthy
walkers were never a test of this path.

Patient outcome (Thomas Jefferson Principle): A patient with genuine gait
asymmetry receives a report of perfect symmetry. This is a dangerous
false negative. The device cannot be deployed under this condition.

Ruling:
1. The pathological walker test (true SI=25%, all four profiles, all
   above 10% clinical threshold) is now a mandatory Stage 3 exit criterion.
2. fabsf() on FPU-register values is banned in this codebase. The
   required replacement is: (diff >= 0.0f) ? diff : -diff
3. Any future clinical-output computation must be validated under input
   conditions where the correct answer is non-zero.

Attorney-B records this ruling in case_law.md before implementation begins.
```

---

## Step 7 — Recording (Pane 2 — Attorney-B)

Attorney-B writes the case_law.md entry using the standard template.
The entry must be committed before any `fabsf()` replacement is implemented.

---

## Evidence Files Referenced

| File | Purpose |
|------|---------|
| `src/gait/rolling_window.c` | Contains `compute_si_x10()` with the fabsf() call |
| `diagnostic_imu_analysis.py` | Generates stance timing comparison plot |
| `docs/executive_branch_document/plots/stair_vs_flat_imu_diagnostic.png` | Existing 4-panel IMU comparison |
| `docs/gaitsense_code/amendments.md` | Attorneys must read before arguing |
| `docs/gaitsense_code/case_law.md` | Attorneys must read; ruling written here |

---

## Key Visual Moments for Recording

| Timestamp | What to show | Why it matters |
|-----------|-------------|----------------|
| Step 1 | Justice types declaration | Shows the governance system activating |
| Step 2 | Both Panes 1+2 start simultaneously | Shows parallel attorney launch |
| Step 3+4 | Attorneys citing amendment numbers | Shows constitutional grounding |
| Step 5 | UART output filling Pane 3 | Shows evidence generation on demand |
| Step 5 | `Final SI : 0.0%` line | The decisive evidence moment |
| Step 5 | Matplotlib popup | Visual confirmation of stance asymmetry |
| Step 6 | Justice ruling typed | Human stays in control |
| Step 7 | Attorney-B writes case_law.md | Shows record-before-implementation rule |
