#!/bin/csh -f
# =============================================================================
# env_gate.sh — DFT Factory Environment Switcher
# =============================================================================
# Mirrors EXACTLY what you type manually in the terminal.
#
# For SYNOPSYS:  you open csh  →  tmax is already in PATH
# For TESSENT:   you open csh  →  source /home/mentor.cshrc  →  tessent
#
# This script is called by orch_run.py via subprocess.
# It prints the resulting environment to stdout so Python can
# absorb the env vars into the current process.
#
# NEVER run this directly. orch_run.py handles it.
# =============================================================================

set TOOL = "$1"

if ( "$TOOL" == "" ) then
    echo "ERROR [env_gate]: No tool specified."
    exit 1
endif

switch ( $TOOL )

    case SYNOPSYS:
        # tmax is already in PATH after csh on your server.
        # Nothing to source — just verify it's reachable.
        echo "INFO [env_gate]: SYNOPSYS environment (tmax in system PATH)"
        if ( ! `which tmax` ) then
            echo "ERROR [env_gate]: tmax not found in PATH."
            echo "                  Are you in a csh session on the correct server?"
            exit 1
        endif
        echo "INFO [env_gate]: tmax = `which tmax`"
        breaksw

    case TESSENT:
        # Source mentor environment — exactly as you do manually.
        if ( -f /home/mentor.cshrc ) then
            source /home/mentor.cshrc
            echo "INFO [env_gate]: Sourced /home/mentor.cshrc"
        else
            echo "ERROR [env_gate]: /home/mentor.cshrc not found."
            echo "                  Check the path with your admin."
            exit 1
        endif
        if ( ! `which tessent` ) then
            echo "ERROR [env_gate]: tessent not found in PATH after sourcing mentor.cshrc."
            exit 1
        endif
        echo "INFO [env_gate]: tessent = `which tessent`"
        breaksw

    default:
        echo "ERROR [env_gate]: Unknown tool '$TOOL'."
        echo "                  Known: SYNOPSYS | TESSENT"
        exit 1
        breaksw

endsw

echo "INFO [env_gate]: Environment ready for $TOOL"

# Print full env so orch_run.py can absorb it into the Python process
env
