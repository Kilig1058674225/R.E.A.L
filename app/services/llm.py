from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterator

from app.config import Settings


class LLMConfigurationError(RuntimeError):
    pass


class LLMRequestError(RuntimeError):
    pass


def chat_completion(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 900,
) -> str:
    if not settings.llm_configured:
        raise LLMConfigurationError("LLM is not configured. Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env.")

    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMRequestError(f"LLM request failed with HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise LLMRequestError(f"LLM request failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMRequestError("LLM request timed out.") from exc

    content = _extract_content(data)
    if not content:
        raise LLMRequestError("LLM response did not contain assistant content.")
    return content


def chat_completion_stream(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 900,
) -> Iterator[str]:
    if not settings.llm_configured:
        raise LLMConfigurationError("LLM is not configured. Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL in .env.")

    url = f"{settings.llm_base_url}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue

                data_text = line.removeprefix("data:").strip()
                if data_text == "[DONE]":
                    break

                try:
                    data = json.loads(data_text)
                except json.JSONDecodeError:
                    continue

                delta = _extract_stream_delta(data)
                if delta:
                    yield delta
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise LLMRequestError(f"LLM stream failed with HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise LLMRequestError(f"LLM stream failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMRequestError("LLM stream timed out.") from exc


def _extract_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def _extract_stream_delta(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0]
    if not isinstance(choice, dict):
        return ""

    delta = choice.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content

    message = choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    text = choice.get("text")
    return text if isinstance(text, str) else ""
