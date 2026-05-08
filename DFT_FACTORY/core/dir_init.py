#!/usr/bin/env python3
"""
dir_init.py — DFT Factory: Directory Initializer
=================================================
Creates the 6-level iteration tree and writes .metadata.

USAGE
-----
# Create one iteration
python core/dir_init.py \\
    --design  i2c_master  \\
    --tool    SYNOPSYS    \\
    --stage   ATPG        \\
    --exp     SA_EXP1     \\
    --sub     E1.1        \\
    --iter    iter_001

# Auto-number the iteration
python core/dir_init.py --design i2c --tool SYNOPSYS --stage SCAN \\
    --exp SA_EXP1 --sub E1.1 --iter auto

# Preview without touching disk
python core/dir_init.py ... --dry-run

# List all registered stages (useful to check what's available)
python core/dir_init.py --list-stages

# Add a new stage on the fly (edits factory_config.py automatically)
python core/dir_init.py --add-stage MBIST \\
    --stage-desc "Memory BIST insertion" \\
    --stage-phases "10,20,25,40,80" \\
    --stage-chain-from SCAN
"""

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
sys.path.insert(0, str(_HERE))

from factory_config import (
    FACTORY_ROOT, TOOL_REGISTRY, STAGE_REGISTRY, ITER_SUBDIRS
)
from utils import (
    iter_path, next_iter_id, init_meta, validate
)


# =============================================================================
# TREE CREATION
# =============================================================================

def create_tree(ipath: Path, dry_run: bool = False) -> None:
    if ipath.exists():
        print(f"ERROR: Already exists: {ipath}")
        print(f"       Use --iter auto to get the next free iteration.")
        sys.exit(1)

    subdirs = [ipath / s for s in ITER_SUBDIRS]

    if dry_run:
        print(f"\n[DRY RUN] Would create:")
        print(f"  {ipath}")
        for d in subdirs:
            print(f"    {d.name}/")
        return

    ipath.mkdir(parents=True)
    for d in subdirs:
        d.mkdir()

    print(f"Created: {ipath}")
    for d in subdirs:
        print(f"  + {d.name}/")


# =============================================================================
# DYNAMIC STAGE ADDER
# Appends a new stage block to factory_config.py
# =============================================================================

def add_stage(name: str, desc: str, phases: list[int],
              chain_from: str | None) -> None:
    """
    Adds a new stage entry to STAGE_REGISTRY in factory_config.py.
    This is the only place you ever need to edit to support a new stage.
    """
    if name in STAGE_REGISTRY:
        print(f"Stage '{name}' already exists in STAGE_REGISTRY.")
        return

    config_path = _HERE.parent / "config" / "factory_config.py"
    content     = config_path.read_text()

    chain_str = f'"{chain_from}"' if chain_from else "None"
    phases_str = str(phases)

    new_block = (
        f'    "{name}": {{\n'
        f'        "description": "{desc}",\n'
        f'        "phases":      {phases_str},\n'
        f'        "chain_from":  {chain_str},\n'
        f'    }},\n'
        f'    # --- end {name} ---\n'
    )

    # Insert before the closing comment block that marks the end of STAGE_REGISTRY
    marker = "    # -------"
    if marker in content:
        content = content.replace(marker, new_block + marker, 1)
    else:
        # Fallback: append before closing brace of STAGE_REGISTRY dict
        content = content.replace(
            "}\n\n# =============================================================================\n# PHASE INDEX",
            "    " + new_block.strip() + "\n}\n\n"
            "# =============================================================================\n# PHASE INDEX"
        )

    config_path.write_text(content)
    print(f"Stage '{name}' added to factory_config.py")
    print(f"  Description : {desc}")
    print(f"  Phases      : {phases}")
    print(f"  Chain from  : {chain_from}")
    print(f"\nRestart any running scripts to pick up the change.")


# =============================================================================
# ENTRYPOINT
# =============================================================================

def parse_args():
    p = argparse.ArgumentParser(
        description="Initialize a DFT Factory iteration directory."
    )

    # --- normal run ---
    p.add_argument("--design",  help="Design name  (e.g. i2c_master)")
    p.add_argument("--tool",    help="Tool suite   (SYNOPSYS | TESSENT)")
    p.add_argument("--stage",   help="DFT stage    (SCAN | ATPG | SIM)")
    p.add_argument("--exp",     help="Experiment ID (e.g. SA_EXP1)")
    p.add_argument("--sub",     help="Sub-exp ID   (e.g. E1.1)")
    p.add_argument("--iter",    help="Iteration ID or 'auto'")
    p.add_argument("--note",    default="", help="Short description of this run")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview without writing anything")

    # --- utility commands ---
    p.add_argument("--list-stages",  action="store_true",
                   help="Print all registered stages and exit")
    p.add_argument("--add-stage",    metavar="NAME",
                   help="Register a new stage in factory_config.py")
    p.add_argument("--stage-desc",   default="",
                   help="Description for --add-stage")
    p.add_argument("--stage-phases", default="10,20,40,80",
                   help="Comma-separated phase indices for --add-stage")
    p.add_argument("--stage-chain-from", default=None,
                   help="Upstream stage name for --add-stage")

    return p.parse_args()


def main():
    args = parse_args()

    # --- utility: list stages ---
    if args.list_stages:
        print("\nRegistered DFT stages:\n")
        for name, cfg in STAGE_REGISTRY.items():
            chain = cfg.get("chain_from") or "none"
            print(f"  {name:<12}  phases={cfg['phases']}"
                  f"  chain_from={chain}")
            print(f"             {cfg['description']}")
        print()
        return

    # --- utility: add stage ---
    if args.add_stage:
        phases = [int(x.strip()) for x in args.stage_phases.split(",")]
        add_stage(
            name       = args.add_stage.upper(),
            desc       = args.stage_desc,
            phases     = phases,
            chain_from = args.stage_chain_from,
        )
        return

    # --- normal: create iteration ---
    required = ["design", "tool", "stage", "exp", "sub", "iter"]
    missing  = [f"--{r}" for r in required if not getattr(args, r)]
    if missing:
        print(f"ERROR: Missing required args: {' '.join(missing)}")
        sys.exit(1)

    tool_suite = args.tool.upper()
    stage      = args.stage.upper()

    errors = validate(args.design, tool_suite, stage)
    if errors:
        print("ERROR:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    # resolve auto iter
    iter_id = args.iter
    if iter_id == "auto":
        parent  = (FACTORY_ROOT / args.design / tool_suite
                   / stage / args.exp / args.sub)
        iter_id = next_iter_id(parent)
        print(f"Auto iter: {iter_id}")

    ipath = iter_path(args.design, tool_suite, stage,
                      args.exp, args.sub, iter_id)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}"
          f"Initializing iteration:")
    print(f"  {args.design} / {tool_suite} / {stage} "
          f"/ {args.exp} / {args.sub} / {iter_id}")
    print(f"  {ipath}\n")

    create_tree(ipath, dry_run=args.dry_run)

    if not args.dry_run:
        init_meta(
            ipath,
            design      = args.design,
            tool_suite  = tool_suite,
            stage       = stage,
            exp_id      = args.exp,
            sub_exp_id  = args.sub,
            iter_id     = iter_id,
            experiment_note = args.note,
        )
        print(f"  + .metadata written")
        print(f"\nNext:")
        print(f"  python core/orch_run.py --iter-path {ipath} --tcl <your_script.tcl>")


if __name__ == "__main__":
    main()
