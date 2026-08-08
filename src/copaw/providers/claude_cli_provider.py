# -*- coding: utf-8 -*-
"""Claude CLI provider — uses the locally installed Claude CLI for inference.

When the ``claude`` command-line tool (Claude Code) is available on the
machine, this provider pipes LLM requests through it instead of making
direct remote API calls.  This lets users leverage their existing Claude
CLI authentication without configuring a separate API key in CoPaw.

The provider is registered as a built-in and can be auto-preferred by
setting the environment variable ``COPAW_PREFER_CLAUDE_CLI=true``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
import uuid
from typing import Any, List

from agentscope.model import ChatModelBase
from agentscope.model._model_response import ChatResponse
from agentscope.model._model_usage import ChatUsage

from copaw.providers.provider import ModelInfo, Provider

logger = logging.getLogger(__name__)

CLAUDE_CLI_MODELS: List[ModelInfo] = [
    ModelInfo(id="sonnet", name="Claude Sonnet"),
    ModelInfo(id="opus", name="Claude Opus"),
    ModelInfo(id="haiku", name="Claude Haiku"),
]

# Regex to extract <tool_call>…</tool_call> blocks from model output.
_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


def is_claude_cli_available() -> bool:
    """Return *True* if the ``claude`` CLI binary is on ``$PATH``."""
    return shutil.which("claude") is not None


# ---------------------------------------------------------------------------
# Chat model
# ---------------------------------------------------------------------------


class ClaudeCLIChatModel(ChatModelBase):
    """A :class:`ChatModelBase` that delegates inference to the local
    ``claude`` CLI (Claude Code) via subprocess.

    Tool-use is supported through a text-based protocol: tool definitions
    are embedded in the system prompt and the model is instructed to emit
    ``<tool_call>`` blocks that this class parses back into proper
    :class:`ToolUseBlock` dicts.
    """

    def __init__(
        self,
        model_name: str = "sonnet",
        cli_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_name=model_name, stream=False)
        self.cli_path = cli_path or "claude"

    # -- message serialisation -----------------------------------------------

    @staticmethod
    def _extract_text(content: Any) -> str:
        """Extract plain text from a message ``content`` field."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)
        return str(content) if content else ""

    def _build_prompt(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[str, str | None]:
        """Convert *messages* and *tools* into a ``(prompt, system)`` pair
        suitable for the ``claude -p`` invocation."""
        system_parts: list[str] = []
        conversation_parts: list[str] = []

        for msg in messages:
            role = msg.get("role", "")
            text = self._extract_text(msg.get("content", ""))

            if role == "system":
                system_parts.append(text)
            elif role == "user":
                conversation_parts.append(f"User: {text}")
            elif role == "assistant":
                conversation_parts.append(f"Assistant: {text}")
            elif role == "tool":
                tool_name = msg.get("name", "unknown")
                conversation_parts.append(
                    f"Tool Result ({tool_name}): {text}",
                )

        if tools:
            system_parts.append(self._format_tool_instructions(tools))

        system = "\n\n".join(system_parts) if system_parts else None
        prompt = "\n\n".join(conversation_parts) if conversation_parts else ""
        return prompt, system

    @staticmethod
    def _format_tool_instructions(tools: list[dict]) -> str:
        """Build a system-prompt section that describes the available tools
        and the expected ``<tool_call>`` response format."""
        lines = [
            "You have access to the following tools. "
            "When you need to use a tool, respond with EXACTLY one JSON "
            "block wrapped in <tool_call> tags like this:",
            "",
            "<tool_call>",
            '{"name": "tool_name", "arguments": {"param1": "value1"}}',
            "</tool_call>",
            "",
            "Available tools:",
        ]

        for tool in tools:
            func = tool.get("function", tool)
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", {})
            lines.append(f"\n### {name}")
            if desc:
                lines.append(f"Description: {desc}")
            if params:
                lines.append(
                    f"Parameters: {json.dumps(params, indent=2)}",
                )

        lines.append(
            "\nIf you do not need to use a tool, respond normally with text.",
        )
        return "\n".join(lines)

    # -- response parsing ----------------------------------------------------

    @staticmethod
    def _parse_tool_calls(text: str) -> list[dict]:
        """Extract ``<tool_call>`` blocks and return ``ToolUseBlock`` dicts."""
        tool_calls: list[dict] = []
        for match in _TOOL_CALL_RE.findall(text):
            try:
                call = json.loads(match)
                tool_calls.append(
                    {
                        "type": "tool_use",
                        "id": f"call_{uuid.uuid4().hex[:12]}",
                        "name": call.get("name", ""),
                        "input": call.get("arguments", {}),
                    },
                )
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse tool_call JSON: %s",
                    match[:200],
                )
        return tool_calls

    # -- main entry point ----------------------------------------------------

    async def __call__(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        prompt, system = self._build_prompt(messages, tools)

        cmd: list[str] = [
            self.cli_path,
            "-p",
            "--output-format",
            "json",
            "--max-turns",
            "1",
        ]
        if self.model_name:
            cmd.extend(["--model", self.model_name])
        if system:
            cmd.extend(["--system-prompt", system])

        t0 = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(prompt.encode("utf-8"))
        elapsed = time.monotonic() - t0

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Claude CLI exited with code {proc.returncode}: {err}",
            )

        # Parse the JSON envelope produced by ``claude -p --output-format json``
        raw = stdout.decode("utf-8", errors="replace")
        try:
            result = json.loads(raw)
            text: str = result.get("result", "")
        except json.JSONDecodeError:
            text = raw.strip()

        # Build content blocks, checking for embedded tool calls.
        content: list[dict] = []
        if tools:
            tool_calls = self._parse_tool_calls(text)
            if tool_calls:
                clean = _TOOL_CALL_RE.sub("", text).strip()
                if clean:
                    content.append({"type": "text", "text": clean})
                content.extend(tool_calls)
            else:
                content.append({"type": "text", "text": text})
        else:
            content.append({"type": "text", "text": text})

        usage = ChatUsage(
            input_tokens=0,
            output_tokens=0,
            time=elapsed,
        )

        return ChatResponse(content=content, usage=usage)


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class ClaudeCLIProvider(Provider):
    """Provider backed by the local ``claude`` CLI binary.

    Unlike the cloud providers this does **not** require an API key — it
    relies on the authentication already configured in the CLI.
    """

    async def check_connection(
        self,
        timeout: float = 5,
    ) -> tuple[bool, str]:
        if not is_claude_cli_available():
            return False, "Claude CLI ('claude') not found on PATH"
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode == 0:
                return True, ""
            return False, "Claude CLI returned non-zero exit code"
        except asyncio.TimeoutError:
            return False, "Claude CLI version check timed out"
        except Exception as exc:
            return False, f"Error checking Claude CLI: {exc}"

    async def fetch_models(
        self,
        timeout: float = 5,
    ) -> List[ModelInfo]:
        return list(CLAUDE_CLI_MODELS)

    async def check_model_connection(
        self,
        model_id: str,
        timeout: float = 5,
    ) -> tuple[bool, str]:
        model_id = (model_id or "").strip()
        if not model_id:
            return False, "Empty model ID"
        if not is_claude_cli_available():
            return False, "Claude CLI not found on PATH"
        # Quick smoke-test via the CLI.
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                "--output-format",
                "json",
                "--model",
                model_id,
                "--max-turns",
                "1",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(b"ping"),
                timeout=timeout,
            )
            if proc.returncode == 0:
                return True, ""
            return (
                False,
                f"Claude CLI failed for model '{model_id}'",
            )
        except asyncio.TimeoutError:
            return False, f"Model check timed out for '{model_id}'"
        except Exception as exc:
            return False, f"Error checking model '{model_id}': {exc}"

    def get_chat_model_instance(self, model_id: str) -> ChatModelBase:
        return ClaudeCLIChatModel(model_name=model_id)
