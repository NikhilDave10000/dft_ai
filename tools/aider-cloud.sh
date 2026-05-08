#!/bin/bash
# DFT AI — Cloud Model Session
#
# Routes Aider through LiteLLM → Gemini / OpenRouter / Groq.
#
# Why --edit-format diff works for cloud models:
#   Cloud models (Gemini 2.5 Pro, DeepSeek, Llama-3.1) have large context
#   windows and strong instruction-following. They reliably produce SEARCH/REPLACE
#   diff patches that Aider expects. Unlike 7B local models, they do not
#   mangle the diff syntax, so surgical edits (not whole-file rewrites) work.
#
# Usage: ./tools/aider-cloud.sh [aider args...]

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

# ── Check litellm binary exists ───────────────────────────────────
if ! command -v litellm > /dev/null 2>&1; then
    echo "❌ 'litellm' command not found."
    echo "   Install with: pip install 'litellm[proxy]'"
    echo "   (Note: 'pip install litellm' is NOT enough — proxy extras required)"
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

# Wait for proxy
echo "⏳ Waiting for proxy to be ready..."
for i in $(seq 1 10); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Proxy is up."
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Proxy failed to start."
        cleanup
        exit 1
    fi
    sleep 1
done

# ── Launch Aider (Cloud Model) ────────────────────────────────────
echo "☁️  Launching Aider — Cloud model (smart = Gemini 2.5 Pro)..."
aider --model openai/smart \
      --openai-api-base http://localhost:8000 \
      --openai-api-key dummy \
      --edit-format diff \
      --map-tokens 4096 \
      "$@"

# Cleanup is handled by trap on EXIT/INT/TERM
