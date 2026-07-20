# -*- coding: utf-8 -*-
"""Small client for GitHub Models inference used for transcript-only document generation."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional
from urllib import error, request


def _debug_enabled() -> bool:
    return os.environ.get("TRANSCRIPTION_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _debug_log(message: str) -> None:
    if _debug_enabled():
        print(f"[github_models] {message}")


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


def github_token() -> Optional[str]:
    load_env_if_available()
    token = (
        os.environ.get("GITHUB_MODELS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )
    if not token and _debug_enabled():
        _debug_log("No GitHub token found in GITHUB_MODELS_TOKEN/GITHUB_TOKEN/GH_TOKEN")
    return token


def github_models_enabled() -> bool:
    return bool(github_token())


def github_models_model(default_model: str = "openai/gpt-4.1-mini") -> str:
    load_env_if_available()
    return os.environ.get("GITHUB_MODELS_MODEL", default_model)


def github_models_fallback_model(default_model: str = "openai/gpt-4.1-mini") -> Optional[str]:
    load_env_if_available()
    value = os.environ.get("GITHUB_MODELS_FALLBACK_MODEL", default_model).strip()
    return value or None


def github_models_max_retries(default_retries: int = 2) -> int:
    load_env_if_available()
    raw = os.environ.get("GITHUB_MODELS_MAX_RETRIES")
    if raw is None:
        return default_retries
    try:
        parsed = int(raw)
    except ValueError:
        _debug_log(f"Invalid GITHUB_MODELS_MAX_RETRIES={raw!r}; using default {default_retries}")
        return default_retries
    return max(0, parsed)


def github_models_retry_base_seconds(default_seconds: float = 1.5) -> float:
    load_env_if_available()
    raw = os.environ.get("GITHUB_MODELS_RETRY_BASE_SECONDS")
    if raw is None:
        return default_seconds
    try:
        parsed = float(raw)
    except ValueError:
        _debug_log(
            f"Invalid GITHUB_MODELS_RETRY_BASE_SECONDS={raw!r}; using default {default_seconds}"
        )
        return default_seconds
    return max(0.1, parsed)


def github_models_endpoint() -> str:
    load_env_if_available()
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
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts).strip() if parts else None
    return None


def chat_completion(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 2200,
) -> Optional[str]:
    token = github_token()
    if not token:
        return None

    max_retries = github_models_max_retries()
    retry_base_seconds = github_models_retry_base_seconds()
    fallback_model = github_models_fallback_model()
    models_to_try = [model]
    if fallback_model and fallback_model != model:
        models_to_try.append(fallback_model)

    endpoint = github_models_endpoint()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "tools-transcription-pipeline",
    }

    for model_index, model_name in enumerate(models_to_try):
        for attempt in range(max_retries + 1):
            _debug_log(
                f"Sending chat completion request | model={model_name} | messages={len(messages)} "
                f"| endpoint={endpoint} | attempt={attempt + 1}/{max_retries + 1}"
            )

            request_body: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }

            req = request.Request(
                endpoint,
                data=json.dumps(request_body).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            try:
                with request.urlopen(req, timeout=120) as response:
                    raw = response.read().decode("utf-8")
                    payload = json.loads(raw)
                    _debug_log(f"HTTP {getattr(response, 'status', 'unknown')} response received")

                text = _extract_text(payload)
                if not text:
                    _debug_log(f"No textual content extracted from payload keys={list(payload.keys())}")
                    try:
                        _debug_log(f"Payload preview={json.dumps(payload)[:1000]}")
                    except Exception:
                        pass
                    return None
                return text
            except error.HTTPError as exc:
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    error_body = "<unavailable>"

                error_code = ""
                try:
                    error_payload = json.loads(error_body)
                    if isinstance(error_payload, dict):
                        maybe_error = error_payload.get("error")
                        if isinstance(maybe_error, dict):
                            error_code = str(maybe_error.get("code", ""))
                except Exception:
                    pass

                _debug_log(
                    f"HTTPError {exc.code} {exc.reason} | model={model_name} | code={error_code or '<none>'} "
                    f"| body={error_body[:1000]}"
                )

                if (
                    exc.code == 400
                    and error_code == "unavailable_model"
                    and model_index + 1 < len(models_to_try)
                ):
                    _debug_log(f"Model {model_name} unavailable; trying fallback model {models_to_try[model_index + 1]}")
                    break

                should_retry = exc.code == 429 or 500 <= exc.code <= 599
                if should_retry and attempt < max_retries:
                    delay = retry_base_seconds * (2**attempt)
                    _debug_log(f"Retrying after transient HTTP error in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                return None
            except error.URLError as exc:
                _debug_log(f"URLError | model={model_name} | reason={exc.reason}")
                if attempt < max_retries:
                    delay = retry_base_seconds * (2**attempt)
                    _debug_log(f"Retrying after network error in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                return None
            except TimeoutError:
                _debug_log(f"TimeoutError while calling GitHub Models endpoint | model={model_name}")
                if attempt < max_retries:
                    delay = retry_base_seconds * (2**attempt)
                    _debug_log(f"Retrying after timeout in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                return None
            except json.JSONDecodeError as exc:
                _debug_log(f"JSONDecodeError | model={model_name} | {exc}")
                return None

    return None
