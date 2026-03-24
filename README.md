<div align="center">

# CoPaw (Secure Minimal)

[![Python Version](https://img.shields.io/badge/python-3.10%20~%20%3C3.14-blue.svg?logo=python&label=Python)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-red.svg?logo=apache&label=License)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-black.svg?logo=python&label=CodeStyle)](https://github.com/psf/black)

<p align="center"><b>Works for you, grows with you.</b></p>

</div>

A stripped-down, enterprise-ready fork of CoPaw — a personal AI assistant that runs on your own machine. This variant is designed for environments where models are accessed exclusively via remote OpenAI-compatible API endpoints, with no local model inference, no Docker, and no external chat channel dependencies.

> **What was removed** (compared to upstream CoPaw):
>
> - Local model backends (llama.cpp, MLX, Ollama)
> - Google Gemini provider (`google-genai` SDK)
> - Office document skills (docx, xlsx, pptx) — required LibreOffice
> - External chat channels (DingTalk, Feishu, QQ, Discord, iMessage, Telegram, etc.)
> - Docker / container deployment files
> - Local Whisper audio transcription
>
> **What remains:**
>
> - Web console for chat and configuration
> - All cloud model providers (OpenAI, Anthropic, DeepSeek, Kimi, MiniMax, DashScope, ModelScope, Azure OpenAI, LM Studio)
> - **Custom auth provider plugin** for enterprise authentication
> - Skills system (cron, PDF, file reader, news, browser, himalaya email, and custom skills)
> - MCP tool support (local stdio-only servers)
> - Scheduled tasks, heartbeat, memory, multi-agent

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Install from Source](#install-from-source)
- [Custom Auth Provider Plugin](#custom-auth-provider-plugin)
- [API Key Configuration](#api-key-configuration)
- [Environment Variables](#environment-variables)
- [Built-in Skills](#built-in-skills)
- [CLI Reference](#cli-reference)
- [Documentation](#documentation)
- [License](#license)

---

## Prerequisites

| Software | Version | Required | Purpose |
|---|---|---|---|
| **Python** | 3.10 – 3.13 | Yes | Runtime |
| **pip** | latest | Yes | Install Python packages |
| **Node.js** | 20+ | Yes (build only) | Build the web console frontend |
| **npm** | (bundled with Node) | Yes (build only) | `npm ci && npm run build` in `console/` |

### Optional (graceful fallback if missing)

| Software | Purpose | Fallback |
|---|---|---|
| Chromium / Chrome / Edge | Browser automation tool | Playwright downloads its own if none found |
| ffmpeg | Audio file conversion | Logs warning, skips audio |
| wget or curl | File downloads in agent tasks | Falls back to Python `urllib` |

---

## Quick Start

```bash
pip install -e .
copaw init --defaults
copaw app
```

Then open **http://127.0.0.1:8088/** in your browser.

On the first run, go to **Settings → Models** to configure a model provider and API key, or use the [Custom Auth Provider Plugin](#custom-auth-provider-plugin) for automated enterprise authentication.

---

## Install from Source

```bash
git clone <this-repo>
cd copaw-secure-minimal

# 1. Build console frontend (required for web UI)
cd console && npm ci && npm run build && cd ..

# 2. Copy console build output to package directory
mkdir -p src/copaw/console
cp -R console/dist/. src/copaw/console/

# 3. Install Python package
pip install -e .

# 4. Initialize and run
copaw init --defaults
copaw app
```

For development (tests, linting):

```bash
pip install -e ".[dev]"
pre-commit install
pytest
```

---

## Custom Auth Provider Plugin

For enterprise environments that require custom authentication (OAuth, vault, token refresh, etc.), CoPaw supports a **plugin mechanism** that loads your custom Python code at startup.

### How it works

1. Create a Python file with a `get_provider_config()` function:

```python
import os

def get_provider_config() -> dict:
    """Return provider credentials. Called once at startup."""
    return {
        "name": "My Company LLM",
        "base_url": os.environ["MY_LLM_BASE_URL"],
        "api_key": os.environ["MY_LLM_API_KEY"],
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
        ],
    }
```

2. Place it in one of these locations:

| Location | How it's found |
|---|---|
| `<COPAW_SECRET_DIR>/custom_auth_provider.py` | Auto-detected (default secret dir: `~/.copaw.secret/`) |
| Any path | Set `COPAW_CUSTOM_AUTH_PROVIDER=/path/to/file.py` |

3. Start CoPaw normally — the provider is registered automatically and appears in **Settings → Models**.

### Required return keys

| Key | Type | Description |
|---|---|---|
| `base_url` | `str` | OpenAI-compatible API base URL |
| `api_key` | `str` | Bearer token / API key |

### Optional return keys

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"Custom Provider"` | Display name in the UI |
| `models` | `list[dict]` | `[]` | Pre-defined models (each needs `{"id": "..."}`) — if omitted, CoPaw tries to discover models from the endpoint |

See `examples/custom_auth_provider.py` for a full example including an OAuth token flow pattern.

---

## API Key Configuration

If you're **not** using the custom auth provider plugin, configure API keys manually:

1. **Console (recommended)** — Open **http://127.0.0.1:8088/** → **Settings** → **Models**. Choose a provider, enter the API key, and select a model.
2. **CLI** — Run `copaw models config-key <provider-id>` to set a key interactively.
3. **Environment variable** — Set keys in a `.env` file in the working directory or export them in your shell.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `COPAW_WORKING_DIR` | `~/.copaw` | Working directory for config, skills, data |
| `COPAW_SECRET_DIR` | `~/.copaw.secret` | Secret directory for provider keys and auth |
| `COPAW_CUSTOM_AUTH_PROVIDER` | *(none)* | Path to custom auth provider plugin file |
| `COPAW_PORT` | `8088` | Port for the web console |
| `COPAW_LOG_LEVEL` | `info` | Log level (`debug`, `info`, `warning`, `error`) |
| `COPAW_TELEMETRY` | `true` | Set to `false` to disable anonymous telemetry |

---

## Built-in Skills

| Skill | Description |
|---|---|
| **cron** | Scheduled jobs — create, list, pause, resume, delete via CLI or Console |
| **file_reader** | Read and summarize text-based files (.txt, .md, .json, .csv, .log, .py, etc.) |
| **pdf** | PDF operations: read, extract text/tables, merge/split, rotate, watermark, forms, encrypt/decrypt |
| **news** | Fetch and summarize latest news from configured sources |
| **browser_visible** | Launch a visible browser window for demos, debugging, or login/CAPTCHA scenarios |
| **himalaya** | Manage emails via CLI (IMAP/SMTP) |
| **guidance** | Agent guidance and behavior customization |
| **agent_message** | Inter-agent messaging |

Custom skills can be added by placing a directory with a `SKILL.md` file in the working directory's `active_skills/` folder, or via the Console under **Agent → Skills**.

---

## CLI Reference

```bash
copaw app                  # Start the web server (default: http://127.0.0.1:8088)
copaw init                 # Interactive first-time setup
copaw init --defaults      # Non-interactive setup with defaults

copaw models list          # Show all providers and configuration
copaw models config        # Interactive provider + model setup
copaw models config-key    # Configure a provider's API key
copaw models set-llm       # Set the active model

copaw skills list          # List loaded skills
copaw skills enable <name> # Enable a skill
copaw skills disable <name># Disable a skill

copaw cron list            # List scheduled jobs
copaw cron create          # Create a scheduled job

copaw clean                # Clean temporary data
copaw update               # Check for updates
copaw uninstall            # Remove CoPaw (keeps config)
copaw uninstall --purge    # Remove CoPaw and all data
```

---

## Documentation

| Topic | Description |
|---|---|
| [Console](https://copaw.agentscope.io/docs/console) | Web UI: chat and agent configuration |
| [Models](https://copaw.agentscope.io/docs/models) | Configure cloud and custom providers |
| [Skills](https://copaw.agentscope.io/docs/skills) | Extend and customize capabilities |
| [MCP](https://copaw.agentscope.io/docs/mcp) | Manage MCP tool servers |
| [Memory](https://copaw.agentscope.io/docs/memory) | Long-term memory |
| [Config](https://copaw.agentscope.io/docs/config) | Working directory and config file |
| [CLI](https://copaw.agentscope.io/docs/cli) | Command-line interface reference |

Full docs source: [website/public/docs/](website/public/docs/).

---

## License

CoPaw is released under the [Apache License 2.0](LICENSE).
