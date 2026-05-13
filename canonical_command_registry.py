#!/usr/bin/env python3
"""
canonical_command_registry.py

Deterministic canonical command identity resolver.
"""

from __future__ import annotations

import json
import os

from dataclasses import dataclass, asdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Any, Tuple

MASTER_INDEX_HTML = "tmax_olh/Content/tmax_cmds/tmax_cmds.htm"
OUTPUT_FILE = "canonical_commands.json"
LOG_DIR = "LOG_REGISTRY"
TELEMETRY_FILE = "registry_loader.log.json"
MIN_EXPECTED_COMMANDS = 200

# FIX 1 — Broader section keyword matching for vendor resilience
SECTION_KEYWORDS: Tuple[str, ...] = ("commands", "command")

os.makedirs(LOG_DIR, exist_ok=True)

@dataclass
class CommandRecord:
    href: str
    canonical_command: str
    command_section: str
    filename_command: str
    category: str
    identity_drift: bool
    # FIX 4 — Preserve original vendor ordering for deterministic downstream use
    command_index: int

@dataclass
class RegistryTelemetry:
    total_commands_indexed: int
    total_sections: int
    identity_drift_count: int
    unknown_section_count: int  # FIX 3 — Parser degradation evidence
    drift_examples: List[Dict[str, str]]

class CommandIndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.records: List[CommandRecord] = []
        self.current_section: str = "UNKNOWN"
        self.in_p: bool = False
        self.in_ul: bool = False
        self.in_li: bool = False
        self.in_a: bool = False
        self.current_href: str = ""
        self.current_text: str = ""
        self._next_index: int = 0

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "p":
            self.in_p = True
        elif tag_lower == "ul":
            self.in_ul = True
        elif tag_lower == "li":
            self.in_li = True
        elif tag_lower == "a":
            self.in_a = True
            self.current_href = dict(attrs).get("href", "")
            self.current_text = ""

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "p":
            self.in_p = False
        elif tag_lower == "ul":
            self.in_ul = False
            # FIX 2 — Section semantic scoping: reset when <ul> closes
            # This prevents state leak across unrelated sections.
            self.current_section = "UNKNOWN"
        elif tag_lower == "li":
            self.in_li = False
        elif tag_lower == "a":
            self.in_a = False
            # FIX 1 — Broader section keyword matching
            if self.in_p and any(
                k in self.current_text.lower()
                for k in SECTION_KEYWORDS
            ):
                self.current_section = self.current_text.strip()
            elif self.in_li:
                self._process_command()

    def handle_data(self, data: str) -> None:
        if self.in_a:
            self.current_text += data

    def _process_command(self) -> None:
        canonical_cmd = self.current_text.strip()
        if not canonical_cmd:
            return
        href_basename = self.current_href.split("/")[-1]
        if href_basename == "predefined_aliases.htm":
            return
        filename_cmd = self._extract_filename_command(self.current_href)
        category = self._infer_category(canonical_cmd)
        # FIX: Case-sensitive drift detection to catch Set_commands vs set_commands
        identity_drift = (
            filename_cmd.strip()
            !=
            canonical_cmd.strip()
        )
        idx = self._next_index
        self._next_index += 1
        self.records.append(CommandRecord(
            href=self.current_href,
            canonical_command=canonical_cmd,
            command_section=self.current_section,
            filename_command=filename_cmd,
            category=category,
            identity_drift=identity_drift,
            command_index=idx,
        ))

    @staticmethod
    def _extract_filename_command(href: str) -> str:
        filename = href.split("/")[-1]
        base = filename.replace(".htm", "").replace(".html", "")
        if base.startswith("man_"):
            base = base[4:]
        return base

    @staticmethod
    def _infer_category(command: str) -> str:
        prefixes = {
            "add_": "ADD",
            "remove_": "REMOVE",
            "report_": "REPORT",
            "read_": "READ",
            "write_": "WRITE",
            "run_": "RUN",
            "set_": "SET",
            "get_": "GET",
            "update_": "UPDATE",
            "analyze_": "ANALYZE",
        }
        for prefix, category in prefixes.items():
            if command.startswith(prefix):
                return category
        return "OTHER"

def write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)

def main() -> None:
    html_path = Path(MASTER_INDEX_HTML)
    if not html_path.exists():
        raise FileNotFoundError(f"Master index HTML not found: {html_path}")

    print(f"[1/4] Parsing master index: {html_path}")
    parser = CommandIndexParser()
    with open(html_path, "r", encoding="utf-8", errors="replace") as fp:
        parser.feed(fp.read())

    if len(parser.records) < MIN_EXPECTED_COMMANDS:
        raise RuntimeError(
            f"Parse yielded only {len(parser.records)} commands; "
            f"expected at least {MIN_EXPECTED_COMMANDS}."
        )

    print("[2/4] Building canonical registry maps...")
    registry: Dict[str, Dict[str, Any]] = {
        "by_filename": {},
        "by_canonical": {}
    }
    drift_examples: List[Dict[str, str]] = []
    unknown_section_count = 0

    for rec in parser.records:
        rec_dict = asdict(rec)
        if rec.filename_command in registry["by_filename"]:
            existing = registry["by_filename"][rec.filename_command]
            raise ValueError(
                f"Duplicate filename command collision for {rec.filename_command!r}: "
                f"existing canonical={existing['canonical_command']!r}, "
                f"new canonical={rec.canonical_command!r}"
            )
        if rec.canonical_command in registry["by_canonical"]:
            existing = registry["by_canonical"][rec.canonical_command]
            raise ValueError(
                f"Duplicate canonical command collision for {rec.canonical_command!r}: "
                f"existing filename={existing['filename_command']!r}, "
                f"new filename={rec.filename_command!r}"
            )
        registry["by_filename"][rec.filename_command] = rec_dict
        registry["by_canonical"][rec.canonical_command] = rec_dict
        if rec.identity_drift:
            drift_examples.append({
                "filename_command": rec.filename_command,
                "canonical_command": rec.canonical_command
            })
        if rec.command_section == "UNKNOWN":
            unknown_section_count += 1

    print("[3/4] Saving registry and telemetry...")
    write_json(Path(OUTPUT_FILE), registry)

    sections = set(
        rec.command_section
        for rec in parser.records
        if rec.command_section != "UNKNOWN"
    )
    telemetry = RegistryTelemetry(
        total_commands_indexed=len(parser.records),
        total_sections=len(sections),
        identity_drift_count=len(drift_examples),
        unknown_section_count=unknown_section_count,
        drift_examples=drift_examples[:10]
    )
    write_json(Path(LOG_DIR) / TELEMETRY_FILE, asdict(telemetry))

    print()
    print("=" * 48)
    print("CANONICAL REGISTRY COMPLETE")
    print(f"Total commands  : {telemetry.total_commands_indexed}")
    print(f"Total sections  : {telemetry.total_sections}")
    print(f"Identity drifts : {telemetry.identity_drift_count}")
    print(f"Unknown sections: {telemetry.unknown_section_count}")
    print("=" * 48)
    if drift_examples:
        print("\nDrift Evidence Preserved:")
        for ex in drift_examples[:5]:
            print(f"  - File: {ex['filename_command']} -> Canonical: {ex['canonical_command']}")

if __name__ == "__main__":
    main()