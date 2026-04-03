# Judicial Session Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                        JUSTICE (human)                          │
│                   declares judicial hearing                     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      JUDICIAL-CLERK                             │
│  1. Print hearing header + timestamp                            │
│  2. Verify agent roster:                                        │
│       attorney-A ✓  attorney-B ✓                               │
│       simulator-operator ✓  plotter ✓  uart-reader ✓           │
│  3. Print COURTROOM READY                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        JUSTICE                                  │
│  Declares hearing: case name + Position A + Position B          │
│  Assigns Attorney-A → Position A                                │
│  Assigns Attorney-B → Position B                                │
└──────────────┬──────────────────────────────┬───────────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│       ATTORNEY-A         │    │         ATTORNEY-B           │
│  Reads:                  │    │  Reads:                      │
│    amendments.md         │    │    amendments.md             │
│    case_law.md           │    │    case_law.md               │
│    relevant src file     │    │    relevant src file         │
│  Argues Position A:      │    │  Argues Position B:          │
│    1. Amendment invoked  │    │    1. Amendment invoked      │
│    2. Precedent cited     │    │    2. Precedent cited        │
│    3. Physical outcome   │    │    3. Physical outcome       │
│    4. Opposing risk      │    │    4. Opposing risk          │
└──────────────┬───────────┘    └──────────────┬───────────────┘
               │                              │
               └──────────────┬───────────────┘
                              │  both arguments complete
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        JUSTICE                                  │
│              requests physical evidence                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SIMULATOR-OPERATOR                            │
│  1. Validate firmware ELF (BUG-005 guard)                       │
│  2. Generate IMU signals from walker profiles                   │
│  3. Launch Renode, feed IMU stub                                │
│  4. Run declared profile × declared mode (healthy/pathological) │

│  5. Dispatch uart-reader ──────────────────────────────────┐   │
│  6. Dispatch plotter ──────────────────────────────────┐   │   │
│  7. Print results summary table                        │   │   │
└────────────────────────────────────────────────────────│───│───┘
                                                         │   │
                            ┌────────────────────────────┘   │
                            ▼                                │
┌───────────────────────────────────────┐                    │
│             UART-READER               │                    │
│  Reads UART log / serial port         │                    │
│  Prints structured table:             │                    │
│    STEP lines  → ts, acc, gyr, cad    │                    │
│    SNAPSHOT    → SI stance/swing      │                    │
│    SESSION_END → steps, final SI      │                    │
│  Prints summary: steps, SI, cadence   │                    │
└───────────────────────────────────────┘                    │
                                                             │
                            ┌────────────────────────────────┘
                            ▼
┌───────────────────────────────────────┐
│               PLOTTER                 │
│  Generate diagnostic signal plots     │
│  Apply firmware-matched filters       │
│  Annotate: step markers, thresholds,  │
│    zero-crossings, timing gaps        │
│  Print data table to stdout           │
│  Save → docs/.../plots/<name>.png     │
│  If GAITSENSE_DEMO=1:                 │
│    open <plot_path>  ← Preview pops  │
└───────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        JUSTICE                                  │
│  Reviews UART table + plot                                      │
│  Applies Benjamin Franklin Principle (empirical basis)          │
│  Applies Thomas Jefferson Principle (best patient outcome)      │
│  Issues ruling: Position A or Position B prevails              │
│  States physical basis + patient outcome consequence            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ATTORNEY-B                                │
│  (prevailing or losing — clerk duty falls to Attorney-B)        │
│  Writes ruling to case_law.md using standard template           │
│  Commit required before any implementation begins              │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Responsibility Matrix

| Step | Actor | Trigger | Output |
|------|-------|---------|--------|
| 0 | Justice | Human declares | Hearing parameters |
| 1 | Judicial-Clerk | Justice calls clerk | Agent roster confirmed, COURTROOM READY |
| 2 | Attorney-A | Justice assigns Position A | 4-part argument |
| 2 | Attorney-B | Justice assigns Position B | 4-part argument |
| 3 | Simulator-Operator | Justice declares profile + mode | Runs declared profile only, results table |
| 3 | UART-Reader | Dispatched by simulator-operator | Formatted UART table |
| 3 | Plotter | Dispatched by simulator-operator | Plot saved + opened in Preview |
| 4 | Justice | Evidence received | Ruling with physical basis |
| 5 | Attorney-B | Ruling issued | case_law.md entry committed |
