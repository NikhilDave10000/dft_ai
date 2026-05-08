# =============================================================================
# TMAX / ATPG_SAF — TCL Flow Body
# =============================================================================
# DO NOT hardcode paths or experiment IDs in this file.
# All variables (LOG_DIR, RPT_DIR, OUT_DIR, DESIGN, TOOL, etc.) are
# injected by orch_run.py as a config header prepended at runtime.
#
# Phase naming follows the factory standard:
#   PHASE_SETUP   = "10_BUILD-T"
#   PHASE_DRC     = "20_DRC-T"
#   PHASE_FAULT   = "30_FAULT"
#   PHASE_ENGINE  = "40_TEST-T"
#   PHASE_SIM     = "60_SIM"
#   PHASE_EXPORT  = "80_EXPORT"
#
# These variables are available from the injected header.
# =============================================================================

# =============================================================================
# REPORT INFRASTRUCTURE
# =============================================================================

set GENERATED_REPORTS {}

proc wrpt {phase name cmd} {
    global RPT_DIR GENERATED_REPORTS
    set fname "${RPT_DIR}/${phase}_${name}.rpt"
    lappend GENERATED_REPORTS $fname
    puts "INFO: Writing report -> [file tail $fname]"
    if { [catch {eval $cmd > $fname} err] } {
        puts "WARNING: Report '$name' failed: $err"
    }
}

proc check_reports {} {
    global GENERATED_REPORTS
    set missing 0
    foreach f $GENERATED_REPORTS {
        if { ![file exists $f] || [file size $f] == 0 } {
            puts "WARNING: Missing or empty report -> $f"
            incr missing
        }
    }
    if { $missing == 0 } {
        puts "INFO: All [llength $GENERATED_REPORTS] reports generated OK."
    } else {
        puts "WARNING: $missing report(s) missing."
    }
}

# =============================================================================
# LOG SETUP
# =============================================================================
# LOG_DIR is injected by orch_run.py — do not hardcode
set_messages \
    -log "${LOG_DIR}/${RUN_TAG}.log" \
    -replace

# =============================================================================
# PHASE 10 — SETUP (BUILD-T)
# Load libraries and netlist, build model
# =============================================================================
puts "INFO: === PHASE 10: SETUP ==="

# Library — path is symlinked into INPUT_DIR by orch_run.py
set LIB_FILE  [lindex [glob -nocomplain "${INPUT_DIR}/*.v"] 0]
set NETLIST   [lindex [glob -nocomplain "${INPUT_DIR}/*_scan*.vg" \
                                        "${INPUT_DIR}/*_dc*.vg"   \
                                        "${INPUT_DIR}/*.vg"] 0]
set SPF_FILE  [lindex [glob -nocomplain "${INPUT_DIR}/*.spf"] 0]

if { $LIB_FILE eq "" || $NETLIST eq "" } {
    puts "ERROR: Required input files not found in INPUT_DIR=$INPUT_DIR"
    puts "       Expected: *.v (lib), *.vg (netlist)"
    exit 1
}

puts "INFO: Library : $LIB_FILE"
puts "INFO: Netlist : $NETLIST"
puts "INFO: SPF     : $SPF_FILE"

# Pre-build reports
report_modules -verbose -summary
report_modules -verbose -error

wrpt $PHASE_SETUP modules_summary {report_modules -verbose -summary}
wrpt $PHASE_SETUP modules_error   {report_modules -verbose -error}

read_netlist -library $LIB_FILE
read_netlist -verbose $NETLIST

# Set build options — nodelete_unused_gates preserves test logic
set_build -nodelete_unused_gates

# TOP_MODULE can be overridden from Python via the config header if needed
if { ![info exists TOP_MODULE] } {
    # Auto-detect: use the last module in the netlist as top
    set modules [report_modules -list_names]
    set TOP_MODULE [lindex $modules end]
    puts "INFO: Auto-detected TOP_MODULE = $TOP_MODULE"
}

run_build_model $TOP_MODULE

# Post-build reports
wrpt $PHASE_SETUP rules_fail    {report_rules -verbose -fail}
wrpt $PHASE_SETUP violations    {report_violations -all}

# =============================================================================
# PHASE 20 — DRC (DRC-T)
# Scan architecture setup, constraint loading, DRC
# =============================================================================
puts "INFO: === PHASE 20: DRC ==="

# Clock definitions — can be overridden via config header
if { ![info exists CLOCKS_0] } { set CLOCKS_0 "wb_clk_i" }
if { ![info exists CLOCKS_1] } { set CLOCKS_1 "arst_i" }

add_clocks 0 $CLOCKS_0
add_clocks 1 $CLOCKS_1

wrpt $PHASE_DRC clocks {report_clocks -verbose}

# Run DRC using SPF if available
if { $SPF_FILE ne "" } {
    run_drc $SPF_FILE
} else {
    puts "WARNING: No SPF file found. Running DRC without constraints."
    run_drc
}

wrpt $PHASE_DRC rules_fail  {report_rules -verbose -fail}
wrpt $PHASE_DRC violations  {report_violations -all}

# --- Scan architecture reports ---
# Note: add_scan_enables is REQUIRED; tool does not auto-detect SE from SPF
# unless SPF has an explicit DFT-typed scan_enable directive
if { [info exists SCAN_ENABLE_PORT] } {
    add_scan_enables $SCAN_ENABLE_PORT
    puts "INFO: Added scan enable: $SCAN_ENABLE_PORT"
}

wrpt $PHASE_DRC scan_enables    {report_scan_enables}
wrpt $PHASE_DRC nonscan_cells   {report_nonscan_cells -verbose -summary}
wrpt $PHASE_DRC buses           {report_buses -verbose -all}
wrpt $PHASE_DRC feedback_paths  {report_feedback_paths -verbose -summary}
wrpt $PHASE_DRC scan_chains     {report_scan_chains -verbose}
wrpt $PHASE_DRC scan_cells      {report_scan_cells -verbose -all}
wrpt $PHASE_DRC scan_ability    {report_scan_ability}
wrpt $PHASE_DRC scan_path       {report_scan_path ALL { SCO SCI } -verbose -physical}

# =============================================================================
# PHASE 30 — FAULT MODEL
# Initialize fault model and report pre-ATPG state
# =============================================================================
puts "INFO: === PHASE 30: FAULT MODEL ==="

# ATPG setup
set_atpg -verbose -summary
set_faults \
    -atpg_effectiveness \
    -fault_coverage \
    -summary verbose \
    -interval_fault_coverage

# Pre-add-faults reports (baseline — no faults loaded yet)
wrpt $PHASE_FAULT pre_summaries  {report_summaries faults patterns primitives \
    library_cells memory_usage optimization sequential_depth cpu_usage \
    -per_clock_domain}
wrpt $PHASE_FAULT pre_summary    {report_faults -summary -verbose}
wrpt $PHASE_FAULT pre_all        {report_faults -all -verbose}
wrpt $PHASE_FAULT pre_collapsed  {report_faults -all -verbose -collapsed}
wrpt $PHASE_FAULT pre_patterns   {report_patterns -all}

# Load fault model
add_faults -all

# Post-add-faults reports
wrpt $PHASE_FAULT post_summaries {report_summaries faults patterns primitives \
    library_cells memory_usage optimization sequential_depth cpu_usage \
    -per_clock_domain}
wrpt $PHASE_FAULT post_summary   {report_faults -summary -verbose}
wrpt $PHASE_FAULT post_all       {report_faults -all -verbose}
wrpt $PHASE_FAULT post_collapsed {report_faults -all -verbose -collapsed}
wrpt $PHASE_FAULT post_patterns  {report_patterns -all}

# =============================================================================
# PHASE 40 — ENGINE (TEST-T / ATPG)
# Run ATPG, generate patterns
# =============================================================================
puts "INFO: === PHASE 40: ENGINE (ATPG) ==="

run_atpg

# Post-ATPG reports — the core deliverable reports
wrpt $PHASE_ENGINE fault_summary  {report_faults -summary -verbose}
wrpt $PHASE_ENGINE fault_all      {report_faults -all -verbose}
wrpt $PHASE_ENGINE fault_collapsed {report_faults -all -verbose -collapsed}
wrpt $PHASE_ENGINE summaries       {report_summaries faults patterns primitives \
    library_cells memory_usage optimization sequential_depth cpu_usage \
    -per_clock_domain}
wrpt $PHASE_ENGINE constraints     {report_atpg_constraints -all -verbose}
wrpt $PHASE_ENGINE primitives      {report_atpg_primitives -all -verbose}
wrpt $PHASE_ENGINE patterns        {report_patterns -all}

# =============================================================================
# PHASE 60 — SIMULATION (optional)
# =============================================================================
puts "INFO: === PHASE 60: SIMULATION ==="

if { [info exists RUN_SIM] && $RUN_SIM } {
    run_simulation
    run_fault_sim
    wrpt $PHASE_SIM fault_sim  {report_faults -summary -verbose}
    wrpt $PHASE_SIM patterns   {report_patterns -all}
} else {
    puts "INFO: Simulation skipped. Set RUN_SIM 1 in config header to enable."
}

# =============================================================================
# PHASE 80 — EXPORT
# Write patterns and fault database
# =============================================================================
puts "INFO: === PHASE 80: EXPORT ==="

# Fault list
write_faults \
    "${OUT_DIR}/faults_${RUN_TAG}.all" \
    -all -replace

# STIL patterns — all variants
write_patterns "${OUT_DIR}/${RUN_TAG}.stil"          -format stil
write_patterns "${OUT_DIR}/${RUN_TAG}_serial.stil"   -serial   -format stil
write_patterns "${OUT_DIR}/${RUN_TAG}_parallel.stil" -parallel -format stil

# Binary patterns (for GUI and re-simulation)
write_patterns "${OUT_DIR}/${RUN_TAG}.bin" -format binary

# WGL patterns
write_patterns "${OUT_DIR}/${RUN_TAG}.wgl"          -format wgl
write_patterns "${OUT_DIR}/${RUN_TAG}_serial.wgl"   -serial   -format wgl
write_patterns "${OUT_DIR}/${RUN_TAG}_parallel.wgl" -parallel -format wgl

puts "INFO: Patterns written to: $OUT_DIR"

# Save tool database for GUI restore
if { [info exists DB_DIR] } {
    write_scan_chain_db "${DB_DIR}/${RUN_TAG}.db" -replace
    puts "INFO: Database written to: $DB_DIR"
}

# =============================================================================
# FINAL CHECK
# =============================================================================
puts "INFO: === FINAL CHECK ==="
check_reports

puts "INFO: === RUN COMPLETE ==="
puts "INFO: Design  = $DESIGN"
puts "INFO: Tool    = $TOOL"
puts "INFO: Stage   = $STAGE"
puts "INFO: Exp     = $EXP_ID / $SUB_EXP / $ITER_ID"
puts "INFO: Reports = $RPT_DIR"
puts "INFO: Outputs = $OUT_DIR"
