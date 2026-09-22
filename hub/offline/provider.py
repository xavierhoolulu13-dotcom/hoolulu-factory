"""Client for a llama.cpp server (or any OpenAI-compatible endpoint).

Standard library only. Every failure raises ``OfflineModelUnavailable`` so the
caller can fall back instead of dying — a missing model is a degraded mode,
never an outage.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .. import config

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class OfflineModelUnavailable(RuntimeError):
    """No model server answered. Callers fall back to deterministic reasoning."""


def base_url() -> str:
    return config.OFFLINE_URL.rstrip("/")


def health(timeout: float | None = None) -> dict:
    """Probe the model server. Returns a status dict; never raises."""
    timeout = timeout if timeout is not None else min(config.OFFLINE_TIMEOUT, 5.0)
    url = base_url()
    models: list[str] = []
    last_error = None
    for path in ("/models", "/health", "/props"):
        try:
            payload = _get(url + path, timeout=timeout)
        except OfflineModelUnavailable as exc:
            last_error = str(exc)
            continue
        if isinstance(payload, dict) and "data" in payload:
            models = [item.get("id", "?") for item in payload["data"] or []]
        return {"ok": True, "url": url, "models": models, "probe": path}
    return {"ok": False, "url": url, "models": [], "error": last_error or "unreachable"}


def complete(messages: list[dict], *, temperature: float = 0.3,
             max_tokens: int = 1200, timeout: float | None = None,
             model: str | None = None) -> dict:
    """Chat completion. Raises ``OfflineModelUnavailable`` on any failure."""
    body = {
        "model": model or config.OFFLINE_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    payload = _post(base_url() + "/chat/completions", body,
                    timeout=timeout or config.OFFLINE_TIMEOUT)
    try:
        choice = payload["choices"][0]
        text = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OfflineModelUnavailable(f"unexpected response shape: {exc}") from exc
    return {
        "text": (text or "").strip(),
        "model": payload.get("model") or model or config.OFFLINE_MODEL,
        "usage": payload.get("usage", {}),
    }


def json_complete(system: str, user: str, **kw) -> dict | None:
    """Ask for JSON and get it back parsed.

    Returns ``None`` — never raises — when the model is absent or its answer is
    not valid JSON, so callers can fall back in one line.
    """
    guard = ("Reply with a single JSON object and nothing else. "
             "No markdown fences, no commentary.")
    try:
        result = complete(
            [{"role": "system", "content": system.strip() + "\n" + guard},
             {"role": "user", "content": user}],
            temperature=0.2, **kw,
        )
    except OfflineModelUnavailable:
        return None
    return parse_json_object(result["text"])


def parse_json_object(text: str) -> dict | None:
    """Extract the first JSON object from model output. Tolerant on purpose."""
    if not text:
        return None
    cleaned = text.strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------

def _request(url: str, *, data: bytes | None = None, headers: dict | None = None,
             timeout: float):
    request = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise OfflineModelUnavailable(f"{url} → HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise OfflineModelUnavailable(f"{url} → {exc.reason}") from exc
    except TimeoutError as exc:
        raise OfflineModelUnavailable(f"{url} → timed out after {timeout}s") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _get(url: str, timeout: float):
    return _request(url, timeout=timeout)


def _post(url: str, body: dict, timeout: float):
    data = json.dumps(body).encode("utf-8")
    return _request(url, data=data, timeout=timeout,
                    headers={"Content-Type": "application/json"})
