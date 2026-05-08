# DFT DATA FACTORY — COMPLETE PROJECT HANDOFF DOCUMENT
# For use as context in a new AI chat session
# Everything that happened, every file, every decision, every detail

================================================================================
## SECTION 1: WHO THE USER IS AND WHAT THEY ARE DOING
================================================================================

The user is a hardware/DFT (Design-for-Test) engineer working at a company on
IC (integrated circuit) designs. They run EDA (Electronic Design Automation)
tools — specifically Synopsys TetraMAX (tmax) and Siemens Tessent — to perform:

  - SCAN insertion and validation
  - ATPG (Automatic Test Pattern Generation) for multiple fault types:
      SAF (Stuck-At Fault), TF (Transition Fault), IDDQ
  - Fault simulation
  - Eventually: MBIST (Memory BIST), EDT (Embedded Deterministic Test), OCC

The user works on a shared remote Linux server running csh (C shell). Multiple
engineers use the same server simultaneously. Tools are already installed by
admins — no installation needed. The user just types:

  For SYNOPSYS (tmax):   open terminal → csh → tmax -f script.tcl
  For TESSENT:           open terminal → csh → source /home/mentor.cshrc → tessent -shell -dofile script.do -log logfile

The user is comfortable with Python and understands shell scripting. They have
real EDA tool access and real designs available (starting with i2c_master).
They have many designs from day 1.

The user had an existing TCL script (EXP1.1 SAF ATPG for i2c) with good
structure but hardcoded paths, timestamps, and directory management baked into
the TCL itself. The goal was to extract all that infrastructure OUT of TCL and
into Python, leaving TCL as pure tool logic only.


================================================================================
## SECTION 2: THE CORE PROBLEM BEING SOLVED
================================================================================

### The "Massiveness" Problem

The user will eventually manage experiments across 5 simultaneous dimensions:
  1. Designs:       i2c_master, spi, uart, many others
  2. Tool suites:   SYNOPSYS (TetraMAX) vs TESSENT
  3. DFT stages:    SCAN, ATPG, SIM (and later MBIST, EDT, OCC)
  4. Experiments:   SA_EXP1, TR_EXP2 ... with sub-experiments E1.1 to E1.50
  5. Iterations:    iter_001 to iter_100 per sub-experiment

Without structure, answering "What was the coverage impact of 2 vs 4 EDT
channels on Design B?" becomes a week of manual grep. The goal is seconds.

### The Old Way (Bad)
- TCL script contained hardcoded paths: /home/DFT_libs/synopsys/gen.v
- TCL script managed its own directory creation with mkdir
- TCL script managed cleanup modes (soft/rerun/clean_exp/clean_all)
- Report names were hardcoded: "01_build_modules_summary.rpt"
- Each experiment required editing the TCL file itself
- No cross-experiment data aggregation
- No structured metadata tracking
- Files scattered in flat ../logs/, ../output/, ../reports/ directories

### The New Way (What We Built)
- Python owns ALL infrastructure: directory creation, metadata, launching
- TCL receives injected variables ($LOG_DIR, $RPT_DIR, $PHASE_ENGINE etc.)
- TCL is pure tool logic only — no paths, no experiment IDs, no cleanup
- Every run lands in a predictable 6-level addressable path
- Every run produces a .metadata JSON tracking status, timing, lineage
- Harvest normalizes all outputs to standard phase-prefixed names
- Lifecycle aggregates everything into a trend_analysis.csv for analysis


================================================================================
## SECTION 3: THE DIRECTORY HIERARCHY (THE CORE DESIGN DECISION)
================================================================================

Fixed 6-level path — every single file in the system is addressable:

  /FACTORY_ROOT
  └── /<DESIGN_NAME>           Level 1 — e.g. i2c_master, spi_controller
      └── /<TOOL_SUITE>        Level 2 — SYNOPSYS | TESSENT
          └── /<DFT_STAGE>     Level 3 — SCAN | ATPG | SIM (extensible)
              └── /<EXP_ID>    Level 4 — e.g. SA_EXP1, TR_EXP2
                  └── /<SUB_EXP_ID>  Level 5 — e.g. E1.1, E1.2
                      └── /<ITER_ID>       Level 6 — iter_001, iter_002...
                          ├── .metadata    hidden JSON — status, timing, tags
                          ├── config/      TCL scripts actually used (physical copies)
                          ├── inputs/      SOFT LINKS ONLY to netlists, libs, SPF
                          ├── scripts/     merged launcher script (physical copy)
                          ├── logs/        renamed: 10_BUILD-T_run.log
                          ├── reports/     standardized: 40_TEST-T_fault_summary.rpt
                          ├── database/    binary save points: 40_TEST-T_state.db
                          ├── outputs/     patterns (.stil .wgl .bin), fault lists
                          └── work/        tool scratchpad — DELETED after harvest

Key decisions:
- inputs/ uses soft links only — never copies heavy netlist/lib files
- work/ is always wiped after harvest to save disk space
- config/ contains the ORIGINAL TCL body (unmodified) for reference
- scripts/ contains the MERGED script (header + body) actually run
- database/ stores binary tool states for GUI debugging or restore


================================================================================
## SECTION 4: THE PHASE INDEX (UNIVERSAL NAMING LANGUAGE)
================================================================================

Reports and logs are named with a numeric phase prefix + tool-mode + description.
This makes logs/reports self-organizing and tool-agnostic:

  Phase  Name      SYNOPSYS mode    TESSENT mode      File example
  ─────────────────────────────────────────────────────────────────────────
  10     setup     BUILD-T          SETUP             10_BUILD-T_modules.rpt
  20     drc       DRC-T            ANALYSIS          20_DRC-T_scan_chains.rpt
  25     insert    INSERT           INSERTION         25_INSERT_edt_config.rpt  (sub-phase)
  30     fault     FAULT            FAULT-MODEL       30_FAULT_pre_summary.rpt
  40     engine    TEST-T           ATPG              40_TEST-T_fault_coverage.rpt
  60     sim       SIM              SIMULATION        60_SIM_fault_sim.rpt
  80     export    EXPORT           EXPORT            80_EXPORT_patterns.stil

Gaps (50, 70, 90) are intentional — reserved for future sub-phases.
You can insert a 25 or 35 sub-phase without renumbering anything.

Custom sub-phases can be defined inline in TCL:
  set PHASE_FAULT_PRE  "30_FAULT-PRE"
  set PHASE_FAULT_POST "30_FAULT-POST"


================================================================================
## SECTION 5: THE .metadata JSON FILE
================================================================================

Written at iter creation by dir_init.py. Updated throughout the run lifecycle.
Lives at: iter_NNN/.metadata (hidden file)

Full schema:
{
  "status":           "PENDING",    // PENDING | RUNNING | PASS | FAIL | ABORTED
  "lock":             false,        // true while a job is active (prevents double-run)
  "iter_tag":         null,         // "GOLDEN" | "TRASH" | null
  "design":           "i2c_master",
  "tool_suite":       "SYNOPSYS",   // SYNOPSYS | TESSENT
  "stage":            "ATPG",       // SCAN | ATPG | SIM
  "exp_id":           "SA_EXP1",
  "sub_exp_id":       "E1.1",
  "iter_id":          "iter_001",
  "experiment_note":  "baseline SAF, default settings",
  "tool_version":     "2024.03",    // extracted from log by harvest.py
  "timestamp_start":  "2025-06-01T09:00:00+00:00",
  "timestamp_end":    "2025-06-01T10:23:11+00:00",
  "runtime_s":        4991,
  "phases_completed": [10, 20, 30, 40, 80],
  "parent_iter":      null,         // set on --rerun, points to original iter_id
  "harvest_done":     false
}

Lifecycle of status:
  PENDING  -> set at dir_init.py creation
  RUNNING  -> set when orch_run.py acquires lock
  PASS     -> set on clean tool exit, returncode 0, no crash/license signals
  FAIL     -> set on non-zero exit, crash signal, or license failure
  ABORTED  -> set on timeout or Ctrl+C

The lock field prevents two orch_run.py instances from writing to the same
iteration simultaneously. If a run crashes without releasing the lock,
manually set "lock": false in .metadata or use --rerun.


================================================================================
## SECTION 6: COMPLETE FILE INVENTORY
================================================================================

dft_factory/
├── config/
│   ├── __init__.py                (empty, makes config a Python package)
│   └── factory_config.py          THE SINGLE SOURCE OF TRUTH — edit only this
├── core/
│   ├── __init__.py                (empty)
│   ├── utils.py                   shared helpers — imported by all scripts
│   ├── dir_init.py                Step 1: create iteration tree
│   ├── orch_run.py                Step 2: launch tool run
│   ├── harvest.py                 Step 3: normalize outputs (auto-called)
│   └── lifecycle.py               Step 4: tag / list / CSV / purge
├── tools/
│   └── env_gate.sh                csh environment switcher
└── tcl/
    ├── SYNOPSYS/
    │   ├── _factory_helpers.tcl   TCL proc library — source at top of every script
    │   └── ATPG_SAF_EXP1.1.tcl   example script showing how to use the helpers
    └── TESSENT/
        └── (empty — place your .do scripts here)


================================================================================
## SECTION 7: factory_config.py — THE SINGLE SOURCE OF TRUTH
================================================================================

Location: config/factory_config.py
Edit only: FACTORY_ROOT + TOOL_REGISTRY paths/licenses
All other scripts import from here — never hardcode anything elsewhere.

KEY SECTIONS:

1. FACTORY_ROOT = Path("/your/path/here")
   → Set this to your actual directory on the server. Only thing to edit.

2. TOOL_REGISTRY
   Defines SYNOPSYS and TESSENT tool suites:
   - binary:       command name ("tmax" or "tessent")
   - shell:        "csh" (both tools use csh on this server)
   - init_source:  None for SYNOPSYS (already in PATH); "/home/mentor.cshrc" for TESSENT
   - launch_flag:  "-f" for SYNOPSYS; "-dofile" for TESSENT
   - extra_flags:  ["-shell"] for TESSENT
   - log_flag:     "-log" for TESSENT (None for SYNOPSYS, uses set_messages in TCL)

3. STAGE_REGISTRY
   Defines SCAN, ATPG, SIM stages:
   - description:  human readable
   - phases:       list of phase indices used in this stage
   - chain_from:   upstream stage (ATPG chains from SCAN; SIM chains from ATPG)

4. PHASE_INDEX
   Maps 10/20/25/30/40/60/80 to names and tool-specific mode strings.

5. ITER_SUBDIRS
   List of 8 subdirs created in every iter folder:
   config, inputs, scripts, logs, reports, database, outputs, work

6. METADATA_DEFAULTS
   Template for .metadata JSON file.

7. TREND_CSV_COLUMNS
   Ordered list of column names for trend_analysis.csv.
   Includes: identity fields, timing, coverage KPIs, scan KPIs, resource KPIs.

To add a new tool suite: add entry to TOOL_REGISTRY + add case to env_gate.sh.
To add a new stage: add entry to STAGE_REGISTRY (or use dir_init.py --add-stage).


================================================================================
## SECTION 8: utils.py — SHARED HELPERS
================================================================================

Location: core/utils.py
Imported by: dir_init.py, orch_run.py, harvest.py, lifecycle.py

Functions:
  iter_path(design, tool_suite, stage, exp_id, sub_exp_id, iter_id) -> Path
      Constructs the canonical 6-level absolute path.

  next_iter_id(parent: Path) -> str
      Scans parent for existing iter_NNN dirs, returns next: iter_001, iter_002...

  read_meta(ipath: Path) -> dict
      Reads .metadata JSON. Exits with error if not found.

  write_meta(ipath: Path, updates: dict) -> None
      Merges updates into existing .metadata JSON (does not overwrite).

  init_meta(ipath: Path, **kwargs) -> None
      Writes fresh .metadata from METADATA_DEFAULTS + provided kwargs.

  validate(design, tool_suite, stage) -> list[str]
      Returns list of validation errors. Empty list = all good.

  phase_prefix(phase_idx: int, tool_suite: str) -> str
      Returns "40_TEST-T" or "20_ANALYSIS" etc. Used for naming files.

  now_iso() -> str
      Returns current UTC time in ISO 8601 format.


================================================================================
## SECTION 9: dir_init.py — STEP 1: CREATE ITERATION TREE
================================================================================

Location: core/dir_init.py
Purpose: Creates the 6-level directory structure + writes initial .metadata

REQUIRED FLAGS (for creating an iteration):
  --design  NAME    Design name. Level 1 folder. e.g. i2c_master
  --tool    SUITE   SYNOPSYS | TESSENT. Level 2 folder.
  --stage   STAGE   SCAN | ATPG | SIM. Level 3 folder.
  --exp     ID      Experiment ID. Level 4 folder. e.g. SA_EXP1
  --sub     ID      Sub-experiment ID. Level 5 folder. e.g. E1.1
  --iter    ID      iter_001 or "auto". Level 6 folder.

OPTIONAL FLAGS:
  --note    TEXT    Written into .metadata experiment_note. Shows in --list and CSV.
                    Put your experiment intent here: "4 EDT channels", "TF fault model"
  --dry-run         Prints what would be created WITHOUT touching disk.
                    Always use first time.

UTILITY FLAGS (no --design etc. needed):
  --list-stages     Prints all stages from STAGE_REGISTRY. Check before creating.
  --add-stage NAME  Adds new stage to factory_config.py automatically.
    + --stage-desc  "Description string"
    + --stage-phases "10,20,25,40,80"  (comma-separated phase indices)
    + --stage-chain-from STAGE_NAME     (or omit for no upstream)

EXAMPLES:
  # Create first iteration
  python core/dir_init.py \
      --design i2c_master --tool SYNOPSYS --stage ATPG \
      --exp SA_EXP1 --sub E1.1 --iter iter_001 \
      --note "baseline SAF, default settings"

  # Auto-number
  python core/dir_init.py --design i2c_master --tool SYNOPSYS --stage ATPG \
      --exp SA_EXP1 --sub E1.1 --iter auto

  # Preview without creating
  python core/dir_init.py ... --dry-run

  # Add MBIST stage (one command, edits factory_config.py automatically)
  python core/dir_init.py --add-stage MBIST \
      --stage-desc "Memory BIST insertion" \
      --stage-phases "10,20,25,40,80" \
      --stage-chain-from SCAN

WHAT IT CREATES:
  FACTORY_ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001/
    ├── .metadata     (JSON with status=PENDING, design, tool, stage etc.)
    ├── config/
    ├── inputs/
    ├── scripts/
    ├── logs/
    ├── reports/
    ├── database/
    ├── outputs/
    └── work/

VERIFIED WORKING: dir_init.py ran successfully on real server in this session.


================================================================================
## SECTION 10: orch_run.py — STEP 2: LAUNCH TOOL RUN
================================================================================

Location: core/orch_run.py
Purpose: Sets up environment, symlinks inputs, injects TCL header, launches
         tool, monitors run, calls harvest.py on exit.

REQUIRED FLAGS:
  --iter-path PATH  Absolute path to iter_NNN folder (from dir_init.py)
  --tcl PATH        Your TCL body script (factory prepends config header)

INPUT SYMLINK FLAGS (all optional, any combination):
  --netlist PATH    Gate-level netlist (.vg)          -> inputs/  [read_netlist]
  --libs P [P...]   Library files (.v, multiple ok)  -> inputs/  [read_netlist -library]
  --spf PATH        Scan protocol file (.spf)         -> inputs/  [run_drc]
  --sdc PATH        SDC timing constraints            -> inputs/  [read_sdc]
  --timing PATH     Timing file                       -> inputs/  [read_timing]
  --layout PATH     Physical layout file              -> inputs/  [read_layout]
  --extras P [P...] Any other files (catch-all)       -> inputs/

  All input flags: SYMLINKS ONLY. Never copies. Saves disk. Your TCL globs
  from $INPUT_DIR to find these files.
  If omitted: pre-populate inputs/ manually before calling orch_run.py.

TCL HEADER INJECTION FLAGS (optional):
  --top-module NAME
      Injects:  set TOP_MODULE "NAME"  into the TCL header.
      Without this, your TCL must define TOP_MODULE itself.
      Example: --top-module i2c_master_top

  --inject KEY=VALUE [KEY=VALUE ...]
      Injects arbitrary "set KEY VALUE" lines into TCL header.
      MOST POWERFUL FLAG: lets you vary experiment parameters from CLI
      without ever editing your TCL script.
      Example: --inject EDT_CHANNELS=4 FAULT_TYPE=transition COMPRESSION=8
      Your TCL then uses $EDT_CHANNELS, $FAULT_TYPE, $COMPRESSION freely.

CONTROL FLAGS (optional):
  --rerun
      Clears: logs/ reports/ outputs/ database/ work/
      Keeps:  inputs/ scripts/ (and .metadata)
      Resets .metadata to PENDING, records old iter_id as parent_iter.
      USE WHEN: fixed a TCL bug and need to rerun the same iteration folder.
      WITHOUT: creates a duplicate run in a new iter folder instead.

  --no-harvest
      Skips calling harvest.py after tool exits.
      work/ directory stays intact with raw tool output.
      USE WHEN: debugging — need to inspect raw tool state before normalization.

  --timeout-hrs N
      Kills tool after N hours. Default: 12.0
      Set lower (e.g. 2.0) for quick smoke-test runs.
      Status set to ABORTED on timeout.

WHAT orch_run.py DOES (in order):
  1. Reads .metadata to get tool_suite, stage, design etc.
  2. Calls env_gate.sh to source correct tool environment into the Python process
  3. Acquires lock (sets .metadata lock=true) — prevents concurrent runs
  4. Sets .metadata timestamp_start
  5. Symlinks all provided input files into inputs/
  6. Builds TCL config header (all $PHASE_*, $LOG_DIR, $RPT_DIR etc.)
  7. Prepends header onto your TCL body → writes merged script to scripts/
  8. Copies original TCL body to config/ (unmodified, for reference)
  9. Launches: csh -c "tmax -f scripts/run_iter_001.tcl"  (runs in work/ dir)
  10. Streams stdout live to terminal AND writes to logs/iter_001_raw.log
  11. Detects license failures (pattern matching) and crash signals in real time
  12. Waits for tool exit OR timeout
  13. Updates .metadata runtime_s, releases lock, sets status=PASS/FAIL/ABORTED
  14. Calls harvest.py automatically (unless --no-harvest)

TCL VARIABLES INJECTED (available in your script):
  $DESIGN         "i2c_master"
  $TOOL_SUITE     "SYNOPSYS"
  $STAGE          "ATPG"
  $EXP_ID         "SA_EXP1"
  $SUB_EXP_ID     "E1.1"
  $ITER_ID        "iter_001"
  $RUN_TAG        "i2c_master__SYNOPSYS__ATPG__SA_EXP1__E1.1__iter_001"
  $LOG_DIR        "/factory/root/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001/logs"
  $RPT_DIR        "...../reports"
  $OUT_DIR        "...../outputs"
  $WORK_DIR       "...../work"
  $INPUT_DIR      "...../inputs"
  $DB_DIR         "...../database"
  $PHASE_SETUP    "10_BUILD-T"
  $PHASE_DRC      "20_DRC-T"
  $PHASE_INSERT   "25_INSERT"
  $PHASE_FAULT    "30_FAULT"
  $PHASE_ENGINE   "40_TEST-T"
  $PHASE_SIM      "60_SIM"
  $PHASE_EXPORT   "80_EXPORT"
  + any --top-module and --inject values

EXAMPLES:
  # Minimum required
  python core/orch_run.py \
      --iter-path $ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001 \
      --tcl tcl/SYNOPSYS/my_atpg.tcl

  # Full with all input types
  python core/orch_run.py \
      --iter-path $ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001 \
      --tcl tcl/SYNOPSYS/my_atpg.tcl \
      --netlist /path/to/i2c_dc_scan.vg \
      --libs /home/DFT_libs/synopsys/gen.v \
      --spf /path/to/i2c_dc_scan.spf \
      --top-module i2c_master_top \
      --inject FAULT_TYPE=SAF EDT_CHANNELS=2

  # Rerun after fixing a TCL bug
  python core/orch_run.py \
      --iter-path $ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001 \
      --tcl tcl/SYNOPSYS/my_atpg.tcl --rerun

  # Debug run (don't normalize outputs yet)
  python core/orch_run.py ... --no-harvest

  # Quick smoke test
  python core/orch_run.py ... --timeout-hrs 2


================================================================================
## SECTION 11: harvest.py — STEP 3: NORMALIZE OUTPUTS
================================================================================

Location: core/harvest.py
Purpose: After tool exits, renames all outputs to standard phase-prefixed names,
         passports logs, wipes work/. Auto-called by orch_run.py.
Scope: PER ITERATION ONLY — never reads or writes outside the given iter folder.

FLAGS:
  --iter-path PATH     Required. Path to iter_NNN folder.
  --no-wipe-work       Keep work/ after harvest (for debugging).
                       Default: work/ is wiped after all files rescued.
  --extra-search-dirs  Additional directories to search for raw outputs.
  --phase-map JSON     Override phase inference with custom pattern->index mapping.
                       Example: '{"my_custom_report": 40, "special_log": 20}'

WHAT harvest.py DOES (in order):
  1. Scans work/ for .rpt files → copies to reports/ with phase prefix
  2. Scans work/ for .log files → copies to logs/ with phase prefix
  3. Prepends "Passport" header to every log in logs/ (idempotent)
  4. Extracts tool version from logs via regex → writes to .metadata
  5. Wipes work/ (unless --no-wipe-work)
  6. Sets .metadata harvest_done=True

PHASE INFERENCE: harvest.py guesses the phase index from the filename using
keyword matching against a comprehensive TMAX 175-command taxonomy map.
Keywords map to phases:
  phase 10: build, setup, init, load_netlist, modules, library, workspace
  phase 20: drc, rules, violations, scan_chain, scan_cell, nonscan, buses,
            clocks, feedback_path, lockup, serializer, compressor, timing, sdc,
            layout, physical, wires, fanin, fanout, pins, instances, memory
  phase 30: fault_pre, fault_before, pre_add, fault_model, add_faults
  phase 40: atpg, coverage, fault_summary, patterns, constraints, primitives,
            summaries, testpoint, diagnosis, power, iddq, toggle, reorder
  phase 60: sim, simulation, fault_sim, simtrace
  phase 80: export, write_pattern, write_fault, stil, wgl, testbench, ydf
  default: phase 40

NOTE: If you use wrpt proc from _factory_helpers.tcl in your TCL, reports
already land in reports/ with correct phase-prefixed names. Harvest is then
purely a safety net that passports logs and wipes work/.

PASSPORT HEADER (prepended to every log):
  # =========================================================================
  # DFT DATA FACTORY — LOG PASSPORT
  # Design       : i2c_master
  # Tool suite   : SYNOPSYS
  # Stage        : ATPG
  # Exp / Sub    : SA_EXP1 / E1.1
  # Iteration    : iter_001
  # Status       : PASS
  # Runtime      : 4991 s
  # Started      : 2025-06-01T09:00:00+00:00
  # Ended        : 2025-06-01T10:23:11+00:00
  # Tool version : 2024.03
  # Source file  : iter_001_raw.log
  # Harvested    : 2025-06-01T10:23:15+00:00
  # =========================================================================

This makes every log self-describing — open any log cold and instantly know
its full context without needing the directory structure.

TOOL VERSION EXTRACTION: Scans logs for patterns:
  SYNOPSYS: "TetraMAX X.X", "TMAX X.X", "Version X.X"
  TESSENT:  "Tessent X.X", "Mentor X.X", "Version X.X"
Writes extracted version to .metadata tool_version.

EXAMPLES:
  # Standard (auto-called by orch_run.py, no need to call manually)
  python core/harvest.py --iter-path .../iter_001

  # Debug: keep work/ to inspect raw output
  python core/harvest.py --iter-path .../iter_001 --no-wipe-work

  # Custom phase mapping for non-standard report names
  python core/harvest.py --iter-path .../iter_001 \
      --phase-map '{"my_custom_cov_rpt": 40, "special_drc_check": 20}'


================================================================================
## SECTION 12: lifecycle.py — STEP 4: CROSS-ITERATION MANAGEMENT
================================================================================

Location: core/lifecycle.py
Purpose: Tag iterations, list status, purge trash, build trend CSV.
Scope: CROSS-ITERATION — reads across multiple iters, never writes inside one.

ACTION FLAGS (one required per call):
  --tag GOLDEN|TRASH|null   Tag a specific iteration.
    GOLDEN: marks as reference/locked. Only settable on PASS (warns on non-PASS).
            Used for chain resolution: ATPG looks for GOLDEN SCAN iteration.
    TRASH:  marks for deletion (does not delete yet).
    null:   clears the tag.
    Requires: --iter-path
    Guards: cannot tag a locked (running) iteration.

  --list                    Print table of all iterations under --scope.
    Shows: status, tag, design, tool_suite, stage, exp_id, sub_exp_id,
           iter_id, runtime.
    Supports filtering (see below).

  --purge-trash             Permanently delete all TRASH-tagged iterations.
    IRREVERSIBLE. Always use --dry-run first.
    Prompts for confirmation.

  --build-csv               Build trend_analysis.csv from all iters under --scope.
    Reads .metadata from every iteration.
    Scrapes report files for KPI values.
    Writes one row per iteration.

SCOPE / OUTPUT FLAGS:
  --scope PATH     Root path to operate on. Default: FACTORY_ROOT.
                   Narrow to a design: --scope $ROOT/i2c_master
                   Narrow to a stage:  --scope $ROOT/i2c_master/SYNOPSYS/ATPG
  --iter-path PATH For --tag only. Path to the specific iteration.
  --output PATH    For --build-csv. Where to write the CSV.
                   Default: scope/analysis/trend_analysis.csv
  --dry-run        For --purge-trash. Preview deletions without executing.

FILTER FLAGS (for --list only):
  --filter-status  PASS|FAIL|RUNNING|ABORTED|PENDING
  --filter-tag     GOLDEN|TRASH
  --filter-design  design_name

KPI EXTRACTION (for --build-csv):
  lifecycle.py reads all .rpt files in iter/reports/ and scrapes 13 KPIs
  using regex patterns:
    fault_coverage_pct       "Fault Coverage = 97.3"
    atpg_effectiveness_pct   "ATPG Effectiveness = 99.1"
    total_faults             "Total Faults: 45231"
    detected_faults          "Detected: 43891"
    undetected_faults        "Undetected: 1340" or "UD: 1340"
    redundant_faults         "Redundant: 412" or "RE: 412"
    blocked_faults           "Blocked: 88" or "BL: 88"
    total_patterns           "Total Patterns: 1247"
    scan_chains_count        "Scan Chains: 4"
    scan_cells_count         "Scan Cells: 8921"
    nonscan_cells_count      "Non-scan Cells: 234"
    cpu_peak_pct             "CPU Usage: 87.3"
    mem_peak_mb              "Memory Usage: 4231.5 MB"

  NOTE: These regex patterns will need tuning once real TMAX output is seen.
  The exact format of report_summaries output determines whether they match.
  Extending: add one entry to _KPI_REGEX dict in lifecycle.py.

TREND CSV COLUMNS (in order):
  design, tool_suite, stage, exp_id, sub_exp_id, iter_id,
  iter_tag, status, experiment_note,
  timestamp_start, runtime_s, tool_version,
  fault_coverage_pct, atpg_effectiveness_pct,
  total_faults, detected_faults, undetected_faults, total_patterns,
  scan_chains_count, scan_cells_count, nonscan_cells_count,
  cpu_peak_pct, mem_peak_mb,
  parent_iter

EXAMPLES:
  # Tag iter_003 as reference
  python core/lifecycle.py --tag GOLDEN \
      --iter-path $ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_003

  # Tag failed runs for cleanup
  python core/lifecycle.py --tag TRASH \
      --iter-path $ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001

  # List all iterations for i2c_master
  python core/lifecycle.py --list --scope $ROOT/i2c_master

  # List only PASS iterations
  python core/lifecycle.py --list --scope $ROOT/i2c_master --filter-status PASS

  # List only GOLDEN iterations
  python core/lifecycle.py --list --filter-tag GOLDEN

  # Preview trash deletion
  python core/lifecycle.py --purge-trash --dry-run --scope $ROOT/i2c_master

  # Delete trash
  python core/lifecycle.py --purge-trash --scope $ROOT/i2c_master

  # Build CSV for analysis
  python core/lifecycle.py --build-csv --scope $ROOT/i2c_master
  # Output: $ROOT/i2c_master/analysis/trend_analysis.csv


================================================================================
## SECTION 13: env_gate.sh — TOOL ENVIRONMENT SWITCHER
================================================================================

Location: tools/env_gate.sh
Written in: csh (not bash — matches the server's tool environment)
Called by: orch_run.py via subprocess
Purpose: Mirror exactly what the user types manually to set up each tool.

For SYNOPSYS: just verifies tmax is in PATH (already available after csh)
For TESSENT:  sources /home/mentor.cshrc (exactly as done manually)

After setup, prints full env via "env" — orch_run.py absorbs these into the
Python process's os.environ so the subprocess launched by Python inherits them.

NEVER call env_gate.sh directly. orch_run.py handles it automatically.

To add a new tool: add a case block following the same pattern.

IMPORTANT SERVER CONTEXT:
- This is a shared remote company server (multiple engineers, location unknown)
- Tools are pre-installed by admins
- No sudo access needed, no installation
- Each engineer has their own home directory and works independently
- The factory hierarchy isolates each engineer's work completely


================================================================================
## SECTION 14: TCL HELPER LIBRARY — _factory_helpers.tcl
================================================================================

Location: tcl/SYNOPSYS/_factory_helpers.tcl
Purpose: 6 TCL procs to use in every script. Source at top of your TCL.
         These are the ONLY interface between your TCL and the factory system.

SOURCE AT TOP OF EVERY SCRIPT:
  if { ![info exists _FACTORY_REPORTS] } {
      source "${_dir}/_factory_helpers.tcl"
  }
  (orch_run.py also sources it automatically via the merged script)

THE 6 PROCS:

1. wrpt  $PHASE_VAR  short_name  { tool_command }
   Writes one report. Names it: $RPT_DIR/${phase}_${name}.rpt
   Tracks it internally for check_reports validation.
   Example:
     wrpt $PHASE_ENGINE fault_summary { report_faults -summary -verbose }
     → reports/40_TEST-T_fault_summary.rpt
   Custom sub-phases:
     set PHASE_FAULT_PRE "30_FAULT-PRE"
     wrpt $PHASE_FAULT_PRE pre_summary { report_faults -summary -verbose }
     → reports/30_FAULT-PRE_pre_summary.rpt

2. wlog  $PHASE_VAR  short_name
   Redirects tool log for a phase section.
   Calls set_messages -log internally.
   Example:
     wlog $PHASE_DRC drc_run
     → logs/20_DRC-T_drc_run.log

3. wdb   $PHASE_VAR  short_name  {ext "db"}
   Returns the correct path for a binary database save.
   YOU still call the save command; this just gives the right path.
   Example:
     set db_path [wdb $PHASE_ENGINE post_atpg]
     write_scan_chain_db $db_path -replace
     → database/40_TEST-T_post_atpg.db

4. wout  short_name  extension
   Returns the correct path for a deliverable output file.
   Names it: $OUT_DIR/${name}_${RUN_TAG}.${ext}
   Example:
     write_patterns [wout patterns stil] -format stil
     → outputs/patterns_i2c_master__SYNOPSYS__ATPG__SA_EXP1__E1.1__iter_001.stil

5. factory_banner  "label text"
   Prints a visible phase separator in the log.
   Use at the start of every phase section for easy grep/navigation.
   Example:
     factory_banner "PHASE 40 — ATPG ENGINE"

6. check_reports
   Call as the VERY LAST LINE of every script.
   Validates all files registered by wrpt actually exist and are non-empty.
   Prints: OK/MISSING/EMPTY for each, total counts, STATUS: ALL REPORTS OK.


================================================================================
## SECTION 15: EXAMPLE SCRIPT — ATPG_SAF_EXP1.1.tcl
================================================================================

Location: tcl/SYNOPSYS/ATPG_SAF_EXP1.1.tcl
This is the user's original EXP1.1 SAF script REWRITTEN using the factory.
It shows exactly what changed vs the old hardcoded version.

WHAT WAS REMOVED vs old script:
  - set DESIGN, EXP_ID, RUN_TAG         (injected by Python)
  - set LOG_DIR, OUT_DIR, RPT_DIR        (injected by Python)
  - set PHASE_BUILD "01_build" etc.      (use $PHASE_SETUP, $PHASE_ENGINE etc.)
  - cleanup_run proc                     (handled by orch_run.py --rerun)
  - file mkdir $LOG_DIR etc.             (Python creates the tree before TCL runs)
  - hardcoded /home/DFT_libs/... paths   (symlinked into $INPUT_DIR)
  - hardcoded ../input/... paths         (symlinked into $INPUT_DIR)

WHAT STAYED THE SAME:
  - Every tool command (read_netlist, run_build_model, run_drc, run_atpg etc.)
  - Every report command (report_faults, report_scan_chains etc.)
  - Every flag on every command (-verbose, -summary, -collapsed etc.)
  - Every write_patterns format variant (stil, wgl, binary, serial, parallel)
  - The wrpt proc (kept, but now from _factory_helpers.tcl)
  - The check_reports proc (kept, now from _factory_helpers.tcl)

HOW INPUTS ARE FOUND:
  Old: read_netlist -library /home/DFT_libs/synopsys/gen.v
  New: set LIB_FILE [lindex [glob "${INPUT_DIR}/*.v"] 0]
       read_netlist -library $LIB_FILE

  Python symlinks /home/DFT_libs/synopsys/gen.v → iter_001/inputs/gen.v
  TCL globs $INPUT_DIR to find it — no hardcoded paths.

PHASE STRUCTURE IN THE EXAMPLE:
  Phase 10 (SETUP):   read_netlist, run_build_model, report_modules, report_rules
  Phase 20 (DRC):     add_clocks, run_drc, all scan reports (chains, cells, path etc.)
  Phase 30 (FAULT):   set_atpg, set_faults, report pre/post add_faults
  Phase 40 (ENGINE):  run_atpg, all post-ATPG reports
  Phase 60 (SIM):     run_simulation, run_fault_sim (optional, behind if block)
  Phase 80 (EXPORT):  write_faults, write_patterns (all variants), write_scan_chain_db


================================================================================
## SECTION 16: COMPLETE WORKFLOW — EVERY RUN FROM ZERO
================================================================================

### ONE-TIME SETUP (do once on the server):
  # 1. Copy factory to your home directory
  cp -r dft_factory ~/dft_factory
  cd ~/dft_factory

  # 2. Set FACTORY_ROOT
  nano config/factory_config.py
  # Change: FACTORY_ROOT = Path("/home/yourname/dft_experiments")

  # 3. Make scripts executable
  chmod +x core/*.py tools/env_gate.sh

  # 4. Test dir creation
  python core/dir_init.py --design i2c_master --tool SYNOPSYS --stage ATPG \
      --exp SA_EXP1 --sub E1.1 --iter iter_001 --dry-run
  # Verify the printed path looks correct, then remove --dry-run

### EVERY EXPERIMENT RUN:

  # Step 1: Create iteration
  python core/dir_init.py \
      --design i2c_master --tool SYNOPSYS --stage ATPG \
      --exp SA_EXP1 --sub E1.1 --iter auto \
      --note "SAF baseline, 2 EDT channels"

  # Step 2: Run
  python core/orch_run.py \
      --iter-path $FACTORY_ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001 \
      --tcl ~/dft_factory/tcl/SYNOPSYS/my_atpg_saf.tcl \
      --netlist /path/to/i2c_dc_scan.vg \
      --libs /home/DFT_libs/synopsys/gen.v \
      --spf /path/to/i2c.spf \
      --top-module i2c_master_top \
      --inject FAULT_TYPE=SAF

  # (harvest.py is called automatically on exit)

  # Step 3: Check results
  python core/lifecycle.py --list --scope $FACTORY_ROOT/i2c_master

  # Step 4: Tag good runs
  python core/lifecycle.py --tag GOLDEN \
      --iter-path $FACTORY_ROOT/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001

  # Step 5: Tag bad runs
  python core/lifecycle.py --tag TRASH \
      --iter-path $FACTORY_ROOT/.../iter_bad

  # Step 6: Build analysis CSV
  python core/lifecycle.py --build-csv --scope $FACTORY_ROOT/i2c_master

  # Step 7: Cleanup
  python core/lifecycle.py --purge-trash --dry-run  # preview first
  python core/lifecycle.py --purge-trash --scope $FACTORY_ROOT/i2c_master


### COMPARING EXPERIMENTS (the whole point):
  # After 10+ iterations, load the CSV in Python/pandas:
  import pandas as pd
  df = pd.read_csv("i2c_master/analysis/trend_analysis.csv")

  # Coverage vs EDT channels
  df[["sub_exp_id","fault_coverage_pct","total_patterns","runtime_s"]]\
      .query("status == 'PASS'")\
      .sort_values("fault_coverage_pct", ascending=False)

  # Synopsys vs Tessent on same design
  df.query("stage == 'ATPG'")\
      .groupby("tool_suite")[["fault_coverage_pct","runtime_s"]].mean()


================================================================================
## SECTION 17: THINGS VERIFIED WORKING
================================================================================

  dir_init.py ran successfully on the real server. Created the correct
  6-level folder tree flawlessly. This was confirmed by the user.

  All Python files pass syntax check (ast.parse) — verified in session.

  The TCL helper procs (wrpt, wlog, wdb, wout, factory_banner, check_reports)
  are logically correct and follow TMAX proc conventions.

  The injected TCL header format is valid TCL syntax (set VAR "VALUE").

  The phase prefix naming is consistent across harvest.py and _factory_helpers.tcl.


================================================================================
## SECTION 18: KNOWN LIMITATIONS AND THINGS NOT YET BUILT
================================================================================

### KPI REGEX NEEDS TUNING (most important)
  lifecycle.py's _KPI_REGEX patterns are best-effort guesses at TMAX output format.
  Once real report_summaries and report_faults output is seen from actual runs,
  the patterns will need tuning. This is easy — one line per KPI in _KPI_REGEX.
  The user should: run one experiment → look at actual .rpt content → adjust patterns.

### ANALYSIS LAYER NOT BUILT
  trend_analysis.csv is generated but no notebooks/plots exist yet.
  Next step: build pandas/matplotlib analysis notebooks in notebooks/ folder.
  Questions to answer: coverage vs iterations, SYNOPSYS vs TESSENT, runtime trends.

### NO PARALLEL LAUNCH
  The factory launches one run at a time. If the user wants to launch
  multiple experiments simultaneously (e.g. 4 EDT channel variants in parallel),
  they currently run orch_run.py multiple times in separate terminals.
  A batch launcher (batch_run.py) could be built to automate this.

### TESSENT TCL TEMPLATE NOT WRITTEN
  tcl/TESSENT/ is empty. The user needs to write their Tessent .do script.
  The factory infrastructure supports it fully — env_gate.sh sources mentor.cshrc,
  TESSENT is in TOOL_REGISTRY, TESSENT phases have correct mode names.
  The user just needs to write the .do body using the same $PHASE_* variables.

### CHAIN RESOLVER NOT FULLY IMPLEMENTED
  factory_config.py defines chain_from (ATPG chains from SCAN, SIM from ATPG).
  But dir_init.py does not yet auto-symlink the GOLDEN upstream iteration's outputs/
  into the new iteration's inputs/. This must be done manually for now:
  manually symlink: $ROOT/design/SYNOPSYS/SCAN/EXP/sub/iter_GOLDEN/outputs/ into
                    $ROOT/design/SYNOPSYS/ATPG/EXP/sub/iter_001/inputs/

### BACKGROUND / NOHUP SUPPORT
  If the SSH connection drops, the tool run may die. The user should use:
    nohup python core/orch_run.py ... > run.log 2>&1 &
  or run inside a screen/tmux session. This is not automated by the factory.

### REPORT EXTENSION SUPPORT
  harvest.py currently only collects .rpt and .log files.
  Some tools produce .csv, .txt, .xml. Use --extra-search-dirs if needed.


================================================================================
## SECTION 19: FILE CONTENTS QUICK REFERENCE
================================================================================

config/factory_config.py
  FACTORY_ROOT, TOOL_REGISTRY, STAGE_REGISTRY, PHASE_INDEX,
  ITER_SUBDIRS, METADATA_DEFAULTS, TREND_CSV_COLUMNS

core/utils.py
  iter_path(), next_iter_id(), read_meta(), write_meta(), init_meta(),
  validate(), phase_prefix(), now_iso()

core/dir_init.py
  create_tree(), add_stage(), main() + argparse
  Flags: --design --tool --stage --exp --sub --iter --note --dry-run
         --list-stages --add-stage --stage-desc --stage-phases --stage-chain-from

core/orch_run.py
  acquire_lock(), release_lock(), rerun_reset(), symlink_inputs(),
  build_tcl_header(), write_merged_tcl(), launch(), main() + argparse
  Flags: --iter-path --tcl --netlist --libs --spf --sdc --timing --layout
         --extras --top-module --inject --rerun --no-harvest --timeout-hrs

core/harvest.py
  passport(), prepend_passport(), infer_phase(), harvest_reports(),
  harvest_logs(), extract_version(), main() + argparse
  Flags: --iter-path --no-wipe-work --extra-search-dirs --phase-map

core/lifecycle.py
  find_iters(), tag(), list_iters(), purge_trash(), extract_kpis(),
  build_csv(), main() + argparse
  Flags: --tag --iter-path --list --purge-trash --build-csv
         --scope --output --dry-run
         --filter-status --filter-tag --filter-design

tools/env_gate.sh
  csh script. switch on $1 (SYNOPSYS or TESSENT).
  SYNOPSYS: verifies tmax in PATH.
  TESSENT: sources /home/mentor.cshrc, verifies tessent in PATH.
  Prints full env at end for Python to absorb.

tcl/SYNOPSYS/_factory_helpers.tcl
  wrpt, wlog, wdb, wout, factory_banner, check_reports

tcl/SYNOPSYS/ATPG_SAF_EXP1.1.tcl
  Example script using all helpers. Shows old→new migration.


================================================================================
## SECTION 20: IMPORTANT DESIGN DECISIONS AND RATIONALE
================================================================================

WHY Python wraps TCL, not the other way:
  Python is better at filesystem ops, metadata, subprocess management, CSV,
  and future analysis. TCL is the tool's native language for tool commands.
  Keep each in its domain.

WHY symlinks in inputs/, never copies:
  Netlist and library files are large. Copying them for every iteration would
  quickly exhaust disk. Symlinks give each iteration independent addressability
  while sharing the actual data. The factory never modifies input files.

WHY work/ is always wiped after harvest:
  work/ is the tool's temporary scratchpad — full of intermediate files,
  temp databases, partial results. It is large and reproducible. After
  harvest rescues everything important, work/ has no value. Wiping it
  keeps the factory disk footprint manageable across hundreds of iterations.

WHY config/ keeps the ORIGINAL TCL body (unmodified):
  scripts/ has the merged script (header + body) that was actually run.
  config/ has your original body exactly as you wrote it.
  This separation means: if you update your TCL script and rerun, you can
  diff config/old_script.tcl vs the new one to see what changed.

WHY .metadata uses lock field:
  On a shared server, it's possible to accidentally launch the same iteration
  twice (two terminals, a cron job, etc.). The lock prevents two orch_run.py
  instances from corrupting each other's outputs. If a run crashes without
  releasing the lock, --rerun clears it.

WHY phase index uses gaps (10, 20, 25, 30, 40, 60, 80):
  Gaps allow inserting sub-phases (like 25_INSERT for EDT/MBIST) without
  renumbering existing phases. If you're at 10, 20, 30, 40 and need to add
  something between 20 and 30, use 25. The sort order is preserved numerically.

WHY SYNOPSYS and TESSENT (not TMAX and TESSENT):
  Level 2 of the hierarchy is the TOOL SUITE (company), not the specific binary.
  SYNOPSYS may have multiple binaries in future (TetraMAX, Formality etc.).
  Using the suite name keeps the hierarchy stable even if specific tools change.


================================================================================
## END OF HANDOFF DOCUMENT
================================================================================

The system is built, tested at dir_init level, and ready for first real run.
The user's next action is to run orch_run.py with their first real TCL script
on the i2c_master design using SYNOPSYS ATPG stage.

After first real run: tune lifecycle.py KPI regex patterns against actual
report_summaries output, then begin building analysis notebooks.
