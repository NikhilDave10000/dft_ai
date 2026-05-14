#!/usr/bin/env python3
"""
message_ir_schema.py

Semantic data model for TestMAX Message Reference documentation.

PURPOSE
-------
Define the canonical IR structure for message pages (tmax_messages/).

This is NOT command IR. Messages have different semantics:
- severity levels (ERROR, WARNING, INFO)
- message text with format specifiers
- cause/solution structure
- no syntax or arguments

SCHEMA
------
{
  "message_id": "TEST-001",
  "severity": "ERROR",
  "message_text": "Cannot open file %s",
  "description": ["This message occurs when..."],
  "cause": ["File does not exist", "Permission denied"],
  "solution": ["Check file path", "Verify permissions"],
  "see_also": ["TEST-002", "run_atpg"],
  "source_file": "msg_test_001.htm"
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


# =====================================================================
# MESSAGE IR MODEL
# =====================================================================

@dataclass
class MessageIR:
    """Canonical semantic IR for a single message reference page."""

    message_id: str
    """Unique message identifier (e.g., TEST-001, ATPG-WARN-123)."""

    severity: str
    """Message severity: ERROR, WARNING, INFO, or DEBUG."""

    message_text: str
    """The actual message text, possibly with format specifiers (%s, %d)."""

    description: List[str] = field(default_factory=list)
    """Explanation of when and why this message occurs."""

    cause: List[str] = field(default_factory=list)
    """Root causes that trigger this message."""

    solution: List[str] = field(default_factory=list)
    """Recommended actions to resolve this message."""

    see_also: List[str] = field(default_factory=list)
    """Related message IDs or commands."""

    source_file: str = ""
    """Original HTML filename."""

    document_type: str = "message_reference"
    """Always "message_reference" for this schema."""

    raw_sections: Dict[str, str] = field(default_factory=dict)
    """Preserved raw HTML section text for audit/debug replay."""

    parser_warnings: List[str] = field(default_factory=list)
    """Parser telemetry: missing fields, malformed HTML, extraction issues."""


# =====================================================================
# VALIDATION RULES (for future message_validator.py)
# =====================================================================

VALID_SEVERITIES = {"ERROR", "WARNING", "INFO", "DEBUG", "FATAL"}

MESSAGE_ID_PATTERN = r"^[A-Za-z0-9_-]+$"  # Relaxed: accepts M1, M100, ATPG-123, WARN_55, DFT001

REQUIRED_FIELDS = ["message_id", "severity", "message_text"]

OPTIONAL_FIELDS = ["description", "cause", "solution", "see_also"]


def validate_message_ir(ir: Dict[str, Any]) -> List[str]:
    """
    Validate a MessageIR dict against schema rules.
    Returns list of violation strings.
    """
    violations = []

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in ir or not ir[field]:
            violations.append(f"Missing required field: {field}")

    # Severity check
    severity = ir.get("severity", "")
    if severity and severity.upper() not in VALID_SEVERITIES:
        violations.append(f"Invalid severity: {severity}. Must be one of: {VALID_SEVERITIES}")

    # Message ID format (relaxed)
    import re
    msg_id = ir.get("message_id", "")
    if msg_id and not re.match(MESSAGE_ID_PATTERN, msg_id):
        violations.append(f"Invalid message_id format: {msg_id}. Expected alphanumeric with hyphens/underscores.")

    # Message text should not be empty
    msg_text = ir.get("message_text", "")
    if msg_text and len(msg_text.strip()) < 5:
        violations.append(f"Message text too short: {len(msg_text)} chars")

    return violations


# =====================================================================
# EXAMPLE
# =====================================================================

EXAMPLE_MESSAGE_IR = {
    "message_id": "TEST-001",
    "severity": "ERROR",
    "message_text": "Cannot open file %s",
    "description": [
        "This message occurs when the specified file cannot be opened.",
        "This typically happens during pattern read/write operations."
    ],
    "cause": [
        "File does not exist at the specified path",
        "Insufficient file permissions",
        "File is locked by another process"
    ],
    "solution": [
        "Verify the file path is correct",
        "Check file permissions (chmod, chown)",
        "Close other applications that may have the file open"
    ],
    "see_also": ["TEST-002", "read_patterns", "write_patterns"],
    "source_file": "msg_test_001.htm",
    "document_type": "message_reference",
    "raw_sections": {
        "severity": "ERROR",
        "message_text": "Cannot open file %s"
    },
    "parser_warnings": []
}


if __name__ == "__main__":
    print("[MESSAGE_IR_SCHEMA] TestMAX Message Reference Schema")
    print("=" * 50)

    # Validate example
    violations = validate_message_ir(EXAMPLE_MESSAGE_IR)

    if violations:
        print(f"Example validation FAILED ({len(violations)} violations):")
        for v in violations:
            print(f"  - {v}")
    else:
        print("Example validation: PASS")

    print()
    print("Schema fields:")
    for field_name, field_type in MessageIR.__dataclass_fields__.items():
        print(f"  {field_name}: {field_type.type}")
