# DFT FACTORY — Architecture Documentation

## System Purpose

The DFT Factory is a structured automation platform for DFT (Design-for-Test) engineering workflows. It wraps EDA tools (TetraMAX, Tessent) with Python/Bash orchestration, TCL generation, and AI-assisted code review.

This is NOT a chat interface. This is an **engineering cognition amplification system** with:
- Auditability (every action logged)
- Traceability (every file change tracked)
- Governance (multi-agent review, deterministic validation)
- Orchestration (Tier 1–4 agent hierarchy)

---

## Architectural Layers

### Layer 1 — Configuration (`config/`)

**Single source of truth.** All paths, tool registries, stage registries, phase indices, and metadata schemas live here.

```
config/factory_config.py
  ├── FACTORY_ROOT        → auto-detected from file location or DFT_FACTORY_ROOT env var
  ├── TOOL_REGISTRY      → {SYNOPSYS: {...}, TESSENT: {...}}
  ├── STAGE_REGISTRY     → {SCAN: {...}, ATPG: {...}, SIM: {...}}
  ├── PHASE_INDEX        → {10: "setup", 20: "drc", ...}
  ├── ITER_SUBDIRS       → [config, inputs, scripts, logs, reports, database, outputs, work]
  ├── METADATA_DEFAULTS  → schema for .metadata JSON
  └── TREND_CSV_COLUMNS  → columns for trend_analysis.csv
```

**Rule:** Never hardcode paths, tool names, or stage definitions anywhere else.

---

### Layer 2 — Core Engine (`core/`)

Shared orchestration, lifecycle, and utility scripts. All import from `config/factory_config.py` and `core/utils.py`.

```
core/
├── utils.py           → iter_path(), read_meta(), write_meta(), phase_prefix(), now_iso()
├── dir_init.py        → creates 6-level iteration tree, writes .metadata
├── orch_run.py        → launches EDA tool, streams logs, calls harvest
├── harvest.py         → normalizes outputs, renames reports, prepends passport
└── lifecycle.py       → tags iterations, builds trend CSV, purges trash
```

**Execution flow:**
```
dir_init.py → creates iter tree + .metadata
    ↓
orch_run.py → sources env_gate.sh → symlinks inputs → injects TCL header
    ↓
    → launches tmax/tessent → streams stdout → calls harvest.py
    ↓
harvest.py → renames reports → prepends passport → wipes work/
    ↓
lifecycle.py → tags GOLDEN/TRASH → builds trend_analysis.csv
```

---

### Layer 3 — TCL Templates (`tcl/`)

Tool-specific TCL flow bodies. These are NEVER hardcoded — all variables (`$LOG_DIR`, `$RPT_DIR`, `$PHASE_*`) are injected by `orch_run.py`.

```
tcl/
└── SYNOPSYS/
    ├── _factory_helpers.tcl  → wrpt, wlog, wdb, wout, factory_banner, check_reports
    ├── ATPG_SAF.tcl          → generic ATPG SAF flow
    └── ATPG_SAF_EXP1.1.tcl → experiment-specific flow (EXP1.1)
```

**Rule:** TCL scripts use helpers (`wrpt $PHASE_ENGINE fault_summary { ... }`). Never redefine injected variables.

---

### Layer 4 — Environment Gate (`tools/`)

Sourced before every tool run. Sets licenses, PATH, and tool binaries.

```
tools/
└── env_gate.sh  → source env_gate.sh SYNOPSYS  (or TESSENT)
```

---

## Iteration Hierarchy (6-Level)

```
FACTORY_ROOT/
└── {design}/               Level 1: i2c_master, spi, ...
    └── {tool_suite}/      Level 2: SYNOPSYS, TESSENT
        └── {stage}/       Level 3: SCAN, ATPG, SIM
            └── {exp}/      Level 4: SA_EXP1, MBIST_EXP1
                └── {sub}/   Level 5: E1.1, E1.2
                    └── {iter}/ Level 6: iter_001, iter_002 (leaf node)
                        ├── .metadata       ← JSON tracking file
                        ├── config/         ← TCL script copies (what was used)
                        ├── inputs/         ← symlinks to netlist/lib/SPF
                        ├── scripts/        ← merged TCL (header + body)
                        ├── logs/           ← passported log transcripts
                        ├── reports/        ← phase-prefixed .rpt files
                        ├── database/       ← binary tool state (.db)
                        ├── outputs/        ← patterns (.stil/.wgl), fault lists
                        └── work/           ← tool scratchpad (deleted after harvest)
```

**Key rules:**
- Level 6 (`iter_NNN/`) is the **only** leaf node that contains `.metadata`
- `inputs/` contains **symlinks only** — never copy heavy files
- `work/` is wiped after harvest — never store permanent data there
- `config/` preserves what was **actually used** for reproducibility

---

## Phase Index System (Universal Naming)

Numeric phase indices decouple the *concept* (setup, drc, fault, engine, sim, export) from *tool-specific mode strings*.

| Index | Concept  | SYNOPSYS Mode   | TESSENT Mode   | Description                    |
|-------|----------|-----------------|-----------------|-------------------------------|
| 10    | setup    | BUILD-T         | SETUP           | Design load, model build        |
| 20    | drc      | DRC-T           | ANALYSIS        | Scan DRC, chain validation     |
| 25    | insert   | INSERT          | INSERTION       | DFT insertion (MBIST/EDT)       |
| 30    | fault    | FAULT           | FAULT-MODEL     | Fault model init               |
| 40    | engine   | TEST-T          | ATPG            | Pattern generation              |
| 60    | sim      | SIM             | SIMULATION      | Fault simulation               |
| 80    | export   | EXPORT          | EXPORT          | Write patterns, save DB         |

**File naming convention:**
```
reports/40_TEST-T_fault_summary.rpt
logs/20_DRC-T_drc_run.log
database/40_TEST-T_post_atpg.db
```

---

## Metadata Schema (`.metadata` JSON)

Every iteration leaf node has a `.metadata` file — the single source of truth for that run.

```json
{
  "status":          "PASS",        // PENDING | RUNNING | PASS | FAIL | ABORTED
  "lock":            false,        // True while job active
  "iter_tag":        "GOLDEN",     // GOLDEN | TRASH | null
  "design":          "i2c_master",
  "tool_suite":      "SYNOPSYS",    // SYNOPSYS | TESSENT
  "stage":           "ATPG",
  "exp_id":          "SA_EXP1",
  "sub_exp_id":      "E1.1",
  "iter_id":         "iter_001",
  "experiment_note": "",
  "tool_version":    "2024.03",
  "timestamp_start": "2026-05-08T10:00:00+00:00",
  "timestamp_end":   "2026-05-08T11:23:11+00:00",
  "runtime_s":       4991,
  "phases_completed":[10, 20, 30, 40, 80],
  "parent_iter":     null,         // set on --rerun
  "harvest_done":    true
}
```

---

## Chain Dependency System

Stages can declare upstream dependencies via `chain_from` in `STAGE_REGISTRY`.

```
SCAN.chain_from = None      ← no upstream (starting point)
ATPG.chain_from = "SCAN"   ← reads SCAN's outputs/
SIM.chain_from  = "ATPG"   ← reads ATPG's outputs/
```

When `dir_init.py` creates an ATPG iteration, it:
1. Looks for a GOLDEN-tagged SCAN iteration
2. Symlinks `SCAN/outputs/` → `ATPG/inputs/from_SCAN`

This ensures **one-way data flow** through the DFT pipeline.

---

## AI Orchestration Architecture (Phase 3 — Next)

The current system is **human-driven with AI assistance**. Phase 3 introduces:

### Tier 1 — Planner (Cloud reasoning models)
- Gemini, Claude, DeepSeek R1
- Architecture planning, refactoring, repo reasoning

### Tier 2 — Executor (Local models)
- Qwen 2.5 Coder 7B, DeepSeek Coder 6.7B
- Code edits, patches, TCL generation

### Tier 3 — Critic (Different model family)
- MUST be different from Tier 1/2 to avoid correlated hallucinations
- Challenges assumptions, detects logic holes

### Tier 4 — Validator (Deterministic)
- pytest, TCL dry-run, syntax checker, graph validator
- **AI consensus ≠ correctness** — always validate deterministically

**Orchestration lifecycle:**
```
User request
    → Tier 1: Planning (Gemini)
    → Tier 3: Critic (DeepSeek, different family)
    → Tier 2: Execution (Qwen)
    → Tier 4: Validation (pytest, TCL dry-run)
    → Audit log (append-only event)
    → Merge if all gates pass
```

---

## Governance Rules

### Rule 1: Deterministic validation > AI opinions
Even if Tiers 1-2-3 all agree, Tier 4 must still pass.

### Rule 2: Everything traceable
Every file change emits an event to `logs/events/events.jsonl`.

### Rule 3: One orchestration lifecycle
No random multi-agent chaos. All AI actions flow through the defined lifecycle.

### Rule 4: Preserve rollbackability
Every session records `parent_iter`. `--rerun` resets but preserves lineage.

### Rule 5: Audit logs are immutable
`events.jsonl` is append-only. No edits, no deletions.

---

## Current State (as of Phase 2 Handoff)

- ✅ Local Ollama + Qwen 2.5 Coder 7B working
- ✅ LiteLLM proxy with fallback routing configured
- ✅ Cloud routing via OpenRouter (DeepSeek, Nemotron)
- ✅ Aider integration (`--edit-format whole` for local models)
- ✅ DFT Factory automation structured (AUTOMATE → unified `DFT_FACTORY/`)
- ✅ `CONVENTIONS.md` for DFT prompting consistency
- ✅ `tools/check_models.py`, `aider-architect.sh`, `aider-cloud.sh`
- ⏳ Phase 3: Audit system (NEXT)
- ⏳ Phase 3: Multi-agent orchestration
- ⏳ Phase 3: Deterministic validation layer

---

## File Inventory

```
DFT_FACTORY/
├── config/factory_config.py      ← single source of truth
├── core/
│   ├── utils.py                 ← shared helpers
│   ├── dir_init.py              ← iteration tree creator
│   ├── orch_run.py              ← tool launcher + monitor
│   ├── harvest.py               ← output normalizer
│   └── lifecycle.py             ← tag, purge, trend CSV
├── tcl/SYNOPSYS/
│   ├── _factory_helpers.tcl     ← TCL helper block
│   ├── ATPG_SAF.tcl            ← generic flow
│   └── ATPG_SAF_EXP1.1.tcl     ← experiment flow
├── tools/env_gate.sh            ← license + PATH setup
├── README.md                    ← quick start guide
├── README_ARCHITECTURE.md       ← this file
├── ROADMAP.md                   ← implementation sequence
├── DECISIONS.md                ← architecture decision records
└── CHANGELOG.md                ← version history
```
