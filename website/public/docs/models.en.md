# Models

You need to configure a model before chatting with CoPaw. You can do this under **Console → Settings → Models**, or use the **custom auth provider plugin** for automated enterprise authentication.

CoPaw supports **cloud providers** (require API Key) and **custom providers** (any OpenAI-compatible endpoint). This page explains how to configure each type.

---

## Configure cloud providers

Cloud providers (including ModelScope, DashScope, Aliyun Coding Plan, OpenAI, Azure OpenAI, DeepSeek, Kimi, MiniMax, and Anthropic) call remote models via API and require an **API Key**.

**In the console:**

1. Open the console and go to **Settings → Models**.
2. Find the target cloud provider card (e.g. OpenAI) and click **Settings**. Enter your **API key** and click **Save**.
3. After saving, the card status in the top-right becomes **Available**. In the **LLM Configuration** section at the top, you can select this provider in the **Provider** dropdown and see the list of models in the **Model** dropdown.
4. Choose the target model and click **Save**.

> To revoke a cloud provider, click **Settings** on its card, then **Revoke Authorization** and confirm.

## Custom auth provider plugin

For enterprise environments that require custom authentication (OAuth, vault, token refresh, etc.), CoPaw supports a **plugin mechanism** that loads your custom Python code at startup.

Create a Python file with a `get_provider_config()` function:

```python
import os

def get_provider_config() -> dict:
    return {
        "name": "My Company LLM",
        "base_url": os.environ["MY_LLM_BASE_URL"],
        "api_key": os.environ["MY_LLM_API_KEY"],
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
        ],
    }
```

Place it at `<COPAW_SECRET_DIR>/custom_auth_provider.py` (auto-detected), or set the `COPAW_CUSTOM_AUTH_PROVIDER` environment variable to point to the file.

CoPaw calls `get_provider_config()` once at startup and registers the returned endpoint as a built-in provider. The provider appears in **Settings → Models** like any other.

**Required keys:** `base_url`, `api_key`

**Optional keys:** `name` (display name), `models` (list of `{"id": "...", "name": "..."}` dicts)

See `examples/custom_auth_provider.py` in the repo for a full example including an OAuth pattern.

## LM Studio provider

The LM Studio provider connects to the **LM Studio** desktop application's built-in OpenAI-compatible server. Models are managed in the LM Studio GUI; CoPaw discovers loaded models automatically via the `/v1/models` endpoint.

**Prerequisites:**

- Install LM Studio from [lmstudio.ai](https://lmstudio.ai).
- In LM Studio, load a model and start the local server (default: `http://localhost:1234`).

1. On the Models page you'll see the LM Studio provider card.
2. Click **Settings** at the bottom right. The default Base URL is `http://localhost:1234/v1`. Adjust if you changed the port. Click **Save**.
3. Click **Models** to view models currently loaded in LM Studio.
4. In **LLM Configuration** at the top, select **LM Studio** in the **Provider** dropdown and your model in the **Model** dropdown, then click **Save**.

> **Tip:** LM Studio does not require an API key by default. Models must be loaded in LM Studio's GUI before they appear in CoPaw.

## Add custom provider

1. On the Models page click **Add provider**.
2. Enter **Provider ID** and **Display name**, then click **Create**.
3. The new provider card will appear. Click **Settings**, enter **Base URL** and **API Key**, then click **Save**.
4. Click **Models**, enter the **Model ID**, then click **Add model**.
5. In **LLM Configuration** at the top, select the custom provider and model, then click **Save**.

> If configuration fails, double-check **Base URL**, **API Key**, and **Model ID** (including case). To remove a custom provider, click **Delete provider** on its card and confirm.
