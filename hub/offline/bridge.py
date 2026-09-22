"""The switch between the local model and deterministic reasoning.

One entry point, ``think_json``: try the model, validate what came back, and if
anything at all goes wrong use the fallback instead. Whichever one answered is
stamped onto the result, so a guess is never presented as research.
"""

from __future__ import annotations

from .provider import OfflineModelUnavailable, health, json_complete
from .. import config

_HEURISTIC = {
    "source": "offline-heuristic",
    "model": None,
}


def provenance(model: str | None = None, source: str = "offline-model") -> dict:
    from datetime import datetime, timezone

    return {
        "source": source,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def think_json(*, system: str, prompt: str, fallback, validate=None,
               max_tokens: int = 1200) -> tuple[dict, dict]:
    """Return ``(data, provenance)`` from the model, or from ``fallback``.

    ``fallback`` is a zero-argument callable returning the deterministic answer.
    ``validate`` optional: ``(data) -> list[str]``; non-empty rejects the answer.
    """
    status = health()
    if status["ok"]:
        data = json_complete(system, prompt, max_tokens=max_tokens)
        if data is not None:
            problems = validate(data) if validate else []
            if not problems:
                model = status["models"][0] if status["models"] else config.OFFLINE_MODEL
                return data, provenance(model)
    data = fallback()
    data.setdefault("provenance", {})
    if isinstance(data.get("provenance"), dict):
        data["provenance"] = {**_HEURISTIC, **data["provenance"]}
    return data, provenance(None, "offline-heuristic")


def status_line() -> str:
    """One line for a UI badge: which brain is answering, and why."""
    status = health()
    if status["ok"]:
        model = status["models"][0] if status["models"] else config.OFFLINE_MODEL
        return f"offline model · {model} · {status['url']}"
    return f"deterministic · no model at {status['url']}"


def available() -> bool:
    try:
        return health()["ok"]
    except OfflineModelUnavailable:
        return False
