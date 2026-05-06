#!/usr/bin/env python3
"""
validator_l2.py — Level 2 Argument-Aware Validator for TetraMAX Commands.

Extends L1 (flag existence) with:
  - Flag argument requirements (e.g., -ndetects needs a value)
  - Mutual exclusion groups (e.g., [basic_scan_only | fast_sequential_only])
  - Required positional constraints (e.g., <0 | 1>)
  - Block argument requirements (e.g., -jtag_lbist {seed count cycles})

Usage:
    from validator_l2 import validate_l2, format_l2_result
    result = validate_l2("run_atpg -ndetects")
    print(format_l2_result(result))
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from difflib import get_close_matches

# Import L1 validator components
from validator import get_graph, parse_command_line, suggest_flag

GRAPH_PATH = Path("tmax_graph.json")


# ─────────────────────────────────────────────────────────────────────────────
# SYNTAX TOKENIZER
# ─────────────────────────────────────────────────────────────────────────────

class SyntaxToken:
    FLAG = "FLAG"
    WORD = "WORD"
    LBRACKET = "LBRACKET"    # [
    RBRACKET = "RBRACKET"    # ]
    LBRACE = "LBRACE"        # {
    RBRACE = "RBRACE"        # }
    LANGLE = "LANGLE"        # <
    RANGLE = "RANGLE"        # >
    PIPE = "PIPE"            # |
    EOF = "EOF"


def tokenize_syntax(syntax: str) -> list[tuple[str, str]]:
    """Tokenize a canonical syntax string into (type, value) pairs."""
    tokens = []
    i = 0
    n = len(syntax)

    while i < n:
        while i < n and syntax[i] in " \t\n\r":
            i += 1
        if i >= n:
            break

        ch = syntax[i]

        if ch == '[':
            tokens.append((SyntaxToken.LBRACKET, '['))
            i += 1
        elif ch == ']':
            tokens.append((SyntaxToken.RBRACKET, ']'))
            i += 1
        elif ch == '{':
            tokens.append((SyntaxToken.LBRACE, '{'))
            i += 1
        elif ch == '}':
            tokens.append((SyntaxToken.RBRACE, '}'))
            i += 1
        elif ch == '<':
            tokens.append((SyntaxToken.LANGLE, '<'))
            i += 1
        elif ch == '>':
            tokens.append((SyntaxToken.RANGLE, '>'))
            i += 1
        elif ch == '|':
            tokens.append((SyntaxToken.PIPE, '|'))
            i += 1
        elif ch == '-':
            j = i + 1
            while j < n and syntax[j] not in " \t\n\r[]{}<>|":
                j += 1
            tokens.append((SyntaxToken.FLAG, syntax[i:j]))
            i = j
        else:
            j = i
            while j < n and syntax[j] not in " \t\n\r[]{}<>|":
                j += 1
            tokens.append((SyntaxToken.WORD, syntax[i:j]))
            i = j

    tokens.append((SyntaxToken.EOF, ''))
    return tokens


# ─────────────────────────────────────────────────────────────────────────────
# AST NODES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FlagNode:
    name: str
    args: list = field(default_factory=list)

@dataclass
class WordNode:
    text: str

@dataclass
class OptionalNode:
    elements: list

@dataclass
class RequiredGroupNode:
    elements: list

@dataclass
class RequiredChoiceNode:
    choices: list  # list of list of elements

@dataclass
class CommandNode:
    name: str
    elements: list


# ─────────────────────────────────────────────────────────────────────────────
# SYNTAX PARSER
# ─────────────────────────────────────────────────────────────────────────────

class SyntaxParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def consume(self):
        tok = self.peek()
        self.pos += 1
        return tok

    def expect(self, token_type):
        tok_type, tok_val = self.consume()
        if tok_type != token_type:
            raise ValueError(f"Expected {token_type}, got {tok_type} ({tok_val})")
        return tok_val

    def parse(self):
        tok_type, tok_val = self.consume()
        if tok_type != SyntaxToken.WORD:
            raise ValueError(f"Expected command name, got {tok_type}")
        elements = []
        while self.peek()[0] != SyntaxToken.EOF:
            elements.append(self.parse_element())
        return CommandNode(tok_val, elements)

    def parse_element(self):
        tok_type, tok_val = self.peek()
        if tok_type == SyntaxToken.LBRACKET:
            return self.parse_optional()
        elif tok_type == SyntaxToken.LBRACE:
            return self.parse_required_group()
        elif tok_type == SyntaxToken.LANGLE:
            return self.parse_required_choice()
        elif tok_type == SyntaxToken.FLAG:
            return self.parse_flag()
        elif tok_type == SyntaxToken.WORD:
            self.consume()
            return WordNode(tok_val)
        else:
            self.consume()
            return WordNode(tok_val)

    def parse_optional(self):
        self.expect(SyntaxToken.LBRACKET)
        elements = self.parse_content_until(SyntaxToken.RBRACKET)
        self.expect(SyntaxToken.RBRACKET)
        return OptionalNode(elements)

    def parse_required_group(self):
        self.expect(SyntaxToken.LBRACE)
        elements = self.parse_content_until(SyntaxToken.RBRACE)
        self.expect(SyntaxToken.RBRACE)
        return RequiredGroupNode(elements)

    def parse_required_choice(self):
        self.expect(SyntaxToken.LANGLE)
        choices = self.parse_choices_until(SyntaxToken.RANGLE)
        self.expect(SyntaxToken.RANGLE)
        return RequiredChoiceNode(choices)

    def parse_content_until(self, end_token):
        elements = []
        while self.peek()[0] != end_token and self.peek()[0] != SyntaxToken.EOF:
            elements.append(self.parse_element())
        return elements

    def parse_choices_until(self, end_token):
        choices = []
        while True:
            choice_elements = []
            while self.peek()[0] not in (end_token, SyntaxToken.PIPE, SyntaxToken.EOF):
                choice_elements.append(self.parse_element())
            choices.append(choice_elements)
            if self.peek()[0] == SyntaxToken.PIPE:
                self.consume()
            else:
                break
        return choices

    def parse_flag(self):
        tok_type, flag_name = self.consume()
        args = []
        while self._is_flag_arg():
            args.append(self.parse_element())
        return FlagNode(flag_name, args)

    def _is_flag_arg(self):
        tok_type = self.peek()[0]
        return tok_type in (SyntaxToken.WORD, SyntaxToken.LBRACE, SyntaxToken.LANGLE)


# ─────────────────────────────────────────────────────────────────────────────
# RULE EXTRACTOR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ValidationRules:
    command: str
    flag_args: dict = field(default_factory=dict)
    mutual_exclusion: list = field(default_factory=list)
    required_positionals: list = field(default_factory=list)


def _flatten_choice_elements(elements):
    """Flatten a list of AST nodes into a string."""
    parts = []
    for n in elements:
        if isinstance(n, WordNode):
            parts.append(n.text)
        elif isinstance(n, FlagNode):
            parts.append(n.name)
    return " ".join(parts)


def extract_rules(ast: CommandNode) -> ValidationRules:
    rules = ValidationRules(command=ast.name)

    def _walk(elem, is_top_level=False):
        if isinstance(elem, FlagNode):
            if not elem.args:
                rules.flag_args[elem.name] = {"type": "boolean"}
            elif len(elem.args) == 1 and isinstance(elem.args[0], RequiredGroupNode):
                rules.flag_args[elem.name] = {"type": "block"}
            elif len(elem.args) == 1 and isinstance(elem.args[0], RequiredChoiceNode):
                choices = []
                for cg in elem.args[0].choices:
                    text = _flatten_choice_elements(cg)
                    if text:
                        choices.append(text)
                rules.flag_args[elem.name] = {"type": "choice", "choices": choices}
            else:
                rules.flag_args[elem.name] = {"type": "value", "count": len(elem.args)}

        elif isinstance(elem, (OptionalNode, RequiredGroupNode)):
            _detect_pipe_choices(elem.elements, rules)
            for child in elem.elements:
                _walk(child, is_top_level=False)

        elif isinstance(elem, RequiredChoiceNode) and is_top_level:
            choices = []
            for cg in elem.choices:
                text = _flatten_choice_elements(cg)
                if text:
                    choices.append(text)
            if choices:
                rules.required_positionals.append({
                    "position": len(rules.required_positionals),
                    "choices": choices
                })
        elif isinstance(elem, RequiredChoiceNode):
            choices = []
            for cg in elem.choices:
                text = _flatten_choice_elements(cg)
                if text:
                    choices.append(text)
            if len(choices) > 1:
                rules.mutual_exclusion.append(choices)

    def _detect_pipe_choices(elements, rules):
        """Detect word | word | word pattern in a flat element list."""
        texts = []
        for e in elements:
            if isinstance(e, WordNode):
                texts.append(e.text)
            elif isinstance(e, FlagNode):
                texts.append(e.name)
            else:
                texts.append(None)

        groups = []
        current = []
        for t in texts:
            if t == "|":
                if current:
                    groups.append(current)
                    current = []
            elif t is not None:
                current.append(t)
            else:
                if current:
                    groups.append(current)
                    current = []
                groups = []
                break

        if current:
            groups.append(current)

        if len(groups) > 1:
            choices = [" ".join(g) for g in groups]
            rules.mutual_exclusion.append(choices)

    for elem in ast.elements:
        _walk(elem, is_top_level=True)

    return rules


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND TOKENIZER (for user input)
# ─────────────────────────────────────────────────────────────────────────────

def tokenize_command(cmd_line: str) -> list[str]:
    """Brace-aware tokenizer for user command lines."""
    tokens = []
    i = 0
    n = len(cmd_line)

    while i < n:
        while i < n and cmd_line[i] in " \t":
            i += 1
        if i >= n:
            break

        if cmd_line[i] == '"':
            j = i + 1
            while j < n and cmd_line[j] != '"':
                j += 1
            tokens.append(cmd_line[i:j+1])
            i = j + 1
        elif cmd_line[i] == '{':
            depth = 1
            j = i + 1
            while j < n and depth > 0:
                if cmd_line[j] == '{':
                    depth += 1
                elif cmd_line[j] == '}':
                    depth -= 1
                j += 1
            tokens.append(cmd_line[i:j])
            i = j
        else:
            j = i
            while j < n and cmd_line[j] not in " \t":
                j += 1
            tokens.append(cmd_line[i:j])
            i = j

    return tokens


def parse_command_structured(cmd_line: str) -> list[tuple]:
    """
    Parse command into structured tokens:
        [("cmd", name), ("flag", name), ("flag_arg", flag, [args]), ("positional", value)]
    """
    tokens = tokenize_command(cmd_line)
    if not tokens:
        return []

    result = [("cmd", tokens[0])]
    i = 1

    while i < len(tokens):
        tok = tokens[i]

        if tok.startswith("-"):
            if "=" in tok:
                # Handle -flag=value format
                parts = tok.split("=", 1)
                flag = parts[0]
                args = [parts[1]] if len(parts) > 1 and parts[1] else []
                result.append(("flag_arg", flag, args))
                i += 1
            else:
                flag = tok
                args = []
                i += 1
                while i < len(tokens) and not tokens[i].startswith("-"):
                    args.append(tokens[i])
                    i += 1
                if args:
                    result.append(("flag_arg", flag, args))
                else:
                    result.append(("flag", flag))
        else:
            result.append(("positional", tok))
            i += 1

    return result


# ─────────────────────────────────────────────────────────────────────────────
# L2 VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

_syntax_cache: dict[str, ValidationRules] = {}


def get_rules(command: str) -> Optional[ValidationRules]:
    """Get or compute validation rules for a command."""
    if command in _syntax_cache:
        return _syntax_cache[command]

    graph = get_graph()
    if command not in graph:
        return None

    syntax = graph[command].get("syntax", "")
    if not syntax:
        return None

    try:
        tokens = tokenize_syntax(syntax)
        parser = SyntaxParser(tokens)
        ast = parser.parse()
        rules = extract_rules(ast)
        _syntax_cache[command] = rules
        return rules
    except Exception as e:
        _syntax_cache[command] = ValidationRules(command=command)
        return _syntax_cache[command]


def validate_l2(cmd_line: str) -> dict:
    """
    Level 2 validation: argument-aware command validation.

    Returns dict with:
        - valid: bool
        - command: str
        - l1_result: dict
        - l2_errors: list[str]
        - l2_warnings: list[str]
    """
    from validator import validate_command
    l1_result = validate_command(cmd_line)

    result = {
        "valid": l1_result["valid"],
        "command": l1_result["command"],
        "l1_result": l1_result,
        "l2_errors": [],
        "l2_warnings": [],
    }

    if not l1_result["command_exists"]:
        result["valid"] = False
        return result

    cmd = l1_result["command"]
    rules = get_rules(cmd)
    if rules is None:
        return result
    
    # ── GAP 11: Reject '=' in flag tokens ──
    tokens = cmd_line.split()
    for tok in tokens:
        if "=" in tok and tok.startswith("-"):
            result["l2_errors"].append(
                f"Invalid syntax '{tok}'. Use space-separated arguments like '-ndetects 10'"
            )
            result["valid"] = False
            return result

    structured = parse_command_structured(cmd_line)

    user_flags = set()
    user_flag_args = {}
    user_positionals = []

    for item in structured:
        if item[0] == "flag":
            user_flags.add(item[1])
            user_flag_args[item[1]] = []
        elif item[0] == "flag_arg":
            user_flags.add(item[1])
            user_flag_args[item[1]] = item[2]
        elif item[0] == "positional":
            user_positionals.append(item[1])
    # ── Check: Duplicate flags ──
    seen_flags = set()
    duplicates = set()

    for item in structured:
        if item[0] in ("flag", "flag_arg"):
            flag = item[1]
            if flag in seen_flags:
                duplicates.add(flag)
            seen_flags.add(flag)

    if duplicates:
        result["l2_warnings"].append(
            f"Duplicate flags used: {', '.join(sorted(duplicates))}"
        )

    # ── Check 1: Flag argument requirements ──
    for flag in user_flags:
        if flag not in rules.flag_args:
            continue

        rule = rules.flag_args[flag]
        arg_type = rule.get("type", "boolean")

        if arg_type == "boolean":
            if flag in user_flag_args and user_flag_args[flag]:
                result["l2_errors"].append(
                    f"Flag '{flag}' does not accept arguments, but got: {user_flag_args[flag]}"
                )
                result["valid"] = False

        elif arg_type == "value":
            if flag not in user_flag_args or not user_flag_args[flag]:
                result["l2_errors"].append(f"Flag '{flag}' requires an argument")
                result["valid"] = False
            else:
                expected = rule.get("count", 1)
                actual = len(user_flag_args[flag])
                if actual != expected:
                    result["l2_errors"].append(
                        f"Flag '{flag}' expects {expected} argument(s), got {actual}"
                    )
                    result["valid"] = False

        elif arg_type == "block":
            if flag not in user_flag_args or not user_flag_args[flag]:
                result["l2_errors"].append(f"Flag '{flag}' requires a block argument {{...}}")
                result["valid"] = False
            else:
                # Basic block validation: check non-empty and token count
                block = user_flag_args[flag][0] if user_flag_args[flag] else ""
                block_content = block.strip("{}")
                if not block_content:
                    result["l2_errors"].append(f"Flag '{flag}' block cannot be empty")
                    result["valid"] = False

        elif arg_type == "choice":
            if flag not in user_flag_args or not user_flag_args[flag]:
                result["l2_errors"].append(f"Flag '{flag}' requires an argument")
                result["valid"] = False
            else:
                choices = rule.get("choices", [])
                if choices:
                    arg_val = user_flag_args[flag][0] if user_flag_args[flag] else ""
                    arg_norm = arg_val.strip("{}")
                    choice_norms = [c.strip("{}") for c in choices]
                    if arg_norm not in choice_norms:
                        result["l2_errors"].append(
                            f"Flag '{flag}' argument must be one of: {', '.join(choices)}, got '{arg_val}'"
                        )
                        result["valid"] = False

    # ── Check 2: Mutual exclusion ──
    for group in rules.mutual_exclusion:
        # Check flags
        found_flags = [f for f in group if f in user_flags]
        # Check positionals
        found_pos = [p for p in group if p in user_positionals]
        found = found_flags + found_pos
        if len(found) > 1:
            result["l2_errors"].append(
                f"Mutually exclusive options used together: {', '.join(found)}"
            )
            result["valid"] = False

    # ── Check 3: Required positionals ──
    for req in rules.required_positionals:
        pos = req["position"]
        choices = req.get("choices", [])

        if pos >= len(user_positionals):
            result["l2_errors"].append(
                f"Missing required positional argument at position {pos} (expected one of: {', '.join(choices)})"
            )
            result["valid"] = False
        elif choices and pos < len(user_positionals):
            val = user_positionals[pos]
            if val not in choices:
                result["l2_errors"].append(
                    f"Positional argument at position {pos} must be one of: {', '.join(choices)}, got '{val}'"
                )
                result["valid"] = False

    # ── Check 4: Unexpected positionals ──
    # If command has no required positionals, but user provided positionals
    # that don't match any mutual exclusion group, they're unexpected
    if not rules.required_positionals and user_positionals:
        # Check if positionals are part of mutual exclusion (mode keywords)
        known_mode_keywords = set()
        for group in rules.mutual_exclusion:
            known_mode_keywords.update(group)

        for pos_val in user_positionals:
            if pos_val not in known_mode_keywords:
                result["l2_errors"].append(
                    f"Unexpected positional argument: '{pos_val}'"
                )
                result["valid"] = False

    return result


def format_l2_result(result: dict) -> str:
    """Pretty-print L2 validation result."""
    lines = []
    cmd = result["command"]

    if result["valid"]:
        lines.append(f"✅  {cmd}  — VALID (L1 + L2)")
    else:
        if result["l2_errors"]:
            lines.append(f"⚠️  {cmd}  — INVALID (L2 argument errors)")
        else:
            lines.append(f"⚠️  {cmd}  — INVALID (L1)")

    for err in result["l2_errors"]:
        lines.append(f"   ❌ {err}")

    for w in result["l2_warnings"]:
        lines.append(f"   ⚠️  {w}")

    l1 = result["l1_result"]
    for err in l1.get("errors", []):
        lines.append(f"   ❌ [L1] {err}")

    for bad, good in l1.get("suggestions", {}).items():
        if bad != "__command__":
            lines.append(f"   💡 '{bad}' → try '{good}'")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        ("run_atpg -auto_compression", "valid: boolean flag"),
        ("run_atpg -ndetects", "missing value for -ndetects"),
        ("run_atpg -ndetects=10", "valid: flag with value"),
        ("run_atpg -ndetects=10 extra", "too many args for -ndetects"),
        ("run_atpg basic_scan_only fast_sequential_only", "mutual exclusion"),
        ("run_atpg basic_scan_only", "valid: single mode"),
        ("add_clocks 0 {CLK RST} -shift", "valid with braces"),
        ("add_clocks {CLK RST}", "missing required <0|1>"),
        ("add_clocks 2 CLK", "invalid positional choice"),
        ("run_atpg -jtag_lbist", "missing required block"),
        ("run_atpg -jtag_lbist {1 100 1}", "valid: flag with block"),
        ("run_atpg -jtag_lbist {}", "empty block"),
        ("run_drc -fake", "unknown flag (L1)"),
    ]

    print("=" * 70)
    print("TetraMAX Command Validator — LEVEL 2 (Argument-Aware)")
    print("=" * 70)

    for cmd, note in test_cases:
        print(f"\n▶ {note}")
        print(f"  Input: {cmd}")
        result = validate_l2(cmd)
        for line in format_l2_result(result).split("\n"):
            print(f"  {line}")
