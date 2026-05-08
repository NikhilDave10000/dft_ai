#!/usr/bin/env python3
"""
DFT AI — Model Health Check
Run before any coding session to verify all configured backends are responding.

Usage:
    python tools/check_models.py
    python tools/check_models.py --verbose
"""

import os
import sys
import argparse
import httpx

# ── Backends to check ───────────────────────────────────────────────
# Each entry: (display_name, url, headers_factory, check_fn)
# check_fn(response) -> (ok: bool, detail: str)

TIMEOUT = 8


def check_ollama():
    """Check Ollama local server and list available models."""
    url = "http://localhost:11434/api/tags"
    try:
        r = httpx.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        data = r.json()
        models = data.get("models", [])
        if not models:
            return True, "running (no models pulled)"
        lines = [f"{m['name']} ({m.get('size', 0)/1e9:.1f} GB)" for m in models]
        return True, "running\n  Local models:\n    • " + "\n    • ".join(lines)
    except httpx.ConnectError:
        return False, "not running — start with: ollama serve"
    except Exception as e:
        return False, str(e)


def check_litellm_proxy(port=8000):
    """Check if LiteLLM proxy is running and list models."""
    url = f"http://localhost:{port}/health"
    try:
        r = httpx.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            # Also try to list models
            m = httpx.get(f"http://localhost:{port}/v1/models", timeout=TIMEOUT)
            if m.status_code == 200:
                data = m.json()
                model_list = data.get("data", [])
                names = [x.get("id", "?") for x in model_list]
                return True, f"healthy\n  Models: {', '.join(names) if names else '(none configured)'}"
            return True, "healthy (model list unavailable)"
        return False, f"HTTP {r.status_code}"
    except httpx.ConnectError:
        return False, f"not running on port {port} — start with: litellm --config tools/litellm_config.yaml"
    except Exception as e:
        return False, str(e)


def check_openrouter():
    """Check OpenRouter API availability."""
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        return False, "OPENROUTER_API_KEY not set"
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        r = httpx.get(url, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            return True, "API reachable"
        elif r.status_code == 401:
            return False, "unauthorized — check OPENROUTER_API_KEY"
        elif r.status_code == 429:
            return False, "rate limited (429)"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


def check_gemini():
    """Check Gemini API availability."""
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return False, "GEMINI_API_KEY not set"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        r = httpx.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return True, "API reachable"
        elif r.status_code == 400:
            return False, "bad request — check GEMINI_API_KEY format"
        elif r.status_code == 403:
            return False, "forbidden — invalid API key"
        elif r.status_code == 429:
            return False, "rate limited (429)"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


def check_groq():
    """Check Groq API availability."""
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return False, "GROQ_API_KEY not set (optional)"
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        r = httpx.get(url, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            return True, "API reachable"
        elif r.status_code == 401:
            return False, "unauthorized — check GROQ_API_KEY"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


# ── Main check table ────────────────────────────────────────────────

CHECKS = [
    ("Ollama (local)",        check_ollama),
    ("LiteLLM Proxy :8000",   lambda: check_litellm_proxy(8000)),
    ("LiteLLM Proxy :8082",   lambda: check_litellm_proxy(8082)),  # free-claude-code default
    ("OpenRouter",            check_openrouter),
    ("Gemini",                check_gemini),
    ("Groq (optional)",       check_groq),
]


def main():
    parser = argparse.ArgumentParser(description="DFT AI Model Health Check")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full error details")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  DFT AI — Model Health Check")
    print("=" * 60)

    results = []
    for name, check_fn in CHECKS:
        ok, detail = check_fn()
        results.append((name, ok, detail))
        status = "✅" if ok else "❌"
        print(f"\n  {status}  {name}")
        if detail:
            for line in detail.split("\n"):
                print(f"      {line}")

    print("\n" + "-" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"  Result: {passed}/{total} backends reachable")
    if passed < total:
        print("  ⚠️  Fix unreachable backends before starting your session")
    else:
        print("  ✅  All backends healthy — ready to code")
    print("-" * 60 + "\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
