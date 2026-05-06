#!/usr/bin/env python3
"""
validator_l3.py — Level 3 Semantic Validator (CORRECTED)

L3 = Command correctness only:
  ✔ type validation
  ✔ enum validation
  ✔ numeric constraints
  ✔ block validation
  ✔ semantic warnings (cross-flag)

NO:
  ❌ dependency enforcement
  ❌ session tracking
  ❌ flow validation
"""

import os
from typing import Optional
from validator_l2 import (
    get_rules,
    parse_command_structured,
    validate_l2
)

# ─────────────────────────────────────────────────────────────
# TYPE SYSTEM
# ─────────────────────────────────────────────────────────────

class TypeChecker:

    @staticmethod
    def is_int(val: str):
        try:
            int(val)
            return True
        except:
            return False

    @staticmethod
    def is_float(val: str):
        try:
            float(val)
            return True
        except:
            return False

    @staticmethod
    def is_bool(val: str):
        return val.lower() in ("true", "false", "1", "0", "yes", "no")

    @staticmethod
    def is_file(val: str):
        return "." in os.path.basename(val) or "/" in val or "\\" in val

    @staticmethod
    def check(val: str, datatype: str):
        checkers = {
            "int": TypeChecker.is_int,
            "float": TypeChecker.is_float,
            "bool": TypeChecker.is_bool,
            "file": TypeChecker.is_file,
            "string": lambda x: True,
        }

        checker = checkers.get(datatype)
        if checker is None:
            return True, ""

        if checker(val):
            return True, ""
        return False, f"expected {datatype}, got '{val}'"


# ─────────────────────────────────────────────────────────────
# TYPE RULES (MANUAL OVERRIDES)
# ─────────────────────────────────────────────────────────────

TYPE_OVERRIDES = {
    "run_atpg": {
        "-ndetects": {"datatype": "int", "min": 1},
        "-jtag_lbist": {"block_size": 3, "block_types": ["int", "int", "int"]},
    },
    "add_clocks": {
        "-timing": {"block_size": 4, "block_types": ["float", "float", "float", "float"]},
        "-unit": {"datatype": "enum", "choices": ["ps", "ns"]},
    },
    "set_atpg": {
        "-patterns": {"datatype": "int", "min": 1},
        "-merge": {"datatype": "enum", "choices": ["low", "medium", "high"]},
        "-abort_limit": {"datatype": "int", "min": 1},
    }
}


def get_enhanced_rules(command):
    base = get_rules(command)
    if not base:
        return None

    rules = dict(base.flag_args)
    overrides = TYPE_OVERRIDES.get(command, {})

    for k, v in overrides.items():
        if k in rules:
            rules[k].update(v)

    return rules


# ─────────────────────────────────────────────────────────────
# CORE VALIDATOR
# ─────────────────────────────────────────────────────────────

class L3Validator:

    def validate(self, cmd_line: str):

        l2 = validate_l2(cmd_line)

        result = {
            "valid": l2["valid"],
            "command": l2["command"],
            "l2_result": l2,
            "l3_errors": [],
            "l3_warnings": [],
        }

        # Stop early if command invalid
        if not l2.get("l1_result", {}).get("command_exists", False):
            result["valid"] = False
            return result

        cmd = result["command"]

        self._check_types(cmd, cmd_line, result)
        self._check_semantics(cmd, cmd_line, result)

        if result["l3_errors"]:
            result["valid"] = False

        return result


# ─────────────────────────────────────────────────────────────
# TYPE VALIDATION
# ─────────────────────────────────────────────────────────────

    def _check_types(self, cmd, cmd_line, result):

        rules = get_enhanced_rules(cmd)
        if not rules:
            return

        structured = parse_command_structured(cmd_line)

        for item in structured:

            if item[0] != "flag_arg":
                continue

            flag = item[1]
            args = item[2]

            if flag not in rules:
                continue

            rule = rules[flag]

            # ───── SCALAR ─────
            datatype = rule.get("datatype")

            if datatype and args:
                val = args[0].strip("{}")

                # ENUM
                if datatype == "enum":
                    if val not in rule.get("choices", []):
                        result["l3_errors"].append(
                            f"Flag '{flag}' must be one of {rule['choices']}, got '{val}'"
                        )
                    continue

                ok, msg = TypeChecker.check(val, datatype)
                if not ok:
                    result["l3_errors"].append(f"Flag '{flag}' {msg}")
                    continue

                # RANGE
                if datatype in ("int", "float"):
                    num = int(val) if datatype == "int" else float(val)

                    if "min" in rule and rule["min"] is not None and num < rule["min"]:
                        result["l3_errors"].append(
                            f"Flag '{flag}' value {num} < min {rule['min']}"
                        )

                    if "max" in rule and rule["max"] is not None and num > rule["max"]:
                        result["l3_errors"].append(
                            f"Flag '{flag}' value {num} > max {rule['max']}"
                        )

            # ───── BLOCK ─────
            if rule.get("block_size") and args:
                block = args[0]

                if not (block.startswith("{") and block.endswith("}")):
                    result["l3_errors"].append(
                        f"Flag '{flag}' requires {{...}} block"
                    )
                    continue

                tokens = block[1:-1].split()

                if len(tokens) != rule["block_size"]:
                    result["l3_errors"].append(
                        f"Flag '{flag}' expects {rule['block_size']} values, got {len(tokens)}"
                    )
                    continue

                for i, (tok, typ) in enumerate(zip(tokens, rule.get("block_types", []))):
                    ok, msg = TypeChecker.check(tok, typ)
                    if not ok:
                        result["l3_errors"].append(
                            f"Flag '{flag}' block[{i}] {msg}"
                        )


# ─────────────────────────────────────────────────────────────
# SEMANTIC RULES
# ─────────────────────────────────────────────────────────────

    def _check_semantics(self, cmd, cmd_line, result):

        structured = parse_command_structured(cmd_line)
        flags = {x[1] for x in structured if x[0] in ("flag", "flag_arg")}

        # Example rules
        if cmd == "run_atpg":
            if "-auto_compression" in flags and "-optimize_patterns" in flags:
                result["l3_warnings"].append(
                    "Using -auto_compression with -optimize_patterns may reduce effectiveness"
                )

        if cmd == "set_atpg":
            merge = None
            abort = None

            for item in structured:
                if item[0] == "flag_arg":
                    if item[1] == "-merge":
                        merge = item[2][0]
                    if item[1] == "-abort_limit":
                        abort = item[2][0]

            if merge == "high" and abort and abort.isdigit() and int(abort) < 10:
                result["l3_warnings"].append(
                    "High merge with low abort_limit may increase runtime"
                )


from preprocessor import normalize_input
from validator_l2 import get_rules, validate_l2

def validate_l3(cmd_line: str):

    # First pass → identify command
    l2 = validate_l2(cmd_line)
    cmd = l2.get("command")

    # Get known flags for normalization
    known_flags = []
    rules = get_rules(cmd)
    if rules:
        known_flags = list(rules.flag_args.keys())

    # 🔥 Normalize input (GAP 1–5)
    clean_cmd = normalize_input(cmd_line, known_flags)

    # Run full validator on cleaned command
    return L3Validator().validate(clean_cmd)


def format_l3_result(result):

    cmd = result["command"]
    lines = []

    if result["valid"]:
        lines.append(f"✅ {cmd} — VALID")
    else:
        lines.append(f"⚠️ {cmd} — INVALID")

    # L3 errors
    for e in result["l3_errors"]:
        lines.append(f"  ❌ {e}")

    # L3 warnings
    for w in result["l3_warnings"]:
        lines.append(f"  ⚠️ {w}")

    # L2 errors
    for e in result["l2_result"].get("l2_errors", []):
        lines.append(f"  ❌ [L2] {e}")

    # 🔥 ADD THIS (missing piece)
    for w in result["l2_result"].get("l2_warnings", []):
        lines.append(f"  ⚠️ [L2] {w}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    tests = [
        "run_atpg -ndetects 5",
        "run_atpg -ndetects abc",
        "run_atpg -jtag_lbist {1 100 1}",
        "run_atpg -jtag_lbist {1 100}",
        "add_clocks 0 CLK -unit ps",
        "add_clocks 0 CLK -unit mm",
        "run_atpg -auto_compression -optimize_patterns",
        "run_atpg -ndetects=10",
        "run_atpg basic_scan_only",
        "run_atpg basic_scan_only fast_sequential_only",
        "run_atpg -random -random"
    ]

    print("\n=== L3 VALIDATION ===\n")

    for t in tests:
        print("Input:", t)
        print(format_l3_result(validate_l3(t)))
        print()