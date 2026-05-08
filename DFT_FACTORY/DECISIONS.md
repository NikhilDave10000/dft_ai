# DFT FACTORY — Architecture Decision Records (ADR)

This file is the index of all major architecture decisions.
Each decision has a dedicated file in `logs/decisions/` with full context.

---

## Decision Record Template

Each `logs/decisions/ADR-XXX-title.md` contains:

```
# ADR-XXX: Title

## Status
proposed | accepted | rejected | deprecated

## Context
Why we needed to decide.

## Decision
What we chose.

## Alternatives Considered
What we rejected and why.

## Consequences
What changed after this decision.
```

---

## Decision Index

| ID | Title | Status | Date | Files Affected |
|----|-------|--------|------|----------------|
| [ADR-001](#adr-001-phase-index-system) | Phase Index System | ✅ accepted | 2026-05-08 | `config/factory_config.py` |
| [ADR-002](#adr-002-chain-dependency) | Chain Dependency Model | ✅ accepted | 2026-05-08 | `config/factory_config.py` |
| [ADR-003](#adr-003-audit-schema) | Audit Event Schema | 🔲 proposed | 2026-05-08 | `core/audit_logger.py` |
| [ADR-004](#adr-004-multi-agent-orchestration) | Multi-Agent Orchestration | 🔲 proposed | 2026-05-08 | `core/orchestrator.py` |
| [ADR-005](#adr-005-deterministic-validation) | Deterministic Validation Layer | 🔲 proposed | 2026-05-08 | `core/validation_pipeline.py` |

---

## ADR-001: Phase Index System

**Status:** ✅ accepted

**Context:**
We needed a universal naming system for DFT tool execution phases that works across multiple EDA tool suites (Synopsys TetraMAX, Siemens Tessent) with their different naming conventions.

**Decision:**
Use numeric phase indices (10, 20, 30...) with per-tool mode string mappings in `PHASE_INDEX`. This decouples the *concept* (setup, drc, fault, engine, sim, export) from *tool-specific commands*.

**Alternatives Considered:**
- Pure string phases ("setup", "drc", etc.) — rejected because numeric indices sort naturally and allow sub-phase insertion (25, 35...) without renumbering.
- Per-tool phase enums — rejected because it duplicates logic across tool suites.

**Consequences:**
- Reports named `40_TEST-T_fault_summary.rpt` (TetraMAX) or `40_ATPG_fault_summary.rpt` (Tessent) from the same index.
- New tools can be added by adding one line to `PHASE_INDEX`.
- Sub-phases (25 for MBIST insertion) inserted without renumbering existing phases.

---

## ADR-002: Chain Dependency Model

**Status:** ✅ accepted

**Context:**
DFT stages have natural data dependencies. ATPG needs scan-inserted netlists from SCAN stage. SIM needs patterns from ATPG. Without explicit dependency tracking, users could run stages out of order and get empty or incorrect results.

**Decision:**
Add `chain_from` field to `STAGE_REGISTRY`. When `dir_init.py` creates an iteration, it looks for a GOLDEN-tagged iteration of the upstream stage and symlinks its `outputs/` into the new iteration's `inputs/from_<stage>`.

**Alternatives Considered:**
- Manual symlink instructions — rejected because it's error-prone and not traceable.
- Copy instead of symlink — rejected because design files can be GB-scale.
- No dependency tracking — rejected because it produces silent failures.

**Consequences:**
- `ATPG.chain_from = "SCAN"` — ATPG iterations auto-link SCAN's outputs.
- `SIM.chain_from = "ATPG"` — SIM iterations auto-link ATPG's patterns.
- `parent_iter` in `.metadata` tracks rerun lineage.

---

## ADR-003: Audit Event Schema

**Status:** 🔲 proposed

**Context:**
Multiple AI agents (planner, executor, critic, validator) will modify code, propose architectures, and make decisions. Without an immutable event log, we cannot answer "Why was this file changed?" or "Which AI introduced this regression?" after the fact.

**Decision:**
Create append-only `logs/events/events.jsonl` with mandatory schema:
```json
{
  "timestamp": "2026-05-08T10:00:00+00:00",
  "session_id": "sess_abc123",
  "actor": "Claude|Gemini|Qwen|User|Orchestrator",
  "action": "modify_file|create_file|run_test|merge",
  "target": "validator_l3.py",
  "reason": "Added L3 context validation for set_atpg",
  "approved_by": "Nikhil",
  "tests_passed": true,
  "rollback_possible": true,
  "model_used": "gemini/gemini-2.5-pro",
  "prompt": "...",
  "dependencies": ["validator.py", "validator_l2.py"],
  "commit_hash": "abc123f"
}
```

**Alternatives Considered:**
- Git history only — rejected because git tracks *what* changed, not *why* (AI reasoning, prompt used, model that generated it).
- Free-text commit messages — rejected because they're not machine-queryable.
- SQL database — rejected because JSONL is simpler, grepable, and doesn't require a running DB.

**Consequences:**
- Every AI action becomes traceable and queryable.
- `DECISIONS.md` links to `logs/discussions/` for full debate transcripts.
- Rollback engine can replay `events.jsonl` to reconstruct state.

---

## ADR-004: Multi-Agent Orchestration

**Status:** 🔲 proposed

**Context:**
A single AI model has blind spots. Even if planner + executor both "agree", they can share the same hallucination pattern if they're from the same model family. We need intentional diversity in the agent hierarchy.

**Decision:**
Define 4 tiers with **mandatory model-family diversity**:
- **Tier 1 (Planner):** Cloud reasoning (Gemini/Claude) — architecture, refactoring
- **Tier 2 (Executor):** Local models (Qwen/DeepSeek Coder) — edits, patches, TCL
- **Tier 3 (Critic):** MUST be different family from Tier 1 — challenges assumptions
- **Tier 4 (Validator):** Deterministic (pytest, TCL dry-run) — **final gate**

**Alternatives Considered:**
- Single powerful model does everything — rejected because no single model is reliable enough for engineering work.
- All agents same family — rejected because correlated failures defeat the purpose of review.
- Consensus voting — rejected because AI consensus ≠ correctness.

**Consequences:**
- `config/agents.yaml` defines roles, models, and diversity constraints.
- `core/orchestrator.py` enforces the lifecycle: Plan → Critique → Execute → Validate → Log.
- Tier 3 veto blocks merge. Tier 4 failure blocks merge.

---

## ADR-005: Deterministic Validation Layer

**Status:** 🔲 proposed

**Context:**
The most important lesson from Phase 2: **AI consensus is NOT proof of correctness**. Even if Gemini (Tier 1), Qwen (Tier 2), and DeepSeek (Tier 3) all agree a patch is correct, the patch can still be wrong. We need a deterministic final gate that does NOT use AI.

**Decision:**
Create `core/validation_pipeline.py` that runs AFTER all AI agents have acted:
1. Python syntax check (`py_compile`)
2. TCL syntax check (`tclsh -n`)
3. Path validation (no forbidden directory writes)
4. Graph validation (validator import chains consistent)
5. Schema validation (`.metadata` conforms to `METADATA_DEFAULTS`)
6. pytest (all tests pass)

**Alternatives Considered:**
- Another AI model as "final validator" — rejected because it's still AI, still can hallucinate.
- Trust Tier 1-2-3 consensus — rejected explicitly (consensus ≠ correctness).
- Manual review only — rejected because it doesn't scale and isn't systematically enforced.

**Consequences:**
- No merge happens without ALL validation gates passing.
- `core/rollback.py` reverts if validation fails post-merge.
- Test coverage becomes a KPI tracked in `trend_analysis.csv`.
