# DFT FACTORY — Phase 3 Roadmap

This roadmap defines the exact sequence for evolving from **Phase 2 (infrastructure proven)** to **Phase 3 (systems engineering platform)**.

**The order matters. Do NOT skip ahead.**

---

## STAGE 0 — FREEZE CURRENT STATE ✅

### 0.1 Snapshot Branch
- [x] `git checkout -b phase2-stable`
- [x] Commit all Phase 2 work
- [x] Tag as rollback point

### 0.2 Root Documentation
- [x] `README_ARCHITECTURE.md` — system architecture (this doc's companion)
- [x] `ROADMAP.md` — this file
- [ ] `DECISIONS.md` — architecture decision records (ADR index)
- [ ] `CHANGELOG.md` — version history

---

## STAGE 1 — AUDIT / TRACEABILITY SYSTEM (TOP PRIORITY)

Build the immutable event stream that makes all future AI actions traceable.

### 1.1 Create Logging Directory Structure
```
DFT_FACTORY/logs/
├── events/           ← append-only event stream (events.jsonl)
├── discussions/       ← prompt/response pairs, AI debates
├── decisions/         ← per-decision detail files
├── test_runs/        ← pytest, TCL dry-run outputs
├── artifacts/         ← generated patches, reports, diagrams
└── sessions/         ← per-session context snapshots
```

### 1.2 Create `core/audit_logger.py`
Functions:
- `log_event(session_id, actor, action, target, reason, ...)` → append to `events.jsonl`
- `log_discussion(session_id, topic, participants, summary)` → `discussions/`
- `log_decision(decision_id, title, rationale, alternatives)` → `decisions/`
- `log_test_result(session_id, test_type, passed, details)` → `test_runs/`
- `log_file_change(session_id, file, change_type, model_used)` → `events.jsonl`
- `log_agent_action(session_id, agent, action, prompt, response)` → `events.jsonl`

### 1.3 Standardize Event Schema (MANDATORY)
Every event in `events.jsonl`:
```json
{
  "timestamp": "2026-05-08T10:00:00+00:00",
  "session_id": "sess_abc123",
  "actor": "Claude|Gemini|Qwen|User|Orchestrator",
  "action": "modify_file|create_file|delete_file|run_test|merge",
  "target": "validator_l3.py",
  "reason": "Added L3 context validation for set_atpg",
  "approved_by": "Nikhil",
  "tests_passed": true,
  "rollback_possible": true,
  "model_used": "gemini/gemini-2.5-pro",
  "prompt": "Add L3 validation...",
  "dependencies": ["validator.py", "validator_l2.py"],
  "commit_hash": "abc123f"
}
```

**Without schema = logs become useless over time.**

### 1.4 Auto-Logging Integration
Every operation must emit an event:
- File create/modify/delete → `log_file_change()`
- AI response → `log_agent_action()`
- Test run → `log_test_result()`
- Architecture decision → `log_decision()`
- Discussion/debate → `log_discussion()`

---

## STAGE 2 — DEFINE AI ORCHESTRATION ARCHITECTURE

Define agent roles and responsibilities BEFORE adding more agents.

### 2.1 Create `config/agents.yaml`
```yaml
planner:
  model: "gemini/gemini-2.5-pro"
  provider: "litellm"
  role: "architecture_reasoning"
  temperature: 0.2

executor:
  model: "ollama/qwen2.5-coder:7b-instruct-q4_K_M"
  provider: "ollama"
  role: "implementation"
  temperature: 0.1

critic:
  model: "openrouter/deepseek/deepseek-chat"
  provider: "openrouter"
  role: "challenge_assumptions"
  temperature: 0.3
  must_differ_from: ["planner"]  # CRITICAL: different family

validator:
  model: "deterministic"
  provider: "internal"
  role: "run_tests_only"
  temperature: null
```

### 2.2 Define Orchestration Lifecycle
```
User Request
    ↓
Tier 1 (Planner: Gemini)
    ├── Analyze request
    ├── Produce plan
    └── Emit log_event()
    ↓
Tier 3 (Critic: DeepSeek, DIFFERENT family)
    ├── Review plan
    ├── Challenge assumptions
    ├── Detect hallucinations
    └── Emit log_event()
    ↓ (only if critic approves)
Tier 2 (Executor: Qwen)
    ├── Implement changes
    ├── Generate patches
    └── Emit log_file_change()
    ↓
Tier 4 (Validator: deterministic)
    ├── pytest
    ├── TCL dry-run
    ├── Schema validation
    └── Emit log_test_result()
    ↓ (only if ALL tests pass)
Merge + log_decision()
```

### 2.3 Create `core/orchestrator.py`
Responsibilities:
- Call agents in defined order
- Collect reviews
- Aggregate consensus
- Trigger validation
- Write audit logs
- Block merge on critic veto or validation failure

---

## STAGE 3 — DETERMINISTIC VALIDATION LAYER

**MOST IMPORTANT:** AI consensus ≠ correctness.

### 3.1 Create `core/validation_pipeline.py`
Checks:
- Python syntax (`py_compile`)
- TCL syntax (`tclsh -n`)
- Path validation (no writes to sacred dirs)
- Graph validation (validator imports consistent)
- Schema validation (`.metadata` conforms to `METADATA_DEFAULTS`)
- Forbidden directory write prevention

### 3.2 Create Mandatory Test Gates
Before any merge:
- [ ] ALL pytest passes
- [ ] TCL syntax clean
- [ ] Validator (L1/L2/L3/L4) passes
- [ ] Audit log written
- [ ] Reviewer (Tier 3) approved

### 3.3 Create `core/rollback.py`
Capabilities:
- Restore files to previous state
- Revert entire session
- Replay `events.jsonl` to reconstruct state
- `parent_iter` lineage tracking

---

## STAGE 4 — MEMORY + KNOWLEDGE SYSTEM

Build the engineering cognition layer.

### 4.1 Create Decision Records
Every major decision stored as ADR (Architecture Decision Record):
```
DECISIONS.md                    ← index of all decisions
decisions/
├── ADR-001-phase-index-system.md
├── ADR-002-chain-dependency.md
├── ADR-003-audit-schema.md
└── ADR-004-multi-agent-orchestration.md
```

Each ADR contains:
- Title
- Status (proposed | accepted | rejected | deprecated)
- Context (why we needed to decide)
- Decision (what we chose)
- Alternatives considered
- Consequences (what changed)

### 4.2 Build Semantic Repository Index
Track:
- Module dependencies
- TCL flow relationships
- Validator L1→L2→L3→L4 chain
- Generated artifact lineage

### 4.3 Searchable Engineering Memory
Eventually queryable:
- "Why was lifecycle.py modified?"
- "Which AI introduced this regression?"
- "Show all changes touching ATPG_SAF.tcl"

---

## STAGE 5 — DFT DOMAIN LAYER

Now begin real DFT specialization.

### 5.1 Enhanced DFT Metadata Schema
Extend `.metadata` with:
- `fault_type`: SAF | TF | IDDQ
- `atpg_mode`: basic_scan | fast_sequential | full_sequential
- `scan_mode`: chain_test | internal_test
- `compression_mode`: none | light | aggressive
- `tool_version`: extracted from logs
- `report_lineage`: which reports generated from which commands

### 5.2 Experiment Tracking
Every run has:
- `experiment_id`: SA_EXP1, MBIST_EXP1, ...
- `sub_exp_id`: E1.1, E1.2, ...
- Full lineage: design → tool → stage → exp → sub → iter

### 5.3 TCL Semantic Analyzer
Track within TCL:
- Proc dependencies (which proc calls which)
- Variable lineage (`$TOP_MODULE` flow from Python → TCL header → TCL body)
- Report generation flow (which command produces which report)

---

## STAGE 6 — MULTI-AI REVIEW SYSTEM

ONLY after orchestration engine exists.

### 6.1 Integrate AutoGen/CrewAI
Agents collaborate:
- Planner (architecture)
- Reviewer (code quality)
- Tester (test generation)
- Security (input validation)
- DFT Expert (domain correctness)

### 6.2 Add Consensus Policies
- Minimum 2 reviewers must approve
- Critic (Tier 3) veto blocks merge
- Confidence scoring: if < 0.8, escalate to human

### 6.3 Add Confidence Scoring
Track per agent:
- Agreement level with other agents
- Uncertainty markers
- Hallucination risk score

---

## STAGE 7 — OBSERVABILITY DASHBOARD

Platform maturity dashboard.

### 7.1 Metrics Collection
Track:
- Failed edits (local vs cloud)
- Model reliability (pass rate by model)
- Token usage per session
- Provider uptime (OpenRouter, Gemini, Ollama)
- Validation failure rate
- Regression frequency (files broken by AI edits)

### 7.2 Timeline Replay
Eventually:
```
python core/replay.py --session sess_abc123
```
Reconstructs entire engineering session from `events.jsonl`.

---

## STAGE 8 — HARDEN FOR PRODUCTION

### 8.1 Add CI/CD (GitHub Actions)
- Run pytest on every push
- Lint Python files
- Validate audit log format
- Check `.metadata` schema compliance

### 8.2 Add Permission Boundaries
AI must NOT:
- Modify `config/factory_config.py` without human approval
- Write to `inputs/` (symlinks only)
- Overwrite `reports/` without going through `harvest.py`
- Bypass validation pipeline

### 8.3 Add Environment Profiles
```
profiles/
├── local.yaml          ← Ollama only, no cloud
├── shared-server.yaml  ← Ollama + LiteLLM proxy
├── production.yaml    ← all models, full audit
└── eda-lab.yaml        ← with real EDA tool licenses
```

---

## STAGE 9 — FUTURE ADVANCED IDEAS (NOT NOW)

### 9.1 Semantic Graph Engine
Cross-file DFT reasoning over the semantic graph (`semantic_graph.py`).

### 9.2 Autonomous Experiment Planner
AI proposes ATPG experiments:
- "Try capture_cycle=4 for partial-scan design"
- "Increase abort_limit for hard-to-detect faults"

### 9.3 AI-Generated Debug Timelines
Failure root-cause reconstruction from `events.jsonl` + report KPIs.

### 9.4 Self-Healing Orchestration
Fallback routing + automatic retries + model degradation (Tier 1 down to Tier 2 on 429).

---

## MOST IMPORTANT RULES

### Rule 1: Do NOT add tools faster than architecture
One stable system > five chaotic ones.

### Rule 2: Deterministic validation > AI opinions
Tier 4 (pytest, TCL dry-run) is the final gate. Always.

### Rule 3: Everything must be traceable
If it's not in `events.jsonl`, it didn't happen.

### Rule 4: One orchestration lifecycle only
No random multi-agent workflows. All actions flow through the defined lifecycle.

### Rule 5: Preserve rollbackability ALWAYS
Every session records lineage. Every change can be reverted.

---

## Recommended Immediate Sequence (Next 7 Days)

| Day | Task | Deliverable |
|-----|------|-------------|
| 1   | Freeze Phase 2 + create architecture docs | `phase2-stable` branch, `README_ARCHITECTURE.md`, `ROADMAP.md` |
| 2   | Build audit logger + event schema | `core/audit_logger.py`, `logs/events/` |
| 3   | Define agent roles + orchestration lifecycle | `config/agents.yaml`, `core/orchestrator.py` |
| 4   | Build deterministic validators | `core/validation_pipeline.py` |
| 5   | Integrate AI review pipeline | Tier 1→3→2→4 wiring |
| 6   | Add rollback engine | `core/rollback.py` |
| 7   | Architecture review + consolidation | Remove chaos, solidify flows |

---

## Current State Transition

```
Phase 2: AI experimentation
    ↓
Phase 3: Systems engineering ← YOU ARE HERE
```

This is the point where:
- **Governance** matters more than model choice
- **Contracts** matter more than new tools
- **Observability** matters more than prompt tuning
- **Traceability** matters more than convenience

That shift is extremely important.
