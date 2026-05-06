#!/usr/bin/env python3

import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

DOCS_DIR = Path("/mnt/c/Nikhil/Synopsys/TetraMax_manual/TetraMax_manual/tmax_olh/tmax_olh/Content/tmax_cmds/tmax_cmds")
OUT = Path("tmax_graph.json")


def extract_flag(dt_text):
    m = re.match(r'(-[a-zA-Z_][a-zA-Z0-9_]*)', dt_text.strip())
    return m.group(1) if m else None


def clean_text(el):
    return el.get_text(separator=" ", strip=True)


def extract_dependencies(text):
    return list(set(re.findall(r'\b(set_[a-z0-9_]+|run_[a-z0-9_]+|report_[a-z0-9_]+)\b', text)))


def parse_page(path):
    soup = BeautifulSoup(open(path, encoding="utf-8", errors="ignore"), "html.parser")

    for tag in soup(["script", "style", "nav"]):
        tag.decompose()

    cmd = path.stem.replace("man_", "")

    # CATEGORY
    category = ""
    html_tag = soup.find("html")
    if html_tag and html_tag.get("data-mc-toc-path"):
    	category = html_tag["data-mc-toc-path"].split("|")[-1]

    # DESCRIPTION
    short_desc = ""
    short_div = soup.find("div", class_=lambda x: x and "short-description" in x)
    if short_div:
        short_desc = clean_text(short_div)

    # SYNTAX (canonical)
    syntax = ""
    syntax_div = soup.find("div", class_=lambda x: x and "syntax-section" in x)
    if syntax_div:
        pre = syntax_div.find("pre")
        if pre:
            raw = pre.get_text("\n", strip=True)
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            syntax = " ".join(lines).replace(" ]", "]")

    # OPTIONS (DICT)
    options = {}
    arg_div = soup.find("div", class_=lambda x: x and "arguments-section" in x)

    if arg_div:
        for dt in arg_div.find_all("dt"):
            flag = extract_flag(dt.get_text())
            if not flag:
                continue

            dd = dt.find_next_sibling("dd")
            desc = clean_text(dd) if dd else ""

            options[flag] = desc

    # FULL DESCRIPTION
    desc = ""
    desc_div = soup.find("div", class_=lambda x: x and "description-section" in x)
    if desc_div:
        desc = desc_div.get_text(separator=" ", strip=True)

    # EXAMPLES
    examples = ""
    ex_div = soup.find("div", class_=lambda x: x and "example-section" in x)
    if ex_div:
        examples = ex_div.get_text(separator="\n", strip=True)

    # RELATED
    related = set()
    nav = soup.find("nav", class_=lambda x: x and "related-links" in x)
    if nav:
        for a in nav.find_all("a", href=True):
            if a["href"].startswith("man_"):
                related.add(a["href"].replace("man_", "").replace(".htm", ""))

    # DEPENDENCIES
    deps = extract_dependencies(desc + " " + examples)

    return cmd, {
        "category": category,
        "syntax": syntax,
        "options": options,
        "description": desc or short_desc,
        "examples": examples,
        "related": sorted(related),
        "depends_on": sorted(set(deps) - {cmd})
    }


def main():
    graph = {"commands": {}, "categories": {}}

    files = sorted(DOCS_DIR.glob("man_*.htm"))
    print(f"Found {len(files)} files")

    for f in files:
        try:
            cmd, data = parse_page(f)
            graph["commands"][cmd] = data

            if data["category"]:
                graph["categories"].setdefault(data["category"], []).append(cmd)

        except Exception as e:
            print(f"ERROR {f.name}: {e}")

    with open(OUT, "w") as f:
        json.dump(graph, f, indent=2)

    print(f"✅ Built graph with {len(graph['commands'])} commands")


if __name__ == "__main__":
    main()
