"""Where is the whitespace?

Compares what the local corpus says buyers are missing against what the spec
actually builds. A need the market has and the spec already covers is a closed
gap — that is your differentiation. A need nobody covers, including you, is the
cheapest feature you can add.
"""

from __future__ import annotations

import re

from ..market_intel.corpus import unmet_needs

_STOPWORDS = {"a", "an", "the", "on", "in", "of", "for", "and", "with", "no", "to"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", (text or "").lower())
            if len(t) > 2 and t not in _STOPWORDS}


def _spec_text(spec: dict) -> set[str]:
    parts = [spec.get("one_liner", ""), spec.get("problem", ""),
             spec.get("value_prop", ""), spec.get("differentiation", "")]
    parts += [f.get("name", "") + " " + f.get("why", "")
              for f in spec.get("features", []) if isinstance(f, dict)]
    parts += [str(item) for item in spec.get("mvp_scope", [])]
    return _tokens(" ".join(parts))


def analyze(spec: dict) -> dict:
    """Score how much of the known whitespace this spec actually occupies."""
    needs = unmet_needs(spec.get("template", "landing_page"))
    text = _spec_text(spec)

    closed, open_gaps = [], []
    for need, play in needs:
        tokens = _tokens(need)
        covered = bool(tokens & text)
        overlap = len(tokens & text) / max(1, len(tokens))
        entry = {
            "need": need,
            "covered": covered,
            "overlap": round(overlap, 2),
            "size": 3 if covered else 5,   # how wide the gap still is, 1–5
            "play": play,
            "evidence": "local corpus: competitor archetypes do not offer this",
        }
        (closed if covered else open_gaps).append(entry)

    total = max(1, len(needs))
    score = round(100 * len(closed) / total)
    return {
        "slug": spec.get("slug"),
        "differentiation_score": score,
        "closed": closed,
        "open": sorted(open_gaps, key=lambda g: -g["size"]),
        "advice": [f"Add “{g['need']}” — {g['play']}" for g in open_gaps[:2]],
    }


def format_gaps(result: dict) -> str:
    lines = [f"Whitespace: {result['differentiation_score']}% of known needs covered"]
    for entry in result["closed"]:
        lines.append(f"  ✓ {entry['need']}")
    for entry in result["open"]:
        lines.append(f"  · open ({entry['size']}/5): {entry['need']} — {entry['play']}")
    return "\n".join(lines)
