# DFT Factory — Code Conventions & Prompting Rules
#
# This file is loaded by Aider via --read CONVENTIONS.md
# It tells the AI how this project is structured, named, and how to reason about DFT.

# ── Project Identity ────────────────────────────────────────────────
# This is NOT a generic Python project. It is a DFT (Design-for-Test) engineering
# automation system that wraps EDA tools (TetraMAX, Tessent) with Python/ Bash
# orchestration and TCL generation.

Project:     DFT AI Factory
Purpose:      Automate ATPG, scan insertion, MBIST, and pattern export
Tools:        TetraMAX (Synopsys), Tessent (Siemens)
Language:     Python 3 (orchestration), TCL (EDA tool scripts)
License:      SNPSLMD_LICENSE_FILE (Synopsys), MGLS_LICENSE_FILE (Siemens)

# ── Repository Layout ───────────────────────────────────────────────
# /DFT_FACTORY/          → DFT automation engine (orchestration, harvesting)
#   AUTOMATE/            → Iteration 1: baseline automation scripts
#   AUTOMATE_1/          → Iteration 2: evolved scripts
#   AUTOMATE_2/          → Iteration 3: evolved scripts
#   AUTOMATE_3/          → Iteration 4: evolved scripts
# /validator.py           → L1: flag-existence validator for TetraMAX commands
# /validator_l2.py        → L2: flag+argument validator with mutual exclusion
# /validator_l3.py        → L3: context-aware validator (ordering, blockers)
# /validator_l4.py        → L4: advisor layer (recommendations, scoring)
# /semantic_graph.py      → Builds knowledge graph from TetraMAX HTML docs
# /build_graph.py         → Graph construction entry point
# /engine_rag.py          → RAG retrieval over semantic graph
# /tools/                 → Session scripts (aider-*.sh, check_models.py)
# /manuals/               → Raw EDA tool documentation (HTML)

# ── Naming Conventions ──────────────────────────────────────────────
# Files:
#   factory_config.py  → master config (single source of truth)
#   orch_run.py        → orchestrator / runner (one per AUTOMATE dir)
#   harvest.py         → output normalizer (runs after tool exits)
#   lifecycle.py       → experiment lifecycle (trend analysis, tagging)
#   dir_init.py        → directory structure initializer
#   env_gate.sh        → license + environment setter (sourced before EDA tool)
#   _factory_helpers.tcl → TCL helper procs injected into tool session

# Functions & Classes:
#   - snake_case for all Python functions: harvest_reports(), read_metadata()
#   - PascalCase for TCL procs: InitDesign, RunATPG, CheckCoverage
#   - Docstrings: Google style, first line is a one-sentence summary
#   - Every function that touches disk MUST accept Path or str, not hardcode paths

# Directories:
#   iter/              → iteration leaf node (one per experiment run)
#   iter/config/       → TCL/DO scripts (physical copies)
#   iter/inputs/       → symlinks to design files (NEVER copy heavy files)
#   iter/scripts/      → Python/Bash launchers (physical copies)
#   iter/work/         → tool scratchpad (deleted after harvest)
#   iter/logs/         → cleaned, passport-prefixed log transcripts
#   iter/reports/       → structured .rpt files with phase-prefix naming
#   iter/database/     → binary tool state (.db/.bin) for GUI restore
#   iter/outputs/      → final deliverables: patterns, fault lists

# ── DFT Domain Vocabulary (use these exact terms) ──────────────────
# ATPG      = Automatic Test Pattern Generation
# SAF       = Stuck-At Fault (0 or 1 stuck at a node)
# TF        = Transition Fault (slow-to-rise or slow-to-fall)
# IDDQ      = Quiescent current fault (leakage-based)
# Scan      = Chain of flip-flops for serial access
# MBIST     = Memory Built-In Self-Test
# EDT       = Embedded Deterministic Test (compress patterns)
# OCC       = On-Chip Clock Controller
# Coverage  = % of faults detected / total faults
# Pattern   = A set of test vectors that detects faults
# DRC       = Design Rule Check (scan chain rules, testability rules)
# TetraMAX  = Synopsys ATPG tool (commands: set_atpg, run_atpg, etc.)
# Tessent   = Siemens DFT tool suite
# STIL      = Standard Test Interface Language (pattern format)
# I2C       = Inter-Integrated Circuit (protocol often tested)

# ── TetraMAX Command Validation Layers ───────────────────────────
# L1 (validator.py)      → Does the flag exist? (e.g., -abort_limit)
# L2 (validator_l2.py)  → Does the flag have required arguments?
#                          Mutual exclusion? (e.g., basic_scan_only vs fast_sequential)
# L3 (validator_l3.py)  → Context: Is this command valid at this stage?
#                          Ordering constraints, blocking conditions
# L4 (validator_l4.py)  → Advisory: "You should increase capture_cycle"
#                          Scoring, recommendations, best practices

# When asked about a TetraMAX command, ALWAYS specify which validator layer
# you are reasoning at. Example:
#   "At L2, set_atpg -abort_limit requires a numeric argument."
#   "At L4, I recommend setting -capture_cycle to 4 for partial-scan designs."

# ── Phase Index System ─────────────────────────────────────────────
# The factory uses numeric phase indices as a universal language:
#   10 = setup    (design load, model build, library setup)
#   20 = drc      (design rule check, scan chain validation)
#   25 = insert   (RTL/gate-level DFT insertion — EDT/MBIST)
#   30 = fault    (fault model init and analysis)
#   40 = engine   (ATPG pattern generation)
#   60 = sim      (fault simulation, pattern verification)
#   80 = export   (write patterns, save databases, deliverables)

# Report files are ALWAYS named with phase prefix:
#   10_TEST-T_setup_modules_summary.rpt
#   40_TEST-T_engine_fault_summary.rpt

# ── Prompting Rules for DFT Tasks ────────────────────────────────
# Rule 1: Be specific about the validator layer
#   GOOD:  "At L2, add argument validation for -jtag_lbist in set_atpg"
#   BAD:   "Fix the validator"

# Rule 2: Specify file scope
#   GOOD:  "Read validator_l3.py. Do not touch validator_l2.py or validator.py."
#   BAD:   "Fix the validators"

# Rule 3: One concern per prompt
#   GOOD:  "Add -resim_atpg_pattern validation to L2 for set_atpg"
#   BAD:   "Add all missing set_atpg flags to L2 and L3"

# Rule 4: Reference TetraMAX commands by name
#   GOOD:  "Handle the -capture_cycle flag in set_atpg (used by run_atpg -auto_compress)"
#   BAD:   "Handle the cycle flag"

# Rule 5: For TCL edits, specify proc name and guard behavior
#   GOOD:  "In proc InitDesign, add a guard: if $RPT_DIR doesn't exist, puts stderr and return -1"
#   BAD:   "Make InitDesign safer"

# Rule 6: Use /ask before edit for anything involving >1 file or >10 lines
#   GOOD:  "/ask Trace how $TOP_MODULE flows from orch_run.py → dir_init.py → TCL header"
#   Then:  "Now add a guard in dir_init.py that substitutes empty string if top_module is None"

# Rule 7: Preserve Passport system in harvest.py
#   Every log MUST have a "# === DFT DATA FACTORY — LOG PASSPORT" header
#   Never remove or modify the passport block in harvest.py

# Rule 8: Metadata schema is sacred
#   The .metadata JSON at each iteration leaf follows METADATA_SCHEMA exactly
#   (defined in factory_config.py). Only add keys via write_metadata() helper.

# ── Code Style Rules ───────────────────────────────────────────────
# 1. Shebang:     #!/usr/bin/env python3
# 2. Docstrings:   Google style, triple-quoted, first line = one-sentence summary
# 3. Imports:      stdlib → third-party → local (with clear section breaks)
# 4. Paths:        Always use pathlib.Path, never os.path
# 5. Errors:       Raise specific exceptions (ValueError, KeyError), not generic Exception
# 6. TCL procs:    PascalCase, with comment block showing inputs/outputs
# 7. Config:       All paths/credentials in factory_config.py or .env, never hardcoded
# 8. Print style:  Use print(f"  OK   : ...") for consistent 2-space indent log output
# 9. JSON:         Use json.dump(data, f, indent=2) — never pretty-print manually
# 10. argparse:    Always use add_argument with help=, required= when needed

# ── What NOT to Touch ─────────────────────────────────────────────
# - tmax_graph.json (2.5MB) — regenerate via build_graph.py if needed
# - semantic_graph.json (16KB) — regenerate via semantic_graph.py if needed
# - .metadata files — use write_metadata() helper only
# - factory_config.py TOOL_REGISTRY / STAGE_REGISTRY — these are the source of truth
# - TCL files in iter/ — these are generated by orch_run.py, not hand-edited
# - venv/ — never modify the virtual environment directly

# ── Session Startup Reminder ──────────────────────────────────────
# 1. source venv/bin/activate
# 2. python tools/check_models.py
# 3. Choose mode:
#    ./tools/aider-local.sh       → local Qwen, --edit-format whole
#    ./tools/aider-cloud.sh       → cloud Gemini, --edit-format diff
#    ./tools/aider-architect.sh   → architect mode (Gemini plans, Qwen edits)
