# TASK_HTML_PARSER_FINDINGS.md

## Findings from Representative Output Audit

**Date:** 2026-05-09
**Auditor:** Claude (session continuation — prior session read parser + representative outputs)
**Files Audited:** `write_patterns.txt`, `set_delay.txt`, `set_atpg.txt`

---

## Finding 1 — Description Label Bleed (CRITICAL)

**Symptom:** The word "Description" appears verbatim at the start of the extracted description text.

**Evidence:**
- `write_patterns.txt` line 7: `Description Use this command to write ATPG patterns...`
- `set_delay.txt` line 7: `Description Use this command to specify options for transition fault...`

**Root Cause:** The `extract_description()` function targets `<div class="description-section">` but does not exclude the `<span class="section-label">Description</span>` child element within that div. The label text node is being concatenated into the output.

**Affected Commands:** All 247 commands where a `description-section` div contains a `section-label` span.

**Fix:** Add a step to skip or strip the `section-label` span's text content before extracting the remaining text from `description-section`.

---

## Finding 2 — Missing EXAMPLES Section (HIGH)

**Symptom:** `set_delay.txt` has no EXAMPLES section at all. File ends after OPTIONS.

**Evidence:**
- `set_delay.txt` terminates at line 96 with the last option entry (`-launch_cycle`). No EXAMPLES header or content follows.
- `write_patterns.txt` does have EXAMPLES but only a single entry (line 194-196).

**Root Cause (likely):** The parser's `extract_examples()` function expects the examples content to be within the same structural pattern as other sections, but the examples section in the source HTML may use a different DOM structure (e.g., `<pre>` blocks inside `<div class="example">` rather than `<div class="examples-section">`). The parser either does not find the section at all or finds only a partial match.

**Affected Commands:** Unknown count — needs a full sweep to determine how many parsed files lack EXAMPLES.

**Fix:** Inspect the actual HTML DOM for `set_delay` and similar commands to understand the examples section structure, then adapt `extract_examples()` to handle that pattern.

---

## Finding 3 — EXAMPLES Section Truncation (HIGH)

**Symptom:** `write_patterns.txt` shows only a single example entry despite the source HTML likely containing many.

**Evidence:**
- `write_patterns.txt` lines 194-196: Only one example (`TEST> write_patterns pat.bin ...`).
- Commands like `write_patterns` typically have 3-10 examples in TetraMAX docs.

**Root Cause:** The parser may be extracting only the first `<pre>` or `<div>` child of the examples section, or the HTML markup nests examples in a way the current selector does not traverse (e.g., examples wrapped in individual `<div class="example-panel">` wrappers).

**Affected Commands:** All commands with multiple examples.

**Fix:** Update `extract_examples()` to iterate over all child elements within the examples section container rather than stopping at the first match.

---

## Finding 4 — Options Separator Smearing (MEDIUM)

**Symptom:** Option entries in the OPTIONS section run together with no blank-line separation between distinct options.

**Evidence:**
- `write_patterns.txt` OPTIONS section (lines 38-191): Each option block ends and the next begins with no visual gap. The boundary between `-cellnames` and `-compress` (line 59) reads as continuous prose rather than discrete entries.
- `set_delay.txt` OPTIONS section (lines 14-96): Same behavior — options are a monolithic text block.

**Root Cause:** The parser extracts option text as a single concatenated string from all `<dt>`/`<dd>` pairs without injecting a separator (e.g., double newline or horizontal rule) between option entries. The raw HTML likely uses `<dl>` lists; the parser flattens them.

**Impact:** Readability is degraded but not correctness-critical if downstream tools parse option boundaries independently.

**Fix:** Insert `\n\n` between each `<dt><dd>` pair when building the options output.

---

## Finding 5 — Inline Code/Emphasis Tags May Be Stripped (LOW)

**Symptom:** In some description and option texts, formatted tokens (e.g., `<code>`, `<b>`, `<i>`) may be stripped of their delimiters, causing text to run together.

**Evidence (suspected):**
- `write_patterns.txt` line 9: `FTDL, STIL, TDL91, TSTL2, WGL, WGL_FLAT` — if these were individually backtick-wrapped in the source, the backticks are gone. The list reads correctly here, but in cases where formatting was the only separator, removal could cause word smashing.

**Root Cause:** `BeautifulSoup.get_text()` with default settings strips all HTML tags and concatenates text nodes directly. If the original used `<code>` tags as visual separators (e.g., `<code>stil</code><code>stil99</code>` → `stilstil99`), the separator is lost.

**Impact:** Low for most commands but could produce confusing output for commands with dense inline formatting.

**Fix:** Add a post-processing pass to insert a space between adjacent inline-code tokens where the original HTML had sibling `<code>` elements.

---

## Finding 6 — No Blank Line After TITLE Before DESCRIPTION (LOW)

**Symptom:** The TITLE section ends and DESCRIPTION begins with no blank line separation, but other section transitions (DESCRIPTION → SYNTAX, SYNTAX → OPTIONS) are clean.

**Evidence:**
- `write_patterns.txt` lines 3-7: `TITLE:\nwrite_patterns\n\nDESCRIPTION:\nDescription Use this command...`
  - TITLE content (`write_patterns`) ends at line 4. Line 5 is blank. Line 6 is `DESCRIPTION:`. This is actually correct — one blank line between sections.

*Retracted:* On closer inspection, section separation is consistent — one blank line between each section boundary. Finding downgraded to an observation for the coverage sweep.

---

## Finding 7 — No Validation or Error Reporting in Current Parser (MEDIUM)

**Symptom:** The parser produces output files but never reports:
- Which sections were found vs. missing per command
- Which commands failed to parse entirely
- Content-length anomalies (e.g., description shorter than 20 chars)

**Root Cause:** `parse_html_structured.py` is a pure extractor — no validation pass exists. The task file correctly identifies this gap as "Next Step 1."

**Fix:** Create a separate `validate_parser.py` script that:
1. Loads every `.txt` in `parsed_html/`
2. Checks for presence of each expected section header (TITLE, DESCRIPTION, SYNTAX, OPTIONS, EXAMPLES)
3. Flags any file missing a section
4. Flags any description < 50 chars (likely extraction failure)
5. Emits a CSV/JSON coverage report

---

## Summary

| # | Finding | Severity | Estimated Impact |
|---|---------|----------|------------------|
| 1 | "Description" label bleeds into description text | CRITICAL | All 247 commands |
| 2 | Missing EXAMPLES section in some commands | HIGH | Unknown subset |
| 3 | EXAMPLES section truncated to single entry | HIGH | All multi-example commands |
| 4 | Options entries lack visual separation | MEDIUM | All commands |
| 5 | Inline code tags stripped without separator | LOW | Commands with dense formatting |
| 6 | Section separation is consistent (no issue) | NONE | 0 commands |
| 7 | No validation/error-reporting pass exists | MEDIUM | All 247 commands |

## Recommended Fix Order

1. **Fix Finding 1 first** — single-line change in `extract_description()`, maximum blast radius payoff
2. **Build Finding 7 next** — validation script to quantify Findings 2, 3, 5 across all 247 commands
3. **Fix Finding 3** — iterate over all examples children
4. **Fix Finding 2** — adapt examples extraction for missing-section cases
5. **Fix Finding 4** — add separator injection in options extraction
6. **Fix Finding 5** — add space insertion between sibling inline-code elements