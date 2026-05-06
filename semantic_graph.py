#!/usr/bin/env python3
"""
semantic_graph.py — Hardened workflow pattern extractor from TetraMAX scripts.

FIXES applied:
  1. Graph-based command validation (not regex guessing)
  2. Blank-line script segmentation (not =====)
  3. ALL transitions stored (no truncation)
  4. Command names normalized (lowercase)
  5. Multiline command joining (backslash continuation)
  6. Report_/get_ filtered from transitions (noise reduction)
  7. Deduplicated flags per line (set, not list)
  8. Configurable input path (argparse)
  9. Empty-safe averages
  10. Separate extraction from interpretation layers

Usage:
    python semantic_graph.py --input tmax_scripts.txt --graph tmax_graph.json
"""

import json
import re
import argparse
from pathlib import Path
from collections import Counter, defaultdict


def load_graph(graph_path: Path) -> set:
    """Load valid command names from tmax_graph.json."""
    with open(graph_path, encoding="utf-8") as f:
        data = json.load(f)
    return set(data["commands"].keys())


def normalize_command(raw: str, valid_commands: set) -> str | None:
    """
    Normalize and validate a command string.

    Returns lowercase command if valid, None otherwise.
    """
    cmd = raw.strip().lower()
    if cmd in valid_commands:
        return cmd
    return None


def join_continued_lines(lines: list[str]) -> list[str]:
    """
    Join lines ending with backslash continuation.

    run_atpg \\
       -ndetects 10
    → "run_atpg -ndetects 10"
    """
    result = []
    buffer = ""

    for line in lines:
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buffer += stripped[:-1] + " "
        else:
            buffer += stripped
            if buffer.strip():
                result.append(buffer.strip())
            buffer = ""

    if buffer.strip():
        result.append(buffer.strip())

    return result


def extract_commands_from_block(block: str, valid_commands: set) -> tuple:
    """
    Extract commands, flags, and sequence from a single script block.

    Returns: (sequence, flag_usage_dict)
    """
    lines = block.split("\n")
    lines = join_continued_lines(lines)

    sequence = []
    flag_usage = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip comments (various formats)
        if line.startswith("#") or line.startswith("//") or line.startswith(";"):
            continue

        # Skip Verilog/shell/TCL variable assignments
        if re.match(r'^(module|wire|assign|always|initial|set\s+[A-Z]|setenv|bsub|qsub|Command:|vcs)', line, re.IGNORECASE):
            continue

        # Skip prompt prefixes: TEST-T>, >, tmax>
        line = re.sub(r'^(?:TEST-T>|tmax|>)\s*', '', line)

        # Extract command: first word that matches valid_commands
        words = line.split()
        if not words:
            continue

        # Try each word position — command might not be first (e.g., "Command: run_atpg")
        cmd = None
        for word in words[:3]:  # Check first 3 words
            normalized = normalize_command(word, valid_commands)
            if normalized:
                cmd = normalized
                break

        if not cmd:
            continue

        sequence.append(cmd)

        # Extract flags (deduplicated per line)
        flags = set(re.findall(r'-([a-zA-Z_][a-zA-Z0-9_]*)', line))
        if flags:
            flag_usage[cmd] = flag_usage.get(cmd, set()) | flags

    return sequence, flag_usage


def is_noise_command(cmd: str) -> bool:
    """Filter noise commands from transition analysis."""
    return cmd.startswith("report_") or cmd.startswith("get_") or cmd.startswith("man_")


def extract_from_scripts(text: str, valid_commands: set) -> dict:
    """
    Main extraction pipeline.

    Returns raw extraction data (no interpretation).
    """
    # Split by blank lines (stronger than =====)
    blocks = re.split(r'\n\s*\n', text)

    all_sequences = []
    all_commands = Counter()
    all_flag_usage = defaultdict(set)
    transitions = Counter()

    for block in blocks:
        block = block.strip()
        if len(block) < 20:  # Skip tiny fragments
            continue

        seq, flags = extract_commands_from_block(block, valid_commands)

        if not seq:
            continue

        all_sequences.append(seq)

        for cmd in seq:
            all_commands[cmd] += 1

        for cmd, cmd_flags in flags.items():
            all_flag_usage[cmd] |= cmd_flags

        # Build transitions (filter noise)
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            if not is_noise_command(a) and not is_noise_command(b):
                transitions[(a, b)] += 1

    return {
        "sequences": all_sequences,
        "commands": all_commands,
        "flag_usage": dict(all_flag_usage),
        "transitions": transitions,
    }


def build_interpretation(raw: dict) -> dict:
    """
    Build interpretation layer from raw extraction.

    Separate from extraction for clean architecture.
    """
    sequences = raw["sequences"]
    commands = raw["commands"]
    flag_usage = raw["flag_usage"]
    transitions = raw["transitions"]

    # Command frequencies
    command_freq = dict(commands.most_common())

    # Flag frequencies (convert sets to counts)
    flag_freq = {}
    for cmd, flags in flag_usage.items():
        flag_freq[cmd] = {f: 1 for f in flags}  # Binary presence

    # ALL transitions (no truncation)
    transition_list = [
        {"from": a, "to": b, "count": c}
        for (a, b), c in transitions.items()
    ]

    # N-grams (3-grams)
    ngrams = Counter()
    for seq in sequences:
        for i in range(len(seq) - 2):
            ngrams[tuple(seq[i:i+3])] += 1

    ngram_list = [
        {"sequence": list(gram), "count": c}
        for gram, c in ngrams.most_common(30)
    ]

    # Script statistics
    total_commands = sum(commands.values())
    unique_commands = len(commands)
    avg_length = sum(len(s) for s in sequences) / len(sequences) if sequences else 0

    return {
        "meta": {
            "scripts_parsed": len(sequences),
            "total_commands": total_commands,
            "unique_commands": unique_commands,
            "avg_script_length": round(avg_length, 2),
        },
        "command_frequency": command_freq,
        "flag_usage": flag_freq,
        "transitions": transition_list,
        "common_sequences": ngram_list,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract TetraMAX workflow patterns")
    parser.add_argument("--input", default="tmax_scripts.txt", help="Input script file")
    parser.add_argument("--graph", default="tmax_graph.json", help="Graph JSON for validation")
    parser.add_argument("--output", default="semantic_graph.json", help="Output file")
    args = parser.parse_args()

    input_path = Path(args.input)
    graph_path = Path(args.graph)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        print("   Place your TetraMAX scripts in this file")
        return

    if not graph_path.exists():
        print(f"❌ Graph file not found: {graph_path}")
        print("   Run build_graph.py first")
        return

    print("Loading command graph...")
    valid_commands = load_graph(graph_path)
    print(f"   {len(valid_commands)} valid commands loaded")

    print(f"Reading scripts from {input_path}...")
    text = input_path.read_text(encoding="utf-8", errors="ignore")

    print("Extracting raw patterns...")
    raw = extract_from_scripts(text, valid_commands)

    print(f"   Sequences: {len(raw['sequences'])}")
    print(f"   Commands: {sum(raw['commands'].values())}")
    print(f"   Transitions: {len(raw['transitions'])}")

    print("Building interpretation layer...")
    semantic = build_interpretation(raw)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(semantic, f, indent=2)

    print(f"\n✅ Saved to {output_path}")

    # Summary
    meta = semantic["meta"]
    print(f"\n📊 Summary:")
    print(f"   Scripts: {meta['scripts_parsed']}")
    print(f"   Commands: {meta['total_commands']} ({meta['unique_commands']} unique)")
    print(f"   Avg length: {meta['avg_script_length']}")

    print(f"\n🔥 Top commands:")
    for cmd, count in list(semantic["command_frequency"].items())[:10]:
        print(f"   {cmd}: {count}x")

    print(f"\n🔗 Top transitions:")
    top_trans = sorted(semantic["transitions"], key=lambda x: -x["count"])[:5]
    for t in top_trans:
        print(f"   {t['from']} → {t['to']} ({t['count']}x)")


if __name__ == "__main__":
    main()