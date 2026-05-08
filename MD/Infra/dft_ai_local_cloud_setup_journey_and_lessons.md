# DFT AI Engineering Stack — Full Journey, Lessons, Problems, and Final Workflow

## Overview

This document captures:

1. Everything set up from Step 0 onward
2. Problems encountered
3. What worked vs what failed
4. Differences from the original MD guide
5. Final stable workflow
6. Recommended next steps
7. Important lessons about local vs cloud AI

---

# STEP 0 — Initial Goal

Goal:

Build a repo-aware AI coding workflow for the DFT AI project using:

- Local LLMs
- Aider
- Ollama
- Cloud fallback models
- Git-integrated AI edits
- Future multi-model routing

Project:

```bash
/mnt/c/Nikhil/DFT/dft_ai
```

---

# STEP 1 — Git Initialization and GitHub Setup

## Actions Performed

Initialized Git repo and prepared for remote sync.

Commands used:

```bash
git init
git add .
git commit -m "Initial commit"
```

Connected GitHub remote.

Initial HTTPS authentication failed.

Errors seen:

```bash
remote: Invalid username or token.
Password authentication is not supported for Git operations.
```

and later:

```bash
403 Permission denied
```

---

# STEP 2 — SSH Authentication Setup

## Problem

GitHub removed password authentication.

HTTPS workflow was failing.

---

## Solution

Switched to SSH authentication.

Generated SSH key:

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

Added SSH public key to GitHub.

Changed remote URL:

```bash
git remote set-url origin git@github.com:NikhilDave10000/dft_ai.git
```

---

## Result

Successful push:

```bash
git push -u origin main
```

GitHub integration became stable.

---

# STEP 3 — Ollama Setup

## Installed/Verified Models

```bash
ollama list
```

Available models:

```text
qwen2.5-coder:7b-instruct-q4_K_M
deepseek-coder:6.7b
qwen2.5:14b-instruct-q4_K_M
nomic-embed-text
```

---

# STEP 4 — Understanding Local Model Reality

## Initial Assumption

Expected:

- local models to behave like ChatGPT/Claude
- autonomous coding agents
- perfect multi-file edits
- browser-quality reasoning

---

## Reality Learned

7B local models are best for:

- repo understanding
- code explanation
- helper generation
- regex/TCL snippets
- targeted edits
- offline coding assistance

They are weaker at:

- strict edit formatting
- massive refactors
- autonomous repo-wide reasoning
- long architectural planning

---

# STEP 5 — Aider Installation

Installed:

```bash
pip install aider-chat
```

Verified:

```bash
aider --version
```

Result:

```text
aider 0.86.2
```

---

# STEP 6 — First Aider Session

Started:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M
```

Aider successfully:

- scanned repo
- built repo-map
- connected Git
- loaded context
- supported /add
- supported /undo
- supported /diff

---

# STEP 7 — Understanding Repo-Aware AI

Added files:

```bash
/add build_graph.py semantic_graph.py validator.py validator_l2.py validator_l3.py validator_l4.py engine_rag.py preprocessor.py
```

Observed:

- AI could explain validator layers
- AI could trace command flow
- AI understood semantic validation
- AI understood layered architecture

This proved:

```text
repo-aware AI assistance was working
```

---

# STEP 8 — Problems with Aider Edit Format

## Observed Problem

When asking:

```text
Show exact code flow
```

or:

```text
Show full file exactly
```

local Qwen sometimes:

- hallucinated edits
- changed text unnecessarily
- generated malformed patches
- failed strict Aider formatting

Example issue:

```text
The LLM did not conform to the edit format.
```

---

# Important Realization

The problem was NOT:

- Aider
- Ollama
- Git
- repo loading

The problem was:

```text
small local model protocol reliability
```

---

# STEP 9 — Auto Undo and Git Safety

Observed important Aider features:

```bash
/undo
```

This:

- removed bad commits
- restored previous repo state
- made experimentation safe

This became a major workflow realization:

```text
AI coding is iterative and review-driven
```

NOT blind automation.

---

# STEP 10 — API Key Setup

Generated keys for:

- Gemini
- Groq
- OpenRouter

Configured persistent environment loading.

Added exports into:

```bash
venv/bin/activate
```

so that:

```bash
source venv/bin/activate
```

automatically loaded:

```bash
GEMINI_API_KEY
GROQ_API_KEY
OPENROUTER_API_KEY
```

---

# STEP 11 — LiteLLM Setup

Installed:

```bash
pip install 'litellm[proxy]'
```

Initially failed because:

```text
ModuleNotFoundError: apscheduler
```

Fixed by installing full proxy extras.

---

# STEP 12 — LiteLLM Routing Layer

Created:

```yaml
model_list:
  - model_name: fast
    litellm_params:
      model: ollama/qwen2.5-coder:7b-instruct-q4_K_M
      api_base: http://localhost:11434

  - model_name: smart
    litellm_params:
      model: gemini/gemini-2.5-pro
      api_key: os.environ/GEMINI_API_KEY

  - model_name: best
    litellm_params:
      model: openrouter/deepseek/deepseek-chat
      api_key: os.environ/OPENROUTER_API_KEY
      api_base: https://openrouter.ai/api/v1
```

---

# Important Architectural Shift

Original MD workflow:

```text
Aider → ONE model directly
```

New workflow built:

```text
Aider
  ↓
LiteLLM router
  ├── local qwen
  ├── Gemini
  ├── OpenRouter
  └── future providers
```

This was significantly more advanced.

---

# STEP 13 — Connecting Aider to LiteLLM

Correct command discovered:

```bash
aider --model openai/fast --openai-api-base http://localhost:8000 --openai-api-key dummy
```

Important discovery:

Aider requires:

```text
openai/
```

prefix when using LiteLLM proxy routing.

---

# STEP 14 — Gemini Problems

## What Worked

- routing worked
- authentication worked
- LiteLLM worked
- Aider worked

## What Failed

Gemini quota exhaustion.

Error:

```text
429 RESOURCE_EXHAUSTED
```

Important realization:

Infrastructure was correct.

Provider quota was the issue.

---

# STEP 15 — OpenRouter Problems

Initial model:

```text
anthropic/claude-3.5-sonnet
```

Failed because:

```text
model no longer available
```

Important realization:

Modern AI infrastructure changes rapidly.

Model IDs evolve constantly.

---

# STEP 16 — Successful Local Repo-Aware Workflow

Eventually achieved:

```text
Explain validator_l3.py line by line
```

Result:

- architecture tracing worked
- semantic understanding worked
- type checking analysis worked
- validator layering understood
- semantic warning logic understood

Most importantly:

Aider successfully:

- generated edits
- applied patch
- auto committed
- supported undo

---

# STEP 17 — Key Realizations About AI Engineering

## Browser AI vs Engineering AI

Browser AI:

```text
copy → ask → receive answer
```

Engineering AI:

```text
repo-aware
iterative
patch-based
Git-integrated
review-driven
```

---

# Biggest Mindset Shift

Expected:

```text
perfect autonomous AI engineer
```

Reality:

```text
collaborative AI engineering assistant
```

---

# What Actually Works Well RIGHT NOW

## Strong Use Cases

- repo explanation
- architecture tracing
- validator analysis
- TCL helper generation
- regex generation
- semantic checks
- helper functions
- targeted edits
- debugging assistance

---

# What Is Still Weak

## Weak Areas

- huge autonomous refactors
- perfect multi-file edits
- long-context architectural coherence
- frontier-model reasoning locally

---

# Differences From Original MD Guide

## Original MD Goal

Simple workflow:

```text
Aider → Ollama
```

Minimal setup.

---

# What Was Actually Built

Advanced orchestration:

```text
Aider
  ↓
LiteLLM
  ├── local models
  ├── Gemini
  ├── OpenRouter
  ├── future Groq
  ├── future Kimi
  └── future DeepSeek
```

This added:

- routing
- provider abstraction
- fallback infrastructure
- future scalability

But also introduced:

- provider debugging
- quota issues
- model naming issues
- routing complexity

---

# Current Recommended Workflow

## Stable Local Workflow

Use:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M
```

This is currently the most stable setup.

---

# Recommended Usage Pattern

## Use Local AI For

- explanations
- tracing
- validator logic
- TCL generation
- helper snippets
- quick edits
- offline coding

## Use Browser/Cloud AI For

- major architecture
- complex refactors
- deep reasoning
- frontier-quality planning

---

# Most Important Final Lessons

## 1. Local AI is real and useful

But not equivalent to frontier proprietary models.

---

## 2. Hybrid workflows are the future

Best setup:

```text
local + cloud together
```

NOT purely local.

---

## 3. Infrastructure complexity is real

Most YouTube demos hide:

- retries
- provider issues
- quotas
- routing problems
- protocol failures

---

## 4. Aider is review-first tooling

Workflow:

```text
ask
review diff
undo if needed
iterate
```

NOT blind automation.

---

# Final Current Architecture

```text
DFT Repo
   ↓
Aider
   ↓
Ollama local qwen
   ↓
Git-integrated edits
```

Optional advanced routing:

```text
Aider
  ↓
LiteLLM
  ├── local qwen
  ├── Gemini
  ├── OpenRouter
  ├── future Kimi
  ├── future Groq
  └── future DeepSeek
```

---

# Recommended Immediate Next Steps

## Priority 1

Become productive with:

```bash
aider --model ollama/qwen2.5-coder:7b-instruct-q4_K_M
```

on REAL DFT tasks.

---

## Priority 2

Gradually improve cloud routing:

- Groq
- DeepSeek
- Kimi
- OpenRouter

ONE provider at a time.

---

## Priority 3

Eventually integrate:

- Continue.dev
- VSCode inline AI
- advanced routing
- larger models
- better local hardware

---

# Final Conclusion

You did NOT fail.

You successfully:

- built a real local AI engineering workflow
- integrated repo-aware coding
- integrated Git-aware AI editing
- built multi-model routing infrastructure
- learned local vs cloud limitations
- understood practical AI engineering realities

This is already significantly beyond basic AI-tool usage.

