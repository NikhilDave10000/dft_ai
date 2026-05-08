#!/usr/bin/env bash
# =============================================================================
# env_gate.sh — DFT Factory Environment Switcher
# =============================================================================
# Sources the correct license server and binary path for a given tool.
# Must be SOURCED (not executed) so that env vars persist in the caller shell.
#
# Usage (from shell or orch_run.py via subprocess):
#   source env_gate.sh TMAX
#   source env_gate.sh TESSENT
#
# Exit codes:
#   0  — environment set successfully
#   1  — unknown tool or setup script not found
# =============================================================================

set -euo pipefail

TOOL="${1:-}"

if [[ -z "$TOOL" ]]; then
    echo "ERROR [env_gate]: No tool specified."
    echo "Usage: source env_gate.sh <TOOL>"
    echo "Known tools: TMAX, TESSENT"
    return 1 2>/dev/null || exit 1
fi

# =============================================================================
# Clear any previously set DFT tool vars to avoid pollution between runs
# =============================================================================
unset SNPSLMD_LICENSE_FILE
unset MGLS_LICENSE_FILE
unset TMAX_HOME
unset TESSENT_HOME

# =============================================================================
# Tool-specific environment setup
# =============================================================================

case "$TOOL" in

    TMAX)
        echo "INFO [env_gate]: Setting up Synopsys TetraMAX environment"

        # --- License ---
        export SNPSLMD_LICENSE_FILE="27000@your_synopsys_license_server"

        # --- Binary path ---
        export TMAX_HOME="/path/to/synopsys/tetramax"
        export PATH="$TMAX_HOME/bin:$PATH"

        # --- Source Synopsys shell init if it exists ---
        SYNOPSYS_INIT="/path/to/synopsys/setup.sh"
        if [[ -f "$SYNOPSYS_INIT" ]]; then
            # shellcheck disable=SC1090
            source "$SYNOPSYS_INIT"
            echo "INFO [env_gate]: Sourced $SYNOPSYS_INIT"
        else
            echo "WARNING [env_gate]: Synopsys init not found at $SYNOPSYS_INIT"
            echo "                    Continuing with manually set PATH"
        fi

        # --- Verify binary is reachable ---
        if ! command -v tmax &>/dev/null; then
            echo "ERROR [env_gate]: 'tmax' binary not found in PATH after setup."
            echo "                  Check TMAX_HOME = $TMAX_HOME"
            return 1 2>/dev/null || exit 1
        fi

        echo "INFO [env_gate]: tmax = $(command -v tmax)"
        echo "INFO [env_gate]: SNPSLMD_LICENSE_FILE = $SNPSLMD_LICENSE_FILE"
        ;;

    TESSENT)
        echo "INFO [env_gate]: Setting up Siemens Tessent environment"

        # --- License ---
        export MGLS_LICENSE_FILE="27000@your_siemens_license_server"

        # --- Binary path ---
        export TESSENT_HOME="/path/to/siemens/tessent"
        export PATH="$TESSENT_HOME/bin:$PATH"

        # --- Source Tessent shell init if it exists ---
        TESSENT_INIT="/path/to/siemens/setup.sh"
        if [[ -f "$TESSENT_INIT" ]]; then
            # shellcheck disable=SC1090
            source "$TESSENT_INIT"
            echo "INFO [env_gate]: Sourced $TESSENT_INIT"
        else
            echo "WARNING [env_gate]: Tessent init not found at $TESSENT_INIT"
        fi

        # --- Verify binary is reachable ---
        if ! command -v tessent &>/dev/null; then
            echo "ERROR [env_gate]: 'tessent' binary not found in PATH after setup."
            echo "                  Check TESSENT_HOME = $TESSENT_HOME"
            return 1 2>/dev/null || exit 1
        fi

        echo "INFO [env_gate]: tessent = $(command -v tessent)"
        echo "INFO [env_gate]: MGLS_LICENSE_FILE = $MGLS_LICENSE_FILE"
        ;;

    *)
        echo "ERROR [env_gate]: Unknown tool '$TOOL'"
        echo "Known tools: TMAX, TESSENT"
        return 1 2>/dev/null || exit 1
        ;;
esac

echo "INFO [env_gate]: Environment ready for $TOOL"
