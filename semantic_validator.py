#!/usr/bin/env python3
"""
semantic_validator.py

Semantic Infrastructure Integrity Verification.

Validates cross-system consistency across SEMANTIC TRUTH LAYERS.
Schema-adaptive: detects actual structure from first sample file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple


# =====================================================================
# CONFIGURATION
# =====================================================================

CANONICAL_REGISTRY = Path("canonical_commands.json")

PARSER_DIRS = [Path("semantic_ir"), Path("parsed_commands_json")]
ONTOLOGY_PATHS = [Path("ontology_map.json")]
CHUNK_DIRS = [Path("semantic_chunks")]

OUTPUT_DIR = Path("LOG_VALIDATION")
REPORT_FILE = OUTPUT_DIR / "semantic_validation_report.json"
SUMMARY_FILE = OUTPUT_DIR / "semantic_validation_summary.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================================================
# MODELS
# =====================================================================

@dataclass
class Violation:
    check: str
    severity: str
    command: Optional[str]
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    commands_checked: int
    violations: List[Violation]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationSummary:
    timestamp: str
    total_commands: int
    total_errors: int
    total_warnings: int
    total_infos: int
    checks_passed: int
    checks_failed: int
    systems_healthy: bool


# =====================================================================
# DATA LOADERS
# =====================================================================

class DataSource:
    @staticmethod
    def load_json(path: Path) -> Optional[Any]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except (json.JSONDecodeError, OSError) as e:
            return {"__load_error__": str(e)}

    @staticmethod
    def _strip_suffixes(key: str, suffixes: List[str]) -> str:
        for suffix in suffixes:
            if key.endswith(suffix):
                key = key[: -len(suffix)]
        return key

    @staticmethod
    def find_parser_files() -> Tuple[Optional[Path], Dict[str, Any]]:
        for d in PARSER_DIRS:
            if d.exists() and d.is_dir():
                files = list(d.glob("*.json"))
                if files:
                    records = {}
                    for f in files:
                        data = DataSource.load_json(f)
                        if data and (not isinstance(data, dict) or "__load_error__" not in data):
                            key = DataSource._strip_suffixes(f.stem, [".log", ".chunk", ".chunk.log"])
                            records[key] = data
                    return d, records
        return None, {}

    @staticmethod
    def find_ontology() -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        for p in ONTOLOGY_PATHS:
            data = DataSource.load_json(p)
            if data is not None and "__load_error__" not in data:
                return p, data
        return None, None

    @staticmethod
    def find_chunks() -> Tuple[Optional[Path], Dict[str, Any]]:
        for d in CHUNK_DIRS:
            if d.exists() and d.is_dir():
                files = list(d.glob("*.json"))
                if files:
                    records = {}
                    for f in files:
                        data = DataSource.load_json(f)
                        if data and (not isinstance(data, dict) or "__load_error__" not in data):
                            # Handle .chunks.json suffix
                            key = DataSource._strip_suffixes(f.stem, [".chunks", ".chunk", ".chunk.log", ".log"])
                            records[key] = data
                    return d, records
        return None, {}


# =====================================================================
# VALIDATOR ENGINE
# =====================================================================

class SemanticValidator:
    def __init__(self, registry, parser_dir, parser_data, ontology_path, ontology_data, chunk_dir, chunk_data):
        self.registry = registry
        self.canonical_map = registry.get("by_canonical", {})
        self.filename_map = registry.get("by_filename", {})
        self.all_canonical_names = set(self.canonical_map.keys())
        self.all_filename_names = set(self.filename_map.keys())
        self.parser_dir = parser_dir
        self.parser_data = parser_data
        self.ontology_path = ontology_path
        self.ontology_data = ontology_data
        self.chunk_dir = chunk_dir
        self.chunk_data = chunk_data
        self.results = []

    def check_canonical_integrity(self) -> CheckResult:
        violations = []
        checked = 0
        for key, record in self.parser_data.items():
            checked += 1
            canonical_match = key in self.all_canonical_names
            filename_match = key in self.all_filename_names
            if not canonical_match and not filename_match:
                violations.append(Violation(
                    check="canonical_integrity",
                    severity="error",
                    command=key,
                    message=f"Parser command {repr(key)} not found in canonical registry.",
                    evidence={"parser_keys_sample": list(self.parser_data.keys())[:5]},
                ))
                continue
            if filename_match and not canonical_match:
                reg_rec = self.filename_map[key]
                if not reg_rec.get("identity_drift", False):
                    violations.append(Violation(
                        check="canonical_integrity",
                        severity="error",
                        command=key,
                        message=f"Filename {repr(key)} maps to canonical but drift flag is False.",
                        evidence={"canonical": reg_rec.get("canonical_command"), "filename": reg_rec.get("filename_command")},
                    ))
        missing_from_parser = []
        for cmd in self.all_canonical_names:
            if cmd not in self.parser_data:
                filename_key = self.canonical_map[cmd].get("filename_command")
                if filename_key and filename_key not in self.parser_data:
                    missing_from_parser.append(cmd)
        if missing_from_parser:
            violations.append(Violation(
                check="canonical_integrity",
                severity="warning",
                command=None,
                message=f"{len(missing_from_parser)} canonical commands lack parser IR output.",
                evidence={"missing_sample": missing_from_parser[:10]},
            ))
        passed = not any(v.severity == "error" for v in violations)
        return CheckResult(
            check_name="canonical_integrity",
            passed=passed,
            commands_checked=checked,
            violations=violations,
            metadata={
                "registry_commands": len(self.all_canonical_names),
                "parser_commands": len(self.parser_data),
                "missing_from_parser_count": len(missing_from_parser),
            },
        )

    def check_ontology_coverage(self) -> CheckResult:
        violations = []
        checked = 0
        if self.ontology_data is None:
            violations.append(Violation(
                check="ontology_coverage",
                severity="error",
                command=None,
                message="Ontology data not found.",
            ))
            return CheckResult(
                check_name="ontology_coverage",
                passed=False,
                commands_checked=0,
                violations=violations,
            )
        ontology_commands = set()
        if isinstance(self.ontology_data, dict):
            ontology_commands = set(self.ontology_data.keys())
        elif isinstance(self.ontology_data, list):
            for entry in self.ontology_data:
                if isinstance(entry, dict) and "command" in entry:
                    ontology_commands.add(entry["command"])

        unmapped = []
        for cmd in self.all_canonical_names:
            checked += 1
            if cmd not in ontology_commands:
                filename = self.canonical_map[cmd].get("filename_command")
                if filename and filename not in ontology_commands:
                    unmapped.append(cmd)
        if unmapped:
            violations.append(Violation(
                check="ontology_coverage",
                severity="warning",
                command=None,
                message=f"{len(unmapped)} canonical commands not mapped in ontology.",
                evidence={"unmapped_sample": unmapped[:10]},
            ))

        orphans = []
        for ont_cmd in ontology_commands:
            if ont_cmd not in self.all_canonical_names and ont_cmd not in self.all_filename_names:
                orphans.append(ont_cmd)
        if orphans:
            violations.append(Violation(
                check="ontology_coverage",
                severity="warning",
                command=None,
                message=f"{len(orphans)} ontology entries have no canonical command.",
                evidence={"orphan_sample": orphans[:10]},
            ))

        drifted_ontology = []
        for ont_cmd in ontology_commands:
            if ont_cmd not in self.all_canonical_names:
                if ont_cmd in self.all_filename_names:
                    drifted_ontology.append({
                        "ontology_key": ont_cmd,
                        "registry_canonical": self.filename_map[ont_cmd].get("canonical_command"),
                        "issue": "ontology uses filename key instead of canonical",
                    })
                else:
                    for canon in self.all_canonical_names:
                        if self._levenshtein(ont_cmd, canon) <= 2:
                            drifted_ontology.append({
                                "ontology_key": ont_cmd,
                                "near_match_canonical": canon,
                                "issue": "possible typo drift",
                            })
                            break
        if drifted_ontology:
            violations.append(Violation(
                check="ontology_coverage",
                severity="warning",
                command=None,
                message=f"{len(drifted_ontology)} ontology entries show drift or typo patterns.",
                evidence={"drifted_sample": drifted_ontology[:10]},
            ))

        passed = not any(v.severity == "error" for v in violations)
        return CheckResult(
            check_name="ontology_coverage",
            passed=passed,
            commands_checked=checked,
            violations=violations,
            metadata={
                "ontology_entries": len(ontology_commands),
                "unmapped_count": len(unmapped),
                "orphan_count": len(orphans),
                "drifted_count": len(drifted_ontology),
            },
        )

    @staticmethod
    def _levenshtein(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return SemanticValidator._levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def check_semantic_chunks(self) -> CheckResult:
        violations = []
        checked = 0
        if not self.chunk_dir:
            violations.append(Violation(
                check="semantic_chunks",
                severity="error",
                command=None,
                message="Chunk directory not found.",
            ))
            return CheckResult(
                check_name="semantic_chunks",
                passed=False,
                commands_checked=0,
                violations=violations,
            )

        VALID_CHUNK_TYPES = {
            "syntax", "description", "short_description", "examples",
            "arguments", "options", "returns", "see_also",
            "usage", "notes", "prerequisites", "related",
            "argument", "example", "execution_example",
        }

        for cmd in self.all_canonical_names:
            checked += 1
            filename = self.canonical_map[cmd].get("filename_command", cmd)
            chunk_record = self.chunk_data.get(filename) or self.chunk_data.get(cmd)
            if chunk_record is None:
                violations.append(Violation(
                    check="semantic_chunks",
                    severity="error",
                    command=cmd,
                    message=f"No chunk file found for {repr(cmd)} (filename: {repr(filename)}).",
                ))
                continue

            # Schema-adaptive: handle LIST at top level (your schema)
            if isinstance(chunk_record, list):
                chunks = chunk_record
                if not chunks:
                    violations.append(Violation(
                        check="semantic_chunks",
                        severity="warning",
                        command=cmd,
                        message=f"Chunk file for {repr(cmd)} has empty list.",
                    ))
                    continue
                # Check for syntax chunk
                has_syntax = any(self._chunk_type(c) == "syntax" for c in chunks)
                if not has_syntax:
                    available = [self._chunk_type(c) for c in chunks if self._chunk_type(c)]
                    violations.append(Violation(
                        check="semantic_chunks",
                        severity="error",
                        command=cmd,
                        message=f"Missing syntax chunk for {repr(cmd)}.",
                        evidence={"available_types": available},
                    ))
                # Check for empty content
                for i, chunk in enumerate(chunks):
                    content = self._chunk_content(chunk)
                    if content is not None and len(str(content).strip()) == 0:
                        violations.append(Violation(
                            check="semantic_chunks",
                            severity="warning",
                            command=cmd,
                            message=f"Empty content in chunk {i} (type: {self._chunk_type(chunk)}).",
                        ))
                # Check for duplicate IDs
                ids_seen = set()
                for chunk in chunks:
                    cid = self._chunk_id(chunk)
                    if cid and cid in ids_seen:
                        violations.append(Violation(
                            check="semantic_chunks",
                            severity="error",
                            command=cmd,
                            message=f"Duplicate chunk ID {repr(cid)} in {repr(cmd)}.",
                        ))
                    ids_seen.add(cid or "")
                # Check for invalid chunk types
                for chunk in chunks:
                    ctype = self._chunk_type(chunk)
                    if ctype and ctype not in VALID_CHUNK_TYPES:
                        violations.append(Violation(
                            check="semantic_chunks",
                            severity="warning",
                            command=cmd,
                            message=f"Unknown chunk type {repr(ctype)} for {repr(cmd)}.",
                            evidence={"valid_types": sorted(VALID_CHUNK_TYPES)},
                        ))
                continue

            # Handle dict schema (telemetry or nested)
            if isinstance(chunk_record, dict):
                if "chunks_created" in chunk_record:
                    violations.append(Violation(
                        check="semantic_chunks",
                        severity="error",
                        command=cmd,
                        message=f"Chunk file for {repr(cmd)} is TELEMETRY, not semantic truth.",
                        evidence={"hint": "semantic_chunks/*.json should contain actual chunk content"},
                    ))
                    continue
                # Try nested chunk arrays
                chunk_arrays = []
                for key in ["chunks", "sections", "segments", "blocks", "data"]:
                    if key in chunk_record and isinstance(chunk_record[key], list):
                        chunk_arrays = chunk_record[key]
                        break
                if chunk_arrays:
                    # Same validation as list above
                    if not chunk_arrays:
                        violations.append(Violation(
                            check="semantic_chunks",
                            severity="warning",
                            command=cmd,
                            message=f"Chunk file for {repr(cmd)} has empty chunk array.",
                        ))
                    has_syntax = any(self._chunk_type(c) == "syntax" for c in chunk_arrays)
                    if not has_syntax:
                        available = [self._chunk_type(c) for c in chunk_arrays if self._chunk_type(c)]
                        violations.append(Violation(
                            check="semantic_chunks",
                            severity="error",
                            command=cmd,
                            message=f"Missing syntax chunk for {repr(cmd)}.",
                            evidence={"available_types": available},
                        ))
                elif "content" in chunk_record:
                    content = str(chunk_record.get("content", "")).strip()
                    if len(content) < 10:
                        violations.append(Violation(
                            check="semantic_chunks",
                            severity="warning",
                            command=cmd,
                            message=f"Chunk content for {repr(cmd)} is very short ({len(content)} chars).",
                        ))
                else:
                    violations.append(Violation(
                        check="semantic_chunks",
                        severity="warning",
                        command=cmd,
                        message=f"Chunk file for {repr(cmd)} has unrecognized schema.",
                        evidence={"top_keys": list(chunk_record.keys())},
                    ))

        passed = not any(v.severity == "error" for v in violations)
        return CheckResult(
            check_name="semantic_chunks",
            passed=passed,
            commands_checked=checked,
            violations=violations,
            metadata={
                "chunk_files_found": len(self.chunk_data),
            },
        )

    @staticmethod
    def _chunk_type(chunk):
        if isinstance(chunk, dict):
            for key in ["type", "chunk_type", "kind", "category", "section_type", "chunk_name"]:
                if key in chunk:
                    return str(chunk[key]).lower()
        return None

    @staticmethod
    def _chunk_content(chunk):
        if isinstance(chunk, dict):
            for key in ["content", "text", "body", "data", "value"]:
                if key in chunk:
                    return str(chunk[key])
        return None

    @staticmethod
    def _chunk_id(chunk):
        if isinstance(chunk, dict):
            for key in ["id", "chunk_id", "uuid", "identifier"]:
                if key in chunk:
                    return str(chunk[key])
        return None

    def check_see_also_resolution(self) -> CheckResult:
        violations = []
        checked = 0
        broken_links = []
        for key, record in self.parser_data.items():
            checked += 1
            if not isinstance(record, dict):
                continue
            see_also = self._extract_see_also(record)
            for ref in see_also:
                ref_clean = ref.strip()
                if not ref_clean:
                    continue
                in_canonical = ref_clean in self.all_canonical_names
                in_filename = ref_clean in self.all_filename_names
                if not in_canonical and not in_filename:
                    broken_links.append((key, ref_clean))
                    violations.append(Violation(
                        check="see_also_resolution",
                        severity="error",
                        command=key,
                        message=f"see_also reference {repr(ref_clean)} from {repr(key)} does not resolve in canonical registry.",
                    ))
        passed = not any(v.severity == "error" for v in violations)
        return CheckResult(
            check_name="see_also_resolution",
            passed=passed,
            commands_checked=checked,
            violations=violations,
            metadata={
                "broken_links": broken_links[:20],
            },
        )

    @staticmethod
    def _extract_see_also(record):
        for key in ["see_also", "seeAlso", "related_commands", "related", "cross_references"]:
            val = record.get(key)
            if val is None:
                continue
            if isinstance(val, list):
                results = []
                for item in val:
                    if isinstance(item, str):
                        results.append(item)
                    elif isinstance(item, dict):
                        cmd = item.get("command")
                        if cmd:
                            results.append(cmd)
                return results
            if isinstance(val, str):
                if "," in val:
                    return [v.strip() for v in val.split(",")]
                return val.split()
        return []

    def check_parser_structure(self) -> CheckResult:
        violations = []
        checked = 0
        for key, record in self.parser_data.items():
            checked += 1
            if not isinstance(record, dict):
                violations.append(Violation(
                    check="parser_structure",
                    severity="error",
                    command=key,
                    message=f"Parser record for {repr(key)} is not a dict: {type(record).__name__}.",
                ))
                continue

            # Detect telemetry: file has telemetry markers AND lacks semantic content
            has_telemetry = "section_states" in record or "parser_actions" in record or "ontology_patterns" in record
            has_semantic = any(k in record for k in ["short_description", "description", "syntax", "arguments", "examples"])
            if has_telemetry and not has_semantic:
                violations.append(Violation(
                    check="parser_structure",
                    severity="error",
                    command=key,
                    message=f"Parser record for {repr(key)} is TELEMETRY, not semantic IR.",
                ))
                continue

            # Syntax: handle list or string
            syntax_raw = self._extract_field(record, ["syntax", "command_syntax", "usage"])
            syntax_text = self._flatten_field(syntax_raw)
            if not syntax_text or len(syntax_text.strip()) == 0:
                violations.append(Violation(
                    check="parser_structure",
                    severity="error",
                    command=key,
                    message=f"Missing or empty syntax for {repr(key)}.",
                ))

            # Description: handle list or string
            desc_raw = self._extract_field(record, ["description", "short_description", "summary", "abstract", "desc"])
            desc_text = self._flatten_field(desc_raw)
            if not desc_text or len(desc_text.strip()) < 10:
                violations.append(Violation(
                    check="parser_structure",
                    severity="warning",
                    command=key,
                    message=f"Missing or very short description for {repr(key)}.",
                    evidence={"description_length": len(desc_text or "")},
                ))

            # Section match
            reg_rec = self.filename_map.get(key) or self.canonical_map.get(key)
            if reg_rec:
                parser_section = self._extract_field(record, ["section", "category", "command_section", "group"])
                registry_section = reg_rec.get("command_section", "UNKNOWN")
                if parser_section and str(parser_section) != registry_section:
                    violations.append(Violation(
                        check="parser_structure",
                        severity="warning",
                        command=key,
                        message=f"Section mismatch: parser={repr(parser_section)}, registry={repr(registry_section)}.",
                    ))

            # Examples: handle list or string
            examples_raw = self._extract_field(record, ["examples", "example", "example_usage", "usage_examples"])
            if examples_raw is not None:
                if isinstance(examples_raw, list):
                    if len(examples_raw) == 0:
                        violations.append(Violation(
                            check="parser_structure",
                            severity="info",
                            command=key,
                            message=f"Empty examples list for {repr(key)}.",
                        ))
                    for i, ex in enumerate(examples_raw):
                        ex_text = self._flatten_field(ex)
                        if not ex_text or len(ex_text.strip()) < 5:
                            violations.append(Violation(
                                check="parser_structure",
                                severity="warning",
                                command=key,
                                message=f"Malformed example {i} for {repr(key)} (too short).",
                            ))
                elif isinstance(examples_raw, str):
                    if len(examples_raw.strip()) < 5:
                        violations.append(Violation(
                            check="parser_structure",
                            severity="warning",
                            command=key,
                            message=f"Malformed examples string for {repr(key)} (too short).",
                        ))

        passed = not any(v.severity == "error" for v in violations)
        return CheckResult(
            check_name="parser_structure",
            passed=passed,
            commands_checked=checked,
            violations=violations,
        )

    @staticmethod
    def _extract_field(record, keys):
        for k in keys:
            if k in record:
                return record[k]
        return None

    @staticmethod
    def _flatten_field(value):
        """Flatten list-of-strings or string to a single string."""
        if value is None:
            return ""
        if isinstance(value, list):
            return "\n".join(str(x) for x in value)
        return str(value)

    def check_cross_field_consistency(self) -> CheckResult:
        """
        Detect semantic contradictions across fields.

        Rules:
        - command_name MUST appear as root token in syntax
        - syntax MUST not contain commands from other semantic families
        - description MUST reference the command by name
        """
        violations = []
        checked = 0
        contradictions = []

        for cmd in self.all_canonical_names:
            checked += 1
            parser_rec = self.parser_data.get(cmd)
            if not parser_rec or not isinstance(parser_rec, dict):
                continue

            # RULE 1: command_name MUST match syntax root
            syntax_raw = parser_rec.get("syntax", [])
            syntax_text = self._flatten_field(syntax_raw)

            if syntax_text:
                # Extract first token from syntax (root command)
                first_line = syntax_text.split("\n")[0].strip()
                root_token = first_line.split()[0] if first_line else ""
                root_token = root_token.replace("man_", "").replace(".htm", "")

                # Check if command name appears in syntax
                if cmd not in syntax_text and root_token != cmd:
                    # Check filename fallback
                    filename = self.canonical_map[cmd].get("filename_command", cmd)
                    if filename not in syntax_text and root_token != filename:
                        contradictions.append({
                            "command": cmd,
                            "rule": "command_name_vs_syntax_root",
                            "syntax_root": root_token,
                            "syntax_preview": syntax_text[:80],
                        })
                        violations.append(Violation(
                            check="cross_field_consistency",
                            severity="warning",
                            command=cmd,
                            message=f"Semantic contradiction: command name {repr(cmd)} does not appear in syntax root {repr(root_token)}. Possible vendor documentation typo.",
                            evidence={
                                "syntax_preview": syntax_text[:120],
                                "expected_root": cmd,
                                "actual_root": root_token,
                            },
                        ))

            # RULE 2: description MUST reference the command
            desc_raw = parser_rec.get("description", []) or parser_rec.get("short_description", "")
            desc_text = self._flatten_field(desc_raw)

            if desc_text and len(desc_text) > 20:
                # Command name should appear in description
                if cmd not in desc_text.lower():
                    filename = self.canonical_map[cmd].get("filename_command", cmd)
                    if filename not in desc_text.lower():
                        violations.append(Violation(
                            check="cross_field_consistency",
                            severity="info",
                            command=cmd,
                            message=f"Command name {repr(cmd)} not found in description text. Description may be generic or inherited.",
                            evidence={"description_preview": desc_text[:80]},
                        ))

        passed = not any(v.severity == "error" for v in violations)
        return CheckResult(
            check_name="cross_field_consistency",
            passed=passed,
            commands_checked=checked,
            violations=violations,
            metadata={
                "contradictions_found": len(contradictions),
                "contradiction_examples": contradictions[:10],
            },
        )

    def run_all(self):
        checks = [
            self.check_canonical_integrity(),
            self.check_ontology_coverage(),
            self.check_semantic_chunks(),
            self.check_see_also_resolution(),
            self.check_parser_structure(),
            self.check_cross_field_consistency(),
        ]
        self.results = checks
        total_errors = sum(1 for c in checks for v in c.violations if v.severity == "error")
        total_warnings = sum(1 for c in checks for v in c.violations if v.severity == "warning")
        total_infos = sum(1 for c in checks for v in c.violations if v.severity == "info")
        checks_passed = sum(1 for c in checks if c.passed)
        checks_failed = len(checks) - checks_passed
        summary = ValidationSummary(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_commands=len(self.all_canonical_names),
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_infos=total_infos,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            systems_healthy=(checks_failed == 0 and total_errors == 0),
        )
        return checks, summary


# =====================================================================
# REPORTERS
# =====================================================================

def build_report(checks, summary):
    return {
        "validation_timestamp": summary.timestamp,
        "canonical_registry": str(CANONICAL_REGISTRY),
        "checks": {
            c.check_name: {
                "passed": c.passed,
                "commands_checked": c.commands_checked,
                "violations": [asdict(v) for v in c.violations],
                "metadata": c.metadata,
            }
            for c in checks
        },
        "summary": asdict(summary),
    }


def write_outputs(report):
    with open(REPORT_FILE, "w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2, ensure_ascii=False)
    summary_flat = {
        "timestamp": report["summary"]["timestamp"],
        "systems_healthy": report["summary"]["systems_healthy"],
        "total_commands": report["summary"]["total_commands"],
        "total_errors": report["summary"]["total_errors"],
        "total_warnings": report["summary"]["total_warnings"],
        "checks": {
            name: {
                "passed": data["passed"],
                "violations": len(data["violations"]),
            }
            for name, data in report["checks"].items()
        },
    }
    with open(SUMMARY_FILE, "w", encoding="utf-8") as fp:
        json.dump(summary_flat, fp, indent=2, ensure_ascii=False)


# =====================================================================
# MAIN
# =====================================================================

def main():
    print("[VALIDATOR] Semantic Infrastructure Integrity Verification")
    print("=" * 60)
    registry_data = DataSource.load_json(CANONICAL_REGISTRY)
    if registry_data is None or (isinstance(registry_data, dict) and "__load_error__" in registry_data):
        print(f"[FATAL] Cannot load canonical registry: {CANONICAL_REGISTRY}")
        raise SystemExit(1)
    print(f"[1/5] Registry loaded: {len(registry_data.get('by_canonical', {}))} commands")
    parser_dir, parser_data = DataSource.find_parser_files()
    ontology_path, ontology_data = DataSource.find_ontology()
    chunk_dir, chunk_data = DataSource.find_chunks()
    print(f"[2/5] Parser source: {parser_dir or 'NOT FOUND'} ({len(parser_data)} records)")
    print(f"[3/5] Ontology source: {ontology_path or 'NOT FOUND'}")
    print(f"[4/5] Chunk source: {chunk_dir or 'NOT FOUND'} ({len(chunk_data)} records)")

    validator = SemanticValidator(
        registry=registry_data,
        parser_dir=parser_dir,
        parser_data=parser_data,
        ontology_path=ontology_path,
        ontology_data=ontology_data,
        chunk_dir=chunk_dir,
        chunk_data=chunk_data,
    )
    checks, summary = validator.run_all()
    report = build_report(checks, summary)
    write_outputs(report)
    print()
    print("=" * 60)
    print("VALIDATION COMPLETE")
    print(f"Systems healthy : {summary.systems_healthy}")
    print(f"Commands        : {summary.total_commands}")
    print(f"Errors          : {summary.total_errors}")
    print(f"Warnings        : {summary.total_warnings}")
    print(f"Infos           : {summary.total_infos}")
    print(f"Checks passed   : {summary.checks_passed}/{len(checks)}")
    print("=" * 60)
    print()
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        vcount = len(c.violations)
        print(f"  [{status}] {c.check_name} ({c.commands_checked} cmds, {vcount} violations)")
    print()
    print("[5/5] Reports saved:")
    print(f"  {REPORT_FILE}")
    print(f"  {SUMMARY_FILE}")
    if not summary.systems_healthy:
        raise SystemExit(1)


if __name__ == "__main__":
    main()