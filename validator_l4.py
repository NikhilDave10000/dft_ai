#!/usr/bin/env python3
"""
validator_l4.py — Level 4: Probabilistic State-Aware Advisor.

Combines:
  - State tracking (what has been configured)
  - Transition probabilities (from real scripts)
  - Semantic insights (from manual text mining)

NOT a validator. An INTERACTIVE ADVISOR.

Usage:
    from validator_l4 import L4Advisor

    advisor = L4Advisor()

    advisor.advise("read_netlist design.v")
    # ✅ read_netlist — VALID

    advisor.advise("run_atpg")
    # ⚠️ run_atpg — VALID but uncommon after read_netlist
    #   Common next: run_build_model, read_netlist
    #   State: no faults defined, no patterns configured
"""

import json
from pathlib import Path
from collections import defaultdict
from validator_l3 import validate_l3, format_l3_result

SEMANTIC_PATH = Path("semantic_graph.json")


class L4Advisor:
    """
    State-aware probabilistic advisor for TetraMAX commands.

    Tracks:
      - Commands executed
      - Configuration state
      - Resource state

    Provides:
      - L1-L3 validation (structural + type)
      - L4 insights (behavioral, based on real usage)
    """

    def __init__(self):
        self.commands_run = []
        self.state = {
            "netlist_loaded": False,
            "model_built": False,
            "drc_passed": False,
            "clocks_defined": False,
            "faults_defined": False,
            "patterns_configured": False,
            "patterns_generated": False,
            "atpg_configured": False,
            "spf_loaded": False,
        }
        self.semantic = self._load_semantic()
        self.transition_prob = self._build_transition_prob()

    def _load_semantic(self) -> dict:
        """Load semantic graph from real scripts."""
        if not SEMANTIC_PATH.exists():
            return {}
        with open(SEMANTIC_PATH, encoding="utf-8") as f:
            return json.load(f)

    def _build_transition_prob(self) -> dict:
        """Convert transition counts to probabilities."""
        transitions = self.semantic.get("transitions", [])
        totals = defaultdict(int)

        for t in transitions:
            totals[t["from"]] += t["count"]

        prob = {}
        for t in transitions:
            a, b, c = t["from"], t["to"], t["count"]
            prob.setdefault(a, {})
            if totals[a] > 0:
                prob[a][b] = c / totals[a]

        return prob

    def advise(self, cmd_line: str) -> dict:
        """
        Full validation + advisory for a command.

        Returns dict with:
            - valid: bool (L1-L3)
            - l3_result: dict
            - l4_warnings: list (behavioral insights)
            - l4_suggestions: list (next command suggestions)
        """
        # Step 1: L3 validation
        l3_result = validate_l3(cmd_line)

        result = {
            "valid": l3_result["valid"],
            "command": l3_result["command"],
            "l3_result": l3_result,
            "l4_warnings": [],
            "l4_suggestions": [],
        }

        cmd = l3_result["command"]

        # Step 2: State-based insights (only if command exists)
        l1_exists = l3_result.get("l2_result", {}).get("l1_result", {}).get("command_exists", False)
        if l1_exists:
            self._check_state(cmd, result)

            # Step 3: Transition probability insights
            self._check_transition(cmd, result)

        # Step 4: Update state ONLY if command is valid
        if l3_result["valid"]:
            self._update_state(cmd, cmd_line)
            self.commands_run.append(cmd)

        return result

    def _check_state(self, cmd: str, result: dict):
        """Check command against current state."""

        if cmd == "run_atpg":
            if not self.state["faults_defined"]:
                result["l4_warnings"].append(
                    "No faults defined — coverage may be limited (use add_faults -all)"
                )
            if not self.state["atpg_configured"]:
                result["l4_warnings"].append(
                    "ATPG using default settings (no set_atpg detected)"
                )
            if not self.state["model_built"]:
                result["l4_warnings"].append(
                    "ATPG model not built — run run_build_model first"
                )

        elif cmd == "report_clocks":
            if not self.state["clocks_defined"] and not self.state["spf_loaded"]:
                result["l4_warnings"].append(
                    "No clocks defined — report may be empty (add_clocks or load SPF)"
                )

        elif cmd == "remove_clocks":
            if not self.state["clocks_defined"]:
                result["l4_warnings"].append(
                    "No clocks currently defined — remove_clocks may have no effect"
                )

        elif cmd == "write_patterns":
            if not self.state["patterns_generated"]:
                result["l4_warnings"].append(
                    "No patterns generated — write may be empty (run run_atpg first)"
                )

        elif cmd == "run_drc":
            if not self.state["netlist_loaded"]:
                result["l4_warnings"].append(
                    "No netlist loaded — run read_netlist first"
                )

        elif cmd == "run_build_model":
            if not self.state["netlist_loaded"]:
                result["l4_warnings"].append(
                    "No netlist loaded — run read_netlist first"
                )

    def _check_transition(self, cmd: str, result: dict):
        """Check transition probability from previous command."""
        if not self.commands_run:
            return

        prev = self.commands_run[-1]
        next_probs = self.transition_prob.get(prev, {})

        if not next_probs:
            return

        if cmd not in next_probs:
            # Uncommon transition — suggest common next commands
            top = sorted(next_probs.items(), key=lambda x: -x[1])[:3]
            suggestions = [c for c, _ in top]
            result["l4_suggestions"].append(
                f"'{cmd}' is uncommon after '{prev}'. "
                f"Common next: {', '.join(suggestions)}"
            )
        else:
            prob = next_probs[cmd]
            if prob < 0.3:
                result["l4_warnings"].append(
                    f"'{cmd}' after '{prev}' is rare in typical flows ({prob:.0%})"
                )

    def _update_state(self, cmd: str, cmd_line: str):
        """Update internal state based on command."""

        if cmd == "read_netlist":
            self.state["netlist_loaded"] = True
            if ".spf" in cmd_line.lower():
                self.state["spf_loaded"] = True

        elif cmd in ("run_build_model", "run_build"):
            self.state["model_built"] = True

        elif cmd == "run_drc":
            self.state["drc_passed"] = True
            if ".spf" in cmd_line.lower():
                self.state["spf_loaded"] = True

        elif cmd == "add_clocks":
            self.state["clocks_defined"] = True

        elif cmd == "add_faults":
            self.state["faults_defined"] = True

        elif cmd == "set_patterns":
            self.state["patterns_configured"] = True

        elif cmd == "set_atpg":
            self.state["atpg_configured"] = True

        elif cmd == "run_atpg":
            self.state["patterns_generated"] = True  # NOT configured — generated

        elif cmd == "remove_clocks":
            self.state["clocks_defined"] = False

        elif cmd == "remove_faults":
            self.state["faults_defined"] = False

    def get_state(self) -> dict:
        """Return current state."""
        return dict(self.state)

    def reset(self):
        """Reset advisor state."""
        self.commands_run = []
        self.state = {
            "netlist_loaded": False,
            "model_built": False,
            "drc_passed": False,
            "clocks_defined": False,
            "faults_defined": False,
            "patterns_configured": False,
            "patterns_generated": False,
            "atpg_configured": False,
            "spf_loaded": False,
        }


def format_l4_result(result: dict) -> str:
    """Pretty-print L4 advisory result."""
    lines = []
    cmd = result["command"]

    if result["valid"]:
        lines.append(f"✅  {cmd}  — VALID")
    else:
        lines.append(f"⚠️  {cmd}  — INVALID")

    # L3 errors
    l3 = result["l3_result"]
    for err in l3.get("l3_errors", []):
        lines.append(f"   ❌ {err}")
    for err in l3.get("l2_result", {}).get("l2_errors", []):
        lines.append(f"   ❌ [L2] {err}")

    # L4 warnings
    for w in result["l4_warnings"]:
        lines.append(f"   ⚠️  {w}")

    # L4 suggestions
    for s in result["l4_suggestions"]:
        lines.append(f"   💡 {s}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CLI DEMO
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 70)
    print("TetraMAX Command Advisor — LEVEL 4 (State + Probabilistic)")
    print("=" * 70)

    advisor = L4Advisor()

    # Simulate a realistic ATPG session
    session = [
        ("read_netlist design.v", "load netlist"),
        ("run_build_model TOP", "build model"),
        ("add_clocks 0 {clk}", "define clocks"),
        ("run_drc", "run DRC"),
        ("add_faults -all", "add all faults"),
        ("run_atpg", "run ATPG (no set_atpg — uses defaults)"),
        ("write_patterns out.stil -format STIL", "write patterns"),
    ]

    for cmd, note in session:
        print(f"\n▶ {note}")
        print(f"  Input: {cmd}")
        result = advisor.advise(cmd)
        for line in format_l4_result(result).split("\n"):
            print(f"  {line}")

    print("\n" + "=" * 70)
    print("State after session:")
    print("=" * 70)
    for key, val in advisor.get_state().items():
        status = "✅" if val else "❌"
        print(f"  {status} {key}")

    # Test uncommon transition
    print("\n" + "=" * 70)
    print("Testing uncommon transition:")
    print("=" * 70)

    advisor2 = L4Advisor()
    advisor2.advise("read_netlist design.v")
    result = advisor2.advise("run_atpg")  # Uncommon after read_netlist
    print(f"\n▶ read_netlist → run_atpg (uncommon)")
    print(f"  Input: run_atpg")
    for line in format_l4_result(result).split("\n"):
        print(f"  {line}")