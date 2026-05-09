# DFT FACTORY — Bootstrap Session

**This is the FIRST file every AI session must read before any work.**

---

## Project Identity

- **Project:** DFT Factory — Unified DFT Automation Platform
- **Domain:** Design-for-Test (DFT) engineering for IC designs
- **EDA Tools:** Synopsys TetraMAX (tmax), Siemens Tessent
- **User:** DFT/hardware engineer — Nikhil Dave
- **Repo root:** `C:/Nikhil/DFT/dft_ai`

---

## Current Stable State

| Field | Value |
|-------|-------|
| **Branch** | `phase2-stable` |
| **Commit** | `9f3a04f19d966d5059a07cc9c196dcca897edd86` |
| **Phase** | Phase 3, Stage 1 — Audit/Traceability (built, integration in progress) |
| **Active Task** | `TASK_HTML_PARSER_HARDENING.md` — validate and harden TetraMAX HTML command parser |

---

## Architecture State

```
Phase 2 (complete): Infrastructure proven — unified factory, local Ollama + Qwen,
                    LiteLLM proxy, Aider integration, validator L1-L4, semantic graph

Phase 3 Stage 1 (in progress): Audit logger built (core/audit_logger.py),
                                events.jsonl schema standardized, AUDIT_SPEC.md written
                                → Integration into orch_run.py / harvest.py pending

Phase 3 Stage 2-9: NOT YET STARTED — do NOT jump ahead
```

### Canonical Paths

| Path | Purpose |
|------|---------|
| `DFT_FACTORY/config/factory_config.py` | Single source of truth — all paths, registries, schemas |
| `DFT_FACTORY/core/utils.py` | Shared helpers — imported by all core scripts |
| `DFT_FACTORY/core/dir_init.py` | Step 1 — create iteration tree |
| `DFT_FACTORY/core/orch_run.py` | Step 2 — launch EDA tool |
| `DFT_FACTORY/core/harvest.py` | Step 3 — normalize outputs |
| `DFT_FACTORY/core/lifecycle.py` | Step 4 — tag/list/purge/trend CSV |
| `DFT_FACTORY/core/audit_logger.py` | Audit system — append-only event logging |
| `DFT_FACTORY/tcl/SYNOPSYS/_factory_helpers.tcl` | TCL helper procs (wrpt, wlog, wdb, wout) |
| `DFT_FACTORY/tools/env_gate.sh` | Tool environment gate |
| `DFT_FACTORY/logs/events/events.jsonl` | Immutable audit trail — append-only |
| `DFT_FACTORY/AUDIT_SPEC.md` | Audit system specification |
| `DFT_FACTORY/ROADMAP.md` | Phase 3 implementation sequence |
| `DFT_FACTORY/DECISIONS.md` | Architecture Decision Records index |
| `DFT_FACTORY/CHANGELOG.md` | Version history |
| `DFT_FACTORY/README_ARCHITECTURE.md` | Full system architecture |
| `DFT_FACTORY/SESSION_CONTINUE.md` | Prior session handoff notes |
| `DFT_FACTORY/tasks/TASK_HTML_PARSER_HARDENING.md` | Active task definition |
| `parse_html_structured.py` | (repo root) HTML parser — target of active hardening task |

---

## Mandatory Startup Procedure

Every new AI session MUST execute these steps in order:

1. **Read this file** — you are doing this now
2. **Verify branch:**
   ```bash
   git branch --show-current   # must be phase2-stable
   ```
3. **Read the active task:**
   ```bash
   cat DFT_FACTORY/tasks/TASK_HTML_PARSER_HARDENING.md
   ```
4. **Check audit log health:**
   ```bash
   wc -l DFT_FACTORY/logs/events/events.jsonl
   ```
5. **Read AUDIT_SPEC.md** if doing any mutative work:
   ```bash
   cat DFT_FACTORY/AUDIT_SPEC.md
   ```
6. **Report to user:**
   - Current branch + commit
   - Active task + status
   - Any anomalies in audit log or repo state

---

## Non-Negotiable Rules

### R1 — Deterministic validation > AI confidence
AI consensus is NOT proof of correctness. Tier 4 (pytest, TCL dry-run, schema check) is the final gate. Always.

### R2 — One active task at a time
No parallel task execution. Complete the current active task before beginning another.
Currently: **TASK_HTML_PARSER_HARDENING.md**

### R3 — All mutations must be logged
Every file create/modify/delete MUST emit an event via `core/audit_logger.py` → `logs/events/events.jsonl`.
If it's not in events.jsonl, it didn't happen.

### R4 — No autonomous agents (yet)
Multi-agent orchestration (Tier 1-4) is designed but NOT activated. Do not spawn autonomous agents.
The orchestrator, critic, and validation pipeline exist in spec only.

### R5 — One orchestration lifecycle
All AI actions flow through: Plan → Critique → Execute → Validate → Log → Merge.
No random multi-agent workflows.

### R6 — Preserve rollbackability
Every session records lineage. Every change must be revertible.
`events.jsonl` is append-only — no edits, no deletions. If a mistake was made, log a new `revert` event.

### R7 — Do NOT add tools faster than architecture
One stable system > five chaotic ones. Governance > new tools.

### R8 — config/ is the single source of truth
Never hardcode paths, tool names, or stage definitions outside `factory_config.py`.

---

## Required Logging Behavior

Every mutative action must call `core/audit_logger.py`:

```python
from core.audit_logger import log_file_change, log_event, generate_session_id

# File changes
log_file_change(session_id, file_path, change_type="modify", ...)

# Test runs
log_test_result(session_id, test_type="pytest", passed=True, ...)

# Architecture decisions
log_decision(session_id, title="...", status="proposed", ...)
```

**events.jsonl schema (8 mandatory fields):**
`timestamp`, `session_id`, `actor`, `action`, `target`, `reason`, `approved_by`, `tests_passed`, `rollback_possible`

---

## Workflow Lifecycle

```
1. Read BOOTSTRAP_SESSION.md        ← YOU ARE HERE
2. Read active task definition
3. Read AUDIT_SPEC.md (if mutating)
4. Plan → get user approval
5. Execute → log every file change
6. Validate → deterministic checks pass
7. Log completion → update task status
8. Report summary to user
```

---

## Known Issues

| Issue | Status |
|-------|--------|
| KPI regex patterns in `lifecycle.py` need tuning against real TMAX output | Unresolved |
| Chain resolver (`chain_from`) not fully auto-symlinking upstream outputs | Manual workaround |
| Tessent TCL templates not yet written (`tcl/TESSENT/` is empty) | Pending |
| HTML parser (`parse_html_structured.py`) — description extraction fixed, validation phase needed | Active task |

---

## Session Startup Command

Paste this exact prompt to begin a new session:

```
Read DFT_FACTORY/BOOTSTRAP_SESSION.md first.
Then read DFT_FACTORY/tasks/TASK_HTML_PARSER_HARDENING.md.
Report current branch, commit, active task, and audit log status.
Do not modify anything until I give direction.
```

---

## Session Recovery

If a prior session was interrupted:

1. Read `DFT_FACTORY/SESSION_CONTINUE.md` for last stopping point
2. Check `git status` for uncommitted changes
3. Check `DFT_FACTORY/logs/events/events.jsonl` for last logged action
4. Resume from the next step in the active task