# DFT FACTORY — Changelog

All notable changes to the DFT Factory automation platform are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — Phase 3 In Progress

### Added
- `README_ARCHITECTURE.md` — full system architecture documentation
- `ROADMAP.md` — Phase 3 implementation sequence (9 stages)
- `DECISIONS.md` — Architecture Decision Records (ADR) index
- `CHANGELOG.md` — this file
- `config/factory_config.py` — unified config with auto-detect `FACTORY_ROOT`
- `core/utils.py` — shared helpers (from AUTOMATE_1)
- `core/dir_init.py` — iteration tree creator (enhanced from AUTOMATE_1)
- `core/orch_run.py` — tool launcher (from AUTOMATE_3, with --inject, --sdc, --timing)
- `core/harvest.py` — output normalizer (from AUTOMATE_3, with --extra-search-dirs)
- `core/lifecycle.py` — iteration manager (from AUTOMATE_3, with --filter-status/tag/design)
- `tcl/SYNOPSYS/_factory_helpers.tcl` — TCL helper block (from AUTOMATE_2)
- `tcl/SYNOPSYS/ATPG_SAF.tcl` — generic ATPG flow (from AUTOMATE/)
- `tcl/SYNOPSYS/ATPG_SAF_EXP1.1.tcl` — experiment flow (from AUTOMATE_2)
- `tools/env_gate.sh` — tool environment switcher (from AUTOMATE_1)

### Changed
- Unified AUTOMATE/ through AUTOMATE_3 into single `DFT_FACTORY/` structure
- `factory_config.py` now auto-detects `FACTORY_ROOT` from file location or `DFT_FACTORY_ROOT` env var
- `TOOL_REGISTRY` keys renamed: `SYNOPSYS` (was `TMAX`), `TESSENT` (was `TESSENT`)
- Metadata keys renamed: `tool_suite` (was `tool`), `sub_exp_id` (was `sub_exp`)
- `METADATA_DEFAULTS` (was `METADATA_SCHEMA`) with enhanced field set

### Deprecated
- `AUTOMATE/` directories kept as reference only — will be removed after Phase 3 validation

---

## [Phase 2.0] — 2026-05-08 — Infrastructure Proven

### Added
- `validator.py` — L1: flag existence validation
- `validator_l2.py` — L2: flag + argument validation with mutual exclusion
- `validator_l3.py` — L3: context-aware validation (ordering, blockers)
- `validator_l4.py` — L4: advisor layer (recommendations, scoring)
- `semantic_graph.py` — builds knowledge graph from TetraMAX HTML docs
- `build_graph.py` — graph construction entry point
- `engine_rag.py` — RAG retrieval over semantic graph
- `CONVENTIONS.md` — DFT prompting rules for AI assistance
- `tools/check_models.py` — model health check script
- `tools/aider-architect.sh` — architect mode (Gemini plans, Qwen edits)
- `tools/aider-architect.ps1` — PowerShell version of architect mode
- `tools/aider-cloud.sh` — cloud model session (Gemini via LiteLLM)
- `tools/litellm_config.yaml` — LiteLLM proxy with fallback routing
- `HANDOFF_TILL_NOW.txt` — Phase 2 engineering handoff report
- `free-claude-code/` — Claude Code proxy for free backends
- `.aiderignore` — prevents AI from touching generated files

### Changed
- Ollama model: `qwen2.5-coder:7b` → `qwen2.5-coder:7b-instruct-q4_K_M`
- Aider: `--edit-format diff` → `--edit-format whole` for local 7B models
- LiteLLM: `pip install litellm` → `pip install 'litellm[proxy]'`
- Aider+LiteLLM: `--model fast` → `--model openai/fast` with `--openai-api-key dummy`

### Fixed
- WSL auth failure: documented as unresolved, works in native Windows
- OpenRouter model drift: `claude-3.5-sonnet` → `deepseek/deepseek-chat`
- Port 8000 collision in architect scripts: added lsof/netstat check
- Cleanup on exit: added `trap cleanup EXIT INT TERM` in shell scripts

---

## [Phase 1.0] — 2026-04-XX — AI Experimentation

### Added
- Initial Ollama + Qwen 2.5 Coder 7B setup
- Aider integration for local repo editing
- NVIDIA NIM experiment (DeepSeek via NVIDIA cloud)
- OpenRouter migration (NVIDIA → OpenRouter free tier)
- LiteLLM basic proxy configuration
- Claude Code proxy via `free-claude-code/`
- Basic DFT automation scripts (AUTOMATE/)
- TetraMAX ATPG_SAF TCL flow (`ATPG_SAF.tcl`)
- Factory config foundation (`factory_config.py`)

### Known Issues
- WSL Claude Code auth failure (unresolved)
- NVIDIA free endpoint instability (abandoned for OpenRouter)
- Local 7B models fail on `diff` edit format (fixed in Phase 2)
- OpenRouter model IDs drift over time (mitigated via health check in Phase 2)

---

## [Pre-Phase 1] — 2026-04-XX — Exploration

### Explored
- TetraMAX command validation (validator L1 concept)
- Semantic graph from EDA tool HTML documentation
- RAG over DFT-specific knowledge base
- Local vs cloud model tradeoffs for DFT workflows
