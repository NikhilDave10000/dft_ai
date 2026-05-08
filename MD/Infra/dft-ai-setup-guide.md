# DFT AI Setup Guide: Multi-Model AI Coding System

> **Goal**: Run multiple top-tier AI models (Claude, GPT, Kimi, GLM, NVIDIA/local models) collaboratively on your local project files — no more copy-pasting code between browser tabs, no lost context.

---

## Step 0: Prerequisites Check

Before installing anything, verify your system can handle this setup.

### 0.1 Check Your Hardware
```bash
# Check available RAM (you want 16GB+ for smooth multi-model operation)
free -h

# Check if you have an NVIDIA GPU (optional but recommended for local models)
nvidia-smi

# Check disk space (50GB+ recommended for models + code)
df -h
```

### 0.2 Install Base Dependencies
```bash
# Update your system
sudo apt update && sudo apt upgrade -y    # Ubuntu/Debian
# OR
brew update && brew upgrade               # macOS

# Install essential tools
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y git nodejs python3 python3-pip python3-venv docker.io

# Verify installations
git --version
node --version
python3 --version
docker --version
```

### 0.3 Create Project Directory Structure
```bash
# Create your main workspace
mkdir -p ~/dft-ai/{projects,models,configs,logs}
cd ~/dft-ai

# This will be your structure:
# ~/dft-ai/
# ├── projects/     # Your actual code projects
# ├── models/       # Local AI models (if running offline)
# ├── configs/      # API keys and configuration files
# └── logs/         # Conversation history and outputs
```

---

## Step 1: Install Ollama (Local AI Engine)

Ollama lets you run AI models locally on your machine (uses NVIDIA GPU if available).

### 1.1 Install Ollama
```bash
# Official install script
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

### 1.2 Pull Coding-Optimized Models
```bash
# Best coding models (choose based on your VRAM):
# 8GB VRAM: qwen2.5-coder:14b
# 16GB VRAM: qwen2.5-coder:32b  
# 24GB+ VRAM: deepseek-coder-v2

ollama pull qwen2.5-coder:14b
ollama pull deepseek-coder-v2:16b
ollama pull nomic-embed-text          # For embeddings/RAG

# List downloaded models
ollama list
```

### 1.3 Test Local Model
```bash
# Quick test
ollama run qwen2.5-coder:14b
# Type: "Write a Python function to reverse a string"
# Exit with: /bye
```

---

## Step 2: Install Open WebUI (Web Interface for Local + Remote Models)

This gives you a ChatGPT-like interface that connects to BOTH local Ollama models AND cloud APIs.

### 2.1 Install via Docker
```bash
# Run Open WebUI container
docker run -d \
  -p 3000:8080 \
  --gpus all \
  --add-host=host.docker.internal:host-gateway \
  -v ollama:/root/.ollama \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main

# Check if it's running
docker ps | grep open-webui
```

### 2.2 Access the Interface
```
Open browser: http://localhost:3000
- First user to sign up becomes admin
- Create your account
```

### 2.3 Connect Ollama to Open WebUI
```
In Open WebUI:
1. Go to Settings (gear icon) → Admin Settings → Connections
2. Ollama API URL: http://host.docker.internal:11434
3. Click "Verify Connection"
4. Your local models should appear in the model selector
```

---

## Step 3: Get API Keys for Cloud Models

You need API keys to use Claude, GPT, Kimi, GLM, and other cloud models.

### 3.1 Get Individual API Keys

| Provider | Sign Up URL | Key Location |
|----------|-------------|--------------|
| **OpenAI (GPT-4o)** | https://platform.openai.com | API Keys → Create new secret key |
| **Anthropic (Claude)** | https://console.anthropic.com | Settings → API Keys |
| **Moonshot (Kimi)** | https://platform.moonshot.cn | API Key Management |
| **Zhipu AI (GLM)** | https://open.bigmodel.cn | User Center → API Keys |
| **NVIDIA NIM** | https://build.nvidia.com | API Catalog → Get API Key |

### 3.2 The Better Way: OpenRouter (One Key for ALL Models)

Instead of managing 5+ API keys, use OpenRouter:

```bash
# 1. Sign up at https://openrouter.ai
# 2. Go to Settings → API Keys
# 3. Create key: sk-or-v1-xxxxxxxx
# 4. This ONE key works for Claude, GPT, Kimi, GLM, Gemini, and 100+ more
```

### 3.3 Store Keys Securely
```bash
cd ~/dft-ai/configs

# Create environment file
cat > .env << 'EOF'
# OpenRouter (Recommended - one key for all)
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Individual providers (optional backups)
OPENAI_API_KEY=sk-proj-your-key
ANTHROPIC_API_KEY=sk-ant-your-key
MOONSHOT_API_KEY=sk-your-kimi-key
ZHIPU_API_KEY=your-glm-key
NVIDIA_API_KEY=nvapi-your-key

# Ollama (local)
OLLAMA_HOST=http://localhost:11434
EOF

# Secure the file
chmod 600 .env
```

---

## Step 4: Configure Open WebUI with Cloud Models

Now connect your cloud APIs to the same interface where your local models live.

### 4.1 Add OpenRouter to Open WebUI
```
In Open WebUI (http://localhost:3000):

1. Go to Settings → Admin Settings → Connections
2. Click "+" to add new connection
3. Fill in:
   - URL: https://openrouter.ai/api/v1
   - Key: sk-or-v1-your-key-here
   - Model IDs: 
     * anthropic/claude-3.5-sonnet
     * openai/gpt-4o
     * moonshot-ai/moonshot-v1-8k
     * thudm/glm-4
     * nvidia/llama-3.1-nemotron-70b
4. Click "Verify" then "Save"
```

### 4.2 Verify All Models Appear
```
In the chat interface:
- Click the model dropdown at the top
- You should see:
  * Local: qwen2.5-coder:14b, deepseek-coder-v2:16b
  * Cloud: Claude 3.5 Sonnet, GPT-4o, Kimi, GLM-4, NVIDIA Nemotron
```

---

## Step 5: Install Continue.dev (IDE Integration)

This is the game-changer: AI directly inside your code editor with full project context.

### 5.1 Install in VS Code
```bash
# Open VS Code
# Press Ctrl+P (or Cmd+P on Mac)
# Type:
ext install Continue.continue

# Or install via terminal:
code --install-extension Continue.continue
```

### 5.2 Configure Continue with All Your Models

Create the config file:
```bash
mkdir -p ~/.continue
cat > ~/.continue/config.json << 'EOF'
{
  "models": [
    {
      "title": "Claude 3.5 Sonnet",
      "provider": "openrouter",
      "model": "anthropic/claude-3.5-sonnet",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    {
      "title": "GPT-4o",
      "provider": "openrouter",
      "model": "openai/gpt-4o",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    {
      "title": "Kimi v1",
      "provider": "openrouter",
      "model": "moonshot-ai/moonshot-v1-8k",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    {
      "title": "GLM-4",
      "provider": "openrouter",
      "model": "thudm/glm-4",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    {
      "title": "NVIDIA Nemotron",
      "provider": "openrouter",
      "model": "nvidia/llama-3.1-nemotron-70b-instruct",
      "apiKey": "sk-or-v1-your-key-here",
      "apiBase": "https://openrouter.ai/api/v1"
    },
    {
      "title": "Local Qwen Coder",
      "provider": "ollama",
      "model": "qwen2.5-coder:14b"
    },
    {
      "title": "Local DeepSeek",
      "provider": "ollama",
      "model": "deepseek-coder-v2:16b"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Local Autocomplete",
    "provider": "ollama",
    "model": "qwen2.5-coder:1.5b"
  },
  "customCommands": [
    {
      "name": "test",
      "prompt": "Write a comprehensive unit test for the selected code. Use the best testing practices for this language."
    },
    {
      "name": "explain",
      "prompt": "Explain this code in detail. Break down the logic, data flow, and any potential issues."
    },
    {
      "name": "refactor",
      "prompt": "Refactor this code to be more readable, efficient, and maintainable. Explain your changes."
    }
  ],
  "contextProviders": [
    {
      "name": "code",
      "params": {}
    },
    {
      "name": "docs",
      "params": {}
    },
    {
      "name": "diff",
      "params": {}
    },
    {
      "name": "terminal",
      "params": {}
    },
    {
      "name": "problems",
      "params": {}
    },
    {
      "name": "folder",
      "params": {}
    },
    {
      "name": "codebase",
      "params": {}
    }
  ],
  "slashCommands": [
    {
      "name": "edit",
      "description": "Edit selected code"
    },
    {
      "name": "comment",
      "description": "Write comments for the selected code"
    },
    {
      "name": "share",
      "description": "Export this session as markdown"
    },
    {
      "name": "cmd",
      "description": "Generate a shell command"
    }
  ]
}
EOF
```

### 5.3 Restart VS Code
```bash
# Close and reopen VS Code
# You should see the Continue panel on the left side
```

---

## Step 6: Install Aider (Terminal-Based Multi-Model Coding)

Aider is a terminal tool that edits your actual files using AI, with full git integration.

### 6.1 Install Aider
```bash
# Install via pip
pip install aider-chat

# Or with uv (faster)
pip install uv
uv tool install aider-chat

# Verify
aider --version
```

### 6.2 Configure Aider with All Models
```bash
cd ~/dft-ai/configs

cat > .aider.conf.yml << 'EOF'
# Default model
model: openrouter/anthropic/claude-3.5-sonnet

# Weak model (for simple tasks like commit messages)
weak-model: openrouter/openai/gpt-4o-mini

# Editor model (for code editing)
editor-model: openrouter/anthropic/claude-3.5-sonnet

# API keys
openrouter-api-key: sk-or-v1-your-key-here

# Git settings
git: true
auto-commits: true
dirty-commits: false

# Output settings
pretty: true
stream: true
show-model-warnings: false

# Context settings
map-tokens: 1024
map-refresh: auto
EOF
```

### 6.3 Create Model Switching Aliases
```bash
cat >> ~/.bashrc << 'EOF'

# Aider with different models
alias aider-claude='aider --model openrouter/anthropic/claude-3.5-sonnet'
alias aider-gpt='aider --model openrouter/openai/gpt-4o'
alias aider-kimi='aider --model openrouter/moonshot-ai/moonshot-v1-8k'
alias aider-glm='aider --model openrouter/thudm/glm-4'
alias aider-nvidia='aider --model openrouter/nvidia/llama-3.1-nemotron-70b-instruct'
alias aider-local='aider --model ollama/qwen2.5-coder:14b'
EOF

source ~/.bashrc
```

---

## Step 7: Your First Multi-Model Workflow

Now let's use the system. Here's how to leverage multiple AIs on one project.

### 7.1 Start a Project
```bash
cd ~/dft-ai/projects
mkdir my-app && cd my-app
git init

# Create a basic structure
mkdir src tests docs
touch src/main.py README.md
```

### 7.2 Use Aider with Claude (Architecture & Complex Logic)
```bash
# Start aider with Claude for high-level design
aider-claude src/main.py README.md

# In the aider chat:
# > Create a FastAPI application with user authentication, 
# > JWT tokens, and a SQLite database. Include proper error handling.
# 
# Claude will write the code directly into your files
# Type /quit to exit
```

### 7.3 Switch to GPT-4o for Testing
```bash
# Now use GPT-4o to write comprehensive tests
aider-gpt tests/test_main.py src/main.py

# In the chat:
# > Write comprehensive pytest tests for the FastAPI app.
# > Cover authentication, token validation, and edge cases.
# > Use pytest-asyncio for async tests.
```

### 7.4 Use Kimi for Documentation
```bash
# Use Kimi for Chinese documentation or specific formatting
aider-kimi docs/API.md src/main.py

# In the chat:
# > Generate API documentation in Markdown format.
# > Include request/response examples and authentication details.
```

### 7.5 Use Local Model for Quick Refactors
```bash
# Use local model for fast, offline edits
aider-local src/main.py

# In the chat:
# > Refactor the database connection to use async SQLAlchemy
# > This is faster and doesn't use API credits
```

---

## Step 8: Using Continue.dev in VS Code (The Daily Driver)

### 8.1 Basic Usage
```
1. Open your project in VS Code
2. Open Continue panel (Ctrl+L or Cmd+L)
3. Select model from dropdown (Claude/GPT/Kimi/Local)
4. Highlight code → Right click → "Continue: Explain"
5. Or type in chat: "@codebase Explain the authentication flow"
```

### 8.2 Context Commands
```
@codebase          - Search entire project for context
@current-file      - Use the current open file
@selected-code     - Use highlighted code
@terminal          - Include terminal output
@diff              - Include git diff
@problems          - Include VS Code error/problems
@folder src/       - Include specific folder
```

### 8.3 Multi-Model Comparison
```
1. Select code you want help with
2. Ask Claude: "Review this code for security issues"
3. Switch model to GPT-4o: "Review this code for performance issues"  
4. Switch to Local: "Refactor this based on the feedback above"
5. All responses stay in the conversation history
```

---

## Step 9: Advanced: Multi-Agent Collaboration

Set up actual AI-to-AI collaboration where models talk to each other.

### 9.1 Install AutoGen
```bash
pip install pyautogen
```

### 9.2 Create Multi-Agent Script
```bash
cat > ~/dft-ai/projects/multi_agent.py << 'PYEOF'
import autogen
import os

# Load API key
api_key = os.getenv("OPENROUTER_API_KEY")

# Configuration for all agents
config_list = [
    {
        "model": "anthropic/claude-3.5-sonnet",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": api_key,
        "api_type": "open_ai"
    }
]

# Create agents with different roles
coder = autogen.AssistantAgent(
    name="SeniorCoder",
    system_message="You are an expert Python developer. Write clean, efficient code with proper error handling.",
    llm_config={"config_list": config_list, "temperature": 0.1}
)

reviewer = autogen.AssistantAgent(
    name="CodeReviewer", 
    system_message="You are a strict code reviewer. Find bugs, security issues, and suggest improvements. Be critical.",
    llm_config={"config_list": config_list, "temperature": 0.2}
)

tester = autogen.AssistantAgent(
    name="TestEngineer",
    system_message="You write comprehensive tests. Cover edge cases, error conditions, and integration scenarios.",
    llm_config={"config_list": config_list, "temperature": 0.1}
)

user_proxy = autogen.UserProxyAgent(
    name="User",
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=10,
    code_execution_config={"work_dir": "coding", "use_docker": False}
)

# Start group chat
groupchat = autogen.GroupChat(
    agents=[user_proxy, coder, reviewer, tester],
    messages=[],
    max_round=12
)

manager = autogen.GroupChatManager(
    groupchat=groupchat,
    llm_config={"config_list": config_list}
)

# Initiate task
user_proxy.initiate_chat(
    manager,
    message="Create a Python CLI tool that: 1) Takes a directory path as argument, 2) Scans for duplicate files by hash, 3) Outputs a JSON report of duplicates, 4) Has a --delete flag to remove duplicates with confirmation, 5) Include comprehensive error handling and logging"
)
PYEOF

# Run it
python3 ~/dft-ai/projects/multi_agent.py
```

---

## Step 10: Daily Workflow Summary

### Your Complete Toolchain
| Tool | Use Case | When to Use |
|------|----------|-------------|
| **Continue.dev** | IDE integration, quick questions | Every day, while coding |
| **Aider** | Multi-file editing, git commits | Complex refactors, new features |
| **Open WebUI** | Web interface, long conversations | Research, exploration, non-code tasks |
| **AutoGen** | Multi-agent collaboration | Complex projects requiring multiple perspectives |

### Typical Day
```bash
# Morning: Open project in VS Code with Continue
# → Use Claude for architecture decisions
# → Use GPT-4o for implementation details

# Afternoon: Terminal with Aider
# → aider-claude for complex multi-file changes
# → aider-local for quick fixes (saves API costs)

# Evening: Review with different model
# → Open WebUI → Kimi or GLM for fresh perspective
# → Ask: "Review this code as if you're a security auditor"

# Before commit: AutoGen multi-agent review
# → Run multi_agent.py for final code review
```

---

## Troubleshooting

### Issue: Ollama models not showing in Open WebUI
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Restart Open WebUI
docker restart open-webui

# Check logs
docker logs open-webui | tail -50
```

### Issue: API key errors in Continue
```bash
# Check config.json syntax
cat ~/.continue/config.json | python3 -m json.tool

# Test API key directly
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer sk-or-v1-your-key"
```

### Issue: Aider can't find models
```bash
# List available models
aider --list-models openrouter

# Test specific model
aider --model openrouter/anthropic/claude-3.5-sonnet --message "test"
```

### Issue: Out of VRAM for local models
```bash
# Use smaller models
ollama pull qwen2.5-coder:7b

# Or run with CPU only
OLLAMA_HOST=0.0.0.0 ollama serve
```

---

## Cost Optimization Tips

1. **Use local models for**: Simple refactors, formatting, comments, autocomplete
2. **Use Claude/GPT for**: Architecture, complex logic, debugging
3. **Use Kimi/GLM for**: Specific language tasks, alternative perspectives
4. **Use OpenRouter**: One key, one bill, easy cost tracking
5. **Set spending limits**: OpenRouter → Settings → Usage Limits

---

## Next Steps

1. Complete Steps 0-4 (infrastructure)
2. Complete Steps 5-6 (tools)
3. Try Step 7 (first workflow)
4. Use Step 8 daily (Continue.dev)
5. Explore Step 9 (multi-agent) when ready
6. Customize: Add more models, create custom prompts, build your own agents

---

*Setup complete. You now have a multi-model AI system that works directly with your local files. No more browser tab juggling.*
