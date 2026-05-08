"""
utils.py — shared helpers used by all factory scripts.
Never import orch_run/harvest/lifecycle from here. This is the base layer.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- config resolution regardless of call site ---
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "config"))
from factory_config import (
    FACTORY_ROOT,
    TOOL_REGISTRY,
    STAGE_REGISTRY,
    PHASE_INDEX,
    ITER_SUBDIRS,
    METADATA_DEFAULTS,
)


# =============================================================================
# PATH BUILDER
# =============================================================================

def iter_path(design: str, tool_suite: str, stage: str,
              exp_id: str, sub_exp_id: str, iter_id: str) -> Path:
    """Returns the canonical absolute path for one iteration leaf node."""
    return (FACTORY_ROOT / design / tool_suite / stage
            / exp_id / sub_exp_id / iter_id)


def next_iter_id(parent: Path) -> str:
    """
    Scans parent directory for existing iter_NNN folders and returns
    the next one. iter_001, iter_002, ... iter_099, iter_100, ...
    """
    existing = sorted([
        d.name for d in parent.glob("iter_*") if d.is_dir()
    ])
    if not existing:
        return "iter_001"
    last = existing[-1]
    try:
        n = int(last.split("_")[1])
        return f"iter_{n + 1:03d}"
    except (IndexError, ValueError):
        return f"iter_{len(existing) + 1:03d}"


# =============================================================================
# METADATA
# =============================================================================

def metadata_path(ipath: Path) -> Path:
    return ipath / ".metadata"


def read_meta(ipath: Path) -> dict:
    mp = metadata_path(ipath)
    if not mp.exists():
        print(f"ERROR: No .metadata at {ipath}")
        print(f"       Run: python core/dir_init.py first.")
        sys.exit(1)
    with open(mp) as f:
        return json.load(f)


def write_meta(ipath: Path, updates: dict) -> None:
    mp = metadata_path(ipath)
    meta = {}
    if mp.exists():
        with open(mp) as f:
            meta = json.load(f)
    meta.update(updates)
    with open(mp, "w") as f:
        json.dump(meta, f, indent=2)


def init_meta(ipath: Path, **kwargs) -> None:
    """Write fresh .metadata from defaults + provided fields."""
    meta = dict(METADATA_DEFAULTS)
    meta.update(kwargs)
    meta["timestamp_start"] = datetime.now(timezone.utc).isoformat()
    with open(metadata_path(ipath), "w") as f:
        json.dump(meta, f, indent=2)


# =============================================================================
# VALIDATION
# =============================================================================

def validate(design: str, tool_suite: str, stage: str) -> list:
    errors = []
    if not design.strip():
        errors.append("--design cannot be empty.")
    if tool_suite not in TOOL_REGISTRY:
        errors.append(
            f"Unknown --tool '{tool_suite}'. "
            f"Known: {list(TOOL_REGISTRY.keys())}"
        )
    if stage not in STAGE_REGISTRY:
        errors.append(
            f"Unknown --stage '{stage}'. "
            f"Known: {list(STAGE_REGISTRY.keys())}"
        )
    return errors


# =============================================================================
# PHASE HELPERS
# =============================================================================

def phase_prefix(phase_idx: int, tool_suite: str) -> str:
    """
    Returns the standard file prefix for a phase.
    e.g.  phase_idx=40, tool_suite=SYNOPSYS  =>  "40_TEST-T"
          phase_idx=20, tool_suite=TESSENT    =>  "20_ANALYSIS"
    """
    info      = PHASE_INDEX.get(phase_idx, {})
    tool_mode = info.get(tool_suite, info.get("name", str(phase_idx)).upper())
    return f"{phase_idx:02d}_{tool_mode}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
