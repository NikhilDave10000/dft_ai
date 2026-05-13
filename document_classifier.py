#!/usr/bin/env python3
"""
document_classifier.py

Namespace-aware documentation corpus classifier.

PURPOSE
-------
Inventory all corpus artifacts, classify semantic types using:
1. NAMESPACE (directory path) as PRIMARY signal
2. FILENAME heuristics as SECONDARY signal
3. CONTENT semantics as TERTIARY signal (future)

This prevents over-classification of .htm files as COMMAND_PAGE.

OUTPUT
------
LOG_CLASSIFICATION/corpus_inventory.json
LOG_CLASSIFICATION/classification_report.json
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# =====================================================================
# CONFIGURATION
# =====================================================================

INPUT_DIR = Path("tmax_olh/Content")
OUTPUT_DIR = Path("LOG_CLASSIFICATION")
INVENTORY_FILE = OUTPUT_DIR / "corpus_inventory.json"
REPORT_FILE = OUTPUT_DIR / "classification_report.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================================================
# SEMANTIC TYPE DEFINITIONS
# =====================================================================

class SemanticType:
    COMMAND_PAGE = "COMMAND_PAGE"
    CATEGORY_INDEX = "CATEGORY_INDEX"
    MASTER_INDEX = "MASTER_INDEX"
    GLOSSARY = "GLOSSARY"
    GUIDE_PAGE = "GUIDE_PAGE"
    POPUP_HELPER = "POPUP_HELPER"
    DRC_RULE = "DRC_RULE"
    MESSAGE_REF = "MESSAGE_REF"
    CTGEN_DOC = "CTGEN_DOC"
    SYSTEM_PAGE = "SYSTEM_PAGE"
    ASSET = "ASSET"
    UNKNOWN = "UNKNOWN"


# =====================================================================
# NAMESPACE CONFIGURATION
# =====================================================================

NAMESPACES = {
    "tmax_cmds": {
        "description": "TestMAX ATPG Command Reference",
        "default_type": SemanticType.COMMAND_PAGE,
        "filename_rules": {
            SemanticType.CATEGORY_INDEX: {"suffixes": ["_commands.htm"]},
            SemanticType.MASTER_INDEX: {"exact": ["tmax_cmds.htm"]},
            SemanticType.GLOSSARY: {"exact": ["glossary.htm"]},
            SemanticType.POPUP_HELPER: {"prefixes": ["popup_"]},
            SemanticType.GUIDE_PAGE: {"prefixes": ["using_", "about_"]},
            SemanticType.SYSTEM_PAGE: {"exact": ["copyright.htm"]},
        }
    },
    "tmax_messages": {
        "description": "TestMAX Message Reference",
        "default_type": SemanticType.MESSAGE_REF,
        "filename_rules": {
            SemanticType.SYSTEM_PAGE: {"exact": ["copyright.htm"]},
        }
    },
    "tmax_rules": {
        "description": "TestMAX DRC Rules",
        "default_type": SemanticType.DRC_RULE,
        "filename_rules": {
            SemanticType.SYSTEM_PAGE: {"exact": ["copyright.htm"]},
        }
    },
    "tmax_ug": {
        "description": "TestMAX User Guide",
        "default_type": SemanticType.GUIDE_PAGE,
        "filename_rules": {
            SemanticType.SYSTEM_PAGE: {"exact": ["copyright.htm"]},
        }
    },
    "ctmgen": {
        "description": "CTGen Documentation",
        "default_type": SemanticType.CTGEN_DOC,
        "filename_rules": {}
    },
}

# Global exclusions (apply across all namespaces)
GLOBAL_EXCLUDED = {
    "copyright.htm",
}

# Asset extensions
ASSET_EXTENSIONS = {".gif", ".png", ".jpg", ".jpeg", ".svg", ".bmp", ".pdf", ".css", ".js", ".ditamap"}


# =====================================================================
# MODELS
# =====================================================================

@dataclass
class DocumentRecord:
    path: str
    basename: str
    namespace: str
    semantic_type: str
    size_bytes: int
    detected_command: Optional[str] = None
    confidence: str = "high"
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassificationReport:
    total_files: int
    by_type: Dict[str, int]
    by_namespace: Dict[str, int]
    by_extension: Dict[str, int]
    command_pages: List[str]
    unclassified: List[str]
    coverage_pct: float


# =====================================================================
# CLASSIFIER ENGINE
# =====================================================================

class DocumentClassifier:
    def __init__(self, input_dir: Path):
        self.input_dir = input_dir
        self.records: List[DocumentRecord] = []

    def discover(self) -> List[Path]:
        """Discover all files recursively."""
        return sorted(self.input_dir.rglob("*"))

    def detect_namespace(self, path: Path) -> Tuple[str, Dict[str, Any]]:
        """Detect namespace from directory path."""
        path_str = str(path).lower()
        for ns_name, ns_config in NAMESPACES.items():
            if ns_name in path_str:
                return ns_name, ns_config
        return "unknown", {"description": "Unknown namespace", "default_type": SemanticType.UNKNOWN, "filename_rules": {}}

    def apply_filename_rules(self, basename: str, rules: Dict[str, Any]) -> Optional[str]:
        """Apply namespace-specific filename rules. Returns semantic type or None."""
        basename_lower = basename.lower()
        for sem_type, rule in rules.items():
            if "exact" in rule:
                if basename_lower in {e.lower() for e in rule["exact"]}:
                    return sem_type
            if "prefixes" in rule:
                for prefix in rule["prefixes"]:
                    if basename_lower.startswith(prefix):
                        return sem_type
            if "suffixes" in rule:
                for suffix in rule["suffixes"]:
                    if basename_lower.endswith(suffix):
                        return sem_type
        return None

    def classify(self, path: Path) -> DocumentRecord:
        """Classify a single file using namespace-aware logic."""
        basename = path.name
        ext = path.suffix.lower()
        size = path.stat().st_size if path.is_file() else 0

        # ASSET: extension-based
        if ext in ASSET_EXTENSIONS:
            return DocumentRecord(
                path=str(path),
                basename=basename,
                namespace="global",
                semantic_type=SemanticType.ASSET,
                size_bytes=size,
                evidence={"rule": "asset_extension", "matched": ext},
            )

        # Not an .htm file and not an asset
        if ext != ".htm":
            return DocumentRecord(
                path=str(path),
                basename=basename,
                namespace="global",
                semantic_type=SemanticType.UNKNOWN,
                size_bytes=size,
                confidence="low",
                evidence={"rule": "unknown_extension", "ext": ext},
            )

        # Detect namespace
        namespace, ns_config = self.detect_namespace(path)

        # Apply namespace-specific filename rules
        matched_type = self.apply_filename_rules(basename, ns_config.get("filename_rules", {}))
        if matched_type:
            return DocumentRecord(
                path=str(path),
                basename=basename,
                namespace=namespace,
                semantic_type=matched_type,
                size_bytes=size,
                evidence={"rule": "filename", "namespace": namespace, "matched": matched_type},
            )

        # Default: use namespace default type
        default_type = ns_config.get("default_type", SemanticType.UNKNOWN)

        # Special case for tmax_cmds: only classify as COMMAND_PAGE if basename looks like a command
        if namespace == "tmax_cmds" and default_type == SemanticType.COMMAND_PAGE:
            # Heuristic: command pages have no special prefix/suffix patterns
            # (we already filtered out popup_, using_, _commands, etc.)
            # So any remaining .htm in tmax_cmds is likely a command page
            cmd_name = basename.replace(".htm", "").replace("man_", "")
            return DocumentRecord(
                path=str(path),
                basename=basename,
                namespace=namespace,
                semantic_type=SemanticType.COMMAND_PAGE,
                size_bytes=size,
                detected_command=cmd_name,
                evidence={"rule": "namespace_default", "namespace": namespace},
            )

        return DocumentRecord(
            path=str(path),
            basename=basename,
            namespace=namespace,
            semantic_type=default_type,
            size_bytes=size,
            evidence={"rule": "namespace_default", "namespace": namespace},
        )

    def run(self) -> ClassificationReport:
        files = self.discover()
        self.records = [self.classify(f) for f in files if f.is_file()]

        by_type: Dict[str, int] = {}
        by_ns: Dict[str, int] = {}
        by_ext: Dict[str, int] = {}
        command_pages = []
        unclassified = []

        for r in self.records:
            by_type[r.semantic_type] = by_type.get(r.semantic_type, 0) + 1
            by_ns[r.namespace] = by_ns.get(r.namespace, 0) + 1
            ext = Path(r.basename).suffix or "no_ext"
            by_ext[ext] = by_ext.get(ext, 0) + 1
            if r.semantic_type == SemanticType.COMMAND_PAGE:
                command_pages.append(r.detected_command or r.basename)
            if r.semantic_type == SemanticType.UNKNOWN:
                unclassified.append(r.basename)

        total = len(self.records)
        classified = total - len(unclassified)
        coverage = (classified / total * 100) if total > 0 else 0

        return ClassificationReport(
            total_files=total,
            by_type=by_type,
            by_namespace=by_ns,
            by_extension=by_ext,
            command_pages=sorted(set(command_pages)),
            unclassified=sorted(unclassified),
            coverage_pct=coverage,
        )


# =====================================================================
# REPORTERS
# =====================================================================

def write_inventory(records: List[DocumentRecord]) -> None:
    with open(INVENTORY_FILE, "w", encoding="utf-8") as fp:
        json.dump([asdict(r) for r in records], fp, indent=2, ensure_ascii=False)


def write_report(report: ClassificationReport) -> None:
    with open(REPORT_FILE, "w", encoding="utf-8") as fp:
        json.dump(asdict(report), fp, indent=2, ensure_ascii=False)


# =====================================================================
# MAIN
# =====================================================================

def main():
    print("[CLASSIFIER] Namespace-Aware Corpus Classification")
    print("=" * 60)
    print(f"Input: {INPUT_DIR}")

    classifier = DocumentClassifier(INPUT_DIR)
    report = classifier.run()

    write_inventory(classifier.records)
    write_report(report)

    print(f"Total files    : {report.total_files}")
    print(f"Classified     : {report.total_files - len(report.unclassified)}")
    print(f"Unclassified   : {len(report.unclassified)}")
    print(f"Coverage       : {report.coverage_pct:.1f}%")
    print()
    print("By semantic type:")
    for stype, count in sorted(report.by_type.items(), key=lambda x: -x[1]):
        print(f"  {stype}: {count}")
    print()
    print("By namespace:")
    for ns, count in sorted(report.by_namespace.items(), key=lambda x: -x[1]):
        print(f"  {ns}: {count}")
    print()
    print(f"Command pages  : {len(report.command_pages)}")
    print(f"Unique commands: {len(set(report.command_pages))}")
    print(f"Unclassified   : {report.unclassified[:10]}...")
    print()
    print("Reports saved:")
    print(f"  {INVENTORY_FILE}")
    print(f"  {REPORT_FILE}")


if __name__ == "__main__":
    main()
