#!/usr/bin/env python3
"""
orch_run.py — DFT Factory Orchestrator
=======================================
What it does:
  1. Reads .metadata from the iteration folder
  2. Sources env_gate.sh for the correct tool (csh + source steps)
  3. Symlinks your netlist/lib/SPF into inputs/
  4. Prepends an auto-generated config header onto YOUR TCL script
     (injects $LOG_DIR, $RPT_DIR, $ITER_ID, $PHASE_* vars etc.)
  5. Launches the tool (tmax -f ... or tessent -shell -dofile ...)
  6. Streams stdout live to terminal + saves to logs/
  7. On exit: calls harvest.py, updates .metadata

What it does NOT do:
  - Write any ATPG/scan/sim logic. That's 100% your TCL.
  - Know about fault types, report content, or tool internals.

USAGE
-----
python core/orch_run.py \\
    --iter-path /your/path/i2c_master/SYNOPSYS/ATPG/SA_EXP1/E1.1/iter_001 \\
    --tcl       /your/path/your_atpg_script.tcl

# Symlink inputs explicitly
python core/orch_run.py --iter-path ... --tcl ... \\
    --netlist /path/to/netlist.vg \\
    --libs    /path/to/cells.v /path/to/io.v \\
    --spf     /path/to/design.spf

# --rerun: wipe logs/reports/outputs/work in this iter and rerun
python core/orch_run.py --iter-path ... --tcl ... --rerun

# --no-harvest: skip automatic harvest (for debugging)
python core/orch_run.py --iter-path ... --tcl ... --no-harvest
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
sys.path.insert(0, str(_HERE))

from factory_config import TOOL_REGISTRY, PHASE_INDEX, STAGE_REGISTRY
from utils import read_meta, write_meta, now_iso, phase_prefix


# =============================================================================
# LOCK MANAGEMENT
# =============================================================================

def acquire_lock(ipath: Path) -> None:
    meta = read_meta(ipath)
    if meta.get("lock"):
        print("ERROR: Iteration is locked — another run may be active.")
        print("       If the previous run crashed, set lock=false in .metadata")
        print("       or use --rerun to reset.")
        sys.exit(1)
    write_meta(ipath, {"lock": True, "status": "RUNNING"})


def release_lock(ipath: Path, status: str) -> None:
    write_meta(ipath, {
        "lock":          False,
        "status":        status,
        "timestamp_end": now_iso(),
    })


# =============================================================================
# RERUN RESET
# =============================================================================

def rerun_reset(ipath: Path) -> None:
    meta     = read_meta(ipath)
    orig_iter = meta.get("iter_id", "unknown")
    clearable = ["work", "logs", "reports", "outputs", "database"]
    print("INFO: --rerun: clearing previous run artifacts...")
    for sub in clearable:
        d = ipath / sub
        if d.exists():
            shutil.rmtree(d)
            d.mkdir()
            print(f"  Cleared: {sub}/")
    write_meta(ipath, {
        "status":          "PENDING",
        "lock":            False,
        "harvest_done":    False,
        "phases_completed":[],
        "timestamp_start": None,
        "timestamp_end":   None,
        "runtime_s":       None,
        "parent_iter":     orig_iter,
    })
    print("INFO: Iteration reset (parent_iter recorded).")


# =============================================================================
# INPUT SYMLINKER
# =============================================================================

def symlink_inputs(ipath: Path,
                   netlist: str | None,
                   libs:    list[str],
                   spf:     str | None) -> None:
    inputs_dir = ipath / "inputs"

    def link(src_str: str) -> None:
        src  = Path(src_str).resolve()
        dest = inputs_dir / src.name
        if not src.exists():
            print(f"  WARNING: Input not found: {src}")
            return
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        dest.symlink_to(src)
        print(f"  Linked: inputs/{src.name}")

    if netlist:  link(netlist)
    if spf:      link(spf)
    for lib in (libs or []):
        link(lib)


# =============================================================================
# TCL CONFIG HEADER BUILDER
# =============================================================================
# Python injects all factory variables into a header block that gets
# prepended to YOUR TCL script. Your script just uses these vars freely.
#
# Variables available in your TCL after injection:
#   $DESIGN, $TOOL_SUITE, $STAGE, $EXP_ID, $SUB_EXP_ID, $ITER_ID, $RUN_TAG
#   $LOG_DIR, $RPT_DIR, $OUT_DIR, $WORK_DIR, $INPUT_DIR, $DB_DIR
#   $PHASE_SETUP, $PHASE_DRC, $PHASE_FAULT, $PHASE_ENGINE, $PHASE_SIM, $PHASE_EXPORT
#   (plus any custom phase vars for phases defined in PHASE_INDEX)
# =============================================================================

def build_tcl_header(meta: dict, ipath: Path) -> str:
    tool  = meta["tool_suite"]
    stage = meta["stage"]

    run_tag = (f"{meta['design']}__{tool}__{stage}__"
               f"{meta['exp_id']}__{meta['sub_exp_id']}__{meta['iter_id']}")

    # Build one TCL variable per phase index
    phase_vars = []
    for idx, info in PHASE_INDEX.items():
        tool_mode = info.get(tool, info["name"].upper())
        var_name  = f"PHASE_{info['name'].upper()}"
        phase_vars.append(f'set {var_name:<20} "{idx:02d}_{tool_mode}"')

    return (
        "# " + "=" * 73 + "\n"
        "# AUTO-GENERATED CONFIG HEADER — DO NOT EDIT\n"
        f"# Generated by orch_run.py  {now_iso()}\n"
        "# " + "=" * 73 + "\n\n"
        f'set DESIGN      "{meta["design"]}"\n'
        f'set TOOL_SUITE  "{tool}"\n'
        f'set STAGE       "{stage}"\n'
        f'set EXP_ID      "{meta["exp_id"]}"\n'
        f'set SUB_EXP_ID  "{meta["sub_exp_id"]}"\n'
        f'set ITER_ID     "{meta["iter_id"]}"\n'
        f'set RUN_TAG     "{run_tag}"\n\n'
        f'set LOG_DIR     "{ipath / "logs"}"\n'
        f'set RPT_DIR     "{ipath / "reports"}"\n'
        f'set OUT_DIR     "{ipath / "outputs"}"\n'
        f'set WORK_DIR    "{ipath / "work"}"\n'
        f'set INPUT_DIR   "{ipath / "inputs"}"\n'
        f'set DB_DIR      "{ipath / "database"}"\n\n'
        + "\n".join(phase_vars) + "\n\n"
        "# " + "=" * 73 + "\n"
        "# END OF AUTO-GENERATED HEADER — your script starts below\n"
        "# " + "=" * 73 + "\n\n"
    )


def write_merged_tcl(ipath: Path, tcl_body: Path, meta: dict) -> Path:
    header = build_tcl_header(meta, ipath)
    body   = tcl_body.read_text()
    merged = header + body

    # Physical copy in scripts/ (reproducibility record)
    run_script = ipath / "scripts" / f"run_{meta['iter_id']}.tcl"
    run_script.write_text(merged)

    # Original body in config/ (what you wrote, unmodified)
    (ipath / "config" / tcl_body.name).write_text(body)
    (ipath / "config" / "_injected_header.tcl").write_text(header)

    print(f"  Merged TCL  : scripts/{run_script.name}")
    print(f"  Your script : config/{tcl_body.name}")
    return run_script


# =============================================================================
# TOOL LAUNCHER
# =============================================================================

# Strings in tool output that flag known failure types
_LICENSE_SIGNALS = [
    "cannot checkout license", "license error", "flexnet",
    "license checkout failed", "cannot open license",
]
_CRASH_SIGNALS = [
    "segmentation fault", "core dumped", "fatal error",
    "aborted (core", "killed",
]


def launch(tool_suite: str, run_script: Path,
           ipath: Path, meta: dict,
           timeout_hrs: float) -> str:
    """
    Runs the tool exactly as you would manually:
      SYNOPSYS:  csh -c "tmax -f script.tcl"
      TESSENT:   csh -c "source /home/mentor.cshrc && tessent -shell -dofile script.tcl -log ..."

    Returns: "PASS" | "FAIL" | "ABORTED"
    """
    cfg     = TOOL_REGISTRY[tool_suite]
    binary  = cfg["binary"]
    raw_log = ipath / "logs" / f"{meta['iter_id']}_raw.log"

    # Build the inner command string (runs inside csh)
    inner_parts = []
    if cfg.get("init_source"):
        inner_parts.append(f"source {cfg['init_source']}")

    tool_cmd = [binary]
    tool_cmd += cfg.get("extra_flags", [])
    tool_cmd += [cfg["launch_flag"], str(run_script)]
    if cfg.get("log_flag"):
        tool_cmd += [cfg["log_flag"],
                     str(ipath / "logs" / f"{meta['iter_id']}.log")]

    inner_parts.append(" ".join(tool_cmd))
    inner_cmd = " && ".join(inner_parts)

    # Wrap in csh
    cmd = ["csh", "-c", inner_cmd]

    print(f"\nINFO: Launching ({tool_suite}):")
    print(f"  {inner_cmd}")
    print(f"  Live log: {raw_log}\n")
    print("=" * 70)

    start    = time.time()
    status   = "FAIL"
    license_fail = crash_seen = False

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(ipath / "work"),
            env=os.environ.copy(),
        )
        with open(raw_log, "w") as lf:
            for line in proc.stdout:
                print(line, end="", flush=True)
                lf.write(line)
                ll = line.lower()
                if any(s in ll for s in _LICENSE_SIGNALS):
                    license_fail = True
                if any(s in ll for s in _CRASH_SIGNALS):
                    crash_seen = True

        proc.wait(timeout=timeout_hrs * 3600)
        print("=" * 70)
        runtime = time.time() - start

        if proc.returncode == 0 and not crash_seen and not license_fail:
            status = "PASS"
        else:
            status = "FAIL"
            if license_fail:
                print("ERROR: License failure detected in output.")
            elif crash_seen:
                print("ERROR: Crash signal detected in output.")
            else:
                print(f"ERROR: Tool exited with code {proc.returncode}.")

    except subprocess.TimeoutExpired:
        proc.kill()
        status  = "ABORTED"
        runtime = time.time() - start
        print(f"\nERROR: Timed out after {timeout_hrs}h. Process killed.")

    except FileNotFoundError:
        status  = "FAIL"
        runtime = 0
        print(f"\nERROR: '{binary}' not found.")
        print(f"       Run env_gate.sh manually to verify your PATH.")

    write_meta(ipath, {"runtime_s": int(runtime)})
    print(f"\nINFO: Status={status}  Runtime={int(runtime)}s")
    return status


# =============================================================================
# HARVEST CALLER
# =============================================================================

def call_harvest(ipath: Path) -> None:
    harvest = _HERE / "harvest.py"
    print("\nINFO: Calling harvest.py...")
    r = subprocess.run(
        [sys.executable, str(harvest), "--iter-path", str(ipath)],
        check=False,
    )
    if r.returncode != 0:
        print("WARNING: harvest.py reported issues.")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Launch one DFT tool run in the factory."
    )
    p.add_argument("--iter-path",   required=True)
    p.add_argument("--tcl",         required=True,
                   help="Your TCL script (factory prepends config header)")
    p.add_argument("--netlist",     default=None)
    p.add_argument("--libs",        nargs="*", default=[])
    p.add_argument("--spf",         default=None)
    p.add_argument("--rerun",       action="store_true")
    p.add_argument("--no-harvest",  action="store_true")
    p.add_argument("--timeout-hrs", type=float, default=12.0)
    return p.parse_args()


def main():
    args   = parse_args()
    ipath  = Path(args.iter_path).resolve()
    tcl    = Path(args.tcl).resolve()

    if not ipath.exists():
        print(f"ERROR: {ipath} does not exist. Run dir_init.py first.")
        sys.exit(1)
    if not tcl.exists():
        print(f"ERROR: TCL script not found: {tcl}")
        sys.exit(1)

    meta = read_meta(ipath)

    if args.rerun:
        rerun_reset(ipath)
        meta = read_meta(ipath)

    # Source env and absorb into this process
    env_gate = _HERE.parent / "tools" / "env_gate.sh"
    tool     = meta["tool_suite"]
    print(f"INFO: Setting up {tool} environment...")
    result = subprocess.run(
        ["csh", "-f", str(env_gate), tool],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: env_gate failed:\n{result.stderr}")
        sys.exit(1)
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("INFO"):
            k, _, v = line.partition("=")
            os.environ[k] = v

    acquire_lock(ipath)
    write_meta(ipath, {"timestamp_start": now_iso()})

    status = "FAIL"
    try:
        print(f"\nINFO: {meta['design']} / {tool} / {meta['stage']} "
              f"/ {meta['exp_id']} / {meta['sub_exp_id']} / {meta['iter_id']}")

        symlink_inputs(ipath, args.netlist, args.libs, args.spf)
        run_script = write_merged_tcl(ipath, tcl, meta)
        status = launch(tool, run_script, ipath, meta, args.timeout_hrs)

    except KeyboardInterrupt:
        print("\nINFO: Interrupted.")
        status = "ABORTED"
    finally:
        release_lock(ipath, status)

    if not args.no_harvest:
        call_harvest(ipath)

    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
