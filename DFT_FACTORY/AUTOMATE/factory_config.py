# =============================================================================
# DFT DATA FACTORY — MASTER CONFIGURATION
# =============================================================================
# This is the single source of truth for the entire system.
# Edit FACTORY_ROOT to your actual path. Everything else derives from it.
# =============================================================================

from pathlib import Path

# =============================================================================
# ROOT — EDIT THIS ONE LINE FOR YOUR ENVIRONMENT
# =============================================================================
FACTORY_ROOT = Path("/your/dedicated/path/dft_factory")

# =============================================================================
# TOOL SUITE REGISTRY
# Each tool suite has: binary path, license env var, supported stages
# =============================================================================
TOOL_REGISTRY = {
    "TMAX": {
        "binary":      "/path/to/synopsys/tetramax/bin/tmax",
        "license_var": "SNPSLMD_LICENSE_FILE",
        "license_val": "27000@your_license_server",
        "shell_init":  "/path/to/synopsys/setup.sh",   # sourced before launch
        "supported_stages": ["ATPG_SAF", "ATPG_TF", "ATPG_IDDQ"],
    },
    "TESSENT": {
        "binary":      "/path/to/siemens/tessent/bin/tessent",
        "license_var": "MGLS_LICENSE_FILE",
        "license_val": "27000@your_license_server",
        "shell_init":  "/path/to/siemens/setup.sh",
        "supported_stages": ["ATPG_SAF", "ATPG_TF", "MBIST", "EDT", "OCC"],
    },
}

# =============================================================================
# STAGE REGISTRY
# Maps stage names to their phase index sequences and chaining rules
# =============================================================================
STAGE_REGISTRY = {
    "ATPG_SAF": {
        "description":    "Stuck-At Fault ATPG",
        "phases":         [10, 20, 30, 40, 60, 80],
        "chain_from":     None,           # no upstream dependency
        "chain_output":   "outputs/patterns",
    },
    "ATPG_TF": {
        "description":    "Transition Fault ATPG",
        "phases":         [10, 20, 30, 40, 60, 80],
        "chain_from":     None,
        "chain_output":   "outputs/patterns",
    },
    "MBIST": {
        "description":    "Memory BIST Insertion",
        "phases":         [10, 20, 25, 40, 80],
        "chain_from":     None,
        "chain_output":   "outputs/mbist_netlist",
    },
    "EDT": {
        "description":    "Embedded Deterministic Test",
        "phases":         [10, 20, 25, 40, 60, 80],
        "chain_from":     "ATPG_SAF",     # EDT takes SAF patterns as input
        "chain_output":   "outputs/edt_patterns",
    },
    "RTL_DFT": {
        "description":    "RTL-level DFT insertion",
        "phases":         [10, 20, 40, 80],
        "chain_from":     None,
        "chain_output":   "outputs/dft_netlist",
    },
}

# =============================================================================
# PHASE INDEX — UNIVERSAL LANGUAGE
# Maps numeric phase index to human name and per-tool mode strings
# =============================================================================
PHASE_INDEX = {
    10: {
        "name":        "setup",
        "TMAX":        "BUILD-T",
        "TESSENT":     "SETUP",
        "description": "Design load, model build, library setup",
    },
    20: {
        "name":        "drc",
        "TMAX":        "DRC-T",
        "TESSENT":     "ANALYSIS",
        "description": "Design Rule Check, scan chain validation",
    },
    25: {
        "name":        "insertion",
        "TMAX":        "INSERT",          # sub-phase slot for EDT/MBIST
        "TESSENT":     "INSERTION",
        "description": "RTL/gate-level DFT insertion sub-phase",
    },
    30: {
        "name":        "fault",
        "TMAX":        "FAULT",
        "TESSENT":     "ANALYSIS",
        "description": "Fault model initialization and analysis",
    },
    40: {
        "name":        "engine",
        "TMAX":        "TEST-T",
        "TESSENT":     "INSERTION-ATPG",
        "description": "ATPG engine execution, pattern generation",
    },
    60: {
        "name":        "sim",
        "TMAX":        "SIM",
        "TESSENT":     "SIMULATION",
        "description": "Fault simulation, pattern verification",
    },
    80: {
        "name":        "export",
        "TMAX":        "EXPORT",
        "TESSENT":     "EXPORT",
        "description": "Write patterns, save databases, deliverables",
    },
}

# =============================================================================
# LEAF NODE SUBDIRECTORY LAYOUT
# Every iteration folder has exactly these subdirs
# =============================================================================
ITER_SUBDIRS = [
    "config",       # TCL/DO scripts actually used (physical copies)
    "inputs",       # symlinks only — never copy heavy files
    "scripts",      # Python/Bash launcher scripts (physical copies)
    "work",         # tool scratchpad — deleted after harvest
    "logs",         # cleaned, renamed log transcripts
    "reports",      # structured .rpt files with phase-prefix naming
    "database",     # binary tool state (.db/.bin) for GUI restore
    "outputs",      # final deliverables: patterns, fault lists
]

# =============================================================================
# METADATA SCHEMA
# Written as .metadata JSON at every iteration leaf node
# =============================================================================
METADATA_SCHEMA = {
    "status":           "PENDING",   # PENDING | RUNNING | PASS | FAIL | ABORTED
    "lock":             False,        # True while a job is active (prevents double-run)
    "iter_tag":         None,         # GOLDEN | TRASH | null
    "tool":             None,
    "tool_version":     None,
    "stage":            None,
    "exp_id":           None,
    "sub_exp":          None,
    "iter_id":          None,
    "design":           None,
    "fault_type":       None,
    "timestamp_start":  None,         # ISO 8601
    "timestamp_end":    None,
    "runtime_s":        None,
    "phase_completed":  [],           # list of phase indices completed
    "parent_iter":      None,         # set on --rerun, points to original iter
    "harvest_done":     False,
    "notes":            "",
}

# =============================================================================
# HARVEST RULES
# Maps TCL report name patterns → standard phase-prefixed output names
# Format: (regex_match_in_source, phase_index, standard_suffix)
# =============================================================================
HARVEST_RULES = {
    "TMAX": [
        # (source filename pattern,    phase, standard name)
        ("01_build_modules_summary",   10,   "setup_modules_summary.rpt"),
        ("01_build_modules_error",     10,   "setup_modules_error.rpt"),
        ("01_build_rules_fail",        10,   "setup_rules_fail.rpt"),
        ("01_build_violations",        10,   "setup_violations.rpt"),
        ("02_drc_rules_fail",          20,   "drc_rules_fail.rpt"),
        ("02_drc_violations",          20,   "drc_violations.rpt"),
        ("03_scan_clocks",             20,   "drc_scan_clocks.rpt"),
        ("03_scan_nonscan_cells",      20,   "drc_nonscan_cells.rpt"),
        ("03_scan_buses",              20,   "drc_buses.rpt"),
        ("03_scan_feedback_paths",     20,   "drc_feedback_paths.rpt"),
        ("03_scan_scan_chains",        20,   "drc_scan_chains.rpt"),
        ("03_scan_scan_cells",         20,   "drc_scan_cells.rpt"),
        ("03_scan_scan_ability",       20,   "drc_scan_ability.rpt"),
        ("03_scan_scan_enables",       20,   "drc_scan_enables.rpt"),
        ("03_scan_scan_path",          20,   "drc_scan_path.rpt"),
        ("04_faults_before_summaries", 30,   "fault_pre_summaries.rpt"),
        ("04_faults_before_fault_summary", 30, "fault_pre_summary.rpt"),
        ("04_faults_before_fault_all", 30,   "fault_pre_all.rpt"),
        ("04_faults_before_fault_coll",30,   "fault_pre_collapsed.rpt"),
        ("05_faults_after_add",        30,   "fault_post_summaries.rpt"),
        ("06_atpg_fault_summary",      40,   "engine_fault_summary.rpt"),
        ("06_atpg_fault_all",          40,   "engine_fault_all.rpt"),
        ("06_atpg_fault_coll",         40,   "engine_fault_collapsed.rpt"),
        ("06_atpg_summaries",          40,   "engine_summaries.rpt"),
        ("06_atpg_constraints",        40,   "engine_constraints.rpt"),
        ("06_atpg_primitives",         40,   "engine_primitives.rpt"),
        ("06_atpg_patterns",           40,   "engine_patterns.rpt"),
    ],
}

# =============================================================================
# TREND CSV COLUMN SCHEMA
# Defines exactly what lifecycle.py extracts into trend_analysis.csv
# =============================================================================
TREND_CSV_COLUMNS = [
    "design",
    "tool",
    "stage",
    "exp_id",
    "sub_exp",
    "iter_id",
    "iter_tag",          # GOLDEN / TRASH / null
    "status",            # PASS / FAIL
    "fault_type",
    "runtime_s",
    "tool_version",
    "timestamp_start",
    # --- extracted from reports ---
    "total_faults",
    "detected_faults",
    "undetected_faults",
    "fault_coverage_pct",
    "atpg_effectiveness_pct",
    "total_patterns",
    "cpu_peak_pct",
    "mem_peak_mb",
    "scan_chains_count",
    "scan_cells_count",
    "nonscan_cells_count",
    # --- experiment metadata ---
    "notes",
    "parent_iter",
]
