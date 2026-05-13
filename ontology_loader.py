#!/usr/bin/env python3
"""
ontology_loader.py

Deterministic curator-ontology loader.

PURPOSE
-------
Convert human-curated ontology HTML:

    tmax_command_pairs.html

into authoritative semantic family mapping:

    ontology_map.json

This loader is:
- deterministic,
- strictly curated (NO inference),
- coverage-auditing,
- telemetry-visible.

IMPORTANT PRINCIPLES
--------------------
Human engineering semantics are MUCH higher quality than
statistical clustering or embedding similarity.

DO NOT infer ontology edges.
DO NOT guess semantic families.
USE curated source ONLY.

OUTPUT
------
ontology_map.json
"""

from __future__ import annotations

import json
import os
import re

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Set


# =====================================================================
# CONFIGURATION
# =====================================================================

ONTOLOGY_HTML_FILE = "tmax_command_pairs_1.html"

PARSED_COMMANDS_DIR = "parsed_commands_json"

OUTPUT_FILE = "ontology_map.json"

LOG_DIR = "LOG_ONTOLOGY"

TELEMETRY_FILE = "ontology_loader.log.json"

os.makedirs(LOG_DIR, exist_ok=True)


# =====================================================================
# TELEMETRY
# =====================================================================

@dataclass
class OntologyTelemetry:
    total_families_loaded: int
    total_commands_mapped: int
    parser_commands_total: int
    parser_commands_covered: int
    parser_commands_uncovered: List[str]
    coverage_percent: float


# =====================================================================
# JAVASCRIPT DATA EXTRACTOR
# =====================================================================

def load_ontology_html(path: Path) -> Dict[str, List[str]]:
    """
    Load and parse the embedded JavaScript data in the HTML file.
    Returns dictionary of { semantic_family: [commands] }
    """
    if not path.exists():
        raise FileNotFoundError(
            f"CRITICAL: Curated ontology HTML not found at {path}\n"
            f"System cannot proceed without Level 3 truth hierarchy."
        )

    with open(path, "r", encoding="utf-8", errors="replace") as fp:
        text = fp.read()

    # The HTML renders data from a JS variable: const data = [ { name:"...", rows:[...] }, ... ];
    # We extract directly from this JS structure for maximum determinism.
    
    # Match the group name and the rows array
    group_pattern = re.compile(
        r'name:"(.*?)".*?rows:(\[\[.*?\]\])', 
        re.DOTALL
    )
    
    # Match the category and command inside the rows array
    # e.g., ["ADD","add_faults"] or ["TCL API","all_clocks"]
    row_pattern = re.compile(r'"(.*?)"\s*,\s*"([^"]+)"')

    ontology_data = {}

    for match in group_pattern.finditer(text):
        group_name = match.group(1).strip().upper()
        rows_str = match.group(2)
        
        if group_name not in ontology_data:
            ontology_data[group_name] = []
            
        # Extract commands from rows
        for row_match in row_pattern.finditer(rows_str):
            command = row_match.group(2).strip()
            if command:
                ontology_data[group_name].append(command)

    # Deduplicate commands within families just in case HTML has repeats
    cleaned_data = {}
    for family, cmds in ontology_data.items():
        cleaned_data[family] = list(dict.fromkeys(cmds)) # Preserves order, removes dups
        
    return cleaned_data


def get_parsed_commands(directory: Path) -> Set[str]:
    """
    Scan parsed_commands_json to get the universe of known commands.
    Used for coverage auditing.
    """
    commands = set()
    for json_file in directory.glob("*.json"):
        commands.add(json_file.stem)
    return commands


def build_ontology_map(
    ontology_data: Dict[str, List[str]]
) -> Dict[str, Dict[str, str]]:
    """
    Flatten family->[commands] into command->{family, source}.
    """
    mapping = {}

    for family, commands in ontology_data.items():
        for cmd in commands:
            clean_cmd = cmd.strip()
            if clean_cmd:
                mapping[clean_cmd] = {
                    "semantic_family": family,
                    "source": "manual_curated"
                }

    return mapping


# =====================================================================
# FILE IO
# =====================================================================

def write_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)


# =====================================================================
# MAIN
# =====================================================================

def main() -> None:
    html_path = Path(ONTOLOGY_HTML_FILE)
    parsed_dir = Path(PARSED_COMMANDS_DIR)
    output_path = Path(OUTPUT_FILE)

    # 1. Extract curated ontology
    print(f"[1/4] Loading curated ontology: {html_path}")
    ontology_data = load_ontology_html(html_path)
    
    # 2. Flatten to command-level mapping
    print("[2/4] Building command-level ontology map...")
    ontology_map = build_ontology_map(ontology_data)

    # 3. Audit coverage against parser output
    print(f"[3/4] Auditing coverage against {parsed_dir}...")
    parser_commands = get_parsed_commands(parsed_dir)
    mapped_commands = set(ontology_map.keys())
    
    uncovered = list(parser_commands - mapped_commands)
    
    total_parsed = len(parser_commands)
    covered_parsed = len(parser_commands & mapped_commands)
    coverage_pct = (covered_parsed / total_parsed * 100) if total_parsed > 0 else 0.0

    telemetry = OntologyTelemetry(
        total_families_loaded=len(ontology_data),
        total_commands_mapped=len(ontology_map),
        parser_commands_total=total_parsed,
        parser_commands_covered=covered_parsed,
        parser_commands_uncovered=sorted(uncovered),
        coverage_percent=round(coverage_pct, 2)
    )

    # 4. Save outputs
    print(f"[4/4] Saving map to {output_path}...")
    write_json(output_path, ontology_map)

    telemetry_path = Path(LOG_DIR) / TELEMETRY_FILE
    write_json(telemetry_path, asdict(telemetry))

    # Summary
    print()
    print("================================================")
    print(f"Families loaded       : {telemetry.total_families_loaded}")
    print(f"Commands mapped       : {telemetry.total_commands_mapped}")
    print(f"Parser coverage       : {telemetry.coverage_percent}%")
    print(f"Uncovered commands    : {len(uncovered)}")
    print("================================================")
    
    if uncovered and len(uncovered) <= 20:
        print("Uncovered list        :", uncovered)
    elif uncovered:
        print("(Uncovered list saved to telemetry log)")


if __name__ == "__main__":
    main()