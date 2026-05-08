#!/usr/bin/env python3
# =============================================================================
# orch_run.py — DFT Factory Orchestrator / Spawner
# =============================================================================
# Responsibilities:
#   1. Validate the iteration directory and .metadata
#   2. Source env_gate.sh for the correct tool environment
#   3. Copy TCL/DO scripts into iter/scripts/ (physical copy for reproducibility)
#   4. Resolve and symlink heavy input files (netlists, libs) into iter/inputs/
#   5. Write the TCL config header with all run variables injected
#   6. Launch the EDA tool process and stream logs in real time
#   7. Monitor for crashes, hangs, license failures
#   8. On exit, call harvest.py automatically
#   9. Update .metadata with final status and timing
#
# Usage:
#   python orch_run.py --iter-path /factory/root/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_01
#
#   # Rerun (wipes previous results in this iter, keeps folder)
#   python orch_run.py --iter-path <path> --rerun
#
#   # Skip harvest (for debugging the launch only)
#   python orch_run.py --iter-path <path> --no-harvest
# =============================================================================

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_FACTORY_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_FACTORY_DIR / "config"))
from factory_config import (
    FACTORY_ROOT,
    TOOL_REGISTRY,
    STAGE_REGISTRY,
    PHASE_INDEX,
)

# =============================================================================
# METADATA HELPERS
# =============================================================================

def read_metadata(iter_path: Path) -> dict:
    meta_file = iter_path / ".metadata"
    if not meta_file.exists():
        print(f"ERROR: .metadata not found at {meta_file}")
        print(f"       Run dir_init.py first.")
        sys.exit(1)
    with open(meta_file) as f:
        return json.load(f)


def write_metadata(iter_path: Path, updates: dict) -> None:
    meta_file = iter_path / ".metadata"
    with open(meta_file) as f:
        meta = json.load(f)
    meta.update(updates)
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)


def acquire_lock(iter_path: Path, meta: dict) -> None:
    """Prevents two orch_run instances from writing to the same iter."""
    if meta.get("lock"):
        print(f"ERROR: Iteration is locked (another run is active or crashed).")
        print(f"       If the previous run crashed, manually set lock=false in .metadata")
        print(f"       or use --rerun to reset.")
        sys.exit(1)
    write_metadata(iter_path, {"lock": True, "status": "RUNNING"})


def release_lock(iter_path: Path, status: str) -> None:
    write_metadata(iter_path, {
        "lock": False,
        "status": status,
        "timestamp_end": datetime.now(timezone.utc).isoformat(),
    })


# =============================================================================
# RERUN LOGIC
# =============================================================================

def rerun_reset(iter_path: Path, meta: dict) -> None:
    """Wipes run artifacts from a previous run, keeps the folder structure."""
    print("INFO: --rerun: Clearing previous run artifacts...")
    clearable = ["work", "logs", "reports", "outputs", "database"]
    for sub in clearable:
        d = iter_path / sub
        if d.exists():
            shutil.rmtree(d)
            d.mkdir()
            print(f"  Cleared: {sub}/")

    # Record parent lineage before resetting
    original_iter = meta.get("iter_id", "unknown")
    write_metadata(iter_path, {
        "status":          "PENDING",
        "lock":            False,
        "harvest_done":    False,
        "phase_completed": [],
        "timestamp_start": None,
        "timestamp_end":   None,
        "runtime_s":       None,
        "parent_iter":     original_iter,
    })
    print("INFO: Iteration reset. Previous iter recorded as parent_iter.")


# =============================================================================
# INPUT SYMLINK RESOLVER
# =============================================================================

def resolve_inputs(iter_path: Path, meta: dict,
                   netlist_path: str = None,
                   lib_paths: list[str] = None) -> None:
    """
    Creates symlinks in iter/inputs/ for netlist and library files.
    Heavy files are never copied — symlinks only.
    """
    inputs_dir = iter_path / "inputs"

    def make_symlink(src: str, link_name: str) -> None:
        src_path = Path(src).resolve()
        link     = inputs_dir / link_name
        if not src_path.exists():
            print(f"WARNING: Input not found: {src_path}")
            return
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(src_path)
        print(f"  Linked: inputs/{link_name} -> {src_path}")

    if netlist_path:
        make_symlink(netlist_path, Path(netlist_path).name)

    if lib_paths:
        for lib in lib_paths:
            make_symlink(lib, Path(lib).name)


# =============================================================================
# TCL SCRIPT BUILDER
# =============================================================================

def build_tcl_config_header(meta: dict, iter_path: Path) -> str:
    """
    Generates the TCL config header block that gets prepended to every
    tool script. Python injects all run variables so the TCL body is
    purely functional — no hardcoded paths or experiment IDs.
    """
    tool    = meta["tool"]
    stage   = meta["stage"]
    exp_id  = meta["exp_id"]
    sub_exp = meta["sub_exp"]
    iter_id = meta["iter_id"]
    design  = meta["design"]

    log_dir     = str(iter_path / "logs")
    rpt_dir     = str(iter_path / "reports")
    out_dir     = str(iter_path / "outputs")
    work_dir    = str(iter_path / "work")
    inputs_dir  = str(iter_path / "inputs")
    db_dir      = str(iter_path / "database")

    # Build phase name map for this tool
    phase_lines = []
    for idx, info in PHASE_INDEX.items():
        tool_mode = info.get(tool, info["name"].upper())
        phase_lines.append(
            f'set PHASE_{info["name"].upper():12s} '
            f'"{idx:02d}_{tool_mode}"'
        )

    phase_block = "\n".join(phase_lines)

    return f"""# =============================================================================
# AUTO-GENERATED CONFIG HEADER — do not edit manually
# Generated by orch_run.py at {datetime.now(timezone.utc).isoformat()}
# =============================================================================

# --- Run coordinates ---
set DESIGN     "{design}"
set TOOL       "{tool}"
set STAGE      "{stage}"
set EXP_ID     "{exp_id}"
set SUB_EXP    "{sub_exp}"
set ITER_ID    "{iter_id}"
set RUN_TAG    "{design}__{tool}__{stage}__{exp_id}__{sub_exp}__{iter_id}"

# --- Directory paths (all absolute, injected by Python) ---
set LOG_DIR    "{log_dir}"
set RPT_DIR    "{rpt_dir}"
set OUT_DIR    "{out_dir}"
set WORK_DIR   "{work_dir}"
set INPUT_DIR  "{inputs_dir}"
set DB_DIR     "{db_dir}"

# --- Phase index names for this tool ---
{phase_block}

# --- End of auto-generated header ---
# =============================================================================
"""


def write_tcl_runner(iter_path: Path, tcl_body_path: Path, meta: dict) -> Path:
    """
    Combines the auto-generated config header + the TCL body script.
    Writes the merged file into iter/scripts/ and iter/config/.
    Returns the path to the script that should be passed to the tool.
    """
    header  = build_tcl_config_header(meta, iter_path)
    body    = tcl_body_path.read_text()
    merged  = header + "\n" + body

    # Physical copy in scripts/ (for reproducibility)
    scripts_dir = iter_path / "scripts"
    run_script  = scripts_dir / f"run_{meta['iter_id']}.tcl"
    run_script.write_text(merged)

    # Also copy into config/ (the 'what was actually used' record)
    config_dir = iter_path / "config"
    (config_dir / tcl_body_path.name).write_text(body)  # original body
    (config_dir / "injected_header.tcl").write_text(header)

    print(f"  TCL script : scripts/{run_script.name}")
    print(f"  Config copy: config/{tcl_body_path.name}")
    return run_script


# =============================================================================
# TOOL LAUNCHER
# =============================================================================

# Patterns that indicate a license failure in tool output
LICENSE_FAILURE_PATTERNS = [
    "Cannot checkout license",
    "license error",
    "SNPS_LICENSE",
    "FlexNet",
    "license checkout failed",
    "cannot open license",
]

# Patterns that indicate a tool crash
CRASH_PATTERNS = [
    "Segmentation fault",
    "core dumped",
    "Fatal error",
    "FATAL",
    "Aborted",
]


def launch_tool(tool: str, tcl_script: Path, iter_path: Path,
                meta: dict, timeout_hours: float = 12.0) -> str:
    """
    Launches the EDA tool, streams stdout/stderr to terminal AND to
    iter/logs/<RUN_TAG>.log in real time.
    Returns final status string: "PASS" | "FAIL" | "ABORTED"
    """
    binary   = TOOL_REGISTRY[tool]["binary"]
    log_file = (iter_path / "logs" /
                f"{meta['design']}__{meta['iter_id']}.raw.log")

    cmd = [binary, "-f", str(tcl_script)]

    print(f"\nINFO: Launching: {' '.join(cmd)}")
    print(f"INFO: Live log  : {log_file}\n")
    print("=" * 70)

    start_time = time.time()
    status     = "FAIL"
    crash_seen = False
    license_fail = False

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(iter_path / "work"),   # tool runs in work/ scratchpad
            env=os.environ.copy(),
        )

        with open(log_file, "w") as lf:
            for line in proc.stdout:
                # Stream to terminal
                print(line, end="", flush=True)
                # Write to log
                lf.write(line)

                # Crash/license detection
                if any(p.lower() in line.lower() for p in LICENSE_FAILURE_PATTERNS):
                    license_fail = True
                    print(f"\nWARNING: License failure detected!")
                if any(p.lower() in line.lower() for p in CRASH_PATTERNS):
                    crash_seen = True
                    print(f"\nWARNING: Crash signal detected!")

        proc.wait(timeout=timeout_hours * 3600)
        print("=" * 70)

        runtime = time.time() - start_time

        if proc.returncode == 0 and not crash_seen and not license_fail:
            status = "PASS"
        elif license_fail:
            status = "FAIL"
            print(f"\nERROR: Run failed due to license issue.")
        else:
            status = "FAIL"
            print(f"\nERROR: Tool exited with code {proc.returncode}")

    except subprocess.TimeoutExpired:
        proc.kill()
        status = "ABORTED"
        runtime = time.time() - start_time
        print(f"\nERROR: Tool timed out after {timeout_hours}h. Process killed.")

    except FileNotFoundError:
        status = "FAIL"
        runtime = 0
        print(f"\nERROR: Binary not found: {binary}")
        print(f"       Check TOOL_REGISTRY in factory_config.py")

    write_metadata(iter_path, {"runtime_s": int(runtime)})
    print(f"\nINFO: Tool finished in {int(runtime)}s with status: {status}")
    return status


# =============================================================================
# HARVEST CALLER
# =============================================================================

def call_harvest(iter_path: Path) -> None:
    harvest_script = _SCRIPT_DIR / "harvest.py"
    print(f"\nINFO: Calling harvest.py...")
    result = subprocess.run(
        [sys.executable, str(harvest_script),
         "--iter-path", str(iter_path)],
        check=False,
    )
    if result.returncode != 0:
        print("WARNING: harvest.py reported errors. Check manually.")
    else:
        print("INFO: Harvest complete.")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Launch one EDA tool run in the DFT Data Factory."
    )
    p.add_argument("--iter-path",   required=True,
                   help="Absolute path to the iteration folder")
    p.add_argument("--tcl",         default=None,
                   help="Path to TCL body script. If omitted, looks for "
                        "tcl/<TOOL>/<STAGE>.tcl in the factory.")
    p.add_argument("--netlist",     default=None,
                   help="Path to netlist file (will be symlinked into inputs/)")
    p.add_argument("--libs",        nargs="*", default=[],
                   help="Library file paths (will be symlinked into inputs/)")
    p.add_argument("--rerun",       action="store_true",
                   help="Clear previous results and rerun this iteration")
    p.add_argument("--no-harvest",  action="store_true",
                   help="Skip automatic harvest.py call after tool exits")
    p.add_argument("--timeout-hrs", type=float, default=12.0,
                   help="Kill tool after N hours (default: 12)")
    return p.parse_args()


def main():
    args     = parse_args()
    iter_path = Path(args.iter_path).resolve()

    if not iter_path.exists():
        print(f"ERROR: Iteration path does not exist: {iter_path}")
        print(f"       Run dir_init.py first.")
        sys.exit(1)

    meta = read_metadata(iter_path)
    tool = meta["tool"]

    # --- rerun reset ---
    if args.rerun:
        rerun_reset(iter_path, meta)
        meta = read_metadata(iter_path)  # re-read after reset

    # --- lock check ---
    acquire_lock(iter_path, meta)

    try:
        print(f"\nINFO: Starting run for {iter_path.name}")
        print(f"INFO: Design={meta['design']}  Tool={tool}  "
              f"Stage={meta['stage']}  Exp={meta['exp_id']}  "
              f"Sub={meta['sub_exp']}  Iter={meta['iter_id']}")

        # --- set up tool environment ---
        env_gate = _FACTORY_DIR / "tools" / "env_gate.sh"
        print(f"\nINFO: Sourcing env_gate.sh for {tool}...")
        # We export the env vars into this process via a subshell eval
        result = subprocess.run(
            ["bash", "-c",
             f"source {env_gate} {tool} && env"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"ERROR: env_gate.sh failed:\n{result.stderr}")
            release_lock(iter_path, "FAIL")
            sys.exit(1)
        # Inject exported vars into current process
        for line in result.stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                os.environ[k] = v

        # --- resolve inputs ---
        resolve_inputs(
            iter_path, meta,
            netlist_path=args.netlist,
            lib_paths=args.libs,
        )

        # --- find TCL body ---
        if args.tcl:
            tcl_body = Path(args.tcl).resolve()
        else:
            # default location: factory/tcl/<TOOL>/<STAGE>.tcl
            tcl_body = (_FACTORY_DIR / "tcl" / tool /
                        f"{meta['stage']}.tcl")

        if not tcl_body.exists():
            print(f"ERROR: TCL script not found: {tcl_body}")
            print(f"       Pass --tcl <path> or place script at above path.")
            release_lock(iter_path, "FAIL")
            sys.exit(1)

        # --- write merged TCL runner ---
        run_script = write_tcl_runner(iter_path, tcl_body, meta)

        # --- launch ---
        write_metadata(iter_path, {
            "timestamp_start": datetime.now(timezone.utc).isoformat()
        })
        status = launch_tool(
            tool, run_script, iter_path, meta,
            timeout_hours=args.timeout_hrs,
        )

    except KeyboardInterrupt:
        print("\nINFO: Interrupted by user.")
        status = "ABORTED"

    finally:
        release_lock(iter_path, status)

    # --- harvest ---
    if not args.no_harvest and status in ("PASS", "FAIL"):
        call_harvest(iter_path)
    elif args.no_harvest:
        print("INFO: Harvest skipped (--no-harvest).")

    print(f"\nINFO: orch_run finished. Status = {status}")
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
