# =============================================================================
# DFT FACTORY — TCL HELPER BLOCK
# =============================================================================
# Paste this block at the TOP of every TCL script you write.
# Do NOT define LOG_DIR, RPT_DIR, OUT_DIR, PHASE_* yourself —
# orch_run.py injects all of those before your script runs.
#
# What this block gives you:
#   - wrpt   : write a named report into the correct folder with correct name
#   - wlog   : redirect tool log for a phase
#   - wdb    : save a binary database checkpoint
#   - wout   : write an output file (patterns, fault lists)
#   - factory_banner : print a clear phase separator in the log
#   - check_reports  : validate all expected reports were generated
#
# Naming convention produced:
#   reports/  40_TEST-T_fault_summary.rpt
#   logs/     20_DRC-T_drc_run.log
#   database/ 40_TEST-T_state.db
#   outputs/  patterns_iter_001.stil
#
# All of: DESIGN, TOOL_SUITE, STAGE, EXP_ID, SUB_EXP_ID, ITER_ID, RUN_TAG,
#         LOG_DIR, RPT_DIR, OUT_DIR, WORK_DIR, INPUT_DIR, DB_DIR,
#         PHASE_SETUP, PHASE_DRC, PHASE_FAULT, PHASE_ENGINE,
#         PHASE_SIM, PHASE_EXPORT
# ...are already set by the time this block runs. Use them freely.
# =============================================================================

# --- Internal report tracker (for check_reports at the end) ---
set _FACTORY_REPORTS {}
set _FACTORY_ERRORS  0

# -----------------------------------------------------------------------------
# wrpt  <phase_var>  <short_name>  { tool_command ... }
#
# Writes one report. The file is named:
#   $RPT_DIR / ${phase}_${short_name}.rpt
#
# Example:
#   wrpt $PHASE_ENGINE fault_summary { report_faults -summary -verbose }
#   => reports/40_TEST-T_fault_summary.rpt
#
# The phase_var is one of: $PHASE_SETUP $PHASE_DRC $PHASE_FAULT
#                           $PHASE_ENGINE $PHASE_SIM $PHASE_EXPORT
# Or any custom phase string you define (e.g. "30_FAULT-PRE")
# -----------------------------------------------------------------------------
proc wrpt {phase name cmd} {
    global RPT_DIR _FACTORY_REPORTS _FACTORY_ERRORS

    set fname "${RPT_DIR}/${phase}_${name}.rpt"
    lappend _FACTORY_REPORTS $fname

    if { [catch { eval $cmd > $fname } err] } {
        puts "WARNING \[wrpt\]: $phase $name failed: $err"
        incr _FACTORY_ERRORS
    } else {
        puts "INFO  \[wrpt\]: ${phase}_${name}.rpt"
    }
}

# -----------------------------------------------------------------------------
# wlog  <phase_var>  <short_name>
#
# Redirects the tool's own log output for a phase section.
# Produces:  logs/<phase>_<name>.log
#
# Example:
#   wlog $PHASE_DRC drc_run
#   run_drc $SPF_FILE
#   => logs/20_DRC-T_drc_run.log  (tool writes here until next set_messages)
# -----------------------------------------------------------------------------
proc wlog {phase name} {
    global LOG_DIR RUN_TAG
    set fname "${LOG_DIR}/${phase}_${name}.log"
    set_messages -log $fname -replace
    puts "INFO  \[wlog\]: logging -> ${phase}_${name}.log"
}

# -----------------------------------------------------------------------------
# wdb   <phase_var>  <short_name>
#
# Saves a binary tool state checkpoint.
# Produces:  database/<phase>_<name>.db  (or .bin for some tools)
#
# Example:
#   wdb $PHASE_ENGINE post_atpg
#   => database/40_TEST-T_post_atpg.db
#
# You still call the actual save command yourself (write_scan_chain_db etc.)
# This proc just returns the correct path to pass to that command.
# -----------------------------------------------------------------------------
proc wdb {phase name {ext "db"}} {
    global DB_DIR
    set fname "${DB_DIR}/${phase}_${name}.${ext}"
    puts "INFO  \[wdb\]: database path -> ${phase}_${name}.${ext}"
    return $fname
}

# -----------------------------------------------------------------------------
# wout  <short_name>  <extension>
#
# Returns the correct path for a deliverable output file.
# Produces:  outputs/<short_name>_<RUN_TAG>.<ext>
#
# Example:
#   write_patterns [wout patterns stil] -format stil
#   => outputs/patterns_i2c__SYNOPSYS__ATPG__SA_EXP1__E1.1__iter_001.stil
# -----------------------------------------------------------------------------
proc wout {name ext} {
    global OUT_DIR RUN_TAG
    set fname "${OUT_DIR}/${name}_${RUN_TAG}.${ext}"
    puts "INFO  \[wout\]: output path -> ${name}_${RUN_TAG}.${ext}"
    return $fname
}

# -----------------------------------------------------------------------------
# factory_banner  <label>
#
# Prints a visible phase separator in the log. Makes grepping phases easy.
#
# Example:
#   factory_banner "PHASE 40 — ATPG ENGINE"
# -----------------------------------------------------------------------------
proc factory_banner {label} {
    puts ""
    puts "# ================================================================="
    puts "# $label"
    puts "# ================================================================="
    puts ""
}

# -----------------------------------------------------------------------------
# check_reports
#
# Call at the very end of your script.
# Validates every file registered by wrpt actually exists and is non-empty.
# -----------------------------------------------------------------------------
proc check_reports {} {
    global _FACTORY_REPORTS _FACTORY_ERRORS

    puts ""
    puts "# ================================================================="
    puts "# FACTORY REPORT CHECK"
    puts "# ================================================================="

    set missing 0
    set empty   0

    foreach f $_FACTORY_REPORTS {
        if { ![file exists $f] } {
            puts "MISSING  : [file tail $f]"
            incr missing
        } elseif { [file size $f] == 0 } {
            puts "EMPTY    : [file tail $f]"
            incr empty
        } else {
            puts "OK       : [file tail $f]"
        }
    }

    set total [llength $_FACTORY_REPORTS]
    puts ""
    puts "Total: $total reports  |  Missing: $missing  |  Empty: $empty  |  Proc errors: $_FACTORY_ERRORS"

    if { $missing > 0 || $empty > 0 || $_FACTORY_ERRORS > 0 } {
        puts "STATUS: INCOMPLETE — check warnings above"
    } else {
        puts "STATUS: ALL REPORTS OK"
    }
    puts "# ================================================================="
}

# =============================================================================
# CONVENIENCE SHORTCUTS
# Use these in set_messages, write_patterns, write_faults etc.
# All are already set by orch_run.py — listed here for quick reference.
# =============================================================================
#
#  $DESIGN        "i2c_master"
#  $TOOL_SUITE    "SYNOPSYS"
#  $STAGE         "ATPG"
#  $EXP_ID        "SA_EXP1"
#  $SUB_EXP_ID    "E1.1"
#  $ITER_ID       "iter_001"
#  $RUN_TAG       "i2c_master__SYNOPSYS__ATPG__SA_EXP1__E1.1__iter_001"
#
#  $LOG_DIR       ".../iter_001/logs"
#  $RPT_DIR       ".../iter_001/reports"
#  $OUT_DIR       ".../iter_001/outputs"
#  $WORK_DIR      ".../iter_001/work"
#  $INPUT_DIR     ".../iter_001/inputs"   <- your netlist/lib/spf are symlinked here
#  $DB_DIR        ".../iter_001/database"
#
#  $PHASE_SETUP   "10_BUILD-T"
#  $PHASE_DRC     "20_DRC-T"
#  $PHASE_FAULT   "30_FAULT"
#  $PHASE_ENGINE  "40_TEST-T"
#  $PHASE_SIM     "60_SIM"
#  $PHASE_EXPORT  "80_EXPORT"
#
# CUSTOM SUB-PHASES: define your own any time, e.g.:
#   set PHASE_FAULT_PRE  "30_FAULT-PRE"
#   set PHASE_FAULT_POST "30_FAULT-POST"
#   wrpt $PHASE_FAULT_PRE  summaries { report_summaries ... }
#   wrpt $PHASE_FAULT_POST summaries { report_summaries ... }
#
# =============================================================================
# END OF HELPER BLOCK — write your flow below this line
# =============================================================================
