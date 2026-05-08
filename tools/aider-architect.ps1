# DFT AI — Architect Mode (Windows PowerShell)
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
# Usage: .\tools\aider-architect.ps1 [aider args...]

$ErrorActionPreference = "Stop"

# ── Cleanup handler ────────────────────────────────────────────────
$LITELLM_PROCESS = $null

function Cleanup {
    if ($LITELLM_PROCESS -and !$LITELLM_PROCESS.HasExited) {
        Write-Host "🛑 Shutting down LiteLLM proxy (PID $($LITELLM_PROCESS.Id))..."
        $LITELLM_PROCESS.Kill()
        $LITELLM_PROCESS.WaitForExit(5000)
    }
}
# Register cleanup for script exit and Ctrl+C
# PowerShell doesn't have a direct trap equivalent; we use try/finally

# ── Activate venv ──────────────────────────────────────────────────
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
} elseif (Test-Path "..\venv\Scripts\Activate.ps1") {
    . ..\venv\Scripts\Activate.ps1
} else {
    Write-Host "❌ venv not found. Run from project root or ensure venv\ exists."
    exit 1
}

# ── LiteLLM config ─────────────────────────────────────────────────
$LITELLM_CONFIG = "tools\litellm_config.yaml"
if (!(Test-Path $LITELLM_CONFIG)) {
    Write-Host "❌ $LITELLM_CONFIG not found."
    exit 1
}

# ── Port 8000 collision check ─────────────────────────────────────
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $tcpClient.Connect("localhost", 8000)
    $tcpClient.Close()
    Write-Host "❌ Port 8000 is already in use."
    Write-Host "   Fix: Either kill the occupying process, or change the port in:"
    Write-Host "     $LITELLM_CONFIG"
    Write-Host "     and update --openai-api-base in this script."
    exit 1
} catch {
    # Port is free, continue
}

try {
    # ── Start LiteLLM proxy ────────────────────────────────────────
    Write-Host "🚀 Starting LiteLLM proxy (background)..."
    $LITELLM_PROCESS = Start-Process -FilePath "litellm" `
        -ArgumentList "--config", "$LITELLM_CONFIG", "--port", "8000" `
        -PassThru -WindowStyle Hidden

    # Wait for proxy to be ready
    Write-Host "⏳ Waiting for proxy to be ready..."
    $ready = $false
    for ($i = 1; $i -le 10; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -UseBasicParsing
            if ($resp.StatusCode -eq 200) {
                Write-Host "✅ Proxy is up."
                $ready = $true
                break
            }
        } catch {
            # Not ready yet
        }
        if ($i -eq 10) {
            Write-Host "❌ Proxy failed to start within 10 attempts."
            Cleanup
            exit 1
        }
        Start-Sleep -Seconds 1
    }

    if (!$ready) {
        Write-Host "❌ Proxy failed to start."
        Cleanup
        exit 1
    }

    # ── Launch Aider (Architect Mode) ─────────────────────────────
    Write-Host "🧠 Launching Aider — Architect mode (Gemini plans, Qwen edits)..."
    $aiderArgs = @(
        "--architect",
        "--model", "openai/smart",
        "--editor-model", "openai/fast",
        "--editor-edit-format", "whole",
        "--openai-api-base", "http://localhost:8000",
        "--openai-api-key", "dummy"
    )
    # Append any user-passed arguments
    if ($args.Count -gt 0) {
        $aiderArgs += $args
    }

    & aider @aiderArgs

} finally {
    Cleanup
    Write-Host "✅ Done."
}
