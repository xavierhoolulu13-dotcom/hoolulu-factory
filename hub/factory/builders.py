"""The build stage: a product spec becomes a folder that runs.

Templates live in ``hoolulu-ecosystem-hub/factory/templates/<template>/`` and
are plain text with ``{{PLACEHOLDER}}`` slots. No template engine — a single
``str.replace`` pass, which keeps the templates readable as HTML and means a
stray brace can never break a build.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from .. import config
from ..contracts import check

PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

ACCENTS = {"web_game": "#2dd4bf", "landing_page": "#0ea5a4", "tool": "#6366f1"}
EMOJI = {"web_game": "\U0001F579️", "landing_page": "\U0001F33A", "tool": "\U0001F9F0"}
CURRENCY = {"web_game": ("free to play", "no card, no install"),
            "landing_page": ("per month", "hosting and care included"),
            "tool": ("per month", "cancel any time")}


class BuildError(RuntimeError):
    pass


def render(text: str, context: dict) -> str:
    """Replace ``{{KEY}}`` with ``context['KEY']``, leaving unknown keys visible."""
    def substitute(match):
        key = match.group(1)
        return str(context[key]) if key in context else match.group(0)
    return PLACEHOLDER.sub(substitute, text)


def context_for(spec: dict) -> dict:
    """Every placeholder the templates can ask for."""
    template = spec.get("template", "landing_page")
    money = spec.get("monetization", {}) or {}
    features = [f for f in spec.get("features", []) if isinstance(f, dict)]
    scope = [str(s) for s in spec.get("mvp_scope", [])]
    price = money.get("price_usd", 0) or 0
    price_text = "Free" if price == 0 else f"${price:,.0f}"
    unit, unit_note = CURRENCY.get(template, ("one-time", ""))

    context = {
        "NAME": spec.get("name", "Hoolulu Product"),
        "SLUG": spec.get("slug", "product"),
        "TAGLINE": _short(spec.get("one_liner", ""), 90),
        "ONE_LINER": spec.get("one_liner", ""),
        "TEMPLATE": template,
        "ACCENT": ACCENTS.get(template, "#2dd4bf"),
        "EMOJI": EMOJI.get(template, "\U0001F33A"),
        "YEAR": str(datetime.now().year),
        "CTA_TITLE": _cta_title(template),
        "CTA_TEXT": _cta_text(template, spec),
        "CTA_LABEL": _cta_label(template),
        "CTA_URL": _cta_url(template, spec),
        "PRICE": price_text,
        "PRICE_UNIT": f"{unit} · {unit_note}" if unit_note else unit,
        "PRICE_POINTS": "\n".join(f"<li>{_escape(s)}</li>" for s in scope[:5]) or
                        "<li>everything in the MVP scope</li>",
        "FEATURE_CARDS": "\n".join(
            f"<li><b>{_escape(str(f.get('name', '')))}</b>"
            f"<span>{_escape(str(f.get('why', '')))}</span></li>"
            for f in features[:6]) or "<li><b>Core</b><span>the reason it exists</span></li>",
        "PROBLEM_TITLE": "The problem",
        "PROBLEM": spec.get("problem", ""),
        "VALUE_PROP": spec.get("value_prop", ""),
        "EYEBROW": _eyebrow(spec),
        "PHONE": "(808) 555-0199",
        "PROMISE": "No contract. No setup fee. Live in 48 hours.",
        "FAQ_ITEMS": _faq(spec),
        "FOOTER": (f"{spec.get('name', '')} · built by the Hoolulu Factory · "
                   f"runs offline on your phone · <span data-year></span>"),
        "LABEL_ONE": _label_one(spec),
        "LABEL_TWO": _label_two(spec),
    }
    return context


def build(spec: dict, *, overwrite: bool = True) -> dict:
    """Instantiate a template into ``builds/<slug>/`` and sign the result."""
    started = time.time()
    config.ensure_dirs()
    slug = spec.get("slug") or "product"
    template = spec.get("template", "landing_page")
    source = config.TEMPLATES_DIR / template
    if not source.is_dir():
        raise BuildError(f"no template '{template}' at {source}")

    target = config.BUILD_ROOT / slug
    if target.exists() and overwrite:
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    context = context_for(spec)
    artifacts = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        # every file is text, and every file may carry placeholders (README included)
        rendered = render(path.read_text(encoding="utf-8"), context)
        destination.write_text(rendered, encoding="utf-8")
        artifacts.append(_artifact(destination, target))

    # the spec travels with the build so a deploy can be reproduced
    spec_path = target / "product.json"
    spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    artifacts.append(_artifact(spec_path, target))

    record = {
        "slug": slug,
        "template": template,
        "artifacts": artifacts,
        "entry": "index.html",
        "checks": [],
        "status": "built",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration_ms": int((time.time() - started) * 1000),
    }
    check("build", record)
    return record


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _artifact(path: Path, root: Path) -> dict:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(root)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _short(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _eyebrow(spec: dict) -> str:
    where = (spec.get("audience") or {}).get("where", "")
    return _short(f"Honolulu · Hawaii · {where}" if where else "Honolulu · Hawaii", 60)


def _cta_title(template: str) -> str:
    return {
        "web_game": "Want this on your own counter?",
        "landing_page": "Ready when you are",
        "tool": "Try it on your next job",
    }[template]


def _cta_text(template: str, spec: dict) -> str:
    if template == "web_game":
        return ("We licence this build to venues, tours and schools — your name and "
                "colours on it, on your QR codes, in a week.")
    if template == "tool":
        return ("Use it free for a week. If it saves you ten minutes a day, it is "
                "worth the subscription; if not, close the tab.")
    return ("Tell us the business and we will have a page you can approve on your "
            "own phone within 48 hours.")


def _cta_label(template: str) -> str:
    return {"web_game": "Get a quote", "landing_page": "Get started",
            "tool": "Start free week"}[template]


def _cta_url(template: str, spec: dict) -> str:
    subject = {
        "web_game": "Game licence enquiry",
        "landing_page": "New page enquiry",
        "tool": "Tool trial",
    }[template]
    name = spec.get("name", "product")
    return f"mailto:hello@hoolulu.local?subject={subject} — {name}".replace(" ", "%20")


def _faq(spec: dict) -> str:
    money = spec.get("monetization", {}) or {}
    price = money.get("price_usd", 0) or 0
    items = [
        ("What does it cost?",
         "Free to play." if price == 0 else
         f"${price:,.0f} {money.get('unit', '')}, billed {money.get('billing', 'once')}."),
        ("What do I get first?",
         " ".join(str(s) for s in (spec.get("mvp_scope") or [])[:3]) or
         "The one job it does, done properly."),
        ("How long until it is live?",
         "Immediately — this build is already running. Custom work is quoted per job."),
        ("Does it work offline?",
         "Yes. The whole thing is one small page with no network requests."),
    ]
    return "\n".join(
        f"<details><summary>{_escape(q)}</summary><p>{_escape(a)}</p></details>"
        for q, a in items
    )


def _label_one(spec: dict) -> str:
    text = (spec.get("request", "") + " " + spec.get("name", "")).lower()
    for word, label in (("mile", "Trip"), ("hour", "Task"), ("invoice", "Client"),
                        ("job", "Job"), ("shift", "Shift"), ("expense", "Item")):
        if word in text:
            return label
    return "Entry"


def _label_two(spec: dict) -> str:
    text = (spec.get("request", "") + " " + spec.get("name", "")).lower()
    for word, label in (("mile", "Miles"), ("hour", "Hours"), ("invoice", "Dollars"),
                        ("expense", "Dollars")):
        if word in text:
            return label
    return "Amount"
