# DFT FACTORY — Audit & Traceability System Specification

**Status:** 🔲 Proposed  
**Target:** Phase 3, Stage 1  
**Precedent:** ADR-003 (see `DECISIONS.md`)

This document defines the audit system BEFORE any implementation.
Read this first. Code must match this spec exactly.

---

## 1. Purpose

Provide an **immutable, machine-readable event stream** that makes every engineering action traceable:

- Who changed what, when, why
- Which AI model generated it
- What prompt was used
- What tests passed/failed
- Can it be rolled back
- What was the discussion/reasoning

**Without this:** AI actions are opaque, regressions are untraceable, and "why was this file modified?" becomes unanswerable.

---

## 2. Directory Structure

```
DFT_FACTORY/logs/
├── events/
│   └── events.jsonl          ← append-only event stream (ONE per factory)
├── discussions/
│   ├── sess_abc123_disc1.md    ← prompt/response pairs, AI debates
│   ├── sess_abc123_disc2.md
│   └── ...
├── decisions/
│   ├── ADR-001-phase-index-system.md
│   ├── ADR-003-audit-schema.md
│   └── ...
├── test_runs/
│   ├── sess_abc123_pytest.jsonl
│   ├── sess_abc123_tcl_dryrun.log
│   └── ...
├── artifacts/
│   ├── sess_abc123_patch_001.diff
│   ├── sess_abc123_arch_plan.md
│   └── ...
└── sessions/
    ├── sess_abc123_meta.json  ← session metadata
    └── sess_abc123_summary.md
```

**Rules:**
- `events.jsonl` is the **single source of truth** for all actions
- All other dirs are **derived** from events (not independent)
- `events.jsonl` is **append-only** — no edits, no deletions
- Session ID (`sess_xxx`) links all artifacts for one session

---

## 3. Event Schema (MANDATORY)

Every line in `events.jsonl` is a complete JSON object. No multi-line JSON.

### 3.1 Core Fields (ALL events MUST have these)

```json
{
  "timestamp":     "2026-05-08T14:30:00+00:00",
  "session_id":   "sess_abc123",
  "actor":        "Claude|Gemini|Qwen|User|Orchestrator|Orchestrator",
  "action":       "create_file|modify_file|delete_file|run_test|merge|revert|discuss|decide",
  "target":       "validator_l3.py",
  "reason":       "Added L3 context validation for set_atpg",
  "approved_by":  "Nikhil",
  "tests_passed": true,
  "rollback_possible": true
}
```

### 3.2 Action-Specific Fields

#### `create_file` / `modify_file` / `delete_file`

```json
{
  "timestamp":       "...",
  "session_id":     "sess_abc123",
  "actor":          "Qwen",
  "action":          "modify_file",
  "target":          "validator_l3.py",
  "reason":          "Added L3 context validation",
  "approved_by":      "Nikhil",
  "tests_passed":    true,
  "rollback_possible": true,
  "model_used":      "ollama/qwen2.5-coder:7b-instruct-q4_K_M",
  "prompt":          "Add L3 validation for set_atpg -ndetects",
  "diff_generated":  "/logs/artifacts/sess_abc123_patch_001.diff",
  "dependencies":     ["validator.py", "validator_l2.py"],
  "commit_hash":     "e7c7609",
  "lines_added":     45,
  "lines_removed":   12
}
```

#### `run_test`

```json
{
  "timestamp":       "...",
  "session_id":     "sess_abc123",
  "actor":          "Validator",
  "action":          "run_test",
  "target":          "pytest",
  "reason":          "Post-merge validation",
  "approved_by":      "Nikhil",
  "tests_passed":    true,
  "rollback_possible": true,
  "test_type":        "pytest|tcl_dryrun|schema_check|syntax_check",
  "passed":           true,
  "failed":           0,
  "output_file":     "/logs/test_runs/sess_abc123_pytest.jsonl",
  "duration_s":       3.2
}
```

#### `discuss`

```json
{
  "timestamp":       "...",
  "session_id":     "sess_abc123",
  "actor":          "Gemini",
  "action":          "discuss",
  "target":          "validator_l3.py refactoring",
  "reason":          "Architecture review",
  "approved_by":      "Nikhil",
  "tests_passed":    false,
  "rollback_possible": true,
  "discussion_id":   "sess_abc123_disc1",
  "participants":     ["Gemini", "DeepSeek", "User"],
  "topic":           "Whether to split L3 into two classes",
  "consensus":        "Split into L3Validator and L3Advisor",
  "dissenting":       ["DeepSeek"]
}
```

#### `decide`

```json
{
  "timestamp":       "...",
  "session_id":     "sess_abc123",
  "actor":          "User",
  "action":          "decide",
  "target":          "ADR-005-deterministic-validation",
  "reason":          "Need deterministic gate before merge",
  "approved_by":      "Nikhil",
  "tests_passed":    false,
  "rollback_possible": true,
  "decision_id":      "ADR-005",
  "title":           "Deterministic Validation Layer",
  "status":           "accepted|proposed|rejected|deprecated",
  "alternatives":     ["AI voting", "Trust Tier 1-2 consensus"]
}
```

#### `merge` / `revert`

```json
{
  "timestamp":       "...",
  "session_id":     "sess_abc123",
  "actor":          "Orchestrator",
  "action":          "merge",
  "target":          "validator_l3.py",
  "reason":          "All tests passed, Tier 3 approved",
  "approved_by":      "Nikhil",
  "tests_passed":    true,
  "rollback_possible": true,
  "commit_hash":     "f1a2b3c",
  "files_changed":    ["validator_l3.py", "CONVENTIONS.md"],
  "session_files":    ["sess_abc123_patch_001.diff", "sess_abc123_disc1.md"]
}
```

---

## 4. Actor Taxonomy

| Actor | Meaning | Example Models |
|-------|---------|----------------|
| `User` | Human (Nikhil) | — |
| `Claude` | Claude Opus/Sonnet/Haiku | claude-opus-4-7 |
| `Gemini` | Google Gemini models | gemini/gemini-2.5-pro |
| `Qwen` | Qwen2.5 Coder (local) | ollama/qwen2.5-coder:7b |
| `DeepSeek` | DeepSeek models | openrouter/deepseek/deepseek-chat |
| `Orchestrator` | Multi-agent coordinator | — |
| `Validator` | Deterministic test runner | — |
| `Orchestrator` | System auto-action | — |

**Rule:** `Orchestrator` is used when the system auto-logs (e.g., auto-merge after all gates pass).

---

## 5. Session Lifecycle

```
User starts session
    → session_id generated (sess_xxx)
    → logs/sessions/sess_xxx_meta.json created
    ↓
Action 1: modify_file
    → log_event() → events.jsonl (1 line)
    → diff saved to artifacts/sess_xxx_patch_NNN.diff
    ↓
Action 2: discuss
    → log_discussion() → events.jsonl (1 line)
    → discussion saved to discussions/sess_xxx_discN.md
    ↓
Action 3: run_test
    → log_test_result() → events.jsonl (1 line)
    → test output to test_runs/sess_xxx_pytest.jsonl
    ↓
Action 4: decide
    → log_decision() → events.jsonl (1 line)
    → decision to decisions/ADR-NNN-title.md
    ↓
Action 5: merge
    → log_event() → events.jsonl (1 line)
    → git commit (commit_hash recorded)
    ↓
Session ends
    → logs/sessions/sess_xxx_summary.md written
```

---

## 6. Query Patterns (What You Must Be Able to Answer)

After implementation, these queries MUST be possible:

### 6.1 "Why was validator_l3.py modified?"
```bash
grep '"target".*"validator_l3.py"' logs/events/events.jsonl | python -m json.tool --sort-keys
```

### 6.2 "Which AI introduced this regression?"
```bash
grep '"action".*"modify_file"' logs/events/events.jsonl | \
grep '"target".*"validator_l3.py"' | \
python -c "import sys,json; [print(json.loads(l)['actor'],json.loads(l)['commit_hash']) for l in sys.stdin]"
```

### 6.3 "Show all changes touching ATPG_SAF.tcl"
```bash
grep '"target".*"ATPG_SAF.tcl"' logs/events/events.jsonl
```

### 6.4 "Which sessions failed validation?"
```bash
grep '"action".*"run_test"' logs/events/events.jsonl | \
grep '"passed".*false'
```

### 6.5 "Regressions introduced by which model?"
```bash
grep '"action".*"modify_file"' logs/events/events.jsonl |
python -c "
import sys, json
for l in sys.stdin:
    e = json.loads(l)
    if not e.get('tests_passed', True):
        print(e['timestamp'], e['actor'], e['model_used'], e['target'])
"
```

---

## 7. Log Functions (to implement in `core/audit_logger.py`)

### 7.1 `log_event(**kwargs)` — Core function

**Responsibility:** Append one line to `logs/events/events.jsonl`.

**Signature:**
```python
def log_event(
    session_id:     str,
    actor:         str,
    action:         str,
    target:         str,
    reason:         str,
    approved_by:    str = "",
    tests_passed:   bool = False,
    rollback_possible: bool = True,
    **extra_fields        # action-specific fields
) -> None:
```

**Behavior:**
1. Create `logs/events/` dir if not exists
2. Build dict with ALL fields (core + extra)
3. Add `"timestamp"`: current UTC ISO 8601
4. Append as single JSON line to `logs/events/events.jsonl`
5. Never overwrite — always append

---

### 7.2 `log_discussion(**kwargs)`

**Responsibility:** Log a discussion event + save full transcript.

```python
def log_discussion(
    session_id:     str,
    topic:          str,
    participants:   list[str],
    transcript:    str,       # full prompt/response pairs
    consensus:      str,
    dissenting:     list[str] = [],
    **kwargs                # passed to log_event()
) -> str:          # returns discussion_id
```

**Behavior:**
1. Generate `discussion_id = f"{session_id}_disc{N}"` (auto-increment)
2. Write transcript to `logs/discussions/{discussion_id}.md`
3. Call `log_event(action="discuss", discussion_id=discussion_id, ...)`

---

### 7.3 `log_decision(**kwargs)`

**Responsibility:** Log an architecture decision + write ADR file.

```python
def log_decision(
    session_id:     str,
    title:          str,
    status:          str = "proposed",  # proposed|accepted|rejected|deprecated
    context:        str = "",
    decision:       str = "",
    alternatives:    list[str] = [],
    consequences:    str = "",
    **kwargs                # passed to log_event()
) -> str:          # returns decision_id
```

**Behavior:**
1. Generate `decision_id = f"ADR-{NNN}-{slug}"` (auto-increment)
2. Write full ADR to `logs/decisions/{decision_id}.md`
3. Append to `DECISIONS.md` index
4. Call `log_event(action="decide", decision_id=decision_id, ...)`

---

### 7.4 `log_test_result(**kwargs)`

**Responsibility:** Log a test run + save output.

```python
def log_test_result(
    session_id:     str,
    test_type:      str,       # pytest|tcl_dryrun|schema_check
    passed:         bool,
    failed:          int = 0,
    output:          str = "",    # raw output text
    duration_s:     float = 0.0,
    **kwargs                # passed to log_event()
) -> None:
```

**Behavior:**
1. Write output to `logs/test_runs/{session_id}_{test_type}.{ext}`
2. Call `log_event(action="run_test", ...)`

---

### 7.5 `log_file_change(**kwargs)`

**Responsibility:** Convenience wrapper for file modify/create/delete.

```python
def log_file_change(
    session_id:     str,
    file_path:      str,
    change_type:    str,       # create|modify|delete
    model_used:     str = "",
    prompt:         str = "",
    diff_path:       str = "",    # path to generated diff
    dependencies:   list[str] = [],
    lines_added:    int = 0,
    lines_removed:  int = 0,
    commit_hash:     str = "",
    **kwargs                # passed to log_event()
) -> None:
```

**Behavior:**
1. Call `log_event(action=f"{change_type}_file", target=file_path, ...)`
2. If `diff_path` provided, verify it exists

---

### 7.6 `generate_session_id()` — Utility

```python
def generate_session_id() -> str:
    """Generate unique session ID like 'sess_a3f8b2'."""
    import uuid
    return f"sess_{uuid.uuid4().hex[:6]}"
```

---

## 8. Integration Points

### 8.1 `core/orch_run.py` must call:
```python
log_file_change(session_id, "orch_run.py", "modify",
                 model_used="User", reason="Updated TCL header injection")
```

### 8.2 `tools/aider-*.sh` must call:
```python
log_file_change(session_id, target_file, "modify",
                 model_used="Qwen", prompt=prompt_text)
```

### 8.3 `core/validation_pipeline.py` must call:
```python
log_test_result(session_id, "pytest", passed=True, output=test_output)
```

### 8.4 All AI agent actions MUST emit:
```python
log_event(session_id, actor="Gemini", action="modify_file",
          target="validator_l3.py", model_used="gemini/gemini-2.5-pro",
          prompt=prompt, reason="Added L3 context checks")
```

---

## 9. Anti-Patterns (DO NOT DO THESE)

### ❌ Pretty-printed JSON in `events.jsonl`
```json
// WRONG — multi-line, hard to grep
{
  "timestamp": "...",
  "session_id": "..."
}
```

✅ **Correct — single line, grepable:**
```json
{"timestamp":"...", "session_id":"...", "action":"modify_file", ...}
```

### ❌ Editing `events.jsonl`
- No deletions
- No corrections
- No pretty-printing
- If you made a mistake: log a NEW event with `"action":"revert"`

### ❌ Missing mandatory fields
All 8 core fields MUST be present in every event. `audit_logger.py` MUST enforce this.

### ❌ Session ID reuse
One session = one `session_id`. If the user starts a new task, generate a new one.

---

## 10. Validation (How to Verify Implementation)

After building `core/audit_logger.py`:

### Test 1: Append-only behavior
```bash
python -c "
from core.audit_logger import log_event
log_event('sess_test', 'User', 'create_file', 'test.py', 'testing')
log_event('sess_test', 'User', 'modify_file', 'test.py', 'more testing')
"
wc -l logs/events/events.jsonl   # MUST be exactly 2
```

### Test 2: Mandatory fields enforced
```bash
python -c "
from core.audit_logger import log_event
log_event('sess_test', 'User', 'modify_file', 'test.py')
# Should fail: missing 'reason', 'approved_by', 'tests_passed', 'rollback_possible'
"
```

### Test 3: Grepability
```bash
grep '"action":"modify_file"' logs/events/events.jsonl
# Must return exactly the matching line, nothing else
```

### Test 4: Discussion transcript saved
```bash
python -c "
from core.audit_logger import log_discussion
log_discussion('sess_test', 'test topic', ['Gemini','Qwen'], 'full transcript here')
"
ls logs/discussions/   # Must have sess_test_disc1.md
```

---

## 11. Implementation Priority

| Order | Function | Lines Est. | Priority |
|-------|----------|-----------|----------|
| 1 | `generate_session_id()` | 5 | High |
| 2 | `log_event()` | 30 | **Highest** |
| 3 | `log_file_change()` | 15 | High |
| 4 | `log_test_result()` | 20 | High |
| 5 | `log_discussion()` | 25 | Medium |
| 6 | `log_decision()` | 30 | Medium |

**Implement in this exact order.** `log_event()` is the foundation. Everything else calls it.

---

## 12. Future (Not Now)

After this spec is implemented and stable:
- `core/replay.py` — reconstruct session from `events.jsonl`
- `core/rollback.py` — revert files using `commit_hash` from events
- Query engine over `events.jsonl` (SQL-like, not grep)
- Dashboard showing event timeline

**DO NOT build these until Stage 1 is stable.**
