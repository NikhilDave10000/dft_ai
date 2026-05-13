#!/usr/bin/env python3
"""
semantic_ir_extractor.py

Transforms hybrid parser output (telemetry + semantic content)
into pure semantic IR for validator consumption.

INPUT:  parsed_commands_json/*.json  (hybrid)
OUTPUT: semantic_ir/*.json           (pure semantic truth)

CLEANUPS:
- Removes telemetry fields (section_states, parser_actions, etc.)
- Filters see_also to only canonical command references
- Normalizes chunk type references
- Validates against canonical registry
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set


# =====================================================================
# CONFIGURATION
# =====================================================================

INPUT_DIR = Path("parsed_commands_json")
OUTPUT_DIR = Path("semantic_ir")
REGISTRY_FILE = Path("canonical_commands.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Telemetry fields to strip
TELEMETRY_FIELDS = {
    "section_states", "parser_actions", "parser_warnings",
    "ontology_patterns", "chunker_telemetry", "parse_metadata",
}

# Fields that are semantic truth and should be preserved
SEMANTIC_FIELDS = {
    "command", "canonical_command", "title", "section",
    "short_description", "description", "syntax",
    "arguments", "options", "examples", "see_also",
    "source_file", "document_type", "category",
}


def load_registry(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    return data


def extract_semantic_ir(hybrid: Dict[str, Any], canonical_names: Set[str], filename_names: Set[str]) -> Optional[Dict[str, Any]]:
    """Extract pure semantic IR from hybrid parser record."""
    if not isinstance(hybrid, dict):
        return None

    # Start with only semantic fields
    semantic = {}
    for key, value in hybrid.items():
        if key in TELEMETRY_FIELDS:
            continue
        if key in SEMANTIC_FIELDS or key not in TELEMETRY_FIELDS:
            semantic[key] = value

    # Ensure canonical_command is set
    cmd = semantic.get("command", "")
    if cmd in canonical_names:
        semantic["canonical_command"] = cmd
    elif cmd in filename_names:
        semantic["canonical_command"] = filename_names[cmd]
    else:
        # Command not in registry — skip (this is the get_licenses case)
        return None

    # Clean see_also: keep only canonical command references
    see_also_raw = semantic.get("see_also", [])
    cleaned_see_also = []
    removed_refs = []

    for ref in see_also_raw:
        if isinstance(ref, dict):
            ref_cmd = ref.get("command", "").strip()
            ref_href = ref.get("href", "")
        elif isinstance(ref, str):
            ref_cmd = ref.strip()
            ref_href = ""
        else:
            continue

        if not ref_cmd:
            continue

        # Check if it's a canonical command or filename
        if ref_cmd in canonical_names or ref_cmd in filename_names:
            cleaned_see_also.append({
                "command": ref_cmd,
                "href": ref_href
            })
        else:
            removed_refs.append(ref_cmd)

    if cleaned_see_also:
        semantic["see_also"] = cleaned_see_also
    elif "see_also" in semantic:
        del semantic["see_also"]

    # Normalize description/syntax/examples: ensure they're lists of strings
    for field in ["description", "syntax", "examples"]:
        if field in semantic:
            val = semantic[field]
            if isinstance(val, str):
                semantic[field] = [val]
            elif not isinstance(val, list):
                semantic[field] = [str(val)]

    # Normalize arguments: ensure list of dicts
    if "arguments" in semantic:
        args = semantic["arguments"]
        if isinstance(args, dict):
            semantic["arguments"] = [args]
        elif not isinstance(args, list):
            semantic["arguments"] = [{"term": str(args), "description": ""}]

    return semantic


def main():
    print("[EXTRACTOR] Semantic IR Extraction")
    print("=" * 50)

    registry = load_registry(REGISTRY_FILE)
    canonical_names = set(registry.get("by_canonical", {}).keys())
    filename_names = {k: v.get("canonical_command", k) for k, v in registry.get("by_filename", {}).items()}

    print(f"Registry: {len(canonical_names)} canonical commands")

    files = list(INPUT_DIR.glob("*.json"))
    print(f"Input files: {len(files)}")

    extracted = 0
    skipped = 0
    see_also_removed = 0

    for f in files:
        with open(f, "r", encoding="utf-8") as fp:
            hybrid = json.load(fp)

        semantic = extract_semantic_ir(hybrid, canonical_names, filename_names)
        if semantic is None:
            skipped += 1
            print(f"  [SKIP] {f.stem} — not in canonical registry")
            continue

        # Count removed see_also refs
        raw_see_also = hybrid.get("see_also", [])
        clean_see_also = semantic.get("see_also", [])
        see_also_removed += len(raw_see_also) - len(clean_see_also)

        out_path = OUTPUT_DIR / f"{f.stem}.json"
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(semantic, fp, indent=2, ensure_ascii=False)

        extracted += 1

    print()
    print("=" * 50)
    print("EXTRACTION COMPLETE")
    print(f"Extracted : {extracted}")
    print(f"Skipped   : {skipped} (not in registry)")
    print(f"See-also cleaned: {see_also_removed} non-command refs removed")
    print(f"Output dir: {OUTPUT_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()