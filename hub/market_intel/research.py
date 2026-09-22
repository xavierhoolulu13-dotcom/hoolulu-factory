"""The research stage: a validated ``research`` contract for one request."""

from __future__ import annotations

from ..contracts import check
from . import adapters
from .corpus import profile_for, timestamp


def research(query: str, *, slug: str | None = None, template: str = "landing_page",
             with_network: bool = True) -> dict:
    """Assemble what the factory knows about a request, honestly labelled."""
    profile = profile_for(template)
    findings = [
        {"claim": f"Buyer: {profile['buyer']}.", "source": "local-corpus",
         "confidence": 0.5, "url": None},
        {"claim": f"Where they are: {profile['where']}.", "source": "local-corpus",
         "confidence": 0.5, "url": None},
        {"claim": profile["demand_signal"], "source": "local-corpus",
         "confidence": 0.4, "url": None},
        {"claim": f"Price band in this category: {profile['price_band']}.",
         "source": "local-corpus", "confidence": 0.35, "url": None},
    ]
    for archetype in profile["archetypes"]:
        findings.append({
            "claim": f"Competitor archetype — {archetype['name']}: {archetype['offering']}. "
                     f"Weakness: {archetype['weakness']}.",
            "source": "local-corpus", "confidence": 0.4, "url": None,
        })

    gaps = [
        "No live demand measurement: searches, volume and willingness-to-pay are "
        "unverified until a network adapter is enabled.",
        "No named competitors: the corpus lists archetypes, not actual businesses.",
    ]

    # --- optional live enrichment -----------------------------------------
    if with_network:
        findings.extend(_live_findings(query, gaps))

    record = {
        "query": query,
        "slug": slug,
        "findings": findings,
        "gaps": gaps,
        "generated_at": timestamp(),
    }
    check("research", record)
    return record


def _live_findings(query: str, gaps: list[str]) -> list[dict]:
    """Merge in live results when an adapter is on. Never fabricate on failure."""
    found: list[dict] = []
    state = adapters.configured()

    if state["searxng"]:
        try:
            found.extend(adapters.searxng_search(query))
        except adapters.AdapterUnavailable as exc:
            gaps.append(f"SearXNG configured but unreachable: {exc}")
    else:
        gaps.append("SearXNG not configured (SEARXNG_URL unset) — no live search.")

    if state["firecrawl"]:
        gaps.append("Firecrawl is configured but no target URL was supplied for this query.")

    return found


def format_research(record: dict, limit: int = 6) -> str:
    lines = [f"Research for “{record['query']}”"]
    for finding in record["findings"][:limit]:
        marker = {"local-corpus": "corpus", "searxng": "live"}.get(
            finding["source"], finding["source"])
        lines.append(f"  · [{marker} {finding['confidence']:.2f}] {finding['claim']}")
    if record["gaps"]:
        lines.append("  Gaps:")
        lines.extend(f"    - {gap}" for gap in record["gaps"])
    return "\n".join(lines)
