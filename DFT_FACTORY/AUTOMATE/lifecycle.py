#!/usr/bin/env python3
# =============================================================================
# lifecycle.py — DFT Factory Iteration Lifecycle Manager
# =============================================================================
# Cross-iteration operations ONLY. Never touches files inside a single iter.
# Responsibilities:
#   1. Tag iterations as GOLDEN (locked reference) or TRASH (delete-ready)
#   2. List all iterations under any path with their status
#   3. Delete TRASH-tagged iterations to reclaim disk space
#   4. Aggregate .metadata + report KPIs across iterations into trend_analysis.csv
#
# Usage:
#   # Tag one iteration as GOLDEN
#   python lifecycle.py --tag GOLDEN \
#       --iter-path /factory/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_03
#
#   # Tag as TRASH
#   python lifecycle.py --tag TRASH \
#       --iter-path /factory/i2c/TMAX/ATPG_SAF/EXP1/1.1/Iter_01
#
#   # List all iterations under a scope (any depth)
#   python lifecycle.py --list --scope /factory/i2c/TMAX/ATPG_SAF
#
#   # Delete all TRASH-tagged iterations under a scope
#   python lifecycle.py --purge-trash --scope /factory/i2c
#
#   # Build trend_analysis.csv for a scope
#   python lifecycle.py --build-csv --scope /factory/i2c \
#       --output /factory/analysis/i2c_trends.csv
# =============================================================================

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_SCRIPT_DIR  = Path(__file__).resolve().parent
_FACTORY_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_FACTORY_DIR / "config"))
from factory_config import TREND_CSV_COLUMNS, FACTORY_ROOT


# =============================================================================
# ITERATION DISCOVERY
# =============================================================================

def find_all_iters(scope: Path) -> list[Path]:
    """
    Walks the directory tree under scope and returns all paths that
    contain a .metadata file (i.e. are valid iteration leaf nodes).
    """
    return sorted([
        p.parent for p in scope.rglob(".metadata")
        if p.is_file()
    ])


def read_metadata(iter_path: Path) -> dict:
    meta_file = iter_path / ".metadata"
    if not meta_file.exists():
        return {}
    with open(meta_file) as f:
        return json.load(f)


def write_metadata(iter_path: Path, updates: dict) -> None:
    meta_file = iter_path / ".metadata"
    with open(meta_file) as f:
        meta = json.load(f)
    meta.update(updates)
    with open(meta_file, "w") as f:
        json.dump(meta, f, indent=2)


# =============================================================================
# TAGGING
# =============================================================================

def tag_iteration(iter_path: Path, tag: str) -> None:
    """Tag an iteration as GOLDEN or TRASH."""
    if tag not in ("GOLDEN", "TRASH", "null"):
        print(f"ERROR: Unknown tag '{tag}'. Use: GOLDEN | TRASH | null")
        sys.exit(1)

    meta = read_metadata(iter_path)
    if not meta:
        print(f"ERROR: No .metadata found at {iter_path}")
        sys.exit(1)

    # Guard: cannot tag a running or locked iteration
    if meta.get("lock"):
        print(f"ERROR: Iteration is currently locked (running). Cannot tag.")
        sys.exit(1)

    # Guard: GOLDEN can only be set on PASS runs
    if tag == "GOLDEN" and meta.get("status") != "PASS":
        print(f"WARNING: Tagging a non-PASS iteration as GOLDEN.")
        print(f"         Status is '{meta.get('status')}'. Proceed? [y/N] ", end="")
        if input().strip().lower() != "y":
            print("Aborted.")
            sys.exit(0)

    old_tag = meta.get("iter_tag")
    write_metadata(iter_path, {"iter_tag": tag if tag != "null" else None})
    print(f"Tagged: {iter_path.name}  {old_tag} -> {tag}")


# =============================================================================
# LISTING
# =============================================================================

STATUS_SYMBOL = {
    "PASS":    "[PASS]   ",
    "FAIL":    "[FAIL]   ",
    "RUNNING": "[RUN]    ",
    "ABORTED": "[ABORT]  ",
    "PENDING": "[PENDING]",
    None:      "[?]      ",
}

TAG_SYMBOL = {
    "GOLDEN": " *GOLDEN*",
    "TRASH":  "  trash  ",
    None:     "         ",
}


def list_iterations(scope: Path) -> None:
    iters = find_all_iters(scope)
    if not iters:
        print(f"No iterations found under: {scope}")
        return

    print(f"\n{'Status':<12} {'Tag':<12} {'Design':<10} {'Tool':<8} "
          f"{'Stage':<12} {'Exp':<8} {'Sub':<6} {'Iter':<10} {'Runtime':>10}")
    print("-" * 90)

    for iter_path in iters:
        meta    = read_metadata(iter_path)
        status  = meta.get("status")
        tag     = meta.get("iter_tag")
        rt      = meta.get("runtime_s")
        rt_str  = f"{rt}s" if rt is not None else "—"

        print(
            f"{STATUS_SYMBOL.get(status, '[?]'):<12} "
            f"{TAG_SYMBOL.get(tag, ''):<12} "
            f"{meta.get('design','?'):<10} "
            f"{meta.get('tool','?'):<8} "
            f"{meta.get('stage','?'):<12} "
            f"{meta.get('exp_id','?'):<8} "
            f"{meta.get('sub_exp','?'):<6} "
            f"{meta.get('iter_id','?'):<10} "
            f"{rt_str:>10}"
        )

    print(f"\nTotal: {len(iters)} iterations")


# =============================================================================
# TRASH PURGE
# =============================================================================

def purge_trash(scope: Path, dry_run: bool = False) -> None:
    iters   = find_all_iters(scope)
    targets = [p for p in iters
               if read_metadata(p).get("iter_tag") == "TRASH"]

    if not targets:
        print("No TRASH-tagged iterations found.")
        return

    print(f"{'[DRY RUN] ' if dry_run else ''}Found {len(targets)} TRASH iterations:")
    for t in targets:
        print(f"  {t}")

    if dry_run:
        return

    print(f"\nDelete all {len(targets)} TRASH iterations? [y/N] ", end="")
    if input().strip().lower() != "y":
        print("Aborted.")
        return

    import shutil
    for t in targets:
        shutil.rmtree(t)
        print(f"  Deleted: {t}")
    print(f"\nPurged {len(targets)} iterations.")


# =============================================================================
# REPORT PARSER — extracts KPIs from normalized report files
# =============================================================================

# Regex patterns for extracting values from TMAX/Tessent reports
_KPI_PATTERNS = {
    # From engine_fault_summary.rpt or engine_summaries.rpt
    "total_faults": [
        r"Total faults\s*[:\|]\s*([\d,]+)",
        r"Fault count\s*[:\|]\s*([\d,]+)",
    ],
    "detected_faults": [
        r"Detected\s*[:\|]\s*([\d,]+)",
        r"DT\s*[:\|]\s*([\d,]+)",
    ],
    "undetected_faults": [
        r"Undetected\s*[:\|]\s*([\d,]+)",
        r"UD\s*[:\|]\s*([\d,]+)",
        r"UNDETECTED\s+([\d,]+)",
    ],
    "fault_coverage_pct": [
        r"Fault coverage\s*[:\|=]\s*([\d.]+)\s*%?",
        r"FC\s*[:\|]\s*([\d.]+)",
        r"Coverage\s*=\s*([\d.]+)%",
    ],
    "atpg_effectiveness_pct": [
        r"ATPG effectiveness\s*[:\|=]\s*([\d.]+)\s*%?",
        r"Atpg eff\s*[:\|]\s*([\d.]+)",
    ],
    "total_patterns": [
        r"Total patterns\s*[:\|]\s*([\d,]+)",
        r"Pattern count\s*[:\|]\s*([\d,]+)",
        r"# patterns\s*[:\|]\s*([\d,]+)",
    ],
    "cpu_peak_pct": [
        r"CPU\s+usage\s*[:\|]\s*([\d.]+)\s*%?",
        r"cpu_usage\s*[:\|]\s*([\d.]+)",
    ],
    "mem_peak_mb": [
        r"Memory\s*[:\|]\s*([\d.]+)\s*MB",
        r"Peak memory\s*[:\|]\s*([\d.]+)",
    ],
    "scan_chains_count": [
        r"Scan chains\s*[:\|]\s*([\d]+)",
        r"Number of scan chains\s*[:\|]\s*([\d]+)",
    ],
    "scan_cells_count": [
        r"Scan cells\s*[:\|]\s*([\d,]+)",
        r"Total scan cells\s*[:\|]\s*([\d,]+)",
    ],
    "nonscan_cells_count": [
        r"Non-scan cells\s*[:\|]\s*([\d,]+)",
        r"Nonscan cells\s*[:\|]\s*([\d,]+)",
    ],
}


def extract_kpis(iter_path: Path) -> dict:
    """
    Reads normalized report files from iter/reports/ and extracts
    numeric KPIs using regex patterns.
    Returns dict of KPI name -> value (or None if not found).
    """
    rpt_dir = iter_path / "reports"
    kpis    = {k: None for k in _KPI_PATTERNS}

    if not rpt_dir.exists():
        return kpis

    # Concatenate all report content for searching
    all_content = ""
    for rpt_file in sorted(rpt_dir.glob("*.rpt")):
        try:
            all_content += rpt_file.read_text(errors="replace") + "\n"
        except Exception:
            continue

    for kpi_name, patterns in _KPI_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, all_content, re.IGNORECASE)
            if match:
                raw = match.group(1).replace(",", "")
                try:
                    kpis[kpi_name] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    kpis[kpi_name] = raw
                break  # first match wins

    return kpis


# =============================================================================
# TREND CSV BUILDER
# =============================================================================

def build_trend_csv(scope: Path, output_path: Path) -> None:
    iters = find_all_iters(scope)
    if not iters:
        print(f"No iterations found under: {scope}")
        return

    rows = []
    for iter_path in iters:
        meta = read_metadata(iter_path)
        if not meta:
            continue

        kpis = extract_kpis(iter_path)

        row = {}
        # Metadata fields
        for col in TREND_CSV_COLUMNS:
            if col in meta:
                row[col] = meta[col]
            elif col in kpis:
                row[col] = kpis[col]
            else:
                row[col] = None

        rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TREND_CSV_COLUMNS,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Trend CSV written: {output_path}")
    print(f"  Rows: {len(rows)}")
    print(f"  Cols: {len(TREND_CSV_COLUMNS)}")

    # Quick summary
    pass_count  = sum(1 for r in rows if r.get("status") == "PASS")
    fail_count  = sum(1 for r in rows if r.get("status") == "FAIL")
    golden_count = sum(1 for r in rows if r.get("iter_tag") == "GOLDEN")
    print(f"  PASS={pass_count}  FAIL={fail_count}  GOLDEN={golden_count}")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="DFT Factory — Lifecycle Manager"
    )
    p.add_argument("--tag",          choices=["GOLDEN", "TRASH", "null"],
                   help="Tag an iteration")
    p.add_argument("--iter-path",    help="Iteration path (for --tag)")
    p.add_argument("--list",         action="store_true",
                   help="List all iterations under --scope")
    p.add_argument("--purge-trash",  action="store_true",
                   help="Delete all TRASH iterations under --scope")
    p.add_argument("--build-csv",    action="store_true",
                   help="Build trend_analysis.csv under --scope")
    p.add_argument("--scope",        default=str(FACTORY_ROOT),
                   help="Root path to operate on (default: FACTORY_ROOT)")
    p.add_argument("--output",       default=None,
                   help="Output path for --build-csv")
    p.add_argument("--dry-run",      action="store_true",
                   help="Preview without making changes")
    return p.parse_args()


def main():
    args  = parse_args()
    scope = Path(args.scope).resolve()

    if args.tag:
        if not args.iter_path:
            print("ERROR: --tag requires --iter-path")
            sys.exit(1)
        tag_iteration(Path(args.iter_path).resolve(), args.tag)

    elif args.list:
        list_iterations(scope)

    elif args.purge_trash:
        purge_trash(scope, dry_run=args.dry_run)

    elif args.build_csv:
        out = Path(args.output) if args.output else (
            scope / "analysis" / "trend_analysis.csv"
        )
        build_trend_csv(scope, out)

    else:
        print("No action specified. Use --tag, --list, --purge-trash, or --build-csv")
        print("Run with --help for usage.")


if __name__ == "__main__":
    main()
