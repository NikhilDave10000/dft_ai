# =============================================================================
# DFT DATA FACTORY — MASTER CONFIGURATION
# =============================================================================
# Single source of truth. Edit this file only.
# All other scripts import from here — never hardcode anything elsewhere.
# =============================================================================

from pathlib import Path

# =============================================================================
# ROOT — SET THIS TO YOUR DIRECTORY ON THE SERVER
# =============================================================================
FACTORY_ROOT = Path("/your/path/here")

# =============================================================================
# TOOL SUITES
# Level 2 of the hierarchy: SYNOPSYS | TESSENT
#
# binary      : command name as you type it in the terminal (no full path needed
#               since the server already has it in PATH after csh/source)
# shell       : "csh" or "bash" — the shell your tool runs in
# init_source : file to source before the tool, or None
# launch_flag : how the tool accepts a script file
# =============================================================================
TOOL_REGISTRY = {
    "SYNOPSYS": {
        "binary":      "tmax",
        "shell":       "csh",
        "init_source": None,           # tmax is already in PATH after csh
        "launch_flag": "-f",           # tmax -f script.tcl
        "suite_label": "Synopsys TetraMAX",
    },
    "TESSENT": {
        "binary":      "tessent",
        "shell":       "csh",
        "init_source": "/home/mentor.cshrc",   # source this before tessent
        "launch_flag": "-dofile",              # tessent -shell -dofile script.do -log
        "extra_flags": ["-shell"],
        "log_flag":    "-log",
        "suite_label": "Siemens Tessent",
    },
}

# =============================================================================
# DFT STAGES
# Level 3 of the hierarchy.
#
# Current stages: SCAN | ATPG | SIM
# To add a new stage: add one entry here. That's it. No other file needs editing.
#
# phases        : ordered list of phase indices active in this stage
# chain_from    : upstream stage whose GOLDEN outputs/ feeds this stage's inputs/
#                 None = no upstream dependency
# =============================================================================
STAGE_REGISTRY = {
    "SCAN": {
        "description": "Scan insertion, DRC, scan chain validation",
        "phases":      [10, 20, 30],
        "chain_from":  None,
    },
    "ATPG": {
        "description": "ATPG pattern generation (SAF, TF, IDDQ, etc.)",
        "phases":      [10, 20, 30, 40, 80],
        "chain_from":  "SCAN",         # ATPG takes scan-inserted netlist from SCAN
    },
    "SIM": {
        "description": "Fault simulation and pattern verification",
        "phases":      [10, 60, 80],
        "chain_from":  "ATPG",         # SIM takes patterns from ATPG
    },
    # -------------------------------------------------------------------------
    # To add a new stage later, just append here. Example:
    # "MBIST": {
    #     "description": "Memory BIST insertion",
    #     "phases":      [10, 20, 25, 40, 80],
    #     "chain_from":  None,
    # },
    # "EDT": {
    #     "description": "Embedded Deterministic Test",
    #     "phases":      [10, 20, 40, 60, 80],
    #     "chain_from":  "ATPG",
    # },
    # -------------------------------------------------------------------------
}

# =============================================================================
# PHASE INDEX — UNIVERSAL NAMING LANGUAGE
# Maps a numeric index (10–99) to a human name and per-tool mode string.
# This is how logs/reports get their prefix: 10_setup.log, 40_engine.rpt
#
# Gaps (50, 70, 90) are intentional — reserved for future sub-phases.
# Insert a new sub-phase (e.g. 25) without renumbering anything.
# =============================================================================
PHASE_INDEX = {
    10: {"name": "setup",   "SYNOPSYS": "BUILD-T",        "TESSENT": "SETUP"},
    20: {"name": "drc",     "SYNOPSYS": "DRC-T",          "TESSENT": "ANALYSIS"},
    25: {"name": "insert",  "SYNOPSYS": "INSERT",         "TESSENT": "INSERTION"},   # sub-phase slot
    30: {"name": "fault",   "SYNOPSYS": "FAULT",          "TESSENT": "FAULT-MODEL"},
    40: {"name": "engine",  "SYNOPSYS": "TEST-T",         "TESSENT": "ATPG"},
    60: {"name": "sim",     "SYNOPSYS": "SIM",            "TESSENT": "SIMULATION"},
    80: {"name": "export",  "SYNOPSYS": "EXPORT",         "TESSENT": "EXPORT"},
}

# =============================================================================
# ITERATION LEAF NODE SUBDIRECTORIES
# Every iter_NNN folder always has exactly these subdirs. No exceptions.
# =============================================================================
ITER_SUBDIRS = [
    "config",     # TCL/.do scripts actually used — physical copies
    "inputs",     # SOFT LINKS ONLY — netlists, libs, SPF
    "scripts",    # Python/Bash launcher — physical copy for reproducibility
    "logs",       # Renamed: 10_setup.log, 20_drc.log
    "reports",    # Standardized: 10_stats.rpt, 40_cov.rpt
    "database",   # Binary save points: 20_state.db, 40_state.bin
    "outputs",    # Deliverables: patterns (.stil/.wgl), fault lists
    "work",       # Tool scratchpad — deleted after harvest
]

# =============================================================================
# .metadata JSON SCHEMA
# Written at iter creation, updated throughout the run lifecycle.
# =============================================================================
METADATA_DEFAULTS = {
    "status":          "PENDING",   # PENDING | RUNNING | PASS | FAIL | ABORTED
    "lock":            False,       # True while a job is active
    "iter_tag":        None,        # GOLDEN | TRASH | null
    "design":          None,
    "tool_suite":      None,        # SYNOPSYS | TESSENT
    "stage":           None,        # SCAN | ATPG | SIM
    "exp_id":          None,
    "sub_exp_id":      None,
    "iter_id":         None,
    "experiment_note": "",          # free-text description of this experiment
    "tool_version":    None,        # extracted from log after run
    "timestamp_start": None,
    "timestamp_end":   None,
    "runtime_s":       None,
    "phases_completed":[],
    "parent_iter":     None,        # set on --rerun, points to original iter_id
    "harvest_done":    False,
}

# =============================================================================
# TREND CSV COLUMNS
# What lifecycle.py extracts into trend_analysis.csv
# Metadata fields first, then KPIs parsed from reports.
# =============================================================================
TREND_CSV_COLUMNS = [
    # --- identity ---
    "design", "tool_suite", "stage", "exp_id", "sub_exp_id", "iter_id",
    "iter_tag", "status", "experiment_note",
    # --- timing ---
    "timestamp_start", "runtime_s", "tool_version",
    # --- coverage KPIs (parsed from reports) ---
    "fault_coverage_pct", "atpg_effectiveness_pct",
    "total_faults", "detected_faults", "undetected_faults",
    "total_patterns",
    # --- scan KPIs ---
    "scan_chains_count", "scan_cells_count", "nonscan_cells_count",
    # --- resource KPIs ---
    "cpu_peak_pct", "mem_peak_mb",
    # --- lineage ---
    "parent_iter",
]
