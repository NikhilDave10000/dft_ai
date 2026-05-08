#!/bin/bash
# DFT AI — Architect Mode
#
# How it works:
#   - Architect model (Gemini via LiteLLM / openai/smart):
#       A large-context cloud model that plans WHAT changes to make.
#       It reasons about architecture, cross-file impact, and design.
#   - Editor model (Qwen via Ollama / openai/fast):
#       A local 7B model that executes the architect's plan as code edits.
#   - --editor-edit-format whole:
#       Local 7B models cannot reliably produce SEARCH/REPLACE diff patches.
#       "whole" sends the entire file back, which any model can do.
#       The architect's plan removes the need for the editor to reason — only execute.
#
# Usage: ./tools/aider-architect.sh [aider args...]

set -e

# ── Cleanup handler ────────────────────────────────────────────────
cleanup() {
    if [ -n "$LITELLM_PID" ] && kill -0 "$LITELLM_PID" 2>/dev/null; then
        echo "🛑 Shutting down LiteLLM proxy (PID $LITELLM_PID)..."
        kill "$LITELLM_PID" 2>/dev/null
        wait "$LITELLM_PID" 2>/dev/null
    fi
}
trap cleanup EXIT INT TERM

# ── Activate venv ──────────────────────────────────────────────────
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
else
    echo "❌ venv not found. Run from project root or ensure venv/ exists."
    exit 1
fi

# ── LiteLLM config ─────────────────────────────────────────────────
LITELLM_CONFIG="tools/litellm_config.yaml"
if [ ! -f "$LITELLM_CONFIG" ]; then
    echo "❌ $LITELLM_CONFIG not found."
    exit 1
fi

# ── Port 8000 collision check ─────────────────────────────────────
if lsof -i :8000 > /dev/null 2>&1 || netstat -an 2>/dev/null | grep -q ':8000.*LISTEN'; then
    echo "❌ Port 8000 is already in use."
    echo "   Process occupying port 8000:"
    lsof -i :8000 2>/dev/null || netstat -an 2>/dev/null | grep ':8000'
    echo ""
    echo "   Fix: Either kill the occupying process, or change the port in:"
    echo "     $LITELLM_CONFIG"
    echo "     and update --openai-api-base in this script."
    exit 1
fi

# ── Start LiteLLM proxy ───────────────────────────────────────────
echo "🚀 Starting LiteLLM proxy (background)..."
litellm --config "$LITELLM_CONFIG" --port 8000 &
LITELLM_PID=$!

# Wait for proxy to be ready
echo "⏳ Waiting for proxy to be ready..."
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Proxy is up."
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Proxy failed to start within 10 attempts."
        cleanup
        exit 1
    fi
    sleep 1
done

# ── Launch Aider (Architect Mode) ─────────────────────────────────
echo "🧠 Launching Aider — Architect mode (Gemini plans, Qwen edits)..."
aider --architect \
      --model openai/smart \
      --editor-model openai/fast \
      --editor-edit-format whole \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy \
      "$@"

# Cleanup is handled by trap on EXIT/INT/TERM
