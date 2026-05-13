
#!/usr/bin/env python3
"""
semantic_chunker.py

Deterministic ontology-aware semantic chunk generator.

PURPOSE
-------
Convert canonical semantic IR:

    parsed_commands_json/*.json

into:

    semantic_chunks/*.json

Binds Level 2 IR with Level 3 Curated Ontology (if available).

This chunker is:
- deterministic,
- ontology-aware (authoritative, not inferred),
- embedding-safe,
- validator-friendly,
- telemetry-visible.

IMPORTANT PRINCIPLES
--------------------
- NO token window chunking
- NO arbitrary paragraph splitting
- NO fixed-size slicing
- NO statistical inference for ontology
- semantic boundaries ONLY

OUTPUT
------
semantic_chunks/<command>.chunks.json
"""

from __future__ import annotations

import json
import os
import re
import hashlib

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any


# =====================================================================
# CONFIGURATION
# =====================================================================

INPUT_DIR = "parsed_commands_json"

OUTPUT_DIR = "semantic_chunks"

LOG_DIR = "LOG_CHUNKER"

ONTOLOGY_MAP_FILE = "ontology_map.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

os.makedirs(LOG_DIR, exist_ok=True)


# =====================================================================
# MODELS
# =====================================================================

@dataclass
class CommandContext:
    """Holds shared context for a single command to avoid parameter explosion."""
    command: str
    group_id: str
    semantic_family: Optional[str]
    workflow_role: Optional[str]
    see_also: List[str]
    source_file: str


@dataclass
class ChunkTelemetry:
    command: str
    command_group_id: str
    chunks_created: int
    chunk_types: List[str]
    warnings: List[str]
    ontology_tags: List[str]


@dataclass
class SemanticChunk:
    chunk_id: str
    command_group_id: str
    command: str
    chunk_type: str
    title: str
    content: str
    embedding_context: str
    semantic_family: Optional[str]
    workflow_role: Optional[str]
    related_commands: List[str]
    see_also: List[str]
    commands_detected: List[str]
    source_file: str
    metadata: Dict[str, Any]


# =====================================================================
# HELPERS
# =====================================================================

def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def unique(items: List[str]) -> List[str]:
    seen = set()
    results = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        results.append(item)
    return results


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_chunk_id(command: str, chunk_type: str, content: str) -> str:
    """
    Generate deterministic hash-based ID to prevent vector DB 
    embedding misalignment on upstream content shifts.
    """
    raw = f"{command}:{chunk_type}:{content}"
    content_hash = hashlib.md5(raw.encode()).hexdigest()[:8]
    return f"{command}:{chunk_type}:{content_hash}"


# =====================================================================
# ONTOLOGY BINDING
# =====================================================================

def load_ontology_map() -> Dict[str, Dict[str, str]]:
    """
    Load authoritative curated ontology map.
    Returns dictionary of { command: { semantic_family, source } }
    Gracefully returns {} if map does not exist yet.
    """
    path = Path(ONTOLOGY_MAP_FILE)
    if not path.exists():
        print(f"[WARNING] {ONTOLOGY_MAP_FILE} not found. semantic_family will be None.")
        return {}
        
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def infer_workflow_role(command: str) -> Optional[str]:
    """
    Strict deterministic prefix matching.
    SAFE because DFT command prefixes strictly adhere to lifecycle verbs.
    """
    prefixes = {
        "add_": "ADD",
        "remove_": "REMOVE",
        "report_": "REPORT",
        "read_": "READ",
        "write_": "WRITE",
        "run_": "RUN",
        "set_": "SET",
        "get_": "GET",
        "update_": "UPDATE",
        "analyze_": "ANALYZE",
        "open_": "OPEN",
        "close_": "CLOSE",
    }

    for prefix, role in prefixes.items():
        if command.startswith(prefix):
            return role
    return None


def extract_see_also(command_json: Dict[str, Any]) -> List[str]:
    """Hardened extraction: handles both string lists and dict lists."""
    results = []

    for item in command_json.get("see_also", []):
        if isinstance(item, str):
            results.append(item)
        elif isinstance(item, dict):
            cmd = item.get("command")
            if cmd:
                results.append(cmd)

    return unique(results)


# =====================================================================
# COMMAND DETECTION
# =====================================================================

def detect_commands_in_text(text: str) -> List[str]:
    """
    Deterministic command extraction from examples / execution blocks.
    NO AI inference.
    """
    pattern = re.compile(
        r"\b("
        r"add_[a-zA-Z0-9_]+|"
        r"remove_[a-zA-Z0-9_]+|"
        r"report_[a-zA-Z0-9_]+|"
        r"read_[a-zA-Z0-9_]+|"
        r"write_[a-zA-Z0-9_]+|"
        r"run_[a-zA-Z0-9_]+|"
        r"set_[a-zA-Z0-9_]+|"
        r"get_[a-zA-Z0-9_]+|"
        r"update_[a-zA-Z0-9_]+|"
        r"analyze_[a-zA-Z0-9_]+|"
        r"open_[a-zA-Z0-9_]+|"
        r"close_[a-zA-Z0-9_]+"
        r")\b"
    )

    return unique(pattern.findall(text))


# =====================================================================
# EMBEDDING CONTEXT
# =====================================================================

def build_embedding_context(
    command: str,
    chunk_type: str,
    content: str,
    semantic_family: Optional[str],
    workflow_role: Optional[str],
    argument: Optional[str] = None
) -> str:
    """
    Prepends deterministic context to prevent embedding drift.
    CRITICAL for micro-chunk retrieval.
    """
    sections = [
        f"COMMAND: {command}",
        f"TYPE: {chunk_type}"
    ]

    if semantic_family:
        sections.append(f"SEMANTIC_FAMILY: {semantic_family}")

    if workflow_role:
        sections.append(f"WORKFLOW_ROLE: {workflow_role}")

    if argument:
        sections.append(f"OPTION: {argument}")

    sections.append("")
    sections.append(content)

    return normalize_whitespace("\n".join(sections))


# =====================================================================
# CHUNK FACTORY
# =====================================================================

class SemanticChunkFactory:

    def __init__(self, ontology_map: Dict[str, Dict[str, str]]):
        self.telemetry: List[ChunkTelemetry] = []
        self.ontology_map = ontology_map

    # ---------------------------------------------------------------
    # MAIN
    # ---------------------------------------------------------------

    def process_command(self, command_json: Dict[str, Any]) -> List[SemanticChunk]:
        command = command_json.get("command", "unknown")
        source_file = command_json.get("source_file", "unknown")
        
        # ---------------------------------------------------------------
        # AUTHORITATIVE ONTOLOGY LOOKUP
        # ---------------------------------------------------------------
        # Strictly bind Level 3 truth. Falls back to None if unmapped.
        curated_data = self.ontology_map.get(command, {})
        semantic_family = curated_data.get("semantic_family")
        
        workflow_role = infer_workflow_role(command)
        see_also = extract_see_also(command_json)

        ctx = CommandContext(
            command=command,
            group_id=command,
            semantic_family=semantic_family,
            workflow_role=workflow_role,
            see_also=see_also,
            source_file=source_file
        )

        chunks = []
        chunks.extend(self.build_description_chunks(ctx, command_json))
        chunks.extend(self.build_syntax_chunks(ctx, command_json))
        chunks.extend(self.build_argument_chunks(ctx, command_json))
        chunks.extend(self.build_example_chunks(ctx, command_json))
        chunks.extend(self.build_embedded_pre_chunks(ctx, command_json))

        # ---------------------------------------------------------------
        # TELEMETRY & VALIDATION WARNINGS
        # ---------------------------------------------------------------
        warnings = []
        has_syntax = any(c.chunk_type == "syntax" for c in chunks)
        has_examples = any(c.chunk_type in ("example", "execution_example") for c in chunks)
        
        if not has_syntax:
            warnings.append("MISSING_SYNTAX")
        if not has_examples:
            warnings.append("MISSING_EXAMPLES")
        if not chunks:
            warnings.append("NO_SEMANTIC_CONTENT")
        if not semantic_family:
            warnings.append("UNMAPPED_ONTOLOGY")

        telemetry = ChunkTelemetry(
            command=command,
            command_group_id=ctx.group_id,
            chunks_created=len(chunks),
            chunk_types=unique([chunk.chunk_type for chunk in chunks]),
            warnings=warnings,
            ontology_tags=command_json.get("ontology_patterns", [])
        )
        self.telemetry.append(telemetry)

        return chunks

    # ---------------------------------------------------------------
    # DESCRIPTION
    # ---------------------------------------------------------------

    def build_description_chunks(self, ctx: CommandContext, command_json: Dict) -> List[SemanticChunk]:
        chunks = []
        short_desc = safe_text(command_json.get("short_description"))

        if short_desc:
            embedding_context = build_embedding_context(
                command=ctx.command,
                chunk_type="short_description",
                content=short_desc,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role
            )
            chunks.append(SemanticChunk(
                chunk_id=generate_chunk_id(ctx.command, "short_description", short_desc),
                command_group_id=ctx.group_id,
                command=ctx.command,
                chunk_type="short_description",
                title=f"{ctx.command} short description",
                content=short_desc,
                embedding_context=embedding_context,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                related_commands=ctx.see_also,
                see_also=ctx.see_also,
                commands_detected=[],
                source_file=ctx.source_file,
                metadata={"priority": "high"}
            ))

        for index, text in enumerate(command_json.get("description", [])):
            text = safe_text(text)
            if not text:
                continue

            embedding_context = build_embedding_context(
                command=ctx.command,
                chunk_type="description",
                content=text,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role
            )
            chunks.append(SemanticChunk(
                chunk_id=generate_chunk_id(ctx.command, "description", text),
                command_group_id=ctx.group_id,
                command=ctx.command,
                chunk_type="description",
                title=f"{ctx.command} description",
                content=text,
                embedding_context=embedding_context,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                related_commands=ctx.see_also,
                see_also=ctx.see_also,
                commands_detected=detect_commands_in_text(text),
                source_file=ctx.source_file,
                metadata={"description_index": index}
            ))

        return chunks

    # ---------------------------------------------------------------
    # SYNTAX
    # ---------------------------------------------------------------

    def build_syntax_chunks(self, ctx: CommandContext, command_json: Dict) -> List[SemanticChunk]:
        chunks = []

        for index, syntax in enumerate(command_json.get("syntax", [])):
            syntax = safe_text(syntax)
            if not syntax:
                continue

            embedding_context = build_embedding_context(
                command=ctx.command,
                chunk_type="syntax",
                content=syntax,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role
            )
            chunks.append(SemanticChunk(
                chunk_id=generate_chunk_id(ctx.command, "syntax", syntax),
                command_group_id=ctx.group_id,
                command=ctx.command,
                chunk_type="syntax",
                title=f"{ctx.command} syntax",
                content=syntax,
                embedding_context=embedding_context,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                related_commands=ctx.see_also,
                see_also=ctx.see_also,
                commands_detected=detect_commands_in_text(syntax),
                source_file=ctx.source_file,
                metadata={"syntax_index": index}
            ))

        return chunks

    # ---------------------------------------------------------------
    # ARGUMENTS
    # ---------------------------------------------------------------

    def build_argument_chunks(self, ctx: CommandContext, command_json: Dict) -> List[SemanticChunk]:
        chunks = []

        for index, argument in enumerate(command_json.get("arguments", [])):
            if not isinstance(argument, dict):
                continue

            term = safe_text(argument.get("term"))
            description = safe_text(argument.get("description"))

            if not term and not description:
                continue

            content = f"OPTION: {term}\n\n{description}"

            embedding_context = build_embedding_context(
                command=ctx.command,
                chunk_type="argument",
                content=content,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                argument=term
            )
            chunks.append(SemanticChunk(
                chunk_id=generate_chunk_id(ctx.command, "argument", content),
                command_group_id=ctx.group_id,
                command=ctx.command,
                chunk_type="argument",
                title=f"{ctx.command} argument {term}",
                content=content,
                embedding_context=embedding_context,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                related_commands=ctx.see_also,
                see_also=ctx.see_also,
                commands_detected=detect_commands_in_text(description),
                source_file=ctx.source_file,
                metadata={"argument": term, "argument_index": index}
            ))

        return chunks

    # ---------------------------------------------------------------
    # EXAMPLES
    # ---------------------------------------------------------------

    def build_example_chunks(self, ctx: CommandContext, command_json: Dict) -> List[SemanticChunk]:
        chunks = []

        for index, example in enumerate(command_json.get("examples", [])):
            example = safe_text(example)
            if not example:
                continue

            commands_detected = detect_commands_in_text(example)
            related = unique(commands_detected + ctx.see_also)

            embedding_context = build_embedding_context(
                command=ctx.command,
                chunk_type="example",
                content=example,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role
            )
            chunks.append(SemanticChunk(
                chunk_id=generate_chunk_id(ctx.command, "example", example),
                command_group_id=ctx.group_id,
                command=ctx.command,
                chunk_type="example",
                title=f"{ctx.command} example",
                content=example,
                embedding_context=embedding_context,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                related_commands=related,
                see_also=ctx.see_also,
                commands_detected=commands_detected,
                source_file=ctx.source_file,
                metadata={"example_index": index}
            ))

        return chunks

    # ---------------------------------------------------------------
    # EMBEDDED PRE (Normalized to execution_example per roadmap)
    # ---------------------------------------------------------------

    def build_embedded_pre_chunks(self, ctx: CommandContext, command_json: Dict) -> List[SemanticChunk]:
        chunks = []

        for index, block in enumerate(command_json.get("embedded_pre_blocks", [])):
            if not isinstance(block, dict):
                continue

            raw_type = safe_text(block.get("type"))
            content = safe_text(block.get("content"))

            if not content:
                continue

            # Enforce roadmap taxonomy strictly
            chunk_type = "execution_example"

            commands_detected = detect_commands_in_text(content)
            related = unique(commands_detected + ctx.see_also)

            embedding_context = build_embedding_context(
                command=ctx.command,
                chunk_type=chunk_type,
                content=content,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role
            )
            chunks.append(SemanticChunk(
                chunk_id=generate_chunk_id(ctx.command, chunk_type, content),
                command_group_id=ctx.group_id,
                command=ctx.command,
                chunk_type=chunk_type,
                title=f"{ctx.command} embedded execution",
                content=content,
                embedding_context=embedding_context,
                semantic_family=ctx.semantic_family,
                workflow_role=ctx.workflow_role,
                related_commands=related,
                see_also=ctx.see_also,
                commands_detected=commands_detected,
                source_file=ctx.source_file,
                metadata={
                    "embedded_pre_index": index,
                    "original_block_type": raw_type
                }
            ))

        return chunks


# =====================================================================
# FILE IO
# =====================================================================

def load_json(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)


# =====================================================================
# MAIN
# =====================================================================

def main() -> None:
    # Load Level 3 Truth Hierarchy FIRST
    ontology_map = load_ontology_map()
    
    # Inject into factory
    factory = SemanticChunkFactory(ontology_map=ontology_map)

    input_paths = sorted(Path(INPUT_DIR).glob("*.json"))
    total_chunks = 0

    for path in input_paths:
        command_json = load_json(path)
        command = command_json.get("command", path.stem)

        chunks = factory.process_command(command_json)
        total_chunks += len(chunks)

        output_path = Path(OUTPUT_DIR) / f"{command}.chunks.json"
        write_json(output_path, [asdict(chunk) for chunk in chunks])

        telemetry = factory.telemetry[-1]
        telemetry_path = Path(LOG_DIR) / f"{command}.chunk.log.json"
        write_json(telemetry_path, asdict(telemetry))

        # Enhanced CLI Output
        warning_str = f" | WARNINGS: {telemetry.warnings}" if telemetry.warnings else ""
        print(f"[OK] {command}: {len(chunks)} chunks{warning_str}")

    print()
    print("================================================")
    print(f"Commands processed : {len(input_paths)}")
    print(f"Total chunks       : {total_chunks}")
    print("================================================")


if __name__ == "__main__":
    main()
