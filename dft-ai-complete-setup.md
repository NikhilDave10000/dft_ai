# DFT AI Complete Setup Guide
## 100% Free · No Copy-Paste · No Server Modifications · Works Offline

---

## Architecture — Read This First

```
[ Local PC (RTX 3050 + i5) ]          [ Shared Remote EDA Server ]
  Ollama + Aider + APIs       --->          git pull
  (Writes Python / TCL)         Git         (Runs tmax / tessent)
                              <---          git push
```

**The Golden Rule:** AI software NEVER touches the remote EDA server.  
Code is written locally and moves to the server via Git only.

**Fallback Principle:** Local model = your safety net. Cloud models = bonus speed.  
If a cloud model rate-limits or fails, you always have Ollama running offline.

---

## Step 0 — Prerequisites

### 0.1 System Requirements
| Item | Minimum | Recommended |
|------|---------|-------------|
| OS | Windows 10 / Ubuntu 20.04 | Windows 11 / Ubuntu 22.04 |
| GPU | Any NVIDIA (4GB VRAM) | RTX 3050 (8GB VRAM) |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB free | 50 GB free |

### 0.2 Check Your GPU (Windows)
```powershell
nvidia-smi
# Look for "Memory-Usage" — you want at least 4GB free
```

### 0.3 Required Software (Install Before Continuing)
```bash
# Verify these are already installed:
git --version       # Git
python --version    # Python 3.10+
pip --version       # pip package manager
```

**Windows:** Download Git from https://git-scm.com and Python from https://python.org if missing.

### 0.4 Initialize Your DFT Project as a Git Repo
```bash
cd C:\path\to\your\dft_factory
git init
git add .
git commit -m "Initial commit"
```

---

## Step 1 — Install Ollama (Local AI Engine)

Ollama uses your RTX 3050 to run models privately, instantly, with no API limits.

**Windows:** Download the installer at https://ollama.com/download  
**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:
```bash
ollama --version
```

---

## Step 2 — Pull Local Coding Models

Choose based on your VRAM. For RTX 3050 (4–8 GB), use 7B models:

```bash
# Primary coding model — best for Python + TCL, your daily driver
ollama pull qwen2.5-coder:7b

# Backup coding model — good for architecture and refactoring
ollama pull deepseek-coder:6.7b

# General reasoning — useful for design decisions
ollama pull mistral:7b

# Confirm models are downloaded
ollama list
```

> **Why 7B?** These fit comfortably in 4–8 GB VRAM and run at ~30–40 tokens/sec locally.  
> qwen2.5-coder is currently the top small model for Python and TCL.

---

## Step 3 — Test Your Local AI

```bash
ollama run qwen2.5-coder:7b
```

At the prompt, type:
```
write a TCL proc that checks if a directory exists and prints a warning if not
```

If you get a sensible response → ✅ Local AI is working.  
Exit with `/bye`.

---

## Step 4 — Install Aider (Your Coding Interface)

Aider is the tool that replaces copy-pasting into browsers. It reads your **entire repo** and edits files directly from your terminal.

```bash
pip install aider-chat
```

Verify:
```bash
aider --version
```

> **Why Aider and NOT "openai-codex" / Codex CLI?**  
> A guide circulating online recommends `pip install openai-codex` with a `config.toml`.  
> That package and config format do not exist as described — it will not work.  
> Aider is actively maintained, battle-tested, and handles multi-file edits + auto Git commits natively.

---

## Step 5 — Get Free Cloud API Keys (Optional but Recommended)

Use cloud models when the local 7B isn't smart enough for complex architecture. All three below have generous free tiers.

### Key 1: Google Gemini — 1 Million Token Context
1. Go to https://aistudio.google.com
2. Click **Get API Key → Create API key in new project**
3. Copy key (starts with `AIza...`)

### Key 2: Groq — Ultra-Fast Large Models
1. Go to https://console.groq.com
2. Sign up → **Keys → Create API Key**
3. Copy key (starts with `gsk_...`)

### Key 3: OpenRouter — One Key for 100+ Models (Claude, GPT, Kimi, and more)
1. Go to https://openrouter.ai
2. Settings → API Keys → Create Key
3. Copy key (starts with `sk-or-v1-...`)

> OpenRouter gives you a single key that switches between Claude 3.5 Sonnet, GPT-4o,
> Kimi, GLM-4, Llama, and many more — without managing separate accounts.

---

## Step 6 — Configure API Keys on Your Local PC

Set these once per terminal session, or add them to your shell profile permanently.

**Command Prompt (Windows):**
```cmd
set GEMINI_API_KEY=AIza...your_key_here
set GROQ_API_KEY=gsk_...your_key_here
set OPENROUTER_API_KEY=sk-or-v1-...your_key_here
```

**PowerShell (Windows):**
```powershell
$env:GEMINI_API_KEY="AIza...your_key_here"
$env:GROQ_API_KEY="gsk_...your_key_here"
$env:OPENROUTER_API_KEY="sk-or-v1-...your_key_here"
```

**Linux / WSL (add to `~/.bashrc` for persistence):**
```bash
export GEMINI_API_KEY="AIza...your_key_here"
export GROQ_API_KEY="gsk_...your_key_here"
export OPENROUTER_API_KEY="sk-or-v1-...your_key_here"
```

---

## Step 7 — Connect Aider to Your DFT Factory

1. Open your terminal
2. Navigate to your project:
```bash
cd C:\path\to\your\dft_factory
```
3. Start Aider on your local GPU:
```bash
aider --model ollama/qwen2.5-coder:7b
```

You are now inside the Aider prompt. It has read your entire `dft_factory` codebase.

---

## Step 8 — (Optional) Add Continue.dev for VS Code

If you use VS Code, Continue.dev gives you AI inline in your editor with full project context — no terminal switching needed.

**Install:**
```
In VS Code → Ctrl+P → type:
ext install Continue.continue
```

**Configure (`~/.continue/config.json`):**
```json
{
  "models": [
    {
      "title": "Local Qwen Coder",
      "provider": "ollama",
      "model": "qwen2.5-coder:7b"
    },
    {
      "title": "Claude 3.5 Sonnet (via OpenRouter)",
      "provider": "openrouter",
      "model": "anthropic/claude-3.5-sonnet",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    {
      "title": "Gemini Pro",
      "provider": "openrouter",
      "model": "google/gemini-pro",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Autocomplete",
    "provider": "ollama",
    "model": "qwen2.5-coder:1.5b"
  }
}
```

**Usage inside VS Code:**
```
Ctrl+L         → Open Continue chat panel
Ctrl+I         → Inline AI edit on selected code
@codebase      → Search entire project for context
@diff          → Include current Git diff
@problems      → Include VS Code error panel
```

---

## Step 9 — Daily Workflow (The Core Loop)

### Switching Models Mid-Session in Aider

Start with local, switch to cloud when the task is too complex:

```text
# Switch to Gemini (best for reading 10+ files at once)
/model gemini/gemini-1.5-pro

# Switch to Groq (fast, complex logic)
/model groq/llama-3.1-70b-versatile

# Switch to Claude via OpenRouter (best architecture decisions)
/model openrouter/anthropic/claude-3.5-sonnet

# Switch back to local (fast, simple edits, free)
/model ollama/qwen2.5-coder:7b
```

If any cloud model fails or rate-limits → go back to local. Local never stops.

### Writing Code — Example Prompts

```text
> Read core/orch_run.py. The TCL header injection is missing the $TOP_MODULE 
  variable if --top-module is not passed. Fix this.

> I need to implement the TetraMAX Validator GAP 1 fix. Create a new file 
  core/tmax_validator.py and write the normalize_input() function to handle 
  command-flag merges using regex.

> Look at tcl/SYNOPSYS/_factory_helpers.tcl. Add error handling to the wrpt 
  proc so it prints a warning if $RPT_DIR does not exist.
```

Aider edits the files locally and shows you the diff.

### Committing Changes

```text
/commit
```

Aider stages the files and writes a Git commit message automatically.

### Other Useful Aider Commands

```text
/add core/harvest.py       → Add a file to the AI's context
/undo                      → Undo the last AI change
/drop                      → Drop all pending changes
/diff                      → Show what changed
/run python core/dir_init.py --help   → Run a command from inside Aider
```

---

## Step 10 — Deploy to Remote EDA Server

When your code is ready to test on real EDA tools:

**1. Push from your local PC:**
```bash
git push origin main
```

**2. SSH into the remote server:**
```bash
ssh your_user@shared_server
```

**3. Pull on the server:**
```bash
cd ~/dft_factory
git pull
```

**4. Execute your DFT runs:**
```bash
python core/dir_init.py \
  --design i2c_master \
  --tool SYNOPSYS \
  --stage ATPG \
  --exp SA_EXP1 \
  --sub E1.1 \
  --iter auto

python core/orch_run.py \
  --iter-path $FACTORY_ROOT/.../iter_001 \
  --tcl tcl/SYNOPSYS/my_atpg.tcl \
  --netlist ...
```

> The AI never touched the remote server. It only wrote Python and TCL locally.
> The server only sees clean, committed, tested code. ✅

---

## Troubleshooting

### Ollama models not loading / VRAM issues
```bash
# Check VRAM usage
nvidia-smi

# Switch to a smaller model
ollama pull qwen2.5-coder:1.5b
aider --model ollama/qwen2.5-coder:1.5b

# Force CPU fallback (slow but works)
OLLAMA_NUM_GPU=0 ollama serve
```

### Aider can't connect to Ollama
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Cloud API key errors in Aider
```bash
# Test OpenRouter key directly
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY"

# List available models in Aider
aider --list-models openrouter
```

### Aider changes broke something
```text
/undo      → Undoes last AI edit (Git-based, safe to use)
```

---

## Performance Tips (RTX 3050)

- Always use 7B models. 13B+ models will thrash VRAM and slow to a crawl.
- Close Chrome tabs and other GPU-heavy apps while Ollama is running.
- `qwen2.5-coder:7b` → best for Python and TCL edits (your primary tool).
- `mistral:7b` → better for reading long design docs and writing summaries.
- `deepseek-coder:6.7b` → good alternative when qwen gives a wrong answer.
- Tab autocomplete in Continue.dev uses `qwen2.5-coder:1.5b` — tiny and fast.

---

## Cheat Sheet

| Action | Command |
|--------|---------|
| Start local AI session | `aider --model ollama/qwen2.5-coder:7b` |
| Switch to Gemini (large context) | `/model gemini/gemini-1.5-pro` |
| Switch to Groq (fast logic) | `/model groq/llama-3.1-70b-versatile` |
| Switch to Claude (via OpenRouter) | `/model openrouter/anthropic/claude-3.5-sonnet` |
| Switch back to local | `/model ollama/qwen2.5-coder:7b` |
| Add a file to context | `/add core/harvest.py` |
| Commit AI changes | `/commit` |
| Undo last AI change | `/undo` |
| Drop all pending changes | `/drop` |
| Push to remote server | `git push origin main` |
| Pull on EDA server | `git pull` |
| Check GPU VRAM | `nvidia-smi` |
| List downloaded models | `ollama list` |

---

## What You Now Have

```
✔ Fully offline AI that never stops working       (Ollama + local 7B models)
✔ Cloud AI for complex tasks, free tier           (Gemini / Groq / OpenRouter)
✔ Multi-file code editing without copy-paste      (Aider)
✔ AI inside VS Code with project context          (Continue.dev)
✔ Automatic Git commits and clean history         (Aider /commit)
✔ Zero AI access to production EDA server         (Git-only code transport)
✔ No rate limits on local model                   (runs on your hardware)
```

---

## Optional Next Steps

- **Multi-agent workflows**: Use `pyautogen` to have multiple AI agents review each other's code (see Guide 1 for setup details).
- **Auto Git commit summaries**: Aider already does this — use `/commit` after every session.
- **Larger local models**: When you upgrade GPU to 16 GB VRAM, switch to `qwen2.5-coder:14b` for noticeably better quality.
- **RAG over your TCL/Python files**: `ollama pull nomic-embed-text` + Continue.dev's `@codebase` gives semantic search over your whole repo.
