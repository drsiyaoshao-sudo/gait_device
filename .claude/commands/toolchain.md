Toolchain Janitor — gatekeeper and RAG setter for all hardware, pin, firmware library, and repository configuration.

This command is the single entry point for recording, updating, and validating what tools,
libraries, and boards are in use. Every other agent (/session, /hear, /plot-profile) reads
from docs/toolchain_config.md before acting. This command is the only thing that writes it.

Usage: /toolchain <subcommand> [args]

Subcommands:
  status                  — print current toolchain config in full
  init                    — interactive setup from scratch (prompts for each section)
  add hw                  — add or update the hardware record (board, MCU, IMU)
  add pins                — add or update pin map entries
  add lib <name>          — add a firmware library (name, version, source, purpose)
  add repo <path_or_url>  — register a git repository (path/URL, branch, purpose)
  block <label>           — mark a toolchain layer as blocked (prompts for reason)
  unblock <label>         — propose lifting a block (requires /hear — cannot self-approve)
  lock                    — mark config as Stage 0 validated (requires Stage 0 pass evidence)
  validate                — run gatekeeper checks: conflicts, amendment violations, missing fields
  diff                    — show what has changed since last lock

If no subcommand: print status and list available subcommands.

---

## The Config File

All state lives in `docs/toolchain_config.md`.
- Human-readable and human-editable at any time
- Structured with section headers so agents can grep for specific records
- Version-controlled — every janitor write is a git commit
- The janitor never overwrites human edits without showing a diff first

Agents that need toolchain context must read this file first. They must not assume a toolchain
from CLAUDE.md amendments alone — amendments say what is allowed, the config file says what
is currently wired up.

---

## Subcommand Procedures

### /toolchain status

Read `docs/toolchain_config.md` in full and print:
1. Lock status and date
2. Hardware summary (one line per device)
3. Active toolchain table
4. Blocked toolchain log
5. Library manifest (name + version)
6. Repo registry (name + purpose)
7. Any validation warnings (missing required fields, blocked toolchain in active slot)

---

### /toolchain init

Interactive setup. Ask the human for each section in order. After each section,
print what you recorded and ask for confirmation before continuing to the next.
Do not guess values — every field must come from human input or be explicitly left blank.

Sections in order:
1. Hardware record (board, MCU, IMU)
2. Pin map
3. Active firmware toolchain
4. Blocked toolchains
5. Firmware libraries
6. Git repositories

After all sections: run validate, then ask Justice to confirm before writing the file.

---

### /toolchain add hw

Prompt for:
- Board model (e.g., "Seeed XIAO nRF52840 Sense 102010448")
- MCU (e.g., "nRF52840, ARM Cortex-M4F, 64 MHz")
- Sensors on board (e.g., "LSM6DS3TR-C IMU, I2C 0x6A, WHO_AM_I=0x6A")
- Any external hardware (PPK2, J-Link, oscilloscope, etc.)
- Notes (e.g., "Must be Sense variant — on-board IMU only on Sense, not standard")

Write to Hardware section of docs/toolchain_config.md.

---

### /toolchain add pins

Prompt for each pin entry:
- Signal name (e.g., "IMU_POWER", "IMU_SDA", "LED_RED")
- Arduino pin number (e.g., "15", "4", "—")
- nRF52840 port/pin (e.g., "P1.08", "P0.07")
- Function description
- Caution if any (e.g., "P0.27 = SCL — do not use as button")

Present current pin map before prompting, so human can see what already exists and choose
to add, update, or remove entries.

Write to Pin Map section of docs/toolchain_config.md.

---

### /toolchain add lib <name>

Prompt for:
- Library name
- Version (exact — not "latest")
- Source (Arduino library manager ID, GitHub URL, or local path)
- Purpose (one sentence: what it enables in this project)
- Known issues or patches (e.g., "setBitOrder() removed on ARDUINO_ARCH_MBED — patched in LSM6DS3.cpp")

Write to Library Manifest section. If library already exists, show diff before overwriting.

---

### /toolchain add repo <path_or_url>

Prompt for:
- Repo path (local) or URL (remote)
- Active branch
- Purpose (one sentence: what this repo contributes)
- Agent commands or scripts available in this repo that are usable cross-repo
- Access notes (e.g., "read-only reference — do not commit here from gait_device sessions")

Write to Repository Registry section.

---

### /toolchain block <label>

Prompt for:
- Which toolchain layer is being blocked (build, flash, serial monitor, simulation, etc.)
- The specific tool/framework being blocked
- Reason (must cite a failure mode — Amendment 7 three-strike rule evidence, or Amendment 16 block)
- Date
- What triggered the block (test result, error message, simulation failure)

Gatekeeper rule: a block recorded here is binding on all agents. An agent that attempts to
use a blocked toolchain must stop and report the block to the human rather than proceeding.

Write to Blocked Toolchains section.

---

### /toolchain unblock <label>

This subcommand cannot complete by itself. It must:
1. Show the current block record
2. Print: "Unblocking a toolchain requires a Judicial Hearing per Amendment 16."
3. Prompt: "Invoke /hear to open a hearing on this unblock? (yes/no)"
4. If yes: invoke /hear with a pre-filled declaration:
   Hearing: "Unblock [label] toolchain"
   Position A: "lift block — [human's reason]"
   Position B: "keep block — prior failure evidence stands"
5. Do not modify docs/toolchain_config.md until the Justice rules in favour of unblocking.

---

### /toolchain lock

Mark the config as Stage 0 validated. Requires the human to confirm:
- Stage 0 HIL smoke tests passed (counter ✓, IMU ✓, algo USB ✓, algo BLE ✓)
- All four test pass evidence logged (timestamps or session log path)

Print a lock summary:
```
══════════════════════════════════════════════════════════════
TOOLCHAIN CONFIG LOCKED
Date: [date]
Stage 0 evidence: [log path or "confirmed by human"]
Hardware: [board name]
Active firmware toolchain: [FQBN]
Libraries: [N] registered
Repos: [N] registered
Blocked: [N] toolchain layers
══════════════════════════════════════════════════════════════
```

Write lock record to docs/toolchain_config.md and commit.

---

### /toolchain validate

Run all gatekeeper checks. Print a report for each check.

Checks:
1. **Blocked toolchain in active slot** — if any layer's active tool appears in the Blocked list, flag as ERROR
2. **Missing required fields** — Hardware: board, MCU, IMU. Toolchain: build FQBN, flash method, serial monitor. Flag blank required fields as WARNING
3. **Library version pinned** — any library with version = "latest" or blank → WARNING
4. **Amendment 17 alignment** — active toolchain table in config must match the table in docs/gaitsense_code/amendments.md. Mismatch → ERROR
5. **Repo paths exist** — for local repo paths: check the path exists on disk. Missing → WARNING
6. **Pin conflicts** — if two signals share the same nRF52840 port/pin → ERROR (e.g., P0.27 as both SCL and button)
7. **Blocked toolchain without reason** — a block entry with no failure mode cited → WARNING (Amendment 7 requires evidence)

Print each check as:
  [PASS]    <check name>
  [WARNING] <check name> — <detail>
  [ERROR]   <check name> — <detail> — must resolve before Stage 0

Overall result:
  CLEAN — all checks pass
  WARNINGS ONLY — can proceed; review warnings
  ERRORS PRESENT — do not proceed with Stage 0 until errors resolved

---

### /toolchain diff

Compare the current docs/toolchain_config.md against the last locked version (git):
```bash
git diff HEAD~1 docs/toolchain_config.md
```

Print a human-readable summary of what changed since the last lock:
- New hardware added
- Pin map changes
- Libraries added/updated
- Repos added
- Blocks added or lifted
- Lock status changed

---

## Gatekeeper Rules (for all other agents)

When any agent (/session, /hear, /plot-profile, simulator-operator, etc.) is about to
take a toolchain-dependent action, it must:

1. Read docs/toolchain_config.md
2. Check that the tool it is about to use is in the Active Toolchain section
3. Check that the tool is NOT in the Blocked Toolchains section
4. If blocked: stop and print:
   "TOOLCHAIN BLOCKED: [tool] is recorded as blocked in docs/toolchain_config.md.
    Reason: [reason]. Use /toolchain unblock to propose lifting this block."
5. If not found in either list: stop and print:
   "TOOLCHAIN NOT REGISTERED: [tool] is not in docs/toolchain_config.md.
    Use /toolchain add to register it before use."

This rule applies to: build tools, flash methods, serial monitor tools, Python packages,
simulation frameworks, and external hardware interfaces.

---

## RAG Usage by Other Agents

Every agent that needs toolchain context should read these specific sections from
docs/toolchain_config.md (grep targets):

| Agent need | Section to read |
|-----------|----------------|
| What FQBN to build for | `## Active Firmware Toolchain` |
| What pin is the IMU on | `## Pin Map` |
| What library version to use | `## Library Manifest` |
| Is this toolchain blocked? | `## Blocked Toolchains` |
| What repos can I reference? | `## Repository Registry` |
| What board is connected? | `## Hardware` |

Agents must not ask the human for toolchain details that are already in this file.
If the file is missing or incomplete for the required section, run /toolchain validate
and report the gaps to the human before proceeding.

---

## Constitutional References

- Article II: no toolchain switch without human decision (the block/unblock gate enforces this)
- Amendment 7: three-strike rule — block entries in this file are the formal record of strikes
- Amendment 16: smoke test order and path switching rule (Stage 0 lock = HIL confirmation)
- Amendment 17: toolchain alignment — this file is the live implementation of Amendment 17's active toolchain record

Now parse "$ARGUMENTS":
  First word is the subcommand (status, init, add, block, unblock, lock, validate, diff).
  For "add": second word is the type (hw, pins, lib, repo).
  For "block" / "unblock": remaining words are the label.
  If no subcommand: print status then list subcommands.
