#!/usr/bin/env python3
"""
parser_router.py — Runtime Integration

Reads classified corpus inventory from document_classifier.py
and routes each document to the correct parser.

CURRENT BEHAVIOR:
- COMMAND_PAGE → CommandParser (existing dita_parser.py logic)
- All other types → NullParser (telemetry only, no IR generated)

FUTURE:
- GUIDE_PAGE → GuideParser
- MESSAGE_REF → MessageParser  
- DRC_RULE → DRCParser
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any

from enum import Enum
from dataclasses import dataclass


# =====================================================================
# SEMANTIC TYPES
# =====================================================================

class SemanticType(Enum):
    COMMAND_PAGE = "COMMAND_PAGE"
    GUIDE_PAGE = "GUIDE_PAGE"
    MESSAGE_REF = "MESSAGE_REF"
    DRC_RULE = "DRC_RULE"
    CATEGORY_INDEX = "CATEGORY_INDEX"
    POPUP_HELPER = "POPUP_HELPER"
    SYSTEM_PAGE = "SYSTEM_PAGE"
    UNKNOWN = "UNKNOWN"


# =====================================================================
# DOCUMENT MODEL
# =====================================================================

@dataclass
class DocumentRecord:
    path: str
    semantic_type: SemanticType


# =====================================================================
# PARSER INTERFACES
# =====================================================================

class BaseParser:
    def parse(self, document: DocumentRecord) -> Dict[str, Any]:
        raise NotImplementedError


class CommandParser(BaseParser):
    """Routes to existing dita_parser.py logic."""
    
    def parse(self, document: DocumentRecord) -> Dict[str, Any]:
        # In production: import and call DITAParser.parse_file()
        # For now: telemetry stub
        return {
            "type": "COMMAND_PAGE",
            "path": document.path,
            "status": "routed_to_dita_parser",
            "ir_generated": True,
        }


class GuideParser(BaseParser):
    """Stub — telemetry only."""
    
    def parse(self, document: DocumentRecord) -> Dict[str, Any]:
        return {
            "type": "GUIDE_PAGE",
            "path": document.path,
            "status": "telemetry_only",
            "ir_generated": False,
            "reason": "guide_parser_not_yet_implemented",
        }


class MessageParser(BaseParser):
    """Stub — telemetry only."""
    
    def parse(self, document: DocumentRecord) -> Dict[str, Any]:
        return {
            "type": "MESSAGE_REF",
            "path": document.path,
            "status": "telemetry_only",
            "ir_generated": False,
            "reason": "message_parser_not_yet_implemented",
        }


class DRCParser(BaseParser):
    """Stub — telemetry only."""
    
    def parse(self, document: DocumentRecord) -> Dict[str, Any]:
        return {
            "type": "DRC_RULE",
            "path": document.path,
            "status": "telemetry_only",
            "ir_generated": False,
            "reason": "drc_parser_not_yet_implemented",
        }


class NullParser(BaseParser):
    """Skip with telemetry."""
    
    def parse(self, document: DocumentRecord) -> Dict[str, Any]:
        return {
            "type": document.semantic_type.value,
            "path": document.path,
            "status": "skipped",
            "ir_generated": False,
            "reason": "unhandled_semantic_type",
        }


# =====================================================================
# ROUTER
# =====================================================================

class ParserRouter:
    def route(self, document: DocumentRecord) -> BaseParser:
        if document.semantic_type == SemanticType.COMMAND_PAGE:
            return CommandParser()
        elif document.semantic_type == SemanticType.GUIDE_PAGE:
            return GuideParser()
        elif document.semantic_type == SemanticType.MESSAGE_REF:
            return MessageParser()
        elif document.semantic_type == SemanticType.DRC_RULE:
            return DRCParser()
        return NullParser()


# =====================================================================
# INVENTORY LOADER
# =====================================================================

def load_inventory(path: Path) -> List[DocumentRecord]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    records = []
    for item in data:
        # Map string semantic_type to enum
        type_str = item.get("semantic_type", "UNKNOWN")
        try:
            sem_type = SemanticType(type_str)
        except ValueError:
            sem_type = SemanticType.UNKNOWN
        
        records.append(DocumentRecord(
            path=item.get("path", ""),
            semantic_type=sem_type,
        ))
    
    return records


# =====================================================================
# MAIN
# =====================================================================

def main():
    INVENTORY_FILE = Path("LOG_CLASSIFICATION/corpus_inventory.json")
    
    if not INVENTORY_FILE.exists():
        print(f"[FATAL] Inventory not found: {INVENTORY_FILE}")
        print("Run: python3 document_classifier.py")
        raise SystemExit(1)
    
    print("[ROUTER] Loading classified corpus inventory...")
    records = load_inventory(INVENTORY_FILE)
    print(f"Loaded: {len(records)} documents")
    
    router = ParserRouter()
    
    results = []
    for doc in records:
        parser = router.route(doc)
        result = parser.parse(doc)
        results.append(result)
    
    # Summary
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    ir_generated = 0
    telemetry_only = 0
    
    for r in results:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        if r.get("ir_generated"):
            ir_generated += 1
        else:
            telemetry_only += 1
    
    print()
    print("=" * 50)
    print("ROUTING COMPLETE")
    print(f"Total documents : {len(results)}")
    print(f"IR generated    : {ir_generated}")
    print(f"Telemetry only  : {telemetry_only}")
    print()
    print("By type:")
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print()
    print("By status:")
    for s, c in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")
    print("=" * 50)


if __name__ == "__main__":
    main()
