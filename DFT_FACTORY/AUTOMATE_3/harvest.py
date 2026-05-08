#!/usr/bin/env python3
"""harvest.py v2 - Per-iteration output normalizer. See docstring in file for flags."""
import argparse, json, re, shutil, sys
from pathlib import Path
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
sys.path.insert(0, str(_HERE))
from factory_config import PHASE_INDEX
from utils import read_meta, write_meta, now_iso, phase_prefix

def passport(meta, source_name):
    return ("# " + "="*73 + "\n# DFT DATA FACTORY - LOG PASSPORT\n# " + "="*73 + "\n"
            + "\n".join(f"# {k:<14}: {v}" for k,v in [
                ("Design", meta.get("design")), ("Tool suite", meta.get("tool_suite")),
                ("Stage", meta.get("stage")), ("Exp / Sub", f"{meta.get('exp_id')} / {meta.get('sub_exp_id')}"),
                ("Iteration", meta.get("iter_id")), ("Status", meta.get("status")),
                ("Runtime", f"{meta.get('runtime_s')} s"), ("Started", meta.get("timestamp_start")),
                ("Ended", meta.get("timestamp_end")), ("Tool version", meta.get("tool_version","unknown")),
                ("Source file", source_name), ("Harvested", now_iso())]) + "\n# " + "="*73 + "\n\n")

def prepend_passport(dest, hdr):
    original = dest.read_text(errors="replace")
    if not original.startswith("# ==="):
        dest.write_text(hdr + original)

# Full TMAX 175-command taxonomy coverage
_PHASE_KEYWORDS = {
    10: ["build","setup","init","load_netlist","read_netlist","modules","model",
         "library","cell_model","read_cell","workspace"],
    20: ["drc","rules","violations","rule_fail","scan_chain","scan_cell","scan_ability",
         "scan_enable","scan_path","nonscan","non_scan","feedback","feedback_path",
         "buses","clocks","clock_gating","lockup","lockup_latch","serializer","compressor",
         "wires","nets","fanin","fanout","pins","ports","instances","timing","sdc",
         "read_sdc","read_timing","layout","physical","read_layout","memory_file","read_memory"],
    30: ["fault_pre","fault_before","pre_fault","pre_add","fault_model","add_faults",
         "fault_summary_pre","fault_all_pre"],
    40: ["atpg","test_t","engine","coverage","fault_summary","fault_all","fault_coll",
         "fault_collapsed","fault_post","fault_after","post_atpg","after_atpg",
         "patterns","pattern_count","constraints","atpg_constraint","primitives",
         "atpg_primitive","summaries","summary","toggleweights","toggle",
         "testpoint","test_point","observe","diagnosis","diag","power","iddq",
         "random_pattern","reorder"],
    60: ["sim","simulation","fault_sim","simtrace","analyze_sim","simulation_data"],
    80: ["export","write_pattern","write_fault","write_netlist","write_image",
         "write_drc","write_db","write_ydf","output","stil","wgl","binary","testbench",
         "streaming","ydf"],
}

def infer_phase(name, custom_map=None):
    nl = name.lower().replace("-","_").replace(".","_")
    if custom_map:
        for pat, idx in custom_map.items():
            if pat.lower() in nl: return int(idx)
    for phase, kws in _PHASE_KEYWORDS.items():
        if any(k in nl for k in kws): return phase
    return 40

def harvest_reports(ipath, meta, extra_dirs, custom_map):
    tool = meta.get("tool_suite","SYNOPSYS")
    rpt_dir = ipath / "reports"
    done = []
    candidates = []
    for d in [ipath/"work", ipath/"logs"] + extra_dirs:
        if d.exists(): candidates += list(d.rglob("*.rpt"))
    for f in rpt_dir.glob("*.rpt"):
        if not re.match(r"^\d{2}_", f.name): candidates.append(f)
    for src in candidates:
        ph = infer_phase(src.stem, custom_map)
        pref = phase_prefix(ph, tool)
        dest = rpt_dir / f"{pref}_{src.name}"
        if src.resolve() != dest.resolve(): shutil.copy2(src, dest)
        print(f"  RPT  {src.name:<45} -> reports/{dest.name}")
        done.append(dest.name)
    return done

def harvest_logs(ipath, meta, extra_dirs, custom_map):
    tool = meta.get("tool_suite","SYNOPSYS")
    logs_dir = ipath / "logs"
    done = []
    for d in [ipath/"work"] + extra_dirs:
        if d.exists():
            for src in d.rglob("*.log"):
                ph = infer_phase(src.stem, custom_map)
                pref = phase_prefix(ph, tool)
                dest = logs_dir / f"{pref}_{src.name}"
                shutil.copy2(src, dest)
                print(f"  LOG  {src.name:<45} -> logs/{dest.name}")
                done.append(dest.name)
    for log in logs_dir.glob("*.log"):
        prepend_passport(log, passport(meta, log.name))
    return done

_VERSION_PATTERNS = {
    "SYNOPSYS": [r"TetraMAX[^\d]*([\d.]+)", r"TMAX[^\d]*([\d.]+)", r"[Vv]ersion[:\s]+([\d.]+)"],
    "TESSENT":  [r"Tessent[^\d]*([\d.]+)", r"Mentor[^\d]*([\d.]+)", r"[Vv]ersion[:\s]+([\d.]+)"],
}

def extract_version(ipath, tool):
    for log in sorted((ipath/"logs").glob("*.log")):
        try:
            content = log.read_text(errors="replace")
            for pat in _VERSION_PATTERNS.get(tool, []):
                m = re.search(pat, content, re.IGNORECASE)
                if m: return m.group(1)
        except Exception: continue
    return "unknown"

def parse_args():
    p = argparse.ArgumentParser(description="Normalize DFT tool outputs.")
    p.add_argument("--iter-path", required=True)
    p.add_argument("--no-wipe-work", action="store_true")
    p.add_argument("--extra-search-dirs", nargs="*", default=[], dest="extra_search_dirs")
    p.add_argument("--phase-map", default=None,
                   help='JSON {"pattern": phase_index} override for phase inference')
    return p.parse_args()

def main():
    args = parse_args()
    ipath = Path(args.iter_path).resolve()
    if not ipath.exists():
        print(f"ERROR: {ipath} not found."); sys.exit(1)
    meta = read_meta(ipath)
    tool = meta.get("tool_suite","SYNOPSYS")
    extra_dirs = [Path(d).resolve() for d in (args.extra_search_dirs or [])]
    custom_map = None
    if args.phase_map:
        try: custom_map = json.loads(args.phase_map)
        except Exception as e: print(f"WARNING: --phase-map parse error: {e}")
    print(f"\nHarvesting: {meta['design']} / {tool} / {meta['stage']} / {meta['iter_id']}\n")
    print("--- Reports ---")
    rpts = harvest_reports(ipath, meta, extra_dirs, custom_map)
    print("\n--- Logs ---")
    logs = harvest_logs(ipath, meta, extra_dirs, custom_map)
    version = extract_version(ipath, tool)
    print(f"\n  Tool version : {version}")
    if not args.no_wipe_work:
        print("\n--- Cleanup ---")
        work = ipath / "work"
        if work.exists(): shutil.rmtree(work); work.mkdir()
        print("  WIPE work/ cleared")
    else:
        print("\nINFO: --no-wipe-work: work/ retained")
    write_meta(ipath, {"harvest_done": True, "tool_version": version})
    print(f"\nHarvest done: {len(rpts)} reports, {len(logs)} logs")

if __name__ == "__main__":
    main()
