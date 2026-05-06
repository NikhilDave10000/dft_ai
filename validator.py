#!/usr/bin/env python3
"""
validator.py — TetraMAX command validator (production-ready).

Validates CLI commands against the structured graph from build_graph.py.

Fixes applied:
  1. Flag normalization: -ndetects=10 → -ndetects
  2. TCL brace-aware parsing: {-scan {chain1:0 chain1:1}}
  3. Self-dependency filtered from graph data
  4. No-flag commands reject flags (strict)
  5. Duplicate flag detection

Usage:
    from validator import validate_command, format_validation

    result = validate_command("run_atpg -auto_compression -fake_flag")
    print(format_validation(result))
"""

import json
import re
from difflib import get_close_matches
from pathlib import Path

GRAPH_PATH = Path("tmax_graph.json")

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        with open(GRAPH_PATH, encoding="utf-8") as f:
            full = json.load(f)
            _graph = full["commands"]
            # Fix 2: Remove self-references from depends_on
            for cmd, data in _graph.items():
                deps = data.get("depends_on", [])
                if cmd in deps:
                    deps.remove(cmd)
                    data["depends_on"] = deps
    return _graph


def parse_command_line(cmd_line: str) -> tuple[str | None, list[str], list[str]]:
    """
    Parse a TetraMAX/TCL command line with brace-aware tokenization.

    Handles:
      - Flags: -flag, -flag=value
      - TCL braces: {a b c}, nested braces
      - Quoted strings: "hello world"

    Returns:
        (command_name, flags, positional_args)
    """
    line = cmd_line.strip()
    if not line:
        return None, [], []

    # Simple tokenizer that respects braces and quotes
    tokens = []
    i = 0
    while i < len(line):
        # Skip whitespace
        while i < len(line) and line[i] in " \t":
            i += 1
        if i >= len(line):
            break

        if line[i] == '"':
            # Quoted string
            j = i + 1
            while j < len(line) and line[j] != '"':
                j += 1
            tokens.append(line[i+1:j])
            i = j + 1
        elif line[i] == '{':
            # Braced block — find matching }
            depth = 1
            j = i + 1
            while j < len(line) and depth > 0:
                if line[j] == '{':
                    depth += 1
                elif line[j] == '}':
                    depth -= 1
                j += 1
            tokens.append(line[i:j])
            i = j
        else:
            # Regular token
            j = i
            while j < len(line) and line[j] not in " \t":
                j += 1
            tokens.append(line[i:j])
            i = j

    if not tokens:
        return None, [], []

    cmd = tokens[0]
    flags = []
    positionals = []

    for tok in tokens[1:]:
        # Fix 1: Normalize -flag=value → -flag
        if tok.startswith("-"):
            flag = tok.split("=")[0]
            flags.append(flag)
        else:
            positionals.append(tok)

    return cmd, flags, positionals


def suggest_flag(flag: str, valid_flags: list[str]) -> str | None:
    """Suggest closest valid flag using difflib."""
    matches = get_close_matches(flag, valid_flags, n=1, cutoff=0.6)
    return matches[0] if matches else None


def validate_command(cmd_line: str) -> dict:
    """
    Validate a single TetraMAX command line against the graph.

    Returns dict with:
        - valid: bool
        - command: str | None
        - command_exists: bool
        - unknown_options: list[str]
        - valid_options: list[str]
        - suggestions: dict[str, str]
        - warnings: list[str]
        - errors: list[str]
        - syntax: str
        - category: str
    """
    graph = get_graph()
    cmd, flags, positionals = parse_command_line(cmd_line)

    result = {
        "valid": True,
        "command": cmd,
        "command_exists": False,
        "unknown_options": [],
        "valid_options": [],
        "suggestions": {},
        "warnings": [],
        "errors": [],
        "syntax": "",
        "category": "",
    }

    if cmd is None:
        result["valid"] = False
        result["errors"].append("Empty command line")
        return result

    if cmd not in graph:
        result["valid"] = False
        result["errors"].append(f"Unknown command: '{cmd}'")
        cmd_suggestions = get_close_matches(cmd, graph.keys(), n=3, cutoff=0.6)
        if cmd_suggestions:
            result["suggestions"]["__command__"] = cmd_suggestions[0]
        return result

    result["command_exists"] = True
    cmd_data = graph[cmd]
    result["syntax"] = cmd_data.get("syntax", "")
    result["category"] = cmd_data.get("category", "")
    result["valid_options"] = list(cmd_data.get("options", {}).keys())

    valid_flags = set(result["valid_options"])

    # Fix 4: Duplicate flag detection
    if len(flags) != len(set(flags)):
        seen = set()
        dups = []
        for f in flags:
            if f in seen:
                dups.append(f)
            seen.add(f)
        result["warnings"].append(f"Duplicate flags: {', '.join(set(dups))}")

    # Fix 3: Strict no-flag command rejection
    if not valid_flags and flags:
        result["valid"] = False
        result["errors"].append(f"Command '{cmd}' does not accept any flags")

    # Validate each flag
    for flag in flags:
        if flag not in valid_flags:
            result["unknown_options"].append(flag)
            result["valid"] = False
            suggestion = suggest_flag(flag, result["valid_options"])
            if suggestion:
                result["suggestions"][flag] = suggestion

    return result


def validate_script(script_lines: list[str]) -> list[dict]:
    """Validate multiple command lines (e.g., a TCL script)."""
    results = []
    for line in script_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        results.append(validate_command(line))
    return results


def format_validation(result: dict) -> str:
    """Pretty-print validation result for CLI display."""
    lines = []
    cmd = result["command"]

    if result["valid"] and result["command_exists"]:
        lines.append(f"✅  {cmd}  — VALID")
    elif not result["command_exists"]:
        lines.append(f"❌  {cmd}  — UNKNOWN COMMAND")
        if "__command__" in result["suggestions"]:
            lines.append(f"   💡 Did you mean: {result['suggestions']['__command__']}?")
    else:
        lines.append(f"⚠️  {cmd}  — INVALID")

    for err in result["errors"]:
        lines.append(f"   ❌ {err}")

    if result["unknown_options"]:
        lines.append(f"   Unknown options: {', '.join(result['unknown_options'])}")
        for bad, good in result["suggestions"].items():
            if bad != "__command__":
                lines.append(f"   💡 '{bad}' → try '{good}'")

    for w in result["warnings"]:
        lines.append(f"   ⚠️  {w}")

    if result["syntax"]:
        lines.append(f"   Syntax: {result['syntax']}")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd_line = " ".join(sys.argv[1:])
        result = validate_command(cmd_line)
        print(format_validation(result))
    else:
        test_cases = [
            ("run_atpg -auto_compression", "valid flag"),
            ("run_atpg -auto_compression -fake_flag", "unknown flag"),
            ("run_atpg -auto_compress", "typo flag"),
            ("run_atp", "typo command"),
            ("add_clocks 0 {CLK RST} -shift", "valid with braces"),
            ("add_clocks 0 CLK -shft", "typo flag"),
            ("run_drc -fake", "no-flag command gets flag"),
            ("run_atpg -ndetects=10", "flag with value"),
            ("run_atpg -random -random", "duplicate flag"),
            ("add_capture_masks -scan {scan_chain_1:0 scan_chain_1:1}", "brace block"),
            ("fake_command -x", "unknown command"),
        ]

        print("=" * 65)
        print("TetraMAX Command Validator — Production Demo")
        print("=" * 65)
        for cmd, note in test_cases:
            print(f"\n▶ {note}")
            print(f"  Input: {cmd}")
            result = validate_command(cmd)
            for line in format_validation(result).split("\n"):
                print(f"  {line}")
