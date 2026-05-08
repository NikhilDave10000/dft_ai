# DFT AI — Phase 2: Battle-Hardened Upgrades
## Built From Real Failures, Quota Exhaustions, and Production Lessons

---

## Why This Document Exists

The Phase 1 guide covers the happy path. This document covers **what actually happens**
when you run it — the 429 errors, the broken edit patches, the model IDs that silently
stopped working, and the architectural decisions that only reveal themselves after
hours of debugging.

Every section here maps to a specific real failure with a specific real fix.

---

## Critical Corrections to Phase 1

### Correction 1 — Model Naming: Quantization Is Not Optional

Phase 1 says:
```bash
ollama pull qwen2.5-coder:7b
```

This pulls a default quantization that may not be optimal. The model that actually runs
well on RTX 3050 with the best quality/speed balance is:

```bash
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

**What the suffix means:**
```
qwen2.5-coder  → model family
:7b            → parameter count
-instruct      → fine-tuned for instruction following (critical for Aider)
-q4_K_M        → 4-bit quantization, K-quant method, Medium quality
```

**Quantization quality ranking for RTX 3050:**
```
q8_0    → best quality, needs ~8 GB VRAM   (may not fit)
q4_K_M  → excellent quality, needs ~5 GB   ← USE THIS
q4_K_S  → slightly smaller, mild quality drop
q4_0    → baseline 4-bit, avoid if possible
q2_K    → lowest quality, avoid except for emergencies
```

Always use the `-instruct` variant. Base models (without `-instruct`) are pre-trained
but not fine-tuned for following instructions — they will produce poor Aider patches.

**Pull the correct versions:**
```bash
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
ollama pull deepseek-coder:6.7b-instruct-q4_K_M
```

Verify what you have:
```bash
ollama list
# NAME                                    ID            SIZE
# qwen2.5-coder:7b-instruct-q4_K_M       abc123...     4.7 GB
```

---

### Correction 2 — LiteLLM Install Fails Without Extras

Phase 1 says:
```bash
pip install litellm
```

This installs the base library but NOT the proxy server. When you run `litellm --config ...`
you will get:

```
ModuleNotFoundError: No module named 'apscheduler'
```

**Correct install:**
```bash
pip install 'litellm[proxy]'
```

This installs the proxy server with all required scheduler, telemetry, and routing
dependencies.

---

### Correction 3 — Aider + LiteLLM Requires `openai/` Prefix

Phase 1's LiteLLM section shows:
```bash
aider --model fast --openai-api-base http://localhost:8000
```

This will fail. Aider requires the `openai/` prefix to recognize that the model
should be routed through an OpenAI-compatible endpoint:

```bash
# WRONG
aider --model fast --openai-api-base http://localhost:8000

# CORRECT
aider --model openai/fast \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy
```

The `--openai-api-key dummy` is also required — Aider validates that a key string
exists even when talking to a local proxy that doesn't actually authenticate.

---

### Correction 4 — API Keys Belong in venv Activation, Not Shell Profile

Phase 1 suggests adding keys to `~/.bashrc` or PowerShell `$PROFILE`. This works but
leaks keys to every process in your shell session.

**Better: embed in venv activation so keys load only when the project venv is active:**

```bash
# Activate your project venv
source /mnt/c/Nikhil/DFT/dft_ai/venv/bin/activate

# Add keys to the bottom of the activate script
nano /mnt/c/Nikhil/DFT/dft_ai/venv/bin/activate
```

Add at the very bottom of `activate`:
```bash
# DFT AI keys — loaded only when this venv is active
export GEMINI_API_KEY="AIza...your_key_here"
export GROQ_API_KEY="gsk_...your_key_here"
export OPENROUTER_API_KEY="sk-or-v1-...your_key_here"
```

**Windows (venv\Scripts\activate.bat):**
```bat
@REM Add at the bottom of activate.bat
set GEMINI_API_KEY=AIza...your_key_here
set GROQ_API_KEY=gsk_...your_key_here
set OPENROUTER_API_KEY=sk-or-v1-...your_key_here
```

Now:
```bash
source venv/bin/activate    # loads Python AND all keys at once
deactivate                  # removes keys from environment
```

Keys never leak into sessions outside the project venv.

---

## Part 1 — Solving the #1 Real Failure: Aider Edit Format

This is the most important section in this document. The journey revealed:

```
"The LLM did not conform to the edit format"
```

This is not a bug. It is a design mismatch. Aider has multiple edit format protocols
and local 7B models cannot reliably produce all of them.

### Understanding Aider's Edit Formats

```
Format       | How It Works                          | Model Requirement
-------------|---------------------------------------|------------------
diff         | SEARCH/REPLACE blocks                 | Strict formatting, high token count
whole        | Outputs entire file                   | Simple, any model can do this
udiff        | Unified diff format                   | Very strict, best for large models
architect    | Two-model: plan + edit separately     | Best results, most powerful
```

### The Right Format for Each Model

```bash
# Local 7B — use 'whole' format. Simple. Reliable. Zero ambiguity.
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole

# Gemini 1.5 Pro — use 'diff'. It's smart enough to produce clean SEARCH/REPLACE.
aider --model gemini/gemini-1.5-pro \
      --edit-format diff

# Claude / DeepSeek (via OpenRouter) — use 'diff' or let Aider auto-detect
aider --model openai/best \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy
```

### `whole` vs `diff` — The Trade-off

```
whole:
  ✔ Never fails format checking
  ✔ Any model can do it
  ✔ Best for small/medium files
  ✗ Rewrites entire file even for 1-line change
  ✗ Higher token usage

diff (SEARCH/REPLACE):
  ✔ Surgical edits, only changes what's needed
  ✔ Faster for large files
  ✗ 7B models produce malformed patches ~30% of the time
  ✗ One wrong line in SEARCH block = entire patch fails
```

**Rule:** Use `whole` for local models. Use `diff` only for cloud models.

### Create Model-Specific Startup Scripts

Create `tools/aider-local.sh`:
```bash
#!/bin/bash
# Aider with local model — 'whole' format for reliability
source venv/bin/activate
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --no-auto-commits \
      --map-tokens 1024 \
      "$@"
```

Create `tools/aider-cloud.sh`:
```bash
#!/bin/bash
# Aider routed through LiteLLM — cloud models, diff format
source venv/bin/activate
litellm --config tools/litellm_config.yaml --port 8000 &
LITELLM_PID=$!
sleep 3
aider --model openai/smart \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy \
      --edit-format diff \
      "$@"
kill $LITELLM_PID
```

Make executable:
```bash
chmod +x tools/aider-local.sh tools/aider-cloud.sh
```

---

## Part 2 — Production-Grade LiteLLM Configuration

Phase 1's LiteLLM config has no fallback routing. When Gemini 429s, Aider just fails.
A production config handles this automatically.

### Full Production Config (`tools/litellm_config.yaml`):

```yaml
model_list:
  # ── LOCAL (always available, zero cost) ──────────────────────
  - model_name: fast
    litellm_params:
      model: ollama/qwen2.5-coder:7b-instruct-q4_K_M
      api_base: http://localhost:11434
      timeout: 120

  - model_name: local-large
    litellm_params:
      model: ollama/qwen2.5:14b-instruct-q4_K_M
      api_base: http://localhost:11434
      timeout: 180

  # ── GEMINI (1M token context) ─────────────────────────────────
  - model_name: smart
    litellm_params:
      model: gemini/gemini-2.5-pro
      api_key: os.environ/GEMINI_API_KEY
      timeout: 60

  # ── OPENROUTER MODELS (stable free/cheap tier) ────────────────
  - model_name: best
    litellm_params:
      model: openrouter/deepseek/deepseek-chat
      api_key: os.environ/OPENROUTER_API_KEY
      api_base: https://openrouter.ai/api/v1
      timeout: 60

  - model_name: fast-cloud
    litellm_params:
      model: openrouter/meta-llama/llama-3.1-8b-instruct:free
      api_key: os.environ/OPENROUTER_API_KEY
      api_base: https://openrouter.ai/api/v1
      timeout: 30

  # ── GROQ (ultra-fast) ─────────────────────────────────────────
  - model_name: turbo
    litellm_params:
      model: groq/llama-3.1-70b-versatile
      api_key: os.environ/GROQ_API_KEY
      timeout: 30

# ── FALLBACK ROUTING (the critical missing piece) ────────────────
router_settings:
  fallbacks:
    - smart:
        - best          # Gemini 429 → OpenRouter DeepSeek
        - fast          # OpenRouter fails → local qwen

    - best:
        - turbo         # OpenRouter fails → Groq
        - fast          # Groq fails → local

    - turbo:
        - fast          # Groq fails → local

  retry_policy:
    RateLimitError:
      num_retries: 2
      retry_after: 5   # wait 5 seconds between retries
    Timeout:
      num_retries: 2

  context_window_fallbacks:
    - smart:
        - best          # If prompt exceeds Gemini context → route to DeepSeek

# ── MONITORING ───────────────────────────────────────────────────
litellm_settings:
  success_callback: []
  failure_callback: []
  request_timeout: 120
  drop_params: true     # silently drop unsupported params per model
  cache: true           # cache identical requests (saves quota)
  cache_params:
    type: local         # no Redis needed, in-memory cache

# ── PROXY SERVER ─────────────────────────────────────────────────
general_settings:
  master_key: "sk-dft-local"      # a fake key for local auth
  port: 8000
  health_check_interval: 30
```

Start with:
```bash
litellm --config tools/litellm_config.yaml
```

Verify it's up:
```bash
curl http://localhost:8000/health
# {"status": "healthy", "router": "active"}
```

Check available models:
```bash
curl http://localhost:8000/v1/models | python -m json.tool
```

---

## Part 3 — Aider Architect Mode (Most Powerful Feature, Almost Nobody Uses It)

Architect mode uses **two models**:
- A smart "architect" model to plan what changes to make
- A fast "editor" model to actually write the code

This gives you frontier-quality reasoning at the planning stage, and fast/cheap
execution at the edit stage.

```bash
# Architect = Gemini plans. Editor = local qwen writes.
aider --architect \
      --model openai/smart \
      --editor-model openai/fast \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy
```

**What happens inside:**
```
You: "Refactor tmax_validator.py to split normalize_input into 3 sub-functions"

Architect (Gemini):
  "Here is the plan: extract _strip_flags(), _merge_continuations(), _validate_format()
   The main normalize_input() becomes an orchestrator that calls all three.
   Error handling moves to each sub-function..."

Editor (local qwen):
  [Generates the actual code edits following the architect's plan]
```

**This solves the edit format problem** because the editor model only needs to follow
specific code instructions from the architect — it doesn't need to reason about
architecture. The local model is much more reliable at execution than at planning.

Add to `tools/aider-architect.sh`:
```bash
#!/bin/bash
source venv/bin/activate
litellm --config tools/litellm_config.yaml --port 8000 --background
sleep 3
aider --architect \
      --model openai/smart \
      --editor-model openai/fast \
      --editor-edit-format whole \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy \
      "$@"
```

---

## Part 4 — Solving OpenRouter Model ID Instability

The journey learned: `anthropic/claude-3.5-sonnet` stopped working. Model IDs on
OpenRouter change because providers update, deprecate, or rename their models.

### Rule 1: Always Check Current Model Availability

```bash
# List all currently working free models on OpenRouter
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | \
  python3 -c "
import json, sys
models = json.load(sys.stdin)['data']
free = [m for m in models if m.get('pricing', {}).get('prompt') == '0']
for m in sorted(free, key=lambda x: x['id']):
    print(m['id'])
"
```

### Rule 2: Use Provider-Pinned IDs When Possible

OpenRouter supports provider pinning with `@` notation:
```
deepseek/deepseek-chat          → may route to any available DeepSeek version
deepseek/deepseek-chat@latest   → explicitly latest
```

### Rule 3: Keep a `tools/check_models.py` Script

```python
#!/usr/bin/env python3
"""
Run before any coding session to verify all configured models are responding.
Usage: python tools/check_models.py
"""
import os
import httpx
import json

MODELS_TO_CHECK = {
    "local/qwen":       ("http://localhost:11434/api/tags", None),
    "litellm/proxy":    ("http://localhost:8000/health", None),
    "openrouter":       ("https://openrouter.ai/api/v1/models",
                         os.getenv("OPENROUTER_API_KEY")),
    "gemini":           ("https://generativelanguage.googleapis.com/v1beta/models",
                         os.getenv("GEMINI_API_KEY")),
}

def check(name, url, key=None):
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        r = httpx.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            print(f"  ✅  {name}")
        else:
            print(f"  ❌  {name}  —  HTTP {r.status_code}")
    except Exception as e:
        print(f"  ❌  {name}  —  {e}")

print("\n=== DFT AI Model Health Check ===")
for name, (url, key) in MODELS_TO_CHECK.items():
    check(name, url, key)
print()

# Bonus: list available local models
try:
    r = httpx.get("http://localhost:11434/api/tags", timeout=5)
    models = r.json().get("models", [])
    print("Local models:")
    for m in models:
        size_gb = m.get("size", 0) / 1e9
        print(f"  • {m['name']}  ({size_gb:.1f} GB)")
except Exception:
    print("  Ollama not running — start with: ollama serve")
print()
```

Run before every session:
```bash
python tools/check_models.py
```

---

## Part 5 — Managing Context in Large DFT Repos

The 7B model has a context window of ~8,192 tokens. Your `dft_factory` repo likely has
thousands of files. Without management, Aider will either truncate context silently or
slow to a crawl building the repo-map.

### 5.1 — Create `.aiderignore`

Tell Aider to skip generated/irrelevant files:

```
# .aiderignore — place in repo root

# Generated outputs — never edit these
reports/
iter_*/
*.rpt
*.log
*.err

# Binary artifacts
*.spf
*.stil
*.fsdb
*.vcd

# Tool-generated TCL logs
synopsys_auto*
dc_shell.log

# Python cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# Virtual environment
venv/
.venv/

# IDE
.vscode/
.idea/
```

### 5.2 — Tune Repo-Map Token Allocation

Aider builds a "repo-map" — a compressed summary of every file in your project.
By default it uses 1,024 tokens for this. For a small focused session, reduce it
so more context space goes to actual code:

```bash
# For local model sessions (tight context)
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --map-tokens 512            # small repo-map, more room for actual code

# For cloud sessions (large context window)
aider --model openai/smart \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy \
      --map-tokens 4096           # large repo-map, Gemini can handle it
```

### 5.3 — Session Context Strategy

**Always start focused:**
```text
# Don't load everything — start with only the file you're working on
> /add core/tmax_validator.py
```

**Add related files progressively:**
```text
> /add core/exceptions.py
> /add tcl/SYNOPSYS/_factory_helpers.tcl
```

**Drop files you no longer need:**
```text
> /drop core/dir_init.py
```

**When the model starts giving wrong answers — clear and restart:**
```text
> /clear
```
`/clear` drops the entire conversation history but keeps loaded files. Use when
the model seems confused or is contradicting itself across responses.

**Check what's in context before asking:**
```text
> /tokens
# Shows how many tokens are being used by each file and the conversation
```

### 5.4 — `/ask` Mode vs Edit Mode

Aider has two operating modes:

```text
/ask   → AI responds with explanations and suggestions (NO file changes)
(none) → AI responds AND makes file edits
```

**Use `/ask` for:**
- Understanding code before touching it
- Architecture planning
- Debugging logic without changing files
- Getting a second opinion on your approach

```text
> /ask Explain the command-flag merge logic in normalize_input(). 
        What happens if a flag spans two list items?
```

**Then switch to edit mode only when you understand the plan:**
```text
> Fix the command-flag merge issue by adding a continuation check in normalize_input()
```

This pattern alone eliminates 80% of unwanted AI edits.

---

## Part 6 — Advanced Aider Flags for DFT Workflows

These flags are not in the official quickstart. They're discovered through use.

### `--read` — Include Files as Read-Only Context

Include `CONVENTIONS.md` or reference files that the AI should read but never edit:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --read CONVENTIONS.md \
      --read docs/dft_architecture.md \
      --edit-format whole
```

These files inform the AI's answers without being in the editable file set.

### `--no-auto-commits` — Review Before Every Commit

By default, Aider auto-commits every successful edit. During exploration sessions,
disable this and commit manually:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --no-auto-commits
```

Then when you're satisfied:
```text
> /commit  ← Commit with AI-generated message
```
or
```text
> /commit "CORE: fix normalize_input command-flag merge"  ← Your own message
```

### `--dry-run` — Preview Changes Without Applying

See the diff the AI wants to make before allowing it to write to disk:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --dry-run \
      --edit-format whole \
      core/tmax_validator.py
```

### `--subtree-only` — Limit Repo Scope to a Subdirectory

When working only on TCL files, tell Aider to only build a repo-map for `tcl/`:

```bash
cd dft_factory
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --subtree-only \
      --edit-format whole \
      tcl/SYNOPSYS/
```

### `--watch-files` — Auto-Detect File Changes

If you're also editing files in VS Code simultaneously, enable file watching so
Aider picks up your manual changes:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --watch-files
```

### `--input-history-file` — Persist Your Prompt History

All your Aider prompts are saved and searchable across sessions:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --input-history-file .aider_history.txt \
      --chat-history-file .aider_chat.md
```

Up-arrow to cycle through previous prompts. `.aider_chat.md` is a readable log of
every conversation.

---

## Part 7 — DFT-Specific Prompt Templates

These patterns consistently produce better results with local 7B models.
Store them in `tools/prompts/` as `.txt` files.

### Pattern 1: Targeted File Edit

```
Read {filename}.
The problem is: {one-sentence description}.
Do not touch anything outside {function_name}().
Preserve all comments.
Fix only this: {exact description of the fix}.
```

Example:
```text
Read core/orch_run.py.
The problem is: TCL header injection missing $TOP_MODULE when --top-module is not passed.
Do not touch anything outside inject_tcl_header().
Preserve all comments.
Fix only this: add a guard that substitutes an empty string if top_module is None.
```

### Pattern 2: New Function Creation

```
Create a new function {name}() in {filename}.
Purpose: {one-sentence description}.
Inputs: {list of inputs with types}.
Returns: {return value description}.
Error handling: raise {ExceptionType} if {condition}.
Do not modify any existing functions.
```

### Pattern 3: TCL Proc Hardening

```
Read {tcl_file}.
Look at the proc {proc_name}.
Add a guard at the top of the proc that:
  1. Checks if $RPT_DIR exists
  2. If not: prints a warning using puts stderr
  3. Returns -1 from the proc
Do not change any other logic in the proc.
```

### Pattern 4: Explanation Before Edit

```
/ask Walk me through exactly what happens when normalize_input() receives 
     a list where a command flag is split across index 3 and 4.
     Trace step by step. Do not suggest changes yet.
```

Then after understanding:
```
Now fix the split-flag case. The fix should be in the _merge_continuations() 
helper that you described. Keep all existing logic intact.
```

### Pattern 5: Cross-File Tracing

```
/add core/orch_run.py core/dir_init.py tcl/SYNOPSYS/_factory_helpers.tcl

/ask Trace what happens to the $TOP_MODULE variable from when orch_run.py 
     calls dir_init.py all the way to when it appears in the TCL header.
     Show every point where it's passed, modified, or could be undefined.
```

---

## Part 8 — The Mental Model: Collaborative Assistant, Not Agent

This section covers the deepest lesson from the journey document and the one most
tutorials get completely wrong.

### What You Expected

```
You: "Refactor my entire DFT factory codebase to support parallel ATPG runs"
AI:  [autonomously redesigns 20 files, tests everything, opens a PR]
```

### What Actually Exists

```
You: "Read orch_run.py. What's the current call chain for parallel execution?"
AI:  [explains the current structure clearly]

You: "Where would I add worker pool logic without breaking the iter directory structure?"
AI:  [suggests 2 clean insertion points]

You: "Add a basic ThreadPoolExecutor wrapper around the main run loop at that point"
AI:  [edits exactly that section]

You: /diff     [review]
You: /commit   [if good] or /undo [if wrong]
```

### The Correct Mental Model

```
AI role:        Extremely fast, knowledgeable pair programmer
                Never the driver — always the navigator

Your role:      Decision maker, reviewer, architecture owner
                You accept or reject every change

Workflow loop:  Ask → Understand → Small targeted prompt → Review diff → Accept/Undo
```

### Decision Tree: Which Mode to Use

```
Task Type                              → Mode
─────────────────────────────────────────────────────────────────────
"I don't understand this code"         → /ask (local model)
"Is this approach correct?"            → /ask (local model)
"What could go wrong with this?"       → /ask (local or cloud)
"Fix this one specific thing"          → Edit mode (local model)
"Write this new small function"        → Edit mode (local model)
"Refactor this whole module"           → Architect mode (cloud planner + local editor)
"Design a new subsystem from scratch"  → Browser Claude/ChatGPT first, then Aider to implement
"Debug a complex multi-file issue"     → /ask cloud first, then targeted edit
```

### What Local 7B Does Well (use it here)

```
✔ Explain any code clearly
✔ Trace variable flow across functions
✔ Generate regex patterns
✔ Write TCL procs with specific behavior
✔ Add error handling to existing functions
✔ Write Python helper functions < 50 lines
✔ Write pytest tests for specific functions
✔ Rename variables consistently in one file
✔ Add docstrings and comments
```

### What Local 7B Does Poorly (use cloud or don't automate)

```
✗ Autonomous multi-file refactors
✗ Maintaining consistency across 10+ file changes
✗ Novel algorithmic design
✗ Long-context architectural coherence (> 4K tokens of conversation)
✗ Detecting subtle logic bugs in complex flow
✗ Self-correcting after a wrong first attempt
```

---

## Part 9 — Session Logging and Audit Trail

Every AI edit to your DFT code should be reviewable. Set up a full audit trail.

### 9.1 — Aider's Built-in History

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --input-history-file .aider/.history \
      --chat-history-file .aider/chat_$(date +%Y%m%d).md
```

Add to `.gitignore`:
```
.aider/
```

### 9.2 — Git Log as the Real Audit Trail

Every Aider commit shows which model made the change in the commit message.
View all AI-generated commits:

```bash
git log --oneline | grep -i "aider\|ai\|fix\|refactor"
```

View what changed in any AI commit:
```bash
git show abc123f
```

Revert a specific AI commit without undoing later work:
```bash
git revert abc123f --no-edit
```

### 9.3 — Weekly Snapshot Script

Create `tools/snapshot.sh` — run at end of each week:

```bash
#!/bin/bash
# Weekly DFT AI session summary

DATE=$(date +%Y%m%d)
REPORT="reports/ai_session_$DATE.md"

mkdir -p reports

cat > $REPORT << EOF
# DFT AI Session Summary — $DATE

## Commits This Week
\`\`\`
$(git log --oneline --since="7 days ago")
\`\`\`

## Files Changed
\`\`\`
$(git diff --name-only HEAD~$(git log --oneline --since="7 days ago" | wc -l) HEAD)
\`\`\`

## Lines Added / Removed
\`\`\`
$(git diff --stat HEAD~$(git log --oneline --since="7 days ago" | wc -l) HEAD)
\`\`\`
EOF

echo "Snapshot saved to $REPORT"
```

---

## Part 10 — The Correct Daily Startup Sequence

This sequence is what an experienced practitioner actually runs, not the happy-path
sequence from tutorials.

```bash
# 1. Activate environment (loads keys automatically)
source venv/bin/activate          # Linux/WSL
# OR
venv\Scripts\activate             # Windows CMD

# 2. Verify everything is up (30 seconds)
python tools/check_models.py

# 3. Check what Ollama has loaded
ollama list

# 4. Start Ollama if not running
ollama serve &

# 5. Navigate to project
cd /mnt/c/Nikhil/DFT/dft_ai

# 6. Quick git sync
git pull origin main              # get any changes from last session

# 7. Choose your session type based on today's task:

# SIMPLE EDITS → local model only
./tools/aider-local.sh

# COMPLEX ARCHITECTURE → architect mode
./tools/aider-architect.sh

# LARGE CONTEXT (reading 10+ files) → LiteLLM + Gemini
./tools/aider-cloud.sh
```

---

## Part 11 — Ollama Model Update Discipline

Models on Ollama are updated regularly. The same tag (`:7b-instruct-q4_K_M`) may
point to a newer version. Pull updates monthly:

```bash
# Update all currently pulled models
ollama list | awk 'NR>1 {print $1}' | xargs -I{} ollama pull {}
```

After an update, test that Aider still works:
```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M \
      --edit-format whole \
      --message "Write a one-line Python function that returns True if a path exists" \
      --yes
```

If the edit format regresses after an update, pin to a specific SHA:
```bash
# Get the current model digest
ollama show qwen2.5-coder:7b-instruct-q4_K_M --modelfile | grep FROM

# Pull a specific version (if Ollama supports digest pinning for that model)
# Otherwise: keep a local copy of the modelfile before updating
ollama show qwen2.5-coder:7b-instruct-q4_K_M --modelfile > tools/qwen_modelfile_backup.txt
```

---

## Part 12 — The Upgrade Path: What To Build Next

Based on where the journey ended, here is the sequenced next-steps roadmap — ordered
by impact vs complexity:

```
Priority  Upgrade                         Effort   Impact
────────────────────────────────────────────────────────────────────────
1         Add .aiderignore                5 min    High — stops AI touching generated files
2         Switch to --edit-format whole   2 min    High — eliminates edit format failures
3         Move keys to venv activate      10 min   Medium — cleaner security model
4         Add check_models.py script      20 min   Medium — catch failures before session
5         LiteLLM fallback routing        30 min   High — auto-recovery on 429 errors
6         CONVENTIONS.md + --read flag    20 min   High — AI learns your project rules
7         Architect mode                  15 min   High — frontier reasoning + local editing
8         .aider_history persist          5 min    Low — quality-of-life
9         Pre-push hook                   15 min   Medium — catch bugs before push
10        Weekly snapshot script          15 min   Low — visibility into AI productivity
────────────────────────────────────────────────────────────────────────
```

**Start with Priority 1–3 today.** They are the highest-impact, lowest-effort changes
and directly fix the failures documented in the journey.

---

## Summary: What Changed Between Phase 1 and Reality

```
Phase 1 Assumption                  →  Reality
──────────────────────────────────────────────────────────────────────────────
pip install litellm works           →  Needs 'litellm[proxy]'
aider --model fast (LiteLLM)        →  Needs openai/fast prefix + dummy key
ollama pull qwen2.5-coder:7b        →  Use qwen2.5-coder:7b-instruct-q4_K_M
Local 7B = reliable patch format    →  Use --edit-format whole
Gemini always available             →  429s hit; need fallback routing
OpenRouter claude-3.5-sonnet works  →  Model ID changed; check availability first
Keys in .bashrc                     →  Keys in venv/bin/activate is cleaner
AI makes changes, you run them      →  AI assists, you review every diff, /undo freely
One model for everything            →  architect (cloud) + editor (local) is the pattern
```
