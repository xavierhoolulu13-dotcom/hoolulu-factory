"""The local corpus: what the factory knows without a network.

Every entry is a *prior*. Confidence stays low on purpose (0.3–0.55) so that a
downstream stage can never mistake it for verified research. Update this file
with what you learn; it is the cheapest intelligence you own.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

KEYWORDS = {
    "web_game": ("game", "games", "arcade", "snake", "tetris", "puzzle",
                 "platformer", "quiz", "trivia", "play", "player", "score"),
    "landing_page": ("landing", "page", "site", "website", "booking", "book",
                     "menu", "reservation", "shop", "store", "portfolio",
                     "lead", "signup", "waitlist"),
    "tool": ("tool", "calculator", "converter", "tracker", "invoice", "estimate",
             "quote", "scheduler", "dashboard", "checklist", "timer", "log"),
}

DOMAINS = {
    "web_game": {
        "buyer": "players killing 2–5 minutes on a phone",
        "where": "mobile web, shared by link or QR",
        "demand_signal": "Huge free-to-play supply; attention is cheap and churn is "
                         "brutal. A game earns only if it has a hook people re-open "
                         "or a reason to be shared (local theme, leaderboard, event).",
        "price_band": "$0 play · $1–5 tip/remove-ads · $300–2,000 white-label licence",
        "archetypes": [
            {"name": "Ad-heavy arcade portals", "offering": "thousands of clones, "
             "interstitial ads every 30 seconds",
             "weakness": "slow to load, ad-ridden, nothing local or personal"},
            {"name": "App-store casual games", "offering": "polished but needs an "
             "install and permissions", "weakness": "install friction, store cut, "
             "no offline play"},
        ],
        "unmet": [
            ("instant load on hotel/venue wifi", "single small HTML file, zero requests"),
            ("offline play", "everything inline; no CDN, no tracking"),
            ("local identity", "place, slang and landmarks people recognise"),
            ("a reason to come back", "stored high scores and a shareable challenge link"),
        ],
        "channels": [
            {"channel": "QR at a physical venue", "why": "table tents, receipts and "
             "front windows turn foot traffic into players", "effort": "s"},
            {"channel": "local Facebook / community groups", "why": "a themed game is "
             "shareable news, not advertising", "effort": "s"},
            {"channel": "white-label to venues", "why": "one build, sold many times to "
             "bars, tours and schools", "effort": "m"},
        ],
    },
    "landing_page": {
        "buyer": "owner-operators of small local businesses",
        "where": "search, Google Business Profile, QR on printed material",
        "demand_signal": "Endless demand, low willingness to pay up front. The money "
                         "is in the monthly care fee and in being the person who "
                         "answers the phone, not in the build.",
        "price_band": "$300–900 build · $29–99/month hosting + care",
        "archetypes": [
            {"name": "Wix/Squarespace DIY", "offering": "templates the owner builds "
             "themselves", "weakness": "never finished, slow, no local SEO"},
            {"name": "Agencies", "offering": "$5k+ sites with a 6-week runway",
             "weakness": "price and latency a small shop will not tolerate"},
        ],
        "unmet": [
            ("live in 48 hours", "template-driven build, no discovery phase"),
            ("one local human to call", "named contact, not a ticket queue"),
            ("knows the islands", "local schema, landmarks, area codes"),
        ],
        "channels": [
            {"channel": "walking the strip with a QR card", "why": "the owner can see "
             "the page on their own phone before you leave", "effort": "s"},
            {"channel": "Google Business Profile gap list", "why": "businesses with no "
             "website link are pre-qualified demand", "effort": "m"},
            {"channel": "referral from existing clients", "why": "owners talk to each "
             "other more than they read ads", "effort": "s"},
        ],
    },
    "tool": {
        "buyer": "operators and crews doing a repeated calculation or log by hand",
        "where": "bookmarked on a phone, used on the job",
        "demand_signal": "Smaller audience, far higher intent. A tool that saves ten "
                         "minutes a day is an easy subscription; a tool that is "
                         "merely neat is not.",
        "price_band": "$9–29/month · $49–199 one-time",
        "archetypes": [
            {"name": "Generic SaaS", "offering": "broad features, login required, "
             "per-seat pricing", "weakness": "overkill, and it wants your data"},
            {"name": "Spreadsheet", "offering": "free and familiar",
             "weakness": "breaks on a phone, no offline, no reminders"},
        ],
        "unmet": [
            ("works offline on a phone", "local storage, no account"),
            ("no account, no onboarding", "open the link and use it"),
            ("fits one job exactly", "opinionated defaults instead of settings"),
        ],
        "channels": [
            {"channel": "trade and industry groups", "why": "the exact buyer is already "
             "in the room", "effort": "s"},
            {"channel": "QR on the job site", "why": "captured at the moment of pain",
             "effort": "s"},
            {"channel": "bundle with an existing service", "why": "attach it to work "
             "you already invoice", "effort": "m"},
        ],
    },
}

DEFAULT_DOMAIN = "landing_page"


def detect_template(text: str) -> str:
    """Pick a template from the words in a request. Ties go to ``landing_page``."""
    lowered = (text or "").lower()
    scores = {name: sum(1 for word in words if re.search(rf"\b{re.escape(word)}\b", lowered))
              for name, words in KEYWORDS.items()}
    best = max(scores, key=lambda name: scores[name])
    return best if scores[best] else DEFAULT_DOMAIN


def profile_for(template: str) -> dict:
    return DOMAINS.get(template, DOMAINS[DEFAULT_DOMAIN])


def unmet_needs(template: str) -> list[tuple[str, str]]:
    return list(profile_for(template)["unmet"])


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
