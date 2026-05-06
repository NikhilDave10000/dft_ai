import re

def normalize_input(cmd: str, known_flags=None):

    if not cmd:
        return cmd

    # Fix "\" continuation (GAP 3 & 5)
    cmd = cmd.replace("\\\n", " ")
    cmd = cmd.replace("\\", " ")

    # Normalize whitespace
    cmd = re.sub(r"\s+", " ", cmd)

    # Fix spacing around braces (GAP 4)
    cmd = re.sub(r"(\S)\{", r"\1 {", cmd)
    cmd = re.sub(r"\}(\S)", r"} \1", cmd)

    # Fix command-flag merge (GAP 1)
    cmd = re.sub(r"([a-zA-Z_]+)-([a-zA-Z_]+)", r"\1 -\2", cmd)

    # Fix value-flag merge (GAP 2)
    if known_flags:
        tokens = cmd.split()
        fixed = []

        for tok in tokens:
            split = False
            for flag in known_flags:
                if tok.endswith(flag) and tok != flag:
                    val = tok[:-len(flag)]
                    if val:
                        fixed.append(val)
                    fixed.append(flag)
                    split = True
                    break
            if not split:
                fixed.append(tok)

        cmd = " ".join(fixed)

    return cmd.strip()