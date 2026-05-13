#!/usr/bin/env python3

"""
Military-Grade Deterministic DITA Parser
========================================

Canonical semantic extraction engine for Synopsys TestMAX/TetraMAX
DITA-generated HTML manuals.

Features
--------
- Deterministic extraction only
- No heuristic scraping
- Ontology-aware parsing
- Section-state semantics
- Multi-pattern syntax extraction
- Syntax-embedded argument extraction
- Repeated section handling
- Structured parser telemetry
- Stable canonical IR
- Graceful degradation
"""

import os
import re
import glob
import json

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from bs4.element import Tag


# =============================================================================
# CONFIG
# =============================================================================

INPUT_DIR = "tmax_olh/Content/tmax_cmds/tmax_cmds"
OUTPUT_DIR = "parsed_commands_json"
LOG_DIR = "LOG_PARSER"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


# =============================================================================
# HELPERS
# =============================================================================


def normalize_inline(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def preserve_pre(pre: Tag) -> str:
    """
    Preserve semantic formatting inside PRE blocks.
    """

    if not pre:
        return ""

    text = pre.get_text()

    lines = []

    for line in text.splitlines():
        line = line.rstrip()

        if line.strip():
            lines.append(line)

    return "\n".join(lines).strip()


def inline_text(node: Tag) -> str:
    if not node:
        return ""

    return normalize_inline(node.get_text(" ", strip=True))


def has_class_fragment(tag: Tag, fragment: str) -> bool:
    if not tag:
        return False

    classes = tag.get("class", [])

    joined = " ".join(classes)

    return fragment in joined


def unique(items: List[str]) -> List[str]:
    out = []
    seen = set()

    for item in items:
        if item in seen:
            continue

        seen.add(item)
        out.append(item)

    return out


# =============================================================================
# IR
# =============================================================================


@dataclass
class Argument:
    term: str
    description: str


@dataclass
class RelatedCommand:
    command: str
    href: str


@dataclass
class SectionState:
    syntax: str = "ABSENT"
    arguments: str = "ABSENT"
    description: str = "ABSENT"
    examples: str = "ABSENT"


@dataclass
class ParserTelemetry:
    document_type: str = "unknown"

    sections_found: List[str] = field(default_factory=list)
    sections_missing: List[str] = field(default_factory=list)

    ontology_patterns: List[str] = field(default_factory=list)

    parser_actions: List[str] = field(default_factory=list)

    warnings: List[str] = field(default_factory=list)


@dataclass
class CommandIR:
    command: str

    title: str = ""

    document_type: str = "unknown"

    short_description: str = ""

    description: List[str] = field(default_factory=list)

    syntax: List[str] = field(default_factory=list)

    arguments: List[Argument] = field(default_factory=list)

    examples: List[str] = field(default_factory=list)

    embedded_pre_blocks: List[Dict] = field(default_factory=list)

    allowed_command_modes: List[str] = field(default_factory=list)

    see_also: List[RelatedCommand] = field(default_factory=list)

    dc_relations: List[str] = field(default_factory=list)

    breadcrumbs: List[str] = field(default_factory=list)

    section_states: Dict[str, str] = field(default_factory=dict)

    ontology_patterns: List[str] = field(default_factory=list)

    parser_actions: List[str] = field(default_factory=list)

    parser_warnings: List[str] = field(default_factory=list)

    source_file: str = ""

# =============================================================================
# PARSER
# =============================================================================


class DITAParser:

    # -------------------------------------------------------------------------
    # DRIVER
    # -------------------------------------------------------------------------

    def parse_file(self, file_path: str) -> CommandIR:

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f, "lxml")

        self.remove_noise(soup)

        command = (
            os.path.basename(file_path)
            .replace("man_", "")
            .replace(".htm", "")
        )

        telemetry = ParserTelemetry()

        ir = CommandIR(
            command=command,
            source_file=os.path.basename(file_path)
        )

        ir.title = self.extract_title(soup)

        ir.document_type = self.classify_document(soup)

        telemetry.document_type = ir.document_type

        ir.short_description = self.extract_short_description(soup)

        ir.description = self.extract_description(
            soup,
            telemetry
        )

        ir.syntax = self.extract_syntax(
            soup,
            telemetry
        )

        ir.arguments = self.extract_arguments(
            soup,
            telemetry
        )

        ir.examples = self.extract_examples(
            soup,
            telemetry
        )

        ir.embedded_pre_blocks = self.extract_embedded_pre_blocks(
            soup,
            telemetry,
            ir.command
        )

        ir.allowed_command_modes = self.extract_allowed_modes(soup)

        ir.see_also = self.extract_see_also(soup)

        ir.dc_relations = self.extract_dc_relations(soup)

        ir.breadcrumbs = self.extract_breadcrumbs(soup)

        ir.section_states = self.compute_section_states(
            soup,
            ir
        )

        ir.ontology_patterns = unique(telemetry.ontology_patterns)

        ir.parser_actions = unique(telemetry.parser_actions)

        ir.parser_warnings = unique(telemetry.warnings)

        self.log_parse(ir)

        return ir

    # -------------------------------------------------------------------------
    # CLEANUP
    # -------------------------------------------------------------------------

    def remove_noise(self, soup: BeautifulSoup):

        for tag in soup([
            "script",
            "style",
            "noscript"
        ]):
            tag.decompose()

    # -------------------------------------------------------------------------
    # CLASSIFICATION
    # -------------------------------------------------------------------------

    def classify_document(self, soup: BeautifulSoup) -> str:

        syntax_sections = self.find_sections(
            soup,
            "syntax-section"
        )

        arguments_sections = self.find_sections(
            soup,
            "arguments-section"
        )

        title = self.extract_title(soup).lower()

        if syntax_sections or arguments_sections:
            return "command_reference"

        if "parameters" in title:
            return "configuration_reference"

        return "auxiliary_topic"

    # -------------------------------------------------------------------------
    # SECTION DISCOVERY
    # -------------------------------------------------------------------------

    def find_sections(
        self,
        soup: BeautifulSoup,
        fragment: str
    ) -> List[Tag]:

        results = []

        for div in soup.find_all("div"):

            if has_class_fragment(div, fragment):
                results.append(div)

        return results

    # -------------------------------------------------------------------------
    # TITLE
    # -------------------------------------------------------------------------

    def extract_title(self, soup: BeautifulSoup) -> str:

        h1 = soup.find("h1")

        if not h1:
            return ""

        return inline_text(h1)

    # -------------------------------------------------------------------------
    # SHORT DESCRIPTION
    # -------------------------------------------------------------------------

    def extract_short_description(self, soup: BeautifulSoup) -> str:

        results = []

        for div in soup.find_all("div"):

            if not has_class_fragment(div, "short-description"):
                continue

            for p in div.find_all("p", recursive=False):

                text = inline_text(p)

                if text:
                    results.append(text)

        return "\n\n".join(results).strip()

    # -------------------------------------------------------------------------
    # DESCRIPTION
    # -------------------------------------------------------------------------

    def extract_description(
    self,
    soup: BeautifulSoup,
    telemetry: ParserTelemetry
) -> List[str]:

        sections = self.find_sections(
            soup,
            "description-section"
        )

        results = []

        # -----------------------------------------------------------------
        # FALLBACK:
        # NO DESCRIPTION SECTION EXISTS
        # -----------------------------------------------------------------

        if not sections:

            intro_paragraphs = []

            syntax_sections = self.find_sections(
                soup,
                "syntax-section"
            )

            syntax_section = (
                syntax_sections[0]
                if syntax_sections else None
            )

            body = soup.find("body")

            if body:

                for p in body.find_all("p"):

                    # stop once syntax section begins
                    if (
                        syntax_section
                        and syntax_section in p.parents
                    ):
                        break

                    text = inline_text(p)

                    if not text:
                        continue

                    if len(text) < 40:
                        continue

                    intro_paragraphs.append(text)

            if intro_paragraphs:

                telemetry.ontology_patterns.append(
                    "fallback_intro_description"
                )

                telemetry.parser_actions.append(
                    "description_extracted_from_intro_prose"
                )

                telemetry.sections_found.append(
                    "description"
                )

                return unique(intro_paragraphs)

            telemetry.sections_missing.append(
                "description"
            )

            return []

        # -----------------------------------------------------------------
        # NORMAL DESCRIPTION SECTION EXISTS
        # -----------------------------------------------------------------

        telemetry.sections_found.append(
            "description"
        )

        if len(sections) > 1:

            telemetry.ontology_patterns.append(
                "repeated_description_sections"
            )

        for section in sections:

            # -------------------------------------------------------------
            # NORMAL DESCRIPTION PARAGRAPHS
            # -------------------------------------------------------------

            for p in section.find_all(
                "p",
                recursive=False
            ):

                text = inline_text(p)

                if not text:
                    continue

                if text.lower() == "description":
                    continue

                results.append(text)

            # -------------------------------------------------------------
            # FALLBACK:
            # DESCRIPTION TEXT BEFORE DESCRIPTION MARKER
            # -------------------------------------------------------------

            if not results:

                for sibling in section.find_previous_siblings("p"):

                    text = inline_text(sibling)

                    if not text:
                        continue

                    if len(text) < 40:
                        continue

                    results.append(text)

                if results:

                    telemetry.ontology_patterns.append(
                        "description_before_description_section"
                    )

                    telemetry.parser_actions.append(
                        "description_recovered_from_parent_section"
                    )

        if results:

            return unique(results)

        telemetry.sections_missing.append(
            "description"
        )

        return []
    # -------------------------------------------------------------------------
    # SYNTAX
    # -------------------------------------------------------------------------

    def extract_syntax(
        self,
        soup: BeautifulSoup,
        telemetry: ParserTelemetry
    ) -> List[str]:

        sections = self.find_sections(
            soup,
            "syntax-section"
        )

        if not sections:
            telemetry.sections_missing.append("syntax")
            return []

        telemetry.sections_found.append("syntax")

        results = []

        for section in sections:

            # -------------------------------------------------------------
            # PRE-BASED SYNTAX
            # -------------------------------------------------------------

            pres = section.find_all("pre")

            if pres:

                telemetry.ontology_patterns.append(
                    "syntax_pre"
                )

                for pre in pres:

                    text = preserve_pre(pre)

                    if text:
                        results.append(text)

            # -------------------------------------------------------------
            # DL-BASED SYNTAX
            # -------------------------------------------------------------

            dls = section.find_all("dl", recursive=False)

            if dls and not pres:

                telemetry.ontology_patterns.append(
                    "syntax_dl"
                )

                telemetry.parser_actions.append(
                    "syntax_extracted_from_dl"
                )

                for dl in dls:

                    for dt in dl.find_all("dt", recursive=False):

                        text = inline_text(dt)

                        if text:
                            results.append(text)

            # -------------------------------------------------------------
            # PROSE-BASED SYNTAX
            # -------------------------------------------------------------

            if not pres and not dls:

                paragraphs = section.find_all(
                    "p",
                    recursive=False
                )

                prose = []

                for p in paragraphs:

                    text = inline_text(p)

                    if not text:
                        continue

                    if text.lower() == "syntax":
                        continue

                    prose.append(text)

                if prose:

                    telemetry.ontology_patterns.append(
                        "syntax_prose"
                    )

                    telemetry.parser_actions.append(
                        "syntax_extracted_from_prose"
                    )

                    results.extend(prose)

        return unique(results)

    # -------------------------------------------------------------------------
    # ARGUMENTS
    # -------------------------------------------------------------------------

    def extract_arguments(
        self,
        soup: BeautifulSoup,
        telemetry: ParserTelemetry
    ) -> List[Argument]:

        results = []

        sections = self.find_sections(
            soup,
            "arguments-section"
        )

        # -----------------------------------------------------------------
        # NORMAL ARGUMENT SECTIONS
        # -----------------------------------------------------------------

        for section in sections:

            telemetry.sections_found.append("arguments")

            # -------------------------------------------------------------
            # EXPLICIT NONE
            # -------------------------------------------------------------

            section_text = inline_text(section).lower()

            if (
                "none" in section_text
                or "no arguments" in section_text
            ):

                telemetry.ontology_patterns.append(
                    "arguments_explicit_none"
                )

                telemetry.parser_actions.append(
                    "arguments_marked_explicit_none"
                )

            # -------------------------------------------------------------
            # DL ARGUMENTS
            # -------------------------------------------------------------

            for dl in section.find_all("dl"):

                telemetry.ontology_patterns.append(
                    "arguments_dl"
                )

                for dt in dl.find_all("dt", recursive=False):

                    term = inline_text(dt)

                    dd = dt.find_next_sibling("dd")

                    if not dd:
                        continue

                    description_parts = []

                    for child in dd.find_all(
                        ["p", "li"],
                        recursive=False
                    ):

                        text = inline_text(child)

                        if text:
                            description_parts.append(text)

                    description = "\n".join(
                        description_parts
                    ).strip()

                    if term and description:

                        results.append(
                            Argument(
                                term=term,
                                description=description
                            )
                        )

        # -----------------------------------------------------------------
        # SYNTAX-EMBEDDED ARGUMENTS
        # -----------------------------------------------------------------

        syntax_sections = self.find_sections(
            soup,
            "syntax-section"
        )

        for section in syntax_sections:

            pres = section.find_all("pre")

            dls = section.find_all("dl", recursive=False)

            if pres and dls:

                telemetry.ontology_patterns.append(
                    "syntax_embedded_argument_dl"
                )

                telemetry.parser_actions.append(
                    "arguments_extracted_from_syntax_dl"
                )

                for dl in dls:

                    for dt in dl.find_all("dt", recursive=False):

                        term = inline_text(dt)

                        dd = dt.find_next_sibling("dd")

                        if not dd:
                            continue

                        description_parts = []

                        for child in dd.find_all(
                            ["p", "li"],
                            recursive=False
                        ):

                            text = inline_text(child)

                            if text:
                                description_parts.append(text)

                        description = "\n".join(
                            description_parts
                        ).strip()

                        if term and description:

                            results.append(
                                Argument(
                                    term=term,
                                    description=description
                                )
                            )

        return results

    # -------------------------------------------------------------------------
    # EXAMPLES
    # -------------------------------------------------------------------------

    def extract_examples(
        self,
        soup: BeautifulSoup,
        telemetry: ParserTelemetry
    ) -> List[str]:

        sections = self.find_sections(
            soup,
            "example-section"
        )

        if not sections:
            telemetry.sections_missing.append("examples")
            return []

        telemetry.sections_found.append("examples")

        results = []

        for section in sections:

            for pre in section.find_all("pre"):

                telemetry.ontology_patterns.append(
                    "example_pre"
                )

                text = preserve_pre(pre)

                if text:
                    results.append(text)

        return unique(results)


    # -------------------------------------------------------------------------
    # EMBEDDED PRE BLOCKS
    # -------------------------------------------------------------------------

    def extract_embedded_pre_blocks(
        self,
        soup: BeautifulSoup,
        telemetry: ParserTelemetry,
        command_name: str
    ) -> List[Dict]:

        results = []

        sections = self.find_sections(
            soup,
            "description-section"
        )

        for section in sections:

            for pre in section.find_all("pre"):

                text = preserve_pre(pre)

                if not text:
                    continue

                block_type = "unknown_pre"

                stripped = text.strip()

                first_line = stripped.splitlines()[0].strip()

                # -------------------------------------------------------------
                # EXECUTION EXAMPLE
                # -------------------------------------------------------------

                if (
                    first_line.startswith(command_name)
                    or f"{command_name} " in first_line
                ):

                    block_type = "execution_example"

                # -------------------------------------------------------------
                # OPERATIONAL OUTPUT
                # -------------------------------------------------------------

                elif (
                    "Warning:" in text
                    or "completed successfully" in text
                    or "Total_time" in text
                ):

                    block_type = "operational_output"

                # -------------------------------------------------------------
                # CONFIGURATION SNIPPET
                # -------------------------------------------------------------

                elif (
                    "=" in text
                    or "-option" in text
                ):

                    block_type = "configuration_snippet"

                telemetry.ontology_patterns.append(
                    "embedded_description_pre"
                )

                telemetry.parser_actions.append(
                    f"embedded_pre_detected:{block_type}"
                )

                results.append({
                    "type": block_type,
                    "content": text
                })

        return results

    # -------------------------------------------------------------------------
    # ALLOWED MODES
    # -------------------------------------------------------------------------

    def extract_allowed_modes(
        self,
        soup: BeautifulSoup
    ) -> List[str]:

        sections = self.find_sections(
            soup,
            "arguments-section"
        )

        for section in sections:

            paragraphs = section.find_all("p")

            for idx, p in enumerate(paragraphs):

                text = inline_text(p)

                if text.lower() != "allowed command modes":
                    continue

                if idx + 1 >= len(paragraphs):
                    continue

                value = inline_text(
                    paragraphs[idx + 1]
                )

                modes = []

                for part in re.split(r"[,/]", value):

                    part = part.strip()

                    if part:
                        modes.append(part)

                return sorted(set(modes))

        return []

    # -------------------------------------------------------------------------
    # SEE ALSO
    # -------------------------------------------------------------------------

    def extract_see_also(
        self,
        soup: BeautifulSoup
    ) -> List[RelatedCommand]:

        results = []

        nav = soup.find(
            "nav",
            class_=lambda x: x and "related-links" in str(x)
        )

        if not nav:
            return []

        for a in nav.find_all("a", href=True):

            href = a.get("href", "").strip()

            text = inline_text(a)

            if not href.endswith(".htm"):
                continue

            if not text:
                continue

            results.append(
                RelatedCommand(
                    command=text,
                    href=href
                )
            )

        return results

    # -------------------------------------------------------------------------
    # DC RELATIONS
    # -------------------------------------------------------------------------

    def extract_dc_relations(
        self,
        soup: BeautifulSoup
    ) -> List[str]:

        rels = []

        for meta in soup.find_all("meta"):

            if meta.get("name") != "DC.relation":
                continue

            content = meta.get("content", "").strip()

            if content:
                rels.append(content)

        return sorted(set(rels))

    # -------------------------------------------------------------------------
    # BREADCRUMBS
    # -------------------------------------------------------------------------

    def extract_breadcrumbs(
        self,
        soup: BeautifulSoup
    ) -> List[str]:

        results = []

        for a in soup.find_all(
            "a",
            class_=lambda x: x and "MCBreadcrumbsLink" in str(x)
        ):

            text = inline_text(a)

            if text:
                results.append(text)

        return results

    # -------------------------------------------------------------------------
    # SECTION STATES
    # -------------------------------------------------------------------------

    def compute_section_states(
        self,
        soup: BeautifulSoup,
        ir: CommandIR
    ) -> Dict[str, str]:

        states = {}

        # -------------------------------------------------------------
        # SYNTAX
        # -------------------------------------------------------------

        syntax_sections = self.find_sections(
            soup,
            "syntax-section"
        )

        if ir.syntax:
            states["syntax"] = "PRESENT"

        elif syntax_sections:
            states["syntax"] = "PRESENT_BUT_EMPTY"

        else:
            states["syntax"] = "ABSENT"

        # -------------------------------------------------------------
        # ARGUMENTS
        # -------------------------------------------------------------

        arguments_sections = self.find_sections(
            soup,
            "arguments-section"
        )

        explicit_none = False

        for section in arguments_sections:

            text = inline_text(section).lower()

            if (
                "none" in text
                or "no arguments" in text
            ):
                explicit_none = True

        if explicit_none:
            states["arguments"] = "EXPLICITLY_NONE"

        elif ir.arguments:
            states["arguments"] = "PRESENT"

        elif arguments_sections:
            states["arguments"] = "PRESENT_BUT_EMPTY"

        else:
            states["arguments"] = "ABSENT"

        # -------------------------------------------------------------
        # DESCRIPTION
        # -------------------------------------------------------------

        if ir.description:
            states["description"] = "PRESENT"
        else:
            states["description"] = "ABSENT"

        # -------------------------------------------------------------
        # EXAMPLES
        # -------------------------------------------------------------

        if ir.examples:
            states["examples"] = "PRESENT"
        else:
            states["examples"] = "ABSENT"

        return states

    # -------------------------------------------------------------------------
    # LOGGING
    # -------------------------------------------------------------------------

    def log_parse(self, ir: CommandIR):

        log_data = {
            "command": ir.command,
            "document_type": ir.document_type,
            "source_file": ir.source_file,
            "section_states": ir.section_states,
            "ontology_patterns": ir.ontology_patterns,
            "parser_actions": ir.parser_actions,
            "parser_warnings": ir.parser_warnings
        }

        # -----------------------------------------------------------------
        # WRITE STRUCTURED JSON LOG
        # -----------------------------------------------------------------

        log_path = os.path.join(
            LOG_DIR,
            f"{ir.command}.log.json"
        )

        with open(log_path, "w", encoding="utf-8") as f:

            json.dump(
                log_data,
                f,
                indent=2,
                ensure_ascii=False
            )

        # -----------------------------------------------------------------
        # TERMINAL OUTPUT
        # -----------------------------------------------------------------

        print("=" * 80)
        print(f"[COMMAND] {ir.command}")
        print(f"[TYPE]    {ir.document_type}")

        print()
        print("[SECTION STATES]")

        for k, v in ir.section_states.items():
            print(f"  - {k}: {v}")

        if ir.ontology_patterns:

            print()
            print("[ONTOLOGY PATTERNS]")

            for item in ir.ontology_patterns:
                print(f"  - {item}")

        if ir.parser_actions:

            print()
            print("[PARSER ACTIONS]")

            for item in ir.parser_actions:
                print(f"  - {item}")

        if ir.parser_warnings:

            print()
            print("[WARNINGS]")

            for item in ir.parser_warnings:
                print(f"  - {item}")

        print()

    # -------------------------------------------------------------------------
    # END CLASS
    # -------------------------------------------------------------------------


# =============================================================================
# EMITTER
# =============================================================================


class JSONEmitter:

    def emit(self, ir: CommandIR):

        out_path = os.path.join(
            OUTPUT_DIR,
            f"{ir.command}.json"
        )

        with open(out_path, "w", encoding="utf-8") as f:

            json.dump(
                asdict(ir),
                f,
                indent=2,
                ensure_ascii=False
            )


# =============================================================================
# DRIVER
# =============================================================================


def main():

    parser = DITAParser()

    emitter = JSONEmitter()
    # OLD
    # files = sorted(
    #     glob.glob(
    #         os.path.join(INPUT_DIR, "man_*.htm")
    #     )
    # )

    # NEW
    all_files = glob.glob(os.path.join(INPUT_DIR, "*.htm"))
    
    excluded = {
        "tmax_cmds.htm",
        "glossary.htm",
        "using_atpg_constraints.htm",
        "copyright.htm",
    }
    
    files = sorted([
        f for f in all_files
        if os.path.basename(f) not in excluded
        and not os.path.basename(f).endswith("_commands.htm")
        and not os.path.basename(f).startswith("popup_")
    ])

    total_ok = 0
    total_fail = 0

    print("=" * 80)
    print("MILITARY-GRADE DITA PARSER")
    print("=" * 80)

    for file_path in files:

        try:

            ir = parser.parse_file(file_path)

            emitter.emit(ir)

            total_ok += 1

            print(f"[OK] {ir.command}")

        except Exception as e:

            total_fail += 1

            print(
                f"[FAILED] "
                f"{os.path.basename(file_path)} -> {e}"
            )

    print()
    print("=" * 80)
    print(f"SUCCESS : {total_ok}")
    print(f"FAILED  : {total_fail}")
    print("=" * 80)


if __name__ == "__main__":
    main()