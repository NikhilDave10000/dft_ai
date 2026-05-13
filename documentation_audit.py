#!/usr/bin/env python3
"""
documentation_audit.py

Deterministic markdown documentation inventory + classification tool.

PURPOSE
-------
Audit all markdown files in the repository and classify them into:

- ACTIVE
- LEGACY
- DUPLICATE
- GENERATED
- ARCHITECTURE
- TASK
- SESSION
- GOVERNANCE
- HISTORY
- ENTRYPOINT
- RESEARCH
- UNKNOWN

This prevents documentation entropy in the DFT AI OS repo.

OUTPUT
------
LOG_DOCS/documentation_inventory.json
LOG_DOCS/documentation_summary.json
"""

from __future__ import annotations

import hashlib
import json
import os

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List


# =====================================================================
# CONFIG
# =====================================================================

ROOT_DIR = "."

LOG_DIR = "LOG_DOCS"

OUTPUT_FILE = "documentation_inventory.json"

SUMMARY_FILE = "documentation_summary.json"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".aider.tags.cache.v4",
    ".claude",
    "venv",
    "__pycache__",
    "free-claude-code",
}

os.makedirs(LOG_DIR, exist_ok=True)


# =====================================================================
# MODELS
# =====================================================================

@dataclass
class DocumentRecord:
    path: str
    filename: str
    classification: str
    status: str
    size_bytes: int
    line_count: int
    content_hash: str
    duplicate_of: str | None


# =====================================================================
# HELPERS
# =====================================================================

def load_text(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fp:
            return fp.read()
    except Exception:
        return ""


def compute_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def count_lines(text: str) -> int:
    return len(text.splitlines())


# =====================================================================
# CLASSIFICATION
# =====================================================================

def classify_document(path: str) -> tuple[str, str]:
    """
    Returns:
        classification, status
    """

    normalized = path.lower()

    # ---------------------------------------------------------
    # GOVERNANCE
    # ---------------------------------------------------------

    governance_keywords = [
        "charter",
        "conventions",
        "rules",
        "policy",
        "governance",
    ]

    if any(keyword in normalized for keyword in governance_keywords):
        return "GOVERNANCE", "ACTIVE"

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------

    history_keywords = [
        "decisions",
        "decision",
        "changelog",
        "history",
    ]

    if any(keyword in normalized for keyword in history_keywords):
        return "HISTORY", "ACTIVE"

    # ---------------------------------------------------------
    # ENTRYPOINT
    # ---------------------------------------------------------

    if normalized.endswith("readme.md"):
        return "ENTRYPOINT", "ACTIVE"

    # ---------------------------------------------------------
    # RESEARCH
    # ---------------------------------------------------------

    research_keywords = [
        "explanation",
        "lessons",
        "journey",
        "research",
    ]

    if any(keyword in normalized for keyword in research_keywords):
        return "RESEARCH", "ACTIVE"

    # ---------------------------------------------------------
    # ARCHITECTURE
    # ---------------------------------------------------------

    architecture_keywords = [
        "architecture",
        "walkthrough",
        "guide",
        "runtime_flow",
        "retrieval_contract",
        "core_rules",
        "skill",
        "agent",
        "ontology",
        "semantic",
        "graph",
        "roadmap",
    ]

    if any(keyword in normalized for keyword in architecture_keywords):
        return "ARCHITECTURE", "ACTIVE"

    # ---------------------------------------------------------
    # TASKS
    # ---------------------------------------------------------

    if "/tasks/" in normalized or "task_" in normalized:
        return "TASK", "LEGACY"

    # ---------------------------------------------------------
    # SESSION / TEMPORARY
    # ---------------------------------------------------------

    session_keywords = [
        "session",
        "handoff",
        "continue",
        ".aider",
        "bootstrap",
    ]

    if any(keyword in normalized for keyword in session_keywords):
        return "SESSION", "LEGACY"

    # ---------------------------------------------------------
    # GENERATED
    # ---------------------------------------------------------

    generated_keywords = [
        "setup",
        "implementation",
        "phase",
        "complete",
    ]

    if any(keyword in normalized for keyword in generated_keywords):
        return "GENERATED", "REVIEW"

    # ---------------------------------------------------------
    # ACTIVE / OPERATIONAL
    # ---------------------------------------------------------

    operational_keywords = [
        "command",
        "audit",
        "rag",
        "embedding",
        "parser",
        "chunk",
        "validator",
    ]

    if any(keyword in normalized for keyword in operational_keywords):
        return "ACTIVE", "ACTIVE"

    # ---------------------------------------------------------
    # UNKNOWN
    # ---------------------------------------------------------

    return "UNKNOWN", "REVIEW"


# =====================================================================
# MAIN
# =====================================================================

def main() -> None:

    inventory: Dict[str, Dict] = {}

    hash_index: Dict[str, str] = {}

    classification_summary: Dict[str, int] = {}

    total_files = 0

    # ---------------------------------------------------------
    # WALK REPO
    # ---------------------------------------------------------

    for root, dirs, files in os.walk(ROOT_DIR):

        # prune excluded dirs
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS
        ]

        for file in files:

            if not file.endswith(".md"):
                continue

            path = Path(root) / file

            rel_path = str(path.relative_to(ROOT_DIR))

            text = load_text(path)

            content_hash = compute_hash(text)

            duplicate_of = None

            # -------------------------------------------------
            # DUPLICATE DETECTION
            # -------------------------------------------------

            if content_hash in hash_index:

                duplicate_of = hash_index[content_hash]

                classification = "DUPLICATE"

                status = "REVIEW"

            else:

                hash_index[content_hash] = rel_path

                classification, status = classify_document(
                    rel_path
                )

            # -------------------------------------------------
            # RECORD
            # -------------------------------------------------

            record = DocumentRecord(
                path=rel_path,
                filename=file,
                classification=classification,
                status=status,
                size_bytes=len(text.encode("utf-8")),
                line_count=count_lines(text),
                content_hash=content_hash,
                duplicate_of=duplicate_of
            )

            inventory[rel_path] = asdict(record)

            classification_summary[classification] = (
                classification_summary.get(classification, 0) + 1
            )

            total_files += 1

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    summary = {
        "total_markdown_files": total_files,
        "classifications": classification_summary
    }

    # ---------------------------------------------------------
    # WRITE OUTPUTS
    # ---------------------------------------------------------

    inventory_path = Path(LOG_DIR) / OUTPUT_FILE

    summary_path = Path(LOG_DIR) / SUMMARY_FILE

    with open(inventory_path, "w", encoding="utf-8") as fp:
        json.dump(
            inventory,
            fp,
            indent=2,
            ensure_ascii=False
        )

    with open(summary_path, "w", encoding="utf-8") as fp:
        json.dump(
            summary,
            fp,
            indent=2,
            ensure_ascii=False
        )

    # ---------------------------------------------------------
    # CLI SUMMARY
    # ---------------------------------------------------------

    print()
    print("================================================")
    print("DOCUMENTATION AUDIT COMPLETE")
    print("================================================")
    print(f"Markdown files : {total_files}")

    for key, value in sorted(classification_summary.items()):
        print(f"{key:<15}: {value}")

    print("================================================")
    print()
    print(f"Inventory : {inventory_path}")
    print(f"Summary   : {summary_path}")


if __name__ == "__main__":
    main()
