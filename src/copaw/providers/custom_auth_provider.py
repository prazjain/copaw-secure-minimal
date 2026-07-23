# -*- coding: utf-8 -*-
"""Custom authentication provider plugin.

Loads a user-supplied Python file that implements a ``get_provider_config()``
function.  That function must return a dict with at least ``base_url`` and
``api_key``.  CoPaw uses those credentials to talk to the user's
OpenAI-compatible endpoint.

The plugin file path is resolved in this order:
  1. ``COPAW_CUSTOM_AUTH_PROVIDER`` environment variable
  2. ``<COPAW_SECRET_DIR>/custom_auth_provider.py``

The plugin module must define::

    def get_provider_config() -> dict:
        '''Return provider credentials and metadata.

        Required keys
        -------------
        base_url : str   – OpenAI-compatible API base URL
        api_key  : str   – bearer token / API key

        Optional keys
        -------------
        name     : str   – display name  (default: "Custom Provider")
        models   : list[dict]
            Each entry: {"id": "<model-id>", "name": "<display-name>"}
            If omitted, CoPaw will try to discover models from the endpoint.
        '''
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .openai_provider import OpenAIProvider
from .provider import ModelInfo

logger = logging.getLogger(__name__)

_PROVIDER_ID = "custom-auth"


def _locate_plugin() -> Optional[Path]:
    """Find the custom auth provider plugin file."""
    # 1. Explicit env var
    env_path = os.environ.get("COPAW_CUSTOM_AUTH_PROVIDER")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file():
            return p
        logger.warning(
            "COPAW_CUSTOM_AUTH_PROVIDER=%s does not exist; skipping",
            env_path,
        )
        return None

    # 2. Convention: <SECRET_DIR>/custom_auth_provider.py
    from ..constant import SECRET_DIR

    p = SECRET_DIR / "custom_auth_provider.py"
    if p.is_file():
        return p

    return None


def _load_plugin(plugin_path: Path) -> dict:
    """Import the plugin module and call ``get_provider_config()``."""
    spec = importlib.util.spec_from_file_location(
        "copaw_custom_auth_plugin",
        plugin_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Cannot load plugin from {plugin_path}",
        )
    module = importlib.util.module_from_spec(spec)
    # Don't pollute sys.modules permanently
    old = sys.modules.get(spec.name)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        if old is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = old

    fn = getattr(module, "get_provider_config", None)
    if fn is None:
        raise ImportError(
            f"Plugin {plugin_path} must define a "
            "'get_provider_config()' function.",
        )
    config = fn()
    if not isinstance(config, dict):
        raise TypeError(
            "get_provider_config() must return a dict, "
            f"got {type(config).__name__}",
        )
    return config


def load_custom_auth_provider() -> Optional[OpenAIProvider]:
    """Try to load the custom auth provider plugin.

    Returns an ``OpenAIProvider`` instance if the plugin is found and valid,
    or ``None`` if no plugin is configured.

    Raises on plugin errors so the user gets clear feedback.
    """
    plugin_path = _locate_plugin()
    if plugin_path is None:
        return None

    logger.info("Loading custom auth provider from %s", plugin_path)
    config = _load_plugin(plugin_path)

    # Validate required keys
    base_url = config.get("base_url")
    api_key = config.get("api_key")
    if not base_url:
        raise ValueError(
            f"Custom auth plugin {plugin_path}: "
            "'base_url' is required in get_provider_config() return value.",
        )
    if not api_key:
        raise ValueError(
            f"Custom auth plugin {plugin_path}: "
            "'api_key' is required in get_provider_config() return value.",
        )

    # Build models list
    raw_models = config.get("models", [])
    models = [
        ModelInfo(
            id=m["id"],
            name=m.get("name", m["id"]),
        )
        for m in raw_models
        if isinstance(m, dict) and "id" in m
    ]

    name = config.get("name", "Custom Provider")
    provider = OpenAIProvider(
        id=_PROVIDER_ID,
        name=name,
        base_url=str(base_url).rstrip("/"),
        api_key=str(api_key),
        api_key_prefix="",
        models=models,
        freeze_url=True,
        require_api_key=False,  # key comes from plugin, not user input
        support_model_discovery=len(models) == 0,
    )

    logger.info(
        "Custom auth provider '%s' loaded (%s, %d models)",
        name,
        base_url,
        len(models),
    )
    return provider
