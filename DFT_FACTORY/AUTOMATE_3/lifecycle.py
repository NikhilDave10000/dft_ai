#!/usr/bin/env python3
"""
lifecycle.py — DFT Factory Lifecycle Manager
=============================================
Cross-iteration operations only. Never writes inside a single iter.

FLAGS — ACTIONS (one per call)
  --tag GOLDEN|TRASH|null     Tag one iteration (needs --iter-path)
  --list                      List all iterations under --scope
  --purge-trash               Delete all TRASH iterations under --scope
  --build-csv                 Build trend_analysis.csv from all iters under --scope

FLAGS — SCOPE / OUTPUT
  --iter-path PATH    Target iteration (for --tag only)
  --scope     PATH    Root to operate on (default: FACTORY_ROOT)
  --output    PATH    Where to write CSV (default: scope/analysis/trend_analysis.csv)
  --dry-run           Preview only, no deletion (for --purge-trash)

FLAGS — FILTERING (for --list)
  --filter-status PASS|FAIL|RUNNING|ABORTED|PENDING
  --filter-tag    GOLDEN|TRASH
  --filter-design NAME
"""

import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
sys.path.insert(0, str(_HERE))

from factory_config import FACTORY_ROOT, TREND_CSV_COLUMNS
from utils import read_meta, write_meta


def find_iters(scope):
    return sorted(p.parent for p in scope.rglob(".metadata") if p.is_file())


def tag(ipath, tag_value):
    meta = read_meta(ipath)
    if meta.get("lock"):
        print("ERROR: Iteration is locked (running). Cannot tag.")
        sys.exit(1)
    if tag_value == "GOLDEN" and meta.get("status") != "PASS":
        print(f"WARNING: Tagging non-PASS iteration as GOLDEN "
              f"(status={meta.get('status')}).")
        print("Proceed? [y/N] ", end="")
        if input().strip().lower() != "y":
            print("Aborted.")
            return
    old = meta.get("iter_tag")
    val = None if tag_value == "null" else tag_value
    write_meta(ipath, {"iter_tag": val})
    print(f"Tagged {ipath.name}:  {old}  ->  {val}")


_SW = {"PASS":"PASS   ","FAIL":"FAIL   ","RUNNING":"RUN    ",
       "ABORTED":"ABORT  ","PENDING":"PENDING"}
_TW = {"GOLDEN":"*GOLDEN*","TRASH":" trash  ",None:"        "}


def list_iters(scope, filter_status=None, filter_tag=None, filter_design=None):
    iters = find_iters(scope)
    if not iters:
        print(f"No iterations found under: {scope}")
        return

    filtered = []
    for ip in iters:
        m = read_meta(ip)
        if filter_status and m.get("status") != filter_status.upper():
            continue
        if filter_tag and m.get("iter_tag") != filter_tag.upper():
            continue
        if filter_design and m.get("design") != filter_design:
            continue
        filtered.append((ip, m))

    if not filtered:
        print("No iterations match the given filters.")
        return

    print(f"\n{'St':<9} {'Tag':<10} {'Design':<14} {'Suite':<10} "
          f"{'Stage':<7} {'Exp':<9} {'Sub':<7} {'Iter':<10} {'Runtime':>9}")
    print("─" * 89)
    for ip, m in filtered:
        st = _SW.get(m.get("status"), "?      ")
        tg = _TW.get(m.get("iter_tag"), "        ")
        rt = f"{m['runtime_s']}s" if m.get("runtime_s") else "—"
        print(f"{st:<9} {tg:<10} "
              f"{m.get('design','?'):<14} {m.get('tool_suite','?'):<10} "
              f"{m.get('stage','?'):<7} {m.get('exp_id','?'):<9} "
              f"{m.get('sub_exp_id','?'):<7} {m.get('iter_id','?'):<10} {rt:>9}")
    print(f"\nShown: {len(filtered)} of {len(iters)} iterations")


def purge_trash(scope, dry_run=False):
    targets = [ip for ip in find_iters(scope)
               if read_meta(ip).get("iter_tag") == "TRASH"]
    if not targets:
        print("No TRASH-tagged iterations found.")
        return
    label = "[DRY RUN] " if dry_run else ""
    print(f"{label}Found {len(targets)} TRASH iterations:")
    for t in targets:
        print(f"  {t}")
    if dry_run:
        return
    print(f"\nDelete {len(targets)} iterations? [y/N] ", end="")
    if input().strip().lower() != "y":
        print("Aborted.")
        return
    for t in targets:
        shutil.rmtree(t)
        print(f"  Deleted: {t}")
    print(f"Purged {len(targets)} iterations.")


# KPI patterns — covers all TMAX report_summaries + report_faults fields
_KPI_REGEX = {
    "fault_coverage_pct":      [r"[Ff]ault\s+[Cc]overage\s*[=:]\s*([\d.]+)",
                                 r"\bFC\b\s*[=:]\s*([\d.]+)",
                                 r"Coverage\s*=\s*([\d.]+)\s*%"],
    "atpg_effectiveness_pct":  [r"[Aa]tpg\s+[Ee]ffectiveness\s*[=:]\s*([\d.]+)",
                                 r"\bAE\b\s*[=:]\s*([\d.]+)"],
    "total_faults":            [r"[Tt]otal\s+[Ff]aults\s*[=:]\s*([\d,]+)"],
    "detected_faults":         [r"[Dd]etected\s*[=:]\s*([\d,]+)",
                                 r"\bDT\b\s+[=:]\s*([\d,]+)"],
    "undetected_faults":       [r"[Uu]ndetected\s*[=:]\s*([\d,]+)",
                                 r"\bUD\b\s+[=:]\s*([\d,]+)"],
    "redundant_faults":        [r"[Rr]edundant\s*[=:]\s*([\d,]+)",
                                 r"\bRE\b\s+[=:]\s*([\d,]+)"],
    "blocked_faults":          [r"[Bb]locked\s*[=:]\s*([\d,]+)",
                                 r"\bBL\b\s+[=:]\s*([\d,]+)"],
    "total_patterns":          [r"[Tt]otal\s+[Pp]atterns\s*[=:]\s*([\d,]+)",
                                 r"[Pp]attern\s+[Cc]ount\s*[=:]\s*([\d,]+)"],
    "scan_chains_count":       [r"[Ss]can\s+[Cc]hains\s*[=:]\s*([\d]+)"],
    "scan_cells_count":        [r"[Ss]can\s+[Cc]ells\s*[=:]\s*([\d,]+)"],
    "nonscan_cells_count":     [r"[Nn]on.?scan\s+[Cc]ells\s*[=:]\s*([\d,]+)"],
    "cpu_peak_pct":            [r"[Cc][Pp][Uu]\s+[Uu]sage\s*[=:]\s*([\d.]+)",
                                 r"cpu_usage\s*[=:]\s*([\d.]+)"],
    "mem_peak_mb":             [r"[Mm]emory\s+[Uu]sage\s*[=:]\s*([\d.]+)\s*[Mm][Bb]",
                                 r"memory_usage\s*[=:]\s*([\d.]+)",
                                 r"[Pp]eak\s+[Mm]emory\s*[=:]\s*([\d.]+)"],
}


def extract_kpis(ipath):
    rpt_dir = ipath / "reports"
    kpis    = {k: None for k in _KPI_REGEX}
    if not rpt_dir.exists():
        return kpis
    content = ""
    for f in sorted(rpt_dir.glob("*.rpt")):
        try:
            content += f.read_text(errors="replace") + "\n"
        except Exception:
            pass
    for kpi, patterns in _KPI_REGEX.items():
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                raw = m.group(1).replace(",", "")
                try:
                    kpis[kpi] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    kpis[kpi] = raw
                break
    return kpis


def build_csv(scope, output):
    iters = find_iters(scope)
    if not iters:
        print(f"No iterations found under: {scope}")
        return
    rows = []
    for ip in iters:
        meta = read_meta(ip)
        kpis = extract_kpis(ip)
        row  = {}
        for col in TREND_CSV_COLUMNS:
            row[col] = meta.get(col) if col in meta else kpis.get(col)
        rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TREND_CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    n_pass   = sum(1 for r in rows if r.get("status") == "PASS")
    n_fail   = sum(1 for r in rows if r.get("status") == "FAIL")
    n_golden = sum(1 for r in rows if r.get("iter_tag") == "GOLDEN")
    print(f"CSV written : {output}")
    print(f"  Rows      : {len(rows)}  PASS={n_pass}  FAIL={n_fail}  GOLDEN={n_golden}")
    print(f"  Columns   : {len(TREND_CSV_COLUMNS)}")


def parse_args():
    p = argparse.ArgumentParser(description="DFT Factory — Lifecycle Manager")
    p.add_argument("--tag",           choices=["GOLDEN", "TRASH", "null"])
    p.add_argument("--iter-path",     help="For --tag only")
    p.add_argument("--list",          action="store_true")
    p.add_argument("--purge-trash",   action="store_true")
    p.add_argument("--build-csv",     action="store_true")
    p.add_argument("--scope",         default=str(FACTORY_ROOT))
    p.add_argument("--output",        default=None)
    p.add_argument("--dry-run",       action="store_true")
    p.add_argument("--filter-status", default=None,
                   choices=["PASS","FAIL","RUNNING","ABORTED","PENDING"])
    p.add_argument("--filter-tag",    default=None,
                   choices=["GOLDEN","TRASH"])
    p.add_argument("--filter-design", default=None)
    return p.parse_args()


def main():
    args  = parse_args()
    scope = Path(args.scope).resolve()

    if args.tag:
        if not args.iter_path:
            print("ERROR: --tag requires --iter-path")
            sys.exit(1)
        tag(Path(args.iter_path).resolve(), args.tag)
    elif args.list:
        list_iters(scope,
                   filter_status=args.filter_status,
                   filter_tag=args.filter_tag,
                   filter_design=args.filter_design)
    elif args.purge_trash:
        purge_trash(scope, dry_run=args.dry_run)
    elif args.build_csv:
        out = (Path(args.output) if args.output
               else scope / "analysis" / "trend_analysis.csv")
        build_csv(scope, out)
    else:
        print("Specify: --tag | --list | --purge-trash | --build-csv")
        print("Run with --help for full usage.")


if __name__ == "__main__":
    main()
