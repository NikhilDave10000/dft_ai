#!/usr/bin/env python3
# =============================================================================
# harvest.py — DFT Factory Output Normalizer
# =============================================================================
# Runs immediately after the tool exits (called by orch_run.py).
# Responsibilities (per-iteration ONLY — never cross-iter):
#   1. Scan iter/work/ and iter/logs/ for raw tool outputs
#   2. Rename reports to standard phase-prefixed names (10_, 20_, 40_...)
#   3. Prepend "Passport" header to every log (timestamp, tool version, coords)
#   4. Move normalized files into iter/reports/ and iter/logs/
#   5. Wipe iter/work/ after successful harvest
#   6. Update .metadata harvest_done = True
#
# Usage:
#   python harvest.py --iter-path /factory/.../Iter_01
#   python harvest.py --iter-path /factory/.../Iter_01 --no-wipe-work
# =============================================================================

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR  = Path(__file__).resolve().parent
_FACTORY_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_FACTORY_DIR / "config"))
from factory_config import HARVEST_RULES, PHASE_INDEX


# =============================================================================
# METADATA HELPERS (local, no cross-import with orch_run)
# =============================================================================

def read_metadata(iter_path: Path) -> dict:
    with open(iter_path / ".metadata") as f:
        return json.load(f)


def write_metadata(iter_path: Path, updates: dict) -> None:
    meta_file = iter_path / ".metadata"
    with open(meta_file) as f:
        meta = json.load(f)
    meta.update(updates)
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)


# =============================================================================
# PASSPORT PREPENDER
# =============================================================================

def build_passport(meta: dict, source_file: Path) -> str:
    """
    Generates a structured header block prepended to every log file.
    Makes logs self-describing — you can open any log cold and immediately
    know its full context.
    """
    return (
        "# " + "=" * 75 + "\n"
        "# DFT DATA FACTORY — LOG PASSPORT\n"
        "# " + "=" * 75 + "\n"
        f"# Design       : {meta.get('design', 'unknown')}\n"
        f"# Tool         : {meta.get('tool', 'unknown')}\n"
        f"# Tool version : {meta.get('tool_version', 'unknown')}\n"
        f"# Stage        : {meta.get('stage', 'unknown')}\n"
        f"# Exp          : {meta.get('exp_id', 'unknown')} / "
                          f"{meta.get('sub_exp', 'unknown')}\n"
        f"# Iteration    : {meta.get('iter_id', 'unknown')}\n"
        f"# Status       : {meta.get('status', 'unknown')}\n"
        f"# Runtime      : {meta.get('runtime_s', 'unknown')} s\n"
        f"# Start        : {meta.get('timestamp_start', 'unknown')}\n"
        f"# End          : {meta.get('timestamp_end', 'unknown')}\n"
        f"# Source file  : {source_file.name}\n"
        f"# Harvested at : {datetime.now(timezone.utc).isoformat()}\n"
        "# " + "=" * 75 + "\n\n"
    )


def prepend_passport(dest_file: Path, passport: str) -> None:
    original = dest_file.read_text(errors="replace")
    dest_file.write_text(passport + original)


# =============================================================================
# PHASE-PREFIX NAMING
# =============================================================================

def phase_prefix(phase_idx: int, tool: str, suffix: str) -> str:
    """
    Builds a normalized file name:
      e.g.  phase_idx=40, tool=TMAX, suffix=fault_summary.rpt
      =>    40_TEST-T_fault_summary.rpt
    """
    info      = PHASE_INDEX.get(phase_idx, {})
    tool_mode = info.get(tool, info.get("name", str(phase_idx)).upper())
    return f"{phase_idx:02d}_{tool_mode}_{suffix}"


# =============================================================================
# REPORT HARVESTER
# =============================================================================

def harvest_reports(iter_path: Path, meta: dict) -> list[str]:
    """
    Scans the raw TCL output directory (logs from orch_run.py knows
    where the TCL wrote to — we look in iter/work/ and also in
    any flat ../reports/ path if the TCL wrote there directly).

    Returns list of harvested file names.
    """
    tool          = meta.get("tool", "TMAX")
    harvest_rules = HARVEST_RULES.get(tool, [])
    rpt_dir       = iter_path / "reports"
    harvested     = []

    # Where the TCL may have written raw outputs:
    # - iter/work/ (tool scratchpad)
    # - iter/logs/ (raw .log files from set_messages)
    search_dirs = [
        iter_path / "work",
        iter_path / "logs",
    ]

    for rule in harvest_rules:
        src_pattern, phase_idx, std_suffix = rule
        dest_name = phase_prefix(phase_idx, tool, std_suffix)
        dest_file = rpt_dir / dest_name

        # Find matching source file in search dirs
        found = None
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for f in search_dir.rglob("*"):
                if src_pattern.lower() in f.name.lower() and f.is_file():
                    found = f
                    break
            if found:
                break

        if found is None:
            # Also check if TCL wrote directly into iter/reports/ already
            for f in rpt_dir.glob("*"):
                if src_pattern.lower() in f.name.lower():
                    found = f
                    break

        if found is None:
            print(f"  MISS : {src_pattern} -> (not found, skipping)")
            continue

        # Copy and rename to standard name
        if found != dest_file:
            shutil.copy2(found, dest_file)

        print(f"  OK   : {found.name} -> reports/{dest_name}")
        harvested.append(dest_name)

    return harvested


# =============================================================================
# LOG HARVESTER
# =============================================================================

def harvest_logs(iter_path: Path, meta: dict) -> list[str]:
    """
    Finds raw log files in iter/work/ and iter/logs/,
    prepends passport, moves to iter/logs/ with standard names.
    """
    logs_dir  = iter_path / "logs"
    work_dir  = iter_path / "work"
    harvested = []
    tool      = meta.get("tool", "TMAX")

    # Collect all .log files from work/
    raw_logs = []
    if work_dir.exists():
        raw_logs = list(work_dir.rglob("*.log"))

    for raw_log in raw_logs:
        # Try to infer phase from filename
        phase_idx = _infer_phase_from_filename(raw_log.name)
        info      = PHASE_INDEX.get(phase_idx, {})
        tool_mode = info.get(tool, info.get("name", "run").upper())
        dest_name = f"{phase_idx:02d}_{tool_mode}_{raw_log.stem}.log"
        dest_file = logs_dir / dest_name

        shutil.copy2(raw_log, dest_file)
        passport = build_passport(meta, raw_log)
        prepend_passport(dest_file, passport)

        print(f"  LOG  : {raw_log.name} -> logs/{dest_name}")
        harvested.append(dest_name)

    # Also passport any existing files already in logs/
    for existing_log in logs_dir.glob("*.log"):
        if not existing_log.name.startswith(tuple("0123456789")):
            # Unnamed raw log — passport and rename
            passport = build_passport(meta, existing_log)
            content  = existing_log.read_text(errors="replace")
            if not content.startswith("# ==="):  # not already passported
                existing_log.write_text(passport + content)
                print(f"  PASS : logs/{existing_log.name} (passported in place)")

    return harvested


def _infer_phase_from_filename(name: str) -> int:
    """Guesses phase index from a filename. Returns 40 (engine) as default."""
    name_lower = name.lower()
    if any(k in name_lower for k in ["build", "setup", "init"]):
        return 10
    if any(k in name_lower for k in ["drc", "rule", "violation"]):
        return 20
    if any(k in name_lower for k in ["fault", "faults"]):
        return 30
    if any(k in name_lower for k in ["atpg", "test", "engine", "pattern"]):
        return 40
    if any(k in name_lower for k in ["sim", "simulation"]):
        return 60
    if any(k in name_lower for k in ["export", "write", "output"]):
        return 80
    return 40  # default: engine phase


# =============================================================================
# TOOL VERSION EXTRACTOR
# =============================================================================

def extract_tool_version(iter_path: Path, tool: str) -> str:
    """
    Scrapes the tool version string from the first available log.
    Returns 'unknown' if not found.
    """
    logs_dir = iter_path / "logs"
    patterns = {
        "TMAX":    r"TetraMAX[^\d]*([\d.]+)",
        "TESSENT": r"Tessent[^\d]*([\d.]+)",
    }
    regex = patterns.get(tool)
    if not regex:
        return "unknown"

    for log_file in sorted(logs_dir.glob("*.log")):
        try:
            content = log_file.read_text(errors="replace")
            match   = re.search(regex, content, re.IGNORECASE)
            if match:
                return match.group(1)
        except Exception:
            continue
    return "unknown"


# =============================================================================
# WORK DIR CLEANUP
# =============================================================================

def wipe_work_dir(iter_path: Path) -> None:
    work_dir = iter_path / "work"
    if work_dir.exists():
        shutil.rmtree(work_dir)
        work_dir.mkdir()
        print(f"  WIPE : work/ cleared")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Normalize and harvest EDA tool outputs for one iteration."
    )
    p.add_argument("--iter-path",    required=True,
                   help="Absolute path to the iteration folder")
    p.add_argument("--no-wipe-work", action="store_true",
                   help="Keep work/ directory after harvest (for debugging)")
    return p.parse_args()


def main():
    args      = parse_args()
    iter_path = Path(args.iter_path).resolve()

    if not iter_path.exists():
        print(f"ERROR: Iteration path not found: {iter_path}")
        sys.exit(1)

    meta = read_metadata(iter_path)
    tool = meta.get("tool", "TMAX")

    print(f"\nHarvesting: {iter_path.name}")
    print(f"  Design={meta['design']}  Tool={tool}  "
          f"Stage={meta['stage']}  Iter={meta['iter_id']}")
    print()

    # 1. Harvest reports
    print("--- Reports ---")
    rpt_files = harvest_reports(iter_path, meta)

    # 2. Harvest and passport logs
    print("\n--- Logs ---")
    log_files = harvest_logs(iter_path, meta)

    # 3. Extract tool version from logs
    tool_version = extract_tool_version(iter_path, tool)
    print(f"\n  Tool version detected: {tool_version}")

    # 4. Wipe work/
    if not args.no_wipe_work:
        print("\n--- Cleanup ---")
        wipe_work_dir(iter_path)
    else:
        print("\nINFO: --no-wipe-work: work/ kept for debugging")

    # 5. Update metadata
    write_metadata(iter_path, {
        "harvest_done":  True,
        "tool_version":  tool_version,
    })

    print(f"\nHarvest complete: {len(rpt_files)} reports, {len(log_files)} logs")


if __name__ == "__main__":
    main()
