# TASK_HTML_PARSER_REMEDIATION_PLAN.md

**Date:** 2026-05-09
**Source:** `TASK_HTML_PARSER_FINDINGS.md`
**Parser:** `parse_html_structured.py` (175 lines, 5 extractor functions)

---

## Subsystem-to-Finding Map

| Subsystem | Function | Lines | Findings |
|-----------|----------|-------|----------|
| Description extraction | `extract_description()` | 15–24 | F1 |
| Examples extraction | `extract_examples()` | 80–89 | F2, F3 |
| Options formatting | `extract_options()` | 50–78 | F4 |
| Inline formatting | `clean_text()` (shared) | 11–12 | F5 |
| Validation/reporting | `main()` | 153–174 | F7 |

---

## 1. Description Extraction

### F1 — "Description" Label Bleeds Into Extracted Text

**Exact function:** `extract_description()` at line 15–24.

**Current code:**
```python
def extract_description(soup):
    desc_section = soup.find("div", class_="description-section")
    if not desc_section:
        return ""
    paragraphs = desc_section.find_all("p")
    desc_texts = [clean_text(p) for p in paragraphs if clean_text(p)]
    return " ".join(desc_texts)
```

**Root cause:** The first `<p>` inside `description-section` contains a `<span class="section-label">Description</span>` as its sole or leading content. `clean_text()` extracts the full text of each `<p>`, so the label text "Description" comes through verbatim.

**Minimum deterministic fix:**
```python
def extract_description(soup):
    desc_section = soup.find("div", class_="description-section")
    if not desc_section:
        return ""

    # Remove section-label spans so their text is not extracted
    for label in desc_section.find_all("span", class_="section-label"):
        label.decompose()

    paragraphs = desc_section.find_all("p")
    desc_texts = [clean_text(p) for p in paragraphs if clean_text(p)]
    return " ".join(desc_texts)
```

**Lines changed:** +3 (insert decompose loop before paragraph extraction).

**Blast radius:** `extract_description()` only. No signature change, no caller impact. The `clean_text()` helper is untouched. `save_command()` output path unchanged.

**Validation strategy:**
1. Re-parse 5 representative commands (e.g., `write_patterns`, `set_delay`, `set_atpg`, `add_faults`, `report_faults`)
2. Assert `data["description"]` does NOT start with "Description" for any of them
3. Assert description is non-empty for all 5
4. Diff old vs. new output — only change should be removal of leading "Description " prefix

**Estimated regression risk:** Near-zero. The `decompose()` call is scoped to `span.section-label` only within the description div. If no such span exists, it's a no-op.

---

## 2. Examples Extraction

### F2 — Missing EXAMPLES Section

**Exact function:** `extract_examples()` at line 80–89.

**Current code:**
```python
def extract_examples(soup):
    ex_div = soup.find("div", class_="example-section")
    if not ex_div:
        return ""
    pre = ex_div.find("pre")
    if not pre:
        return ""
    return pre.get_text("\n", strip=True)
```

**Root cause hypothesis:** Some commands use a different CSS class for the examples container (e.g., `example` instead of `example-section`) or an entirely different DOM structure. The current selector is a single rigid class match with no fallback.

**Minimum deterministic fix:** This requires a 1-time HTML inspection to confirm the actual class name(s) used. Proposed approach:

```python
def extract_examples(soup):
    # Try primary selector first
    ex_div = soup.find("div", class_="example-section")
    # Fallback: some pages use a bare "example" class
    if not ex_div:
        ex_div = soup.find("div", class_="example")
    if not ex_div:
        return ""
    # ... rest unchanged
```

**Alternative if HTML structure is radically different:** Search for a heading element containing "Examples" and extract the following content block.

**Blast radius:** `extract_examples()` only. Adds a fallback path without changing the primary path.

**Validation strategy:**
1. Identify 3 known-missing commands from validation sweep (F7 output)
2. Inspect their source HTML to confirm class name
3. Apply fallback selector
4. Re-parse and assert EXAMPLES section is non-empty
5. Spot-check 3 known-working commands to confirm no regression

**Estimated regression risk:** Low. Fallback is gated behind `if not ex_div` — primary path is never altered.

### F3 — EXAMPLES Section Truncated to Single Entry

**Exact function:** `extract_examples()` at line 85 — `ex_div.find("pre")` returns only the first `<pre>`.

**Root cause:** `find()` returns the first match. Commands with multiple examples have multiple `<pre>` blocks within the examples section, but only the first is extracted.

**Minimum deterministic fix:**
```python
def extract_examples(soup):
    ex_div = soup.find("div", class_="example-section")
    if not ex_div:
        ex_div = soup.find("div", class_="example")
    if not ex_div:
        return ""

    # Collect ALL <pre> blocks, not just the first
    pre_blocks = ex_div.find_all("pre")
    if not pre_blocks:
        return ""

    return "\n\n".join(pre.get_text("\n", strip=True) for pre in pre_blocks)
```

**Lines changed:** Replace `find("pre")` → `find_all("pre")`, join with `\n\n`.

**Blast radius:** `extract_examples()` only. Callers receive a (potentially longer) string — no type change, no schema change.

**Validation strategy:**
1. Re-parse `write_patterns` (known to have multiple examples)
2. Assert EXAMPLES section contains > 1 `TEST>` prompt
3. Re-parse `set_delay` (known missing) — should still return `""`
4. Re-parse 20 random commands, assert no regressions in EXAMPLES content

**Estimated regression risk:** Low. The `"\n\n".join()` over one element produces identical output to the old single-`<pre>` path. Zero semantic change for single-example commands.

---

## 3. Options Formatting

### F4 — Options Entries Lack Visual Separation

**Exact function:** `extract_options()` at line 77 — `return "\n".join(options)`.

**Current code (lines 50–78):**
```python
def extract_options(soup):
    arg_div = soup.find("div", class_="arguments-section")
    if not arg_div:
        return ""
    options = []
    dl = arg_div.find("dl")
    if dl:
        for dt in dl.find_all("dt"):
            opt = clean_text(dt)
            dd = dt.find_next_sibling("dd")
            desc = clean_text(dd) if dd else ""
            if opt:
                options.append(f"{opt} : {desc}")
    ul = arg_div.find("ul")
    if ul:
        for li in ul.find_all("li"):
            text = clean_text(li)
            if text:
                options.append(text)
    return "\n".join(options)
```

**Root cause:** Options are joined with a single `\n`. Each option block is typically 3–8 lines of prose, so adjacent option blocks appear as one continuous wall of text.

**Minimum deterministic fix:**
```python
    return "\n\n".join(options)   # was "\n".join(options)
```

**Lines changed:** 1 character (`"\n"` → `"\n\n"`).

**Blast radius:** `extract_options()` return value only. The extra blank line is purely cosmetic — downstream parsers that split on `\n` may see empty-string entries between options. If any downstream consumer iterates line-by-line without filtering blanks, this could be a regression.

**Validation strategy:**
1. Re-parse 3 commands with large option blocks (`write_patterns`, `set_delay`, `set_atpg`)
2. Verify OPTIONS section has blank lines between option entries
3. If a downstream consumer exists that reads options line-by-line, verify it handles blank lines
4. If no downstream consumer exists yet, note this in the fix commit

**Estimated regression risk:** Very low for human readability. Medium if a downstream script splits options on `\n` without filtering empty lines — but no such script is known to exist yet.

**Mitigation:** If blank-line sensitivity is a concern, use a visible separator instead:
```python
    return "\n---\n".join(options)   # unambiguous delimiter
```

---

## 4. Inline Formatting

### F5 — Inline Code Tags Stripped, Potential Text Smashing

**Exact function:** `clean_text()` at line 11–12 — the shared text extraction helper used by ALL extractors.

```python
def clean_text(el):
    return el.get_text(separator=" ", strip=True)
```

**Root cause:** `BeautifulSoup.get_text(separator=" ", strip=True)` inserts the separator between text nodes within the element. When adjacent `<code>` elements have no whitespace text node between them, the separator is still injected (because each `<code>` yields a text node). **This means the `separator=" "` already mitigates text-smashing in most cases.**

**Actual risk:** The real danger is when two `<code>` elements are separated by a punctuation text node like `</` or `|` that gets swallowed. Example:

```html
<code>stil</code>/<code>stil99</code>
```

Here `get_text(separator=" ")` would produce `"stil / stil99"` — note the spaces around `/`. This is readable but changes the original `stil/stil99` to `stil / stil99`. However, this is a cosmetic issue, not a correctness failure, and TetraMAX documentation is unlikely to use such dense formatting.

**Minimum fix:** This finding should be **verified before fixing**. The proposed approach if confirmed:

```python
def clean_text(el, preserve_inline=False):
    if not preserve_inline:
        return el.get_text(separator=" ", strip=True)
    # For inline-heavy content, insert space before/after code tags
    for code in el.find_all("code"):
        code.insert_before(" ")
        code.insert_after(" ")
    return el.get_text(separator=" ", strip=True)
```

**However:** This should only be implemented IF the validation sweep (F7) surfaces concrete examples of text smashing. The current `separator=" "` is likely sufficient.

**Blast radius:** If `clean_text()` signature changes, ALL extractors are affected. This is the highest-risk change. **Recommend deferring until evidence confirms the problem.**

**Validation strategy:**
1. Run F7 validation sweep
2. Scan for anomalous description/syntax/options strings that appear to have smashed words
3. Only proceed with fix if ≥ 5 concrete instances found

**Estimated regression risk:** Medium (shared helper, all extractors affected). Defer without confirmed evidence.

---

## 5. Validation/Reporting

### F7 — No Validation or Error Reporting Pass

**Exact function:** `main()` at lines 153–174. The only output is per-file `[OK]`/`[ERROR]` and a total count.

**Current state:** The parser is a pure extractor — it writes `.txt` files but never checks:
- Section presence (which of TITLE/DESCRIPTION/SYNTAX/OPTIONS/EXAMPLES exist per command)
- Content quality (description < 50 chars, syntax < 10 chars)
- Structural anomalies (options with no DT/DD pairs despite DL presence)

**Design:** This is a **new script**, not a parser modification. No existing code is mutated.

**Proposed script:** `validate_parsed_output.py`

```python
"""
validate_parsed_output.py — Section completeness and quality check
Reads all .txt files from parsed_html/, emits coverage CSV + anomaly log.
"""
import os, csv, sys

PARSED_DIR = "parsed_html"
OUTPUT_CSV = "DFT_FACTORY/reports/parser_coverage.csv"
ANOMALY_LOG = "DFT_FACTORY/reports/parser_anomalies.txt"

SECTIONS = ["TITLE", "DESCRIPTION", "SYNTAX", "OPTIONS", "EXAMPLES"]
MIN_DESC_LEN = 50
MIN_SYNTAX_LEN = 10

def parse_sections(filepath):
    """Parse a single .txt output file into its sections."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    sections = {}
    current_section = None
    current_lines = []

    for line in content.split("\n"):
        # Detect section header: "SECTION_NAME:"
        for sec in SECTIONS:
            if line.strip() == f"{sec}:":
                if current_section:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = sec
                current_lines = []
                break
        else:
            if current_section:
                current_lines.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections

def validate_all():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    files = sorted(f for f in os.listdir(PARSED_DIR) if f.endswith(".txt"))
    anomalies = []
    rows = []

    for fname in files:
        filepath = os.path.join(PARSED_DIR, fname)
        sections = parse_sections(filepath)
        command = fname.replace(".txt", "")

        present = {sec: (sec in sections and len(sections[sec]) > 0) for sec in SECTIONS}
        desc_len = len(sections.get("DESCRIPTION", ""))
        syntax_len = len(sections.get("SYNTAX", ""))

        issues = []

        # Quality checks
        if present["DESCRIPTION"] and desc_len < MIN_DESC_LEN:
            issues.append(f"SHORT_DESC({desc_len} chars)")
        if present["SYNTAX"] and syntax_len < MIN_SYNTAX_LEN:
            issues.append(f"SHORT_SYNTAX({syntax_len} chars)")

        # Missing section checks
        for sec in SECTIONS:
            if not present[sec]:
                issues.append(f"MISSING_{sec}")

        if issues:
            anomalies.append((command, issues))

        rows.append([
            command,
            present["TITLE"],
            present["DESCRIPTION"], desc_len,
            present["SYNTAX"], syntax_len,
            present["OPTIONS"],
            present["EXAMPLES"],
            ";".join(issues) if issues else "OK"
        ])

    # Write coverage CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["command", "has_title", "has_desc", "desc_len",
                      "has_syntax", "syntax_len", "has_options",
                      "has_examples", "issues"])
        w.writerows(rows)

    # Write anomaly log
    with open(ANOMALY_LOG, "w", encoding="utf-8") as f:
        f.write(f"Parser Anomaly Report — {len(anomalies)} files with issues\n")
        f.write(f"Total files scanned: {len(files)}\n")
        f.write("=" * 60 + "\n\n")
        for cmd, issues in sorted(anomalies):
            f.write(f"[{cmd}]\n")
            for issue in issues:
                f.write(f"  - {issue}\n")
            f.write("\n")

    # Summary to stdout
    print(f"Scanned: {len(files)} files")
    print(f"Anomalies: {len(anomalies)} files")
    print(f"Coverage CSV: {OUTPUT_CSV}")
    print(f"Anomaly log: {ANOMALY_LOG}")

    # Quick stats
    for sec in SECTIONS:
        count = sum(1 for r in rows if r[SECTIONS.index(sec) + 1])
        pct = count / len(rows) * 100 if rows else 0
        print(f"  {sec}: {count}/{len(files)} ({pct:.1f}%)")

if __name__ == "__main__":
    validate_all()
```

**Blast radius:** Zero. New file, no existing code modified.

**Validation strategy:** Run once. Manually review anomaly log for false positives (e.g., commands that legitimately have no EXAMPLES in source HTML). Tune thresholds if needed.

**Deliverables produced:**
- `DFT_FACTORY/reports/parser_coverage.csv` — per-command section presence matrix
- `DFT_FACTORY/reports/parser_anomalies.txt` — human-readable issue log

---

## Prioritized Implementation Sequence

| Step | Finding | Subsystem | Change | Risk | Impact |
|------|---------|-----------|--------|------|--------|
| **1** | F1 | Description | Decompose `span.section-label` in `extract_description()` | Near-zero | All 247 commands |
| **2** | F7 | Validation | Create `validate_parsed_output.py` (new file) | Zero (addition) | Quantifies F2/F3/F5 scope |
| **3** | F3 | Examples | `find("pre")` → `find_all("pre")` in `extract_examples()` | Low | Multi-example commands |
| **4** | — | — | **STOP. Read validation report. Decide if F2/F4/F5 are warranted.** | — | — |
| **5** | F2 | Examples | Add fallback class selector in `extract_examples()` | Low | Commands missing examples section |
| **6** | F4 | Options | `"\n"` → `"\n\n"` in `extract_options()` | Very low | All commands |
| **7** | F5 | Inline | Modify `clean_text()` with code-tag spacing | Medium | Only if F7 finds concrete instances |

---

## Decision Gate After Step 3

After Steps 1–3 are complete, the validation report will answer:

| Question | Informs |
|----------|---------|
| How many commands lack EXAMPLES? | Whether F2 is needed, or if those commands genuinely have no examples |
| How many commands have `SHORT_DESC`? | Whether the description extraction fix (F1) fully resolved extraction quality |
| Any text-smashing instances found? | Whether F5 is real or a false alarm |
| Any commands that fail to parse entirely? | Whether the parser has gaping structural coverage holes |

**Rule:** Do NOT proceed past Step 4 until the validation CSV is read and the numbers are known. Findings F2 and F5 were inferred from a 3-file sample — the 247-file sweep will confirm or refute them.

---

## Summary

| Metric | Value |
|--------|-------|
| Total parser functions touched | 2 (`extract_description`, `extract_examples`) |
| New files created | 1 (`validate_parsed_output.py`) |
| Total lines of code change | ~8 lines modified, ~100 lines added |
| Riskiest change | None — all changes are scoped, additive, or guarded by fallback paths |
| Validation gate | After Step 3 — read CSV before proceeding to F2/F4/F5 |
| Rollback strategy | Git revert per-step; each step is an independent commit |