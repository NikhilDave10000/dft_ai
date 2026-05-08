#!/usr/bin/env python3
# =============================================================================
# dir_init.py — DFT Factory Directory Initializer
# =============================================================================
# Creates the complete 6-level directory tree for one iteration.
# This is the FIRST thing called before any tool run.
#
# Usage:
#   python dir_init.py \
#       --design i2c \
#       --tool   TMAX \
#       --stage  ATPG_SAF \
#       --exp    EXP1 \
#       --sub    1.1 \
#       --iter   Iter_01
#
#   # Or with --dry-run to preview without creating anything
#   python dir_init.py --design i2c --tool TMAX --stage ATPG_SAF \
#       --exp EXP1 --sub 1.1 --iter Iter_01 --dry-run
#
#   # Auto-increment iteration (finds next Iter_NN)
#   python dir_init.py --design i2c --tool TMAX --stage ATPG_SAF \
#       --exp EXP1 --sub 1.1 --iter auto
# =============================================================================

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- resolve config regardless of where this script is called from ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_FACTORY_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_FACTORY_DIR / "config"))
from factory_config import (
    FACTORY_ROOT,
    TOOL_REGISTRY,
    STAGE_REGISTRY,
    ITER_SUBDIRS,
    METADATA_SCHEMA,
)


# =============================================================================
# PATH BUILDER
# =============================================================================

def build_iter_path(design: str, tool: str, stage: str,
                    exp: str, sub: str, iter_id: str) -> Path:
    """Constructs the canonical 6-level path for one iteration."""
    return FACTORY_ROOT / design / tool / stage / exp / sub / iter_id


def next_auto_iter(parent: Path) -> str:
    """Finds the next available Iter_NN under parent."""
    existing = sorted([
        d.name for d in parent.glob("Iter_*") if d.is_dir()
    ])
    if not existing:
        return "Iter_01"
    last = existing[-1]
    try:
        n = int(last.split("_")[1])
        return f"Iter_{n + 1:02d}"
    except (IndexError, ValueError):
        return f"Iter_{len(existing) + 1:02d}"


# =============================================================================
# VALIDATION
# =============================================================================

def validate_inputs(design: str, tool: str, stage: str) -> list[str]:
    """Returns list of validation errors (empty = all good)."""
    errors = []
    if tool not in TOOL_REGISTRY:
        errors.append(
            f"Unknown tool '{tool}'. Known: {list(TOOL_REGISTRY.keys())}"
        )
    if stage not in STAGE_REGISTRY:
        errors.append(
            f"Unknown stage '{stage}'. Known: {list(STAGE_REGISTRY.keys())}"
        )
    if tool in TOOL_REGISTRY and stage in STAGE_REGISTRY:
        supported = TOOL_REGISTRY[tool]["supported_stages"]
        if stage not in supported:
            errors.append(
                f"Tool '{tool}' does not support stage '{stage}'. "
                f"Supported: {supported}"
            )
    if not design.strip():
        errors.append("Design name cannot be empty.")
    return errors


# =============================================================================
# DIRECTORY CREATION
# =============================================================================

def create_iter_tree(iter_path: Path, dry_run: bool = False) -> None:
    """Creates the iteration leaf node with all standard subdirectories."""
    dirs_to_create = [iter_path / sub for sub in ITER_SUBDIRS]

    if dry_run:
        print(f"\n[DRY RUN] Would create: {iter_path}")
        for d in dirs_to_create:
            print(f"  + {d.relative_to(FACTORY_ROOT)}")
        return

    if iter_path.exists():
        print(f"WARNING: Iteration path already exists: {iter_path}")
        print("         Use orch_run.py --rerun to safely reset it.")
        sys.exit(1)

    iter_path.mkdir(parents=True, exist_ok=False)
    for d in dirs_to_create:
        d.mkdir(exist_ok=True)

    print(f"Created: {iter_path}")
    for d in dirs_to_create:
        print(f"  + {d.name}/")


# =============================================================================
# METADATA WRITER
# =============================================================================

def write_metadata(iter_path: Path, design: str, tool: str, stage: str,
                   exp: str, sub: str, iter_id: str,
                   fault_type: str = "", notes: str = "",
                   dry_run: bool = False) -> None:
    """Writes the initial .metadata JSON file into the iteration folder."""
    meta = dict(METADATA_SCHEMA)   # copy the schema defaults
    meta.update({
        "design":          design,
        "tool":            tool,
        "stage":           stage,
        "exp_id":          exp,
        "sub_exp":         sub,
        "iter_id":         iter_id,
        "fault_type":      fault_type,
        "notes":           notes,
        "timestamp_start": datetime.now(timezone.utc).isoformat(),
    })

    meta_path = iter_path / ".metadata"

    if dry_run:
        print(f"\n[DRY RUN] Would write .metadata:")
        print(json.dumps(meta, indent=2))
        return

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  + .metadata written")


# =============================================================================
# CHAIN RESOLVER — links inputs from upstream GOLDEN iteration
# =============================================================================

def resolve_chain_inputs(iter_path: Path, stage: str,
                         design: str, tool: str,
                         exp: str, sub: str,
                         dry_run: bool = False) -> None:
    """
    If stage has a chain_from dependency, finds the GOLDEN iteration of the
    upstream stage and symlinks its outputs/ into this iter's inputs/.
    """
    chain_from = STAGE_REGISTRY[stage].get("chain_from")
    if chain_from is None:
        return  # no upstream dependency for this stage

    upstream_base = FACTORY_ROOT / design / tool / chain_from / exp / sub
    if not upstream_base.exists():
        print(f"WARNING: Chain source not found: {upstream_base}")
        print(f"         Stage '{stage}' expects upstream '{chain_from}'.")
        print(f"         Run upstream stage first and tag a GOLDEN iteration.")
        return

    # Find the GOLDEN-tagged iteration
    golden_iter = None
    for iter_dir in sorted(upstream_base.iterdir()):
        meta_path = iter_dir / ".metadata"
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            if meta.get("iter_tag") == "GOLDEN":
                golden_iter = iter_dir
                break

    if golden_iter is None:
        print(f"WARNING: No GOLDEN iteration found in {upstream_base}")
        print(f"         Tag one with: python lifecycle.py --tag GOLDEN ...")
        return

    # Create symlink: inputs/upstream_STAGE -> golden_iter/outputs/
    link_target = golden_iter / "outputs"
    link_name   = iter_path / "inputs" / f"from_{chain_from}"

    if dry_run:
        print(f"\n[DRY RUN] Would symlink:")
        print(f"  {link_name} -> {link_target}")
        return

    if link_target.exists():
        link_name.symlink_to(link_target)
        print(f"  + Chained inputs from: {golden_iter.name} ({chain_from})")
    else:
        print(f"WARNING: GOLDEN outputs/ not found at {link_target}")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Initialize one iteration in the DFT Data Factory hierarchy."
    )
    p.add_argument("--design",     required=True, help="Design name (e.g. i2c)")
    p.add_argument("--tool",       required=True, help="Tool suite (e.g. TMAX, TESSENT)")
    p.add_argument("--stage",      required=True, help="DFT stage (e.g. ATPG_SAF)")
    p.add_argument("--exp",        required=True, help="Experiment ID (e.g. EXP1)")
    p.add_argument("--sub",        required=True, help="Sub-experiment (e.g. 1.1)")
    p.add_argument("--iter",       required=True, help="Iteration ID or 'auto'")
    p.add_argument("--fault-type", default="",   help="Fault type label (e.g. SAF, TF)")
    p.add_argument("--notes",      default="",   help="Free-text notes for this run")
    p.add_argument("--dry-run",    action="store_true",
                   help="Preview what would be created without writing anything")
    return p.parse_args()


def main():
    args = parse_args()

    # --- validation ---
    errors = validate_inputs(args.design, args.tool, args.stage)
    if errors:
        print("ERROR: Invalid arguments:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # --- resolve auto iter ---
    iter_id = args.iter
    if iter_id == "auto":
        parent = (FACTORY_ROOT / args.design / args.tool /
                  args.stage / args.exp / args.sub)
        iter_id = next_auto_iter(parent)
        print(f"Auto-selected iteration: {iter_id}")

    iter_path = build_iter_path(
        args.design, args.tool, args.stage, args.exp, args.sub, iter_id
    )

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Initializing iteration:")
    print(f"  Design  : {args.design}")
    print(f"  Tool    : {args.tool}")
    print(f"  Stage   : {args.stage}")
    print(f"  Exp     : {args.exp}  Sub: {args.sub}  Iter: {iter_id}")
    print(f"  Path    : {iter_path}")
    print()

    create_iter_tree(iter_path, dry_run=args.dry_run)
    write_metadata(
        iter_path,
        design=args.design, tool=args.tool, stage=args.stage,
        exp=args.exp, sub=args.sub, iter_id=iter_id,
        fault_type=args.fault_type, notes=args.notes,
        dry_run=args.dry_run,
    )
    resolve_chain_inputs(
        iter_path, stage=args.stage,
        design=args.design, tool=args.tool,
        exp=args.exp, sub=args.sub,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print(f"\nIteration ready. Next step:")
        print(f"  python orch_run.py --iter-path {iter_path}")


if __name__ == "__main__":
    main()
