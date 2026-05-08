#!/usr/bin/env python3
"""
orch_run.py — DFT Factory Orchestrator
=======================================
Launches one EDA tool run inside the factory hierarchy.

WHAT IT DOES
  1. Reads .metadata from the iteration folder
  2. Sources env_gate.sh for the correct tool (csh + source steps)
  3. Symlinks ALL input file types into inputs/
  4. Prepends auto-generated config header onto YOUR TCL script
     (injects all $PHASE_*, $LOG_DIR, $RPT_DIR, custom vars etc.)
  5. Launches: csh -c "tmax -f script.tcl"
  6. Streams stdout live to terminal AND logs/
  7. Detects license failures and crashes in real time
  8. On exit: calls harvest.py, updates .metadata

WHAT IT DOES NOT DO
  Write any ATPG/scan/sim logic — that is 100% your TCL.

FLAGS — REQUIRED
  --iter-path PATH    Absolute path to iter_NNN folder (from dir_init.py)
  --tcl       PATH    Your TCL body script

FLAGS — INPUT SYMLINKS (all optional, any combination)
  --netlist   PATH    Gate-level netlist (.vg)         -> inputs/
  --libs      P ...   Library files (.v, multiple ok)  -> inputs/
  --spf       PATH    Scan protocol file (.spf)        -> inputs/
  --sdc       PATH    SDC timing constraints           -> inputs/  [read_sdc]
  --timing    PATH    Timing file                      -> inputs/  [read_timing]
  --layout    PATH    Physical layout file             -> inputs/  [read_layout]
  --extras    P ...   Any other files (catch-all)      -> inputs/

FLAGS — TCL HEADER INJECTION
  --top-module NAME   Injects: set TOP_MODULE "NAME" into TCL header.
                      Without this, your TCL must define TOP_MODULE itself.
  --inject K=V ...    Inject arbitrary "set K V" lines into TCL header.
                      Lets you vary experiment params from CLI without editing TCL.
                      Example: --inject EDT_CHANNELS=4 FAULT_TYPE=transition

FLAGS — CONTROL
  --rerun             Wipe logs/ reports/ outputs/ database/ work/, reset
                      .metadata to PENDING, record current iter as parent_iter.
                      inputs/ and scripts/ are kept. Use when fixing a TCL bug.
  --no-harvest        Skip harvest.py after tool exits. work/ stays intact.
                      Use to inspect raw tool output before normalization.
  --timeout-hrs N     Kill tool after N hours (default: 12.0).
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
sys.path.insert(0, str(_HERE))

from factory_config import TOOL_REGISTRY, PHASE_INDEX
from utils import read_meta, write_meta, now_iso


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
    meta      = read_meta(ipath)
    orig_iter = meta.get("iter_id", "unknown")
    # Wipe run artifacts only — keep inputs/ and scripts/
    for sub in ["work", "logs", "reports", "outputs", "database"]:
        d = ipath / sub
        if d.exists():
            shutil.rmtree(d)
            d.mkdir()
            print(f"  Cleared: {sub}/")
    write_meta(ipath, {
        "status":           "PENDING",
        "lock":             False,
        "harvest_done":     False,
        "phases_completed": [],
        "timestamp_start":  None,
        "timestamp_end":    None,
        "runtime_s":        None,
        "parent_iter":      orig_iter,
    })
    print("INFO: Reset complete. parent_iter recorded for lineage.")


# =============================================================================
# INPUT SYMLINKER
# Covers all TMAX read_* input types. Never copies — symlinks only.
# =============================================================================

def symlink_inputs(ipath:   Path,
                   netlist: str | None = None,
                   libs:    list       = None,
                   spf:     str | None = None,
                   sdc:     str | None = None,
                   timing:  str | None = None,
                   layout:  str | None = None,
                   extras:  list       = None) -> None:
    inputs_dir = ipath / "inputs"

    def link(src_str: str) -> None:
        src  = Path(src_str).resolve()
        dest = inputs_dir / src.name
        if not src.exists():
            print(f"  WARNING: Input not found, skipping: {src}")
            return
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        dest.symlink_to(src)
        print(f"  Linked: inputs/{src.name}")

    if netlist: link(netlist)
    if spf:     link(spf)
    if sdc:     link(sdc)
    if timing:  link(timing)
    if layout:  link(layout)
    for f in (libs   or []): link(f)
    for f in (extras or []): link(f)


# =============================================================================
# TCL HEADER BUILDER
# =============================================================================

def build_tcl_header(meta: dict, ipath: Path,
                     top_module: str | None,
                     injections: dict) -> str:
    tool    = meta["tool_suite"]
    run_tag = (f"{meta['design']}__{tool}__{meta['stage']}__"
               f"{meta['exp_id']}__{meta['sub_exp_id']}__{meta['iter_id']}")

    phase_lines = []
    for idx, info in PHASE_INDEX.items():
        tool_mode = info.get(tool, info["name"].upper())
        var_name  = f"PHASE_{info['name'].upper()}"
        phase_lines.append(f"set {var_name:<20} \"{idx:02d}_{tool_mode}\"")

    inject_lines = []
    if top_module:
        inject_lines.append(f"set TOP_MODULE      \"{top_module}\"")
    for k, v in injections.items():
        inject_lines.append(f"set {k:<18} \"{v}\"")

    inject_block = ""
    if inject_lines:
        inject_block = (
            "\n# --- injected experiment variables ---\n"
            + "\n".join(inject_lines) + "\n"
        )

    return (
        "# " + "=" * 73 + "\n"
        "# AUTO-GENERATED CONFIG HEADER — DO NOT EDIT\n"
        f"# orch_run.py  {now_iso()}\n"
        "# " + "=" * 73 + "\n\n"
        "# --- run coordinates ---\n"
        f"set DESIGN      \"{meta['design']}\"\n"
        f"set TOOL_SUITE  \"{tool}\"\n"
        f"set STAGE       \"{meta['stage']}\"\n"
        f"set EXP_ID      \"{meta['exp_id']}\"\n"
        f"set SUB_EXP_ID  \"{meta['sub_exp_id']}\"\n"
        f"set ITER_ID     \"{meta['iter_id']}\"\n"
        f"set RUN_TAG     \"{run_tag}\"\n\n"
        "# --- directory paths ---\n"
        f"set LOG_DIR     \"{ipath / 'logs'}\"\n"
        f"set RPT_DIR     \"{ipath / 'reports'}\"\n"
        f"set OUT_DIR     \"{ipath / 'outputs'}\"\n"
        f"set WORK_DIR    \"{ipath / 'work'}\"\n"
        f"set INPUT_DIR   \"{ipath / 'inputs'}\"\n"
        f"set DB_DIR      \"{ipath / 'database'}\"\n\n"
        "# --- phase index names ---\n"
        + "\n".join(phase_lines)
        + inject_block + "\n\n"
        "# " + "=" * 73 + "\n"
        "# END OF AUTO-GENERATED HEADER — your script starts below\n"
        "# " + "=" * 73 + "\n\n"
    )


def write_merged_tcl(ipath: Path, tcl_body: Path, meta: dict,
                     top_module: str | None, injections: dict) -> Path:
    header     = build_tcl_header(meta, ipath, top_module, injections)
    body       = tcl_body.read_text()
    run_script = ipath / "scripts" / f"run_{meta['iter_id']}.tcl"
    run_script.write_text(header + body)
    (ipath / "config" / tcl_body.name).write_text(body)
    (ipath / "config" / "_injected_header.tcl").write_text(header)
    print(f"  Merged TCL : scripts/{run_script.name}")
    print(f"  Your body  : config/{tcl_body.name}")
    return run_script


# =============================================================================
# TOOL LAUNCHER
# =============================================================================

_LICENSE_SIGNALS = [
    "cannot checkout license", "license error", "flexnet",
    "license checkout failed", "cannot open license",
]
_CRASH_SIGNALS = [
    "segmentation fault", "core dumped", "fatal error",
    "aborted (core", "killed",
]


def launch(tool_suite: str, run_script: Path,
           ipath: Path, meta: dict, timeout_hrs: float) -> str:
    cfg     = TOOL_REGISTRY[tool_suite]
    binary  = cfg["binary"]
    raw_log = ipath / "logs" / f"{meta['iter_id']}_raw.log"

    inner_parts = []
    if cfg.get("init_source"):
        inner_parts.append(f"source {cfg['init_source']}")

    tool_cmd  = [binary]
    tool_cmd += cfg.get("extra_flags", [])
    tool_cmd += [cfg["launch_flag"], str(run_script)]
    if cfg.get("log_flag"):
        tool_cmd += [cfg["log_flag"],
                     str(ipath / "logs" / f"{meta['iter_id']}.log")]

    inner_parts.append(" ".join(tool_cmd))
    inner_cmd = " && ".join(inner_parts)
    cmd       = ["csh", "-c", inner_cmd]

    print(f"\nINFO: Launching ({tool_suite}):")
    print(f"  {inner_cmd}")
    print(f"  Live log : {raw_log}\n")
    print("=" * 70)

    start        = time.time()
    status       = "FAIL"
    license_fail = crash_seen = False

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(ipath / "work"), env=os.environ.copy(),
        )
        with open(raw_log, "w") as lf:
            for line in proc.stdout:
                print(line, end="", flush=True)
                lf.write(line)
                ll = line.lower()
                if any(s in ll for s in _LICENSE_SIGNALS): license_fail = True
                if any(s in ll for s in _CRASH_SIGNALS):   crash_seen   = True

        proc.wait(timeout=timeout_hrs * 3600)
        print("=" * 70)
        runtime = time.time() - start

        if proc.returncode == 0 and not crash_seen and not license_fail:
            status = "PASS"
        else:
            status = "FAIL"
            if license_fail: print("ERROR: License failure detected.")
            elif crash_seen: print("ERROR: Crash signal detected.")
            else:            print(f"ERROR: Exit code {proc.returncode}.")

    except subprocess.TimeoutExpired:
        proc.kill()
        status  = "ABORTED"
        runtime = time.time() - start
        print(f"\nERROR: Timed out after {timeout_hrs}h. Process killed.")

    except FileNotFoundError:
        status  = "FAIL"
        runtime = 0
        print(f"\nERROR: '{binary}' not found. Check env_gate.sh PATH setup.")

    write_meta(ipath, {"runtime_s": int(runtime)})
    print(f"\nINFO: Status={status}  Runtime={int(runtime)}s")
    return status


# =============================================================================
# MAIN
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="DFT Factory — launch one tool run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--iter-path",   required=True)
    p.add_argument("--tcl",         required=True)
    # inputs
    p.add_argument("--netlist",     default=None)
    p.add_argument("--libs",        nargs="*", default=[])
    p.add_argument("--spf",         default=None)
    p.add_argument("--sdc",         default=None)
    p.add_argument("--timing",      default=None)
    p.add_argument("--layout",      default=None)
    p.add_argument("--extras",      nargs="*", default=[])
    # TCL injection
    p.add_argument("--top-module",  default=None)
    p.add_argument("--inject",      nargs="*", default=[],
                   metavar="K=V")
    # control
    p.add_argument("--rerun",       action="store_true")
    p.add_argument("--no-harvest",  action="store_true")
    p.add_argument("--timeout-hrs", type=float, default=12.0)
    return p.parse_args()


def main():
    args  = parse_args()
    ipath = Path(args.iter_path).resolve()
    tcl   = Path(args.tcl).resolve()

    if not ipath.exists():
        print(f"ERROR: {ipath} does not exist. Run dir_init.py first.")
        sys.exit(1)
    if not tcl.exists():
        print(f"ERROR: TCL script not found: {tcl}")
        sys.exit(1)

    injections = {}
    for kv in (args.inject or []):
        if "=" in kv:
            k, _, v = kv.partition("=")
            injections[k.strip()] = v.strip()
        else:
            print(f"WARNING: --inject '{kv}' is not KEY=VALUE, skipping.")

    meta = read_meta(ipath)
    if args.rerun:
        print("INFO: --rerun: resetting iteration...")
        rerun_reset(ipath)
        meta = read_meta(ipath)

    # Source environment
    env_gate = _HERE.parent / "tools" / "env_gate.sh"
    tool     = meta["tool_suite"]
    print(f"INFO: Setting up {tool} environment...")
    result = subprocess.run(
        ["csh", "-f", str(env_gate), tool],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: env_gate.sh failed:\n{result.stderr}")
        sys.exit(1)
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("INFO"):
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip()

    acquire_lock(ipath)
    write_meta(ipath, {"timestamp_start": now_iso()})

    status = "FAIL"
    try:
        print(f"\nINFO: {meta['design']} / {tool} / {meta['stage']} "
              f"/ {meta['exp_id']} / {meta['sub_exp_id']} / {meta['iter_id']}")
        if injections:
            print(f"INFO: Injections: {injections}")

        symlink_inputs(ipath,
                       netlist=args.netlist, libs=args.libs,
                       spf=args.spf, sdc=args.sdc,
                       timing=args.timing, layout=args.layout,
                       extras=args.extras)

        run_script = write_merged_tcl(ipath, tcl, meta,
                                      args.top_module, injections)
        status = launch(tool, run_script, ipath, meta, args.timeout_hrs)

    except KeyboardInterrupt:
        print("\nINFO: Interrupted.")
        status = "ABORTED"
    finally:
        release_lock(ipath, status)

    if not args.no_harvest:
        h = _HERE / "harvest.py"
        print("\nINFO: Calling harvest.py...")
        subprocess.run([sys.executable, str(h), "--iter-path", str(ipath)])
    else:
        print("INFO: --no-harvest: work/ kept intact.")

    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
