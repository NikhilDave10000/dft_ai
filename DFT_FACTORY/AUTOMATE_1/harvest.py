#!/usr/bin/env python3
"""
harvest.py — DFT Factory Output Normalizer
===========================================
Runs per-iteration immediately after tool exit (auto-called by orch_run.py).

What it does:
  1. Scans logs/ and work/ for raw tool output files
  2. Renames everything to the standard phase-prefix naming:
       10_BUILD-T_modules.rpt,  20_DRC-T_chains.rpt,  40_TEST-T_coverage.rpt
  3. Prepends a "Passport" header to every log (who/what/when — self-describing)
  4. Extracts tool version from logs and writes to .metadata
  5. Wipes work/ (tool scratchpad) after successful harvest
  6. Sets .metadata harvest_done = True

What it does NOT do:
  - Touch any other iteration's files
  - Parse report content (that's lifecycle.py's job for the CSV)
  - Know anything about fault coverage or ATPG internals

USAGE
-----
python core/harvest.py --iter-path /path/to/iter_001
python core/harvest.py --iter-path /path/to/iter_001 --no-wipe-work
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
sys.path.insert(0, str(_HERE))

from factory_config import PHASE_INDEX
from utils import read_meta, write_meta, now_iso, phase_prefix


# =============================================================================
# PASSPORT
# =============================================================================

def passport(meta: dict, source_name: str) -> str:
    """Self-describing header prepended to every log file."""
    return (
        "# " + "=" * 73 + "\n"
        "# DFT DATA FACTORY — LOG PASSPORT\n"
        "# " + "=" * 73 + "\n"
        f"# Design       : {meta.get('design')}\n"
        f"# Tool suite   : {meta.get('tool_suite')}\n"
        f"# Stage        : {meta.get('stage')}\n"
        f"# Exp / Sub    : {meta.get('exp_id')} / {meta.get('sub_exp_id')}\n"
        f"# Iteration    : {meta.get('iter_id')}\n"
        f"# Status       : {meta.get('status')}\n"
        f"# Runtime      : {meta.get('runtime_s')} s\n"
        f"# Started      : {meta.get('timestamp_start')}\n"
        f"# Ended        : {meta.get('timestamp_end')}\n"
        f"# Tool version : {meta.get('tool_version', 'unknown')}\n"
        f"# Source file  : {source_name}\n"
        f"# Harvested    : {now_iso()}\n"
        "# " + "=" * 73 + "\n\n"
    )


def prepend_passport(dest: Path, header: str) -> None:
    original = dest.read_text(errors="replace")
    if not original.startswith("# ==="):  # don't double-passport
        dest.write_text(header + original)


# =============================================================================
# PHASE INFERENCE
# Guesses phase index from a filename so we can prefix it correctly.
# =============================================================================

_PHASE_KEYWORDS = {
    10: ["build", "setup", "init", "load", "model"],
    20: ["drc", "rule", "violation", "scan_chain", "scan_cell",
         "nonscan", "bus", "feedback", "clock"],
    30: ["fault_pre", "fault_before", "pre_fault", "fault_model"],
    40: ["atpg", "test", "engine", "coverage", "pattern", "fault_post",
         "fault_after", "constraint", "primitive"],
    60: ["sim", "simulation", "fault_sim"],
    80: ["export", "write", "output", "pattern_write"],
}

def infer_phase(name: str) -> int:
    nl = name.lower()
    for phase, keywords in _PHASE_KEYWORDS.items():
        if any(k in nl for k in keywords):
            return phase
    return 40  # default: engine phase


# =============================================================================
# REPORT RENAMING
# =============================================================================

def harvest_reports(ipath: Path, meta: dict) -> list[str]:
    """
    Looks for .rpt files in work/ and already in reports/.
    Renames them to: NN_TOOLMODE_originalname.rpt
    """
    tool     = meta["tool_suite"]
    rpt_dir  = ipath / "reports"
    work_dir = ipath / "work"
    done     = []

    # Collect candidate rpt files from work/ and reports/
    candidates = list(work_dir.rglob("*.rpt")) if work_dir.exists() else []
    candidates += [
        f for f in rpt_dir.glob("*.rpt")
        if not re.match(r"^\d{2}_", f.name)   # not already prefixed
    ]

    for src in candidates:
        phase  = infer_phase(src.stem)
        prefix = phase_prefix(phase, tool)
        dest   = rpt_dir / f"{prefix}_{src.name}"

        if src != dest:
            shutil.copy2(src, dest)

        print(f"  RPT  {src.name:40s} -> reports/{dest.name}")
        done.append(dest.name)

    return done


# =============================================================================
# LOG RENAMING + PASSPORTING
# =============================================================================

def harvest_logs(ipath: Path, meta: dict) -> list[str]:
    """
    Moves .log files from work/ into logs/ with phase prefix.
    Prepends passport to all logs in logs/.
    """
    tool     = meta["tool_suite"]
    logs_dir = ipath / "logs"
    work_dir = ipath / "work"
    done     = []

    raw_logs = list(work_dir.rglob("*.log")) if work_dir.exists() else []

    for src in raw_logs:
        phase  = infer_phase(src.stem)
        prefix = phase_prefix(phase, tool)
        dest   = logs_dir / f"{prefix}_{src.name}"
        shutil.copy2(src, dest)
        print(f"  LOG  {src.name:40s} -> logs/{dest.name}")
        done.append(dest.name)

    # Passport all logs in logs/ that aren't already passported
    for log in logs_dir.glob("*.log"):
        hdr = passport(meta, log.name)
        prepend_passport(log, hdr)

    return done


# =============================================================================
# TOOL VERSION EXTRACTION
# =============================================================================

_VERSION_PATTERNS = {
    "SYNOPSYS": [
        r"TetraMAX[^\d]*([\d.]+)",
        r"TMAX[^\d]*([\d.]+)",
        r"Version[:\s]+([\d.]+)",
    ],
    "TESSENT": [
        r"Tessent[^\d]*([\d.]+)",
        r"Version[:\s]+([\d.]+)",
    ],
}

def extract_version(ipath: Path, tool: str) -> str:
    patterns = _VERSION_PATTERNS.get(tool, [])
    for log in sorted((ipath / "logs").glob("*.log")):
        try:
            content = log.read_text(errors="replace")
            for pat in patterns:
                m = re.search(pat, content, re.IGNORECASE)
                if m:
                    return m.group(1)
        except Exception:
            continue
    return "unknown"


# =============================================================================
# WORK WIPE
# =============================================================================

def wipe_work(ipath: Path) -> None:
    work = ipath / "work"
    if work.exists():
        shutil.rmtree(work)
        work.mkdir()
        print(f"  WIPE work/ cleared")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Normalize and harvest DFT tool outputs."
    )
    p.add_argument("--iter-path",    required=True)
    p.add_argument("--no-wipe-work", action="store_true",
                   help="Keep work/ after harvest (for debugging)")
    return p.parse_args()


def main():
    args  = parse_args()
    ipath = Path(args.iter_path).resolve()

    if not ipath.exists():
        print(f"ERROR: {ipath} not found.")
        sys.exit(1)

    meta = read_meta(ipath)
    tool = meta.get("tool_suite", "SYNOPSYS")

    print(f"\nHarvesting: {meta['design']} / {tool} / {meta['stage']} "
          f"/ {meta['iter_id']}\n")

    print("--- Reports ---")
    rpts = harvest_reports(ipath, meta)

    print("\n--- Logs ---")
    logs = harvest_logs(ipath, meta)

    version = extract_version(ipath, tool)
    print(f"\n  Tool version : {version}")

    if not args.no_wipe_work:
        print("\n--- Cleanup ---")
        wipe_work(ipath)

    write_meta(ipath, {
        "harvest_done": True,
        "tool_version": version,
    })

    print(f"\nHarvest done: {len(rpts)} reports, {len(logs)} logs")


if __name__ == "__main__":
    main()
