"""Optional network adapters.

Off by default. Each function returns ``(results, note)`` so the caller can
record an honest gap when an adapter is configured but unreachable. Standard
library only, short timeouts, and a failure is data rather than a crash.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .. import config

TIMEOUT = 6


class AdapterUnavailable(RuntimeError):
    pass


def configured() -> dict[str, bool]:
    return {
        "searxng": bool(config.SEARXNG_URL),
        "firecrawl": bool(config.FIRECRAWL_URL),
    }


def searxng_search(query: str, limit: int = 5) -> list[dict]:
    """Search a self-hosted SearXNG instance. Raises if not configured/broken."""
    if not config.SEARXNG_URL:
        raise AdapterUnavailable("SEARXNG_URL is not set")
    url = f"{config.SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json"
    payload = _get(url)
    return [{"claim": item.get("title", ""), "url": item.get("url"),
             "source": "searxng", "confidence": 0.6}
            for item in (payload or {}).get("results", [])[:limit]]


def firecrawl_scrape(url: str) -> dict:
    """Scrape one page through Firecrawl. Raises if not configured/broken."""
    if not config.FIRECRAWL_URL:
        raise AdapterUnavailable("FIRECRAWL_URL is not set")
    body = {"url": url}
    headers = {"Content-Type": "application/json"}
    if config.FIRECRAWL_API_KEY:
        headers["Authorization"] = f"Bearer {config.FIRECRAWL_API_KEY}"
    return _post(f"{config.FIRECRAWL_URL}/v0/scrape", body, headers)


# --------------------------------------------------------------------------

def _get(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "hoolulu-hub/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AdapterUnavailable(str(exc)) from exc


def _post(url: str, body: dict, headers: dict):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, timeout=TIMEOUT
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AdapterUnavailable(str(exc)) from exc
