import os
from bs4 import BeautifulSoup

# -------- CONFIG --------
INPUT_DIR = "/mnt/c/Nikhil/Synopsys/TetraMax_manual/TetraMax_manual/tmax_olh/tmax_olh/Content/tmax_cmds/tmax_cmds"
OUTPUT_DIR = "parsed_html"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_text(el):
    return el.get_text(separator=" ", strip=True)


def extract_description(soup):
    # First meaningful <p> after title
    p_tags = soup.find_all("p")
    for p in p_tags:
        text = clean_text(p)
        if len(text) > 20:  # skip trivial/empty lines
            return text
    return ""


def extract_syntax(soup):
    syntax_div = soup.find("div", class_="syntax-section")
    if not syntax_div:
        return ""

    pre = syntax_div.find("pre")
    if not pre:
        return ""

    raw = pre.get_text("\n", strip=True)

    # Split lines and clean
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    # Join into one line
    syntax = " ".join(lines)

    # 🔥 FIX: remove space before closing brackets
    syntax = syntax.replace(" ]", "]")

    return syntax


def extract_options(soup):
    arg_div = soup.find("div", class_="arguments-section")
    if not arg_div:
        return ""

    options = []

    # -------- DL STRUCTURE (PRIMARY) --------
    dl = arg_div.find("dl")
    if dl:
        for dt in dl.find_all("dt"):
            opt = clean_text(dt)

            dd = dt.find_next_sibling("dd")
            desc = clean_text(dd) if dd else ""

            if opt:
                options.append(f"{opt} : {desc}")

    # -------- UL FALLBACK --------
    ul = arg_div.find("ul")
    if ul:
        for li in ul.find_all("li"):
            text = clean_text(li)
            if text:
                options.append(text)

    return "\n".join(options)


def extract_examples(soup):
    ex_div = soup.find("div", class_="example-section")
    if not ex_div:
        return ""

    pre = ex_div.find("pre")
    if not pre:
        return ""

    return pre.get_text("\n", strip=True)


def parse_command(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f, "lxml")

    # Remove noise
    for tag in soup(["script", "style", "nav"]):
        tag.decompose()

    command = os.path.basename(file_path).replace("man_", "").replace(".htm", "")

    data = {
        "command": command,
        "title": "",
        "description": "",
        "syntax": "",
        "options": "",
        "examples": ""
    }

    # -------- TITLE --------
    h1 = soup.find("h1")
    if h1:
        data["title"] = clean_text(h1)

    # -------- DESCRIPTION --------
    data["description"] = extract_description(soup)

    # -------- SYNTAX --------
    data["syntax"] = extract_syntax(soup)

    # -------- OPTIONS --------
    data["options"] = extract_options(soup)

    # -------- EXAMPLES --------
    data["examples"] = extract_examples(soup)

    return data


def save_command(data):
    path = os.path.join(OUTPUT_DIR, f"{data['command']}.txt")

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"COMMAND: {data['command']}\n\n")

        if data["title"]:
            f.write("TITLE:\n" + data["title"] + "\n\n")

        if data["description"]:
            f.write("DESCRIPTION:\n" + data["description"] + "\n\n")

        if data["syntax"]:
            f.write("SYNTAX:\n" + data["syntax"] + "\n\n")

        if data["options"]:
            f.write("OPTIONS:\n" + data["options"] + "\n\n")

        if data["examples"]:
            f.write("EXAMPLES:\n" + data["examples"] + "\n\n")


def main():
    total = 0

    for file in os.listdir(INPUT_DIR):
        if not file.startswith("man_") or not file.endswith(".htm"):
            continue

        path = os.path.join(INPUT_DIR, file)

        try:
            data = parse_command(path)
            save_command(data)
            total += 1
            print(f"✅ Parsed: {data['command']}")
        except Exception as e:
            print(f"❌ Failed: {file} → {e}")

    print(f"\n🎯 TOTAL COMMANDS PARSED: {total}")


if __name__ == "__main__":
    main()
