# -*- coding: utf-8 -*-
"""Small client for GitHub Models inference used for Copilot/GitHub-backed generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional
from urllib import error, request


def load_env_if_available() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv  # type: ignore[import-untyped]
    except Exception:
        return

    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        script_env = Path(__file__).resolve().parent / ".env"
        if script_env.exists():
            dotenv_path = str(script_env)

    if dotenv_path:
        load_dotenv(dotenv_path, override=False)


def _github_token() -> Optional[str]:
    load_env_if_available()
    return (
        os.environ.get("GITHUB_MODELS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )


def github_models_enabled() -> bool:
    return bool(_github_token())


def github_models_model(default_model: str = "openai/gpt-5") -> str:
    return os.environ.get("GITHUB_MODELS_MODEL", default_model)


def _endpoint() -> str:
    org = os.environ.get("GITHUB_MODELS_ORG")
    if org:
        return f"https://models.github.ai/orgs/{org}/inference/chat/completions"
    return "https://models.github.ai/inference/chat/completions"


def _extract_text(payload: dict[str, Any]) -> Optional[str]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return str(content) if content else None


def chat_completion(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 2000,
    response_format: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    token = _github_token()
    if not token:
        return None

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if response_format:
        body["response_format"] = response_format

    req = request.Request(
        _endpoint(),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "tools-transcription-pipeline",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    return _extract_text(payload)
