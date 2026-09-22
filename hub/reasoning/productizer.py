"""Turn one sentence into a product spec that is worth building.

The output is always a valid ``product`` contract. Two ways to get there:

1. The local model drafts it (llama.cpp at ``HOOLULU_OFFLINE_URL``), and the
   draft is rejected unless it validates against the contract.
2. The deterministic builder below fills it in from the local corpus.

Either way ``provenance.source`` says which one happened, so a template-generated
guess is never presented as research-backed positioning.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..contracts import validate_contract
from ..market_intel.corpus import profile_for
from ..offline import bridge

SLUG_MAX = 38

_STRIP_LEAD = re.compile(
    r"^\s*(please\s+)?(hey\s+amanda[,\s]+)?(can you\s+)?"
    r"(build|make|create|whip up|spin up|generate|ship|i need|i want|i'd like)\s+"
    r"(me\s+)?(a\s+|an\s+|the\s+)?", re.IGNORECASE)
_STRIP_TAIL = re.compile(
    r"\s*(,?\s*(and|then|please)?\s*(host|deploy|publish|ship|launch)\s*(it|that)?"
    r"(\s+(and\s+)?(maintain|keep|monitor)\s+(it|that|running)?)?)\s*$",
    re.IGNORECASE)
_HOST_HINT = re.compile(r"\b(host|deploy|publish|launch|ship)\b", re.IGNORECASE)


_SMALL_WORDS = {"a", "an", "the", "and", "or", "for", "of", "to", "in", "on",
                "my", "with", "at", "by", "me"}


def slugify(text: str, fallback: str = "product") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:SLUG_MAX].strip("-")
    return slug or fallback


def title_case(text: str) -> str:
    """Title case that leaves small words alone: 'a mileage tracker for my crew'."""
    words = text.split()
    cased = []
    for index, word in enumerate(words):
        lowered = word.lower()
        if index not in (0, len(words) - 1) and lowered in _SMALL_WORDS:
            cased.append(lowered)
        else:
            cased.append(word[:1].upper() + word[1:])
    return " ".join(cased)


def slug_words(text: str, max_len: int = 32) -> str:
    """Slug from the words that carry meaning, so URLs stay short enough to share."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    keep = [w for w in words if w not in _SMALL_WORDS] or words
    slug = "-".join(keep)
    while len(slug) > max_len and len(keep) > 2:
        keep = keep[:-1]
        slug = "-".join(keep)
    return slug[:max_len].strip("-")


def parse_request(request: str, template: str | None = None) -> dict:
    """Pull the product name, slug, template and intent out of a sentence."""
    from ..market_intel.corpus import detect_template

    text = (request or "").strip()
    core = _STRIP_LEAD.sub("", text)
    core = _STRIP_TAIL.sub("", core)
    core = re.sub(r"\s+", " ", core).strip(" .!?,")
    if not core:
        core = "Hoolulu Product"

    name = title_case(core)
    return {
        "request": text,
        "core": core,
        "name": name,
        "slug": slug_words(core) or slugify(template or "", "product"),
        "template": template or detect_template(text),
        "wants_hosting": bool(_HOST_HINT.search(text)),
    }


def build_spec(request: str, *, template: str | None = None, slug: str | None = None,
               name: str | None = None, research: dict | None = None) -> dict:
    """Build a validated product spec from a plain-language request."""
    parsed = parse_request(request, template)
    template = template or parsed["template"]
    slug = slugify(slug or parsed["slug"])
    name = name or parsed["name"]
    profile = profile_for(template)
    research = research or {}

    def deterministic() -> dict:
        builder = _BUILDERS.get(template, _landing_page_spec)
        spec = builder(name, parsed["core"], profile)
        spec["slug"] = slug
        spec["template"] = template
        spec["name"] = name
        spec["scores"] = _scores(spec, research, template, model=False)
        return spec

    system = (
        "You are the product manager of an offline AI factory that ships small, "
        "sellable web products for Hawaii small businesses. You return one JSON "
        "object and nothing else. Be specific and commercial: name the buyer, the "
        "pain, the cheapest path to the first dollar, and what to leave out."
    )
    user = (
        f"Operator request: {request}\n"
        f"Product name: {name}\n"
        f"Slug: {slug}\n"
        f"Template (fixed, do not change): {template}\n"
        f"Local market context: {profile['demand_signal']}\n"
        f"Price band: {profile['price_band']}\n"
        f"Known competitor weaknesses: "
        f"{'; '.join(a['weakness'] for a in profile['archetypes'])}\n\n"
        "Return JSON with keys: slug, name, one_liner, template, audience{who,where,"
        "pain_level 1-5}, problem, value_prop, features[{name,why,effort s|m|l}] (3-6),"
        " mvp_scope[3-6 strings], out_of_scope[strings], monetization{model,price_usd,"
        "unit,billing once|monthly|yearly|usage,first_dollar_path}, distribution"
        "[{channel,why,effort s|m|l}] (2-4), competitors[{name,offering,weakness}],"
        " differentiation, risks[{risk,mitigation}] (2-4), scale_path[2-4 strings],"
        " scores{sellability,scalability,buildability,confidence 0-100}."
    )

    spec, provenance = bridge.think_json(
        system=system, prompt=user, fallback=deterministic,
        validate=lambda data: validate_contract("product", _coerce(data, slug, name, template)),
        max_tokens=1400,
    )

    spec = _coerce(spec, slug, name, template)
    spec["provenance"] = provenance
    spec.setdefault("scores", {})
    spec["scores"] = _scores(spec, research, template,
                             model=provenance.get("source") == "offline-model")
    spec["scores"]["confidence"] = spec["scores"].get("confidence", 55)
    spec["request"] = request
    spec["wants_hosting"] = parsed["wants_hosting"]
    return spec


# --------------------------------------------------------------------------
# deterministic specs
# --------------------------------------------------------------------------

def _web_game_spec(name: str, core: str, profile: dict) -> dict:
    return {
        "one_liner": f"{name} — a one-thumb browser game that loads instantly, "
                     f"plays offline and is easy to share.",
        "audience": {"who": "phone-first players with two minutes to kill",
                     "where": "mobile web, handed over by link or QR",
                     "pain_level": 2},
        "problem": "Arcade clones are ad-ridden, slow to load and need an install. "
                   "Nobody wants another app for five minutes of play.",
        "value_prop": "Open the link and you are playing in under a second — no app, "
                      "no signup, no ads, and it still works with no signal.",
        "features": [
            {"name": "Instant load, zero network requests", "why": "the whole game is "
             "one small page; it survives hotel wifi and airplane mode", "effort": "s"},
            {"name": "Keyboard, WASD and swipe controls", "why": "one thumb on a phone, "
             "arrow keys on a laptop", "effort": "s"},
            {"name": "Stored high score", "why": "gives a reason to open it a second "
             "time", "effort": "s"},
            {"name": "Pause and instant restart", "why": "play happens in stolen "
             "moments; quitting and resuming must be free", "effort": "s"},
            {"name": "Shareable challenge link", "why": "distribution is the whole "
             "game; a score in a link is the cheapest viral loop", "effort": "m"},
        ],
        "mvp_scope": ["single canvas game loop", "score + stored high score",
                      "swipe and keyboard controls", "game over and restart",
                      "one shareable link"],
        "out_of_scope": ["accounts", "leaderboard server", "multiplayer", "ads"],
        "monetization": {
            "model": "free play, tip jar, then white-label licence to venues",
            "price_usd": 0, "unit": "player", "billing": "once",
            "first_dollar_path": "Put a QR code on a table tent or a tour van; add a "
                                 "tip button; then reskin the same build and licence "
                                 "it to one venue for a few hundred dollars.",
        },
        "distribution": list(profile["channels"]),
        "competitors": list(profile["archetypes"]),
        "differentiation": "It is local, it loads instantly, and it works offline — "
                           "three things the portals and the app stores cannot copy "
                           "without giving up their ad stack.",
        "risks": [
            {"risk": "Games have brutal churn; most players never return",
             "mitigation": "ship the high score and the challenge link in v1 so the "
                           "second visit is built in"},
            {"risk": "Free play earns nothing by itself",
             "mitigation": "treat the game as a lead magnet for the white-label "
                           "licence, not as the product"},
            {"risk": "Copycats",
             "mitigation": "the asset is the local theme and the venue relationship, "
                           "not the code"},
        ],
        "scale_path": ["reskin per venue and licence repeatedly",
                       "bundle into a local-games collection with one shared hub page",
                       "sell the QR + analytics package to tourism operators"],
    }


def _landing_page_spec(name: str, core: str, profile: dict) -> dict:
    return {
        "one_liner": f"{name} — a fast, mobile-first page that turns a search or a "
                     f"QR scan into a call, a booking or a visit.",
        "audience": {"who": "owner-operators of small local businesses",
                     "where": "search, Google Business Profile, printed QR",
                     "pain_level": 4},
        "problem": "Small shops either have no page at all, or a DIY builder page they "
                   "never finished. Both lose the customer who was already looking.",
        "value_prop": "A page that loads in under a second on a phone, says what you "
                      "do and where you are, and gives one obvious way to contact you.",
        "features": [
            {"name": "Above-the-fold promise and one call to action",
             "why": "a visitor decides in three seconds", "effort": "s"},
            {"name": "Tap-to-call and tap-to-text buttons",
             "why": "the phone is the conversion for a local business", "effort": "s"},
            {"name": "Hours, service area and map link",
             "why": "the three questions every local search asks", "effort": "s"},
            {"name": "Proof block (reviews, photos, years in business)",
             "why": "strangers need a reason to trust", "effort": "m"},
            {"name": "Local schema markup", "why": "helps Google show the right "
             "hours and address", "effort": "s"},
        ],
        "mvp_scope": ["hero with promise and CTA", "services list", "hours and "
                      "location", "tap-to-call footer", "one-page, no CMS"],
        "out_of_scope": ["blog", "multi-language", "e-commerce", "custom back end"],
        "monetization": {
            "model": "one-time build fee plus monthly hosting and care",
            "price_usd": 490, "unit": "project", "billing": "monthly",
            "first_dollar_path": "Walk the block with a QR card, build the page on the "
                                 "spot, and take a deposit before you leave the shop.",
        },
        "distribution": list(profile["channels"]),
        "competitors": list(profile["archetypes"]),
        "differentiation": "Live in 48 hours, priced for a shop not an enterprise, and "
                           "answered by a person who knows the islands.",
        "risks": [
            {"risk": "Owners stall on content and photos",
             "mitigation": "ship with placeholder copy they can approve, never a blank "
                           "template awaiting answers"},
            {"risk": "One-off builds do not compound",
             "mitigation": "the monthly care fee is the product; the build is the "
                           "on-ramp"},
            {"risk": "Churn after month three",
             "mitigation": "monthly report showing calls and scans from the page"},
        ],
        "scale_path": ["template the build so it takes an hour, not a week",
                       "productise care into a fixed monthly plan",
                       "resell the same page shape across one industry at a time"],
    }


def _tool_spec(name: str, core: str, profile: dict) -> dict:
    return {
        "one_liner": f"{name} — a single-job utility that works on a phone, offline, "
                     f"with no account.",
        "audience": {"who": "operators doing the same calculation or log by hand",
                     "where": "bookmarked on a phone, used on the job",
                     "pain_level": 3},
        "problem": "The job is done in a spreadsheet that breaks on a phone, or in a "
                   "SaaS that wants a login, a seat and your data for ten minutes of "
                   "work a day.",
        "value_prop": "Open the link, do the job, close the tab. It remembers your "
                      "entries locally and works with no signal.",
        "features": [
            {"name": "Works offline, stores locally", "why": "job sites and vans have "
             "bad reception", "effort": "m"},
            {"name": "No account, no onboarding", "why": "friction kills a tool used "
             "for two minutes", "effort": "s"},
            {"name": "Opinionated defaults", "why": "the value is not having to "
             "configure it", "effort": "s"},
            {"name": "Export to CSV or copy-to-clipboard", "why": "the result has to "
             "leave the tool and land in an invoice or a message", "effort": "s"},
        ],
        "mvp_scope": ["one screen, one job", "local persistence", "export",
                      "mobile layout"],
        "out_of_scope": ["accounts", "sync", "teams", "reporting dashboards"],
        "monetization": {
            "model": "monthly subscription with a one-time lifetime option",
            "price_usd": 19, "unit": "seat", "billing": "monthly",
            "first_dollar_path": "Put it in the hands of five people in one trade; "
                                 "charge from the first month — a tool that saves ten "
                                 "minutes a day is an expense claim, not a purchase.",
        },
        "distribution": list(profile["channels"]),
        "competitors": list(profile["archetypes"]),
        "differentiation": "It does one job, offline, without an account — the exact "
                           "shape a spreadsheet cannot take and a SaaS will not bother "
                           "to build.",
        "risks": [
            {"risk": "Too narrow to find buyers",
             "mitigation": "pick a job that already has a weekly rhythm for a trade "
                           "you can reach in person"},
            {"risk": "Local-only storage loses data on a cleared browser",
             "mitigation": "one-tap export from day one, and say so in the UI"},
            {"risk": "Free clones appear",
             "mitigation": "own the distribution inside one trade, not the feature set"},
        ],
        "scale_path": ["one trade at a time, reusing the same shell",
                       "bundle tools into a crew toolkit",
                       "attach to an existing service you already invoice"],
    }


_BUILDERS = {
    "web_game": _web_game_spec,
    "landing_page": _landing_page_spec,
    "tool": _tool_spec,
}


# --------------------------------------------------------------------------
# scoring + coercion
# --------------------------------------------------------------------------

_TEMPLATE_BUILDABILITY = {"web_game": 85, "landing_page": 92, "tool": 78}
_TEMPLATE_SELLABILITY = {"web_game": 46, "landing_page": 66, "tool": 60}
_TEMPLATE_SCALABILITY = {"web_game": 72, "landing_page": 48, "tool": 76}


def _scores(spec: dict, research: dict, template: str, *, model: bool) -> dict:
    channels = spec.get("distribution") or []
    features = spec.get("features") or []
    money = spec.get("monetization") or {}
    live = any(f.get("source") not in (None, "local-corpus")
               for f in (research.get("findings") or []))

    sellability = _TEMPLATE_SELLABILITY.get(template, 55)
    sellability += 6 * min(len(channels), 3)
    sellability += 5 if (money.get("price_usd") or 0) > 0 else 0
    sellability += 4 if len(features) >= 4 else 0
    sellability += 4 if len(spec.get("differentiation") or "") > 60 else 0
    sellability += 5 if live else 0

    scalability = _TEMPLATE_SCALABILITY.get(template, 60)
    scalability += 5 if money.get("billing") in ("monthly", "yearly", "usage") else 0
    scalability += 4 if any(c.get("effort") == "s" for c in channels) else 0
    scalability -= 8 if template == "landing_page" else 0  # human labour per sale

    buildability = _TEMPLATE_BUILDABILITY.get(template, 80)
    buildability -= 3 * max(0, len(spec.get("mvp_scope") or []) - 4)

    confidence = 55
    confidence += 20 if model else 0
    confidence += 6 if live else 0

    def clamp(value: int) -> int:
        return max(0, min(100, int(value)))

    return {"sellability": clamp(sellability), "scalability": clamp(scalability),
            "buildability": clamp(buildability), "confidence": clamp(confidence)}


def _coerce(spec: dict, slug: str, name: str, template: str) -> dict:
    """Force the fields the build stage depends on, whatever the model said."""
    spec = dict(spec or {})
    # the slug is ours: the operator asked for a name, the URL should match it
    spec["slug"] = slugify(slug, fallback=slug)
    spec["name"] = str(spec.get("name") or name)[:60]
    spec["template"] = template
    spec.setdefault("one_liner", f"{spec['name']} — built by the Hoolulu Factory.")
    spec.setdefault("audience", {"who": "local customers", "where": "mobile web"})
    spec.setdefault("problem", "Not yet validated with a human.")
    spec.setdefault("value_prop", "Fast, offline, and specific to one job.")
    spec.setdefault("features", [{"name": "Core feature", "why": "the reason it exists",
                                  "effort": "s"}])
    spec.setdefault("mvp_scope", ["the one job it does"])
    spec.setdefault("monetization", {
        "model": "one-time", "price_usd": 0, "unit": "unit", "billing": "once",
        "first_dollar_path": "Sell it to one person before building anything else.",
    })
    spec.setdefault("distribution", [{"channel": "direct", "why": "ask first",
                                      "effort": "s"}])
    for key in ("audience", "monetization"):
        if not isinstance(spec[key], dict):
            spec[key] = {}
    for key in ("features", "mvp_scope", "distribution"):
        if not isinstance(spec[key], list):
            spec[key] = []
    # provenance is part of the contract but is stamped by build_spec, never by
    # the model — put a placeholder in so validation does not reject a good draft
    spec.setdefault("provenance", {"source": "offline-model", "model": None})
    return spec


def format_spec(spec: dict) -> str:
    money = spec.get("monetization", {})
    scores = spec.get("scores", {})
    lines = [
        f"{spec['name']}  ({spec['slug']} · {spec['template']})",
        f"  {spec['one_liner']}",
        f"  buyer      : {spec.get('audience', {}).get('who', '?')}",
        f"  money      : {money.get('model', '?')} — "
        f"${money.get('price_usd', 0)}/{money.get('unit', '?')}"
        f" ({money.get('billing', 'once')})",
        f"  scores     : sell {scores.get('sellability', '?')} · "
        f"scale {scores.get('scalability', '?')} · "
        f"build {scores.get('buildability', '?')} · "
        f"confidence {scores.get('confidence', '?')}",
        f"  provenance : {spec.get('provenance', {}).get('source', '?')}",
    ]
    return "\n".join(lines)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
