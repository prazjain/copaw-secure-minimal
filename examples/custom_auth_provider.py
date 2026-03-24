"""Example custom auth provider plugin for CoPaw.

Copy this file to one of these locations:
  1. <COPAW_SECRET_DIR>/custom_auth_provider.py  (auto-detected)
  2. Any path, then set COPAW_CUSTOM_AUTH_PROVIDER=/path/to/your_file.py

CoPaw calls get_provider_config() at startup to register your provider.
The returned base_url + api_key are used to talk to your OpenAI-compatible
endpoint.  Your code can do any authentication logic here: fetch tokens
from a vault, call an OAuth flow, read from env vars, etc.
"""

import os


def get_provider_config() -> dict:
    """Return provider credentials and metadata.

    Required keys:
        base_url (str): Your OpenAI-compatible API base URL.
        api_key  (str): Bearer token / API key for authentication.

    Optional keys:
        name   (str):       Display name in CoPaw UI (default: "Custom Provider")
        models (list[dict]): Pre-defined models. Each entry needs at least {"id": "..."}.
                             If omitted, CoPaw tries to discover models from the endpoint.

    This function is called once at startup. If your token expires, you can
    implement refresh logic here or use a long-lived token.
    """

    # ----- Example: read credentials from environment variables -----
    base_url = os.environ.get("MY_LLM_BASE_URL", "https://my-company.example.com/v1")
    api_key = os.environ.get("MY_LLM_API_KEY", "")

    if not api_key:
        raise ValueError(
            "MY_LLM_API_KEY environment variable is not set. "
            "Set it to your API key before starting CoPaw."
        )

    return {
        "name": "My Company LLM",
        "base_url": base_url,
        "api_key": api_key,
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
        ],
    }


# ----- Alternative examples -----

# Example: fetch a short-lived token from a vault / OAuth endpoint
#
# import httpx
#
# def get_provider_config() -> dict:
#     resp = httpx.post(
#         "https://auth.mycompany.com/oauth/token",
#         data={
#             "grant_type": "client_credentials",
#             "client_id": os.environ["CLIENT_ID"],
#             "client_secret": os.environ["CLIENT_SECRET"],
#         },
#     )
#     resp.raise_for_status()
#     token = resp.json()["access_token"]
#
#     return {
#         "name": "Corp LLM Gateway",
#         "base_url": "https://llm-gateway.mycompany.com/v1",
#         "api_key": token,
#         "models": [
#             {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet"},
#         ],
#     }
