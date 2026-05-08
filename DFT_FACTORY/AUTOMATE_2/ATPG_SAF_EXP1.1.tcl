# =============================================================================
# YOUR SCRIPT BODY — EXP1.1: SAF ATPG on i2c_master
# =============================================================================
# HOW TO USE:
#   1. Source the factory helpers first (or let orch_run.py do it):
#      source tcl/SYNOPSYS/_factory_helpers.tcl
#
#   2. All $PHASE_*, $LOG_DIR, $RPT_DIR, $OUT_DIR, $INPUT_DIR etc.
#      are already set. Do NOT redefine them here.
#
#   3. Use wrpt / wlog / wdb / wout / factory_banner / check_reports
#      from the helper block.
#
# WHAT CHANGED vs your old script:
#   REMOVED  - set DESIGN, EXP_ID, RUN_TAG  (injected by Python)
#   REMOVED  - set LOG_DIR, OUT_DIR, RPT_DIR (injected by Python)
#   REMOVED  - set PHASE_BUILD "01_build"    (use $PHASE_SETUP etc.)
#   REMOVED  - cleanup_run proc              (handled by orch_run.py --rerun)
#   REMOVED  - hardcoded /home/DFT_libs/...  (symlinked into $INPUT_DIR)
#   REMOVED  - hardcoded ../input/...        (symlinked into $INPUT_DIR)
#   KEPT     - every tool command, every report, every flag — untouched
# =============================================================================

# Source helpers (if not already sourced by orch_run)
if { ![info exists _FACTORY_REPORTS] } {
    set _dir [file dirname [info script]]
    source "${_dir}/_factory_helpers.tcl"
}

# --- custom sub-phase labels (your old 04/05 split) ---
set PHASE_FAULT_PRE  "30_FAULT-PRE"
set PHASE_FAULT_POST "30_FAULT-POST"

# =============================================================================
# PHASE 10 — SETUP  (was "01_build" in your old script)
# =============================================================================
factory_banner "PHASE 10 — SETUP / BUILD"

# Log for this phase
wlog $PHASE_SETUP build

# Inputs are symlinked into $INPUT_DIR by orch_run.py
# No hardcoded paths here — glob for what you need
set LIB_FILE  [lindex [glob "${INPUT_DIR}/*.v"]  0]
set NETLIST   [lindex [glob "${INPUT_DIR}/*.vg"] 0]
set SPF_FILE  [lindex [glob -nocomplain "${INPUT_DIR}/*.spf"] 0]

puts "INFO: lib     = $LIB_FILE"
puts "INFO: netlist = $NETLIST"
puts "INFO: spf     = $SPF_FILE"

read_netlist -library $LIB_FILE
read_netlist -verbose $NETLIST

wrpt $PHASE_SETUP modules_summary { report_modules -verbose -summary }
wrpt $PHASE_SETUP modules_error   { report_modules -verbose -error   }

set TOP_MODULE "i2c_master_top"
set_build -nodelete_unused_gates
run_build_model $TOP_MODULE

wrpt $PHASE_SETUP rules_fail  { report_rules -verbose -fail }
wrpt $PHASE_SETUP violations  { report_violations -all      }

# =============================================================================
# PHASE 20 — DRC  (was "02_drc" + "03_scan" in your old script)
# =============================================================================
factory_banner "PHASE 20 — DRC + SCAN ARCHITECTURE"

wlog $PHASE_DRC drc

add_clocks 0 wb_clk_i
add_clocks 1 arst_i

wrpt $PHASE_DRC clocks { report_clocks -verbose }

run_drc $SPF_FILE

wrpt $PHASE_DRC rules_fail { report_rules -verbose -fail }
wrpt $PHASE_DRC violations { report_violations -all      }

# Scan architecture reports
wrpt $PHASE_DRC nonscan_cells  { report_nonscan_cells -verbose -summary            }
wrpt $PHASE_DRC buses          { report_buses -verbose -all                        }
wrpt $PHASE_DRC feedback_paths { report_feedback_paths -verbose -summary           }
wrpt $PHASE_DRC scan_chains    { report_scan_chains -verbose                       }
wrpt $PHASE_DRC scan_cells     { report_scan_cells -verbose -all                   }
wrpt $PHASE_DRC scan_ability   { report_scan_ability                               }
wrpt $PHASE_DRC scan_enables   { report_scan_enables                               }
wrpt $PHASE_DRC scan_path      { report_scan_path ALL { SCO SCI } -verbose -physical }

# =============================================================================
# PHASE 30 — FAULT MODEL  (was "04_faults_before" + "05_faults_after")
# =============================================================================
factory_banner "PHASE 30 — FAULT MODEL"

wlog $PHASE_FAULT fault_model

set_atpg -verbose -summary
set_faults -atpg_effectiveness -fault_coverage -summary verbose -interval_fault_coverage

# --- pre-add snapshots ---
wrpt $PHASE_FAULT_PRE summaries     { report_summaries faults patterns primitives library_cells memory_usage optimization sequential_depth cpu_usage -per_clock_domain }
wrpt $PHASE_FAULT_PRE fault_summary { report_faults -summary -verbose      }
wrpt $PHASE_FAULT_PRE fault_all     { report_faults -all -verbose          }
wrpt $PHASE_FAULT_PRE fault_coll    { report_faults -all -verbose -collapsed }
wrpt $PHASE_FAULT_PRE patterns      { report_patterns -all                 }

add_faults -all

# --- post-add snapshots ---
wrpt $PHASE_FAULT_POST summaries     { report_summaries faults patterns primitives library_cells memory_usage optimization sequential_depth cpu_usage -per_clock_domain }
wrpt $PHASE_FAULT_POST fault_summary { report_faults -summary -verbose      }
wrpt $PHASE_FAULT_POST fault_all     { report_faults -all -verbose          }
wrpt $PHASE_FAULT_POST fault_coll    { report_faults -all -verbose -collapsed }
wrpt $PHASE_FAULT_POST patterns      { report_patterns -all                 }

# =============================================================================
# PHASE 40 — ENGINE / ATPG  (was "06_atpg")
# =============================================================================
factory_banner "PHASE 40 — ATPG ENGINE"

wlog $PHASE_ENGINE atpg

run_atpg

wrpt $PHASE_ENGINE fault_summary  { report_faults -summary -verbose      }
wrpt $PHASE_ENGINE fault_all      { report_faults -all -verbose          }
wrpt $PHASE_ENGINE fault_coll     { report_faults -all -verbose -collapsed }
wrpt $PHASE_ENGINE summaries      { report_summaries faults patterns primitives library_cells memory_usage optimization sequential_depth cpu_usage -per_clock_domain }
wrpt $PHASE_ENGINE constraints    { report_atpg_constraints -all -verbose }
wrpt $PHASE_ENGINE primitives     { report_atpg_primitives  -all -verbose }
wrpt $PHASE_ENGINE patterns       { report_patterns -all                  }

# Save engine state for GUI restore
set db_path [wdb $PHASE_ENGINE post_atpg]
catch { write_scan_chain_db $db_path -replace }

# =============================================================================
# PHASE 60 — SIMULATION  (optional — comment out if not needed yet)
# =============================================================================
factory_banner "PHASE 60 — SIMULATION"

wlog $PHASE_SIM sim

run_simulation
run_fault_sim

wrpt $PHASE_SIM fault_summary { report_faults -summary -verbose }
wrpt $PHASE_SIM patterns      { report_patterns -all            }

# =============================================================================
# PHASE 80 — EXPORT
# =============================================================================
factory_banner "PHASE 80 — EXPORT"

# Fault list
write_faults [wout faults all] -all -replace

# STIL
write_patterns [wout patterns          stil] -format stil
write_patterns [wout patterns_serial   stil] -serial   -format stil
write_patterns [wout patterns_parallel stil] -parallel -format stil

# Binary
write_patterns [wout patterns bin] -format binary

# WGL
write_patterns [wout patterns          wgl] -format wgl
write_patterns [wout patterns_serial   wgl] -serial   -format wgl
write_patterns [wout patterns_parallel wgl] -parallel -format wgl

# =============================================================================
# FINAL CHECK
# =============================================================================
check_reports
