"""Revenue: projections are labelled, receipts are facts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import config

LEDGER = None


def ledger_path() -> Path:
    return Path(LEDGER or (config.STATE_DIR / "receipts.jsonl"))


def projection(spec: dict, *, customers: int = 10, churn: float = 0.08) -> dict:
    """A deliberately simple model. The assumptions travel with the number."""
    money = spec.get("monetization", {}) or {}
    price = float(money.get("price_usd") or 0)
    billing = money.get("billing", "once")
    monthly = price if billing in ("monthly", "yearly") else price / 12

    month_1 = customers * monthly
    month_3 = month_1 * (1 + 2 * (1 - churn)) if billing in ("monthly", "yearly") \
        else month_1 * 1.5
    month_12 = month_1 * (1 + 11 * (1 - churn)) if billing in ("monthly", "yearly") \
        else month_1 * 4

    record = {
        "slug": spec.get("slug"),
        "model": money.get("model", "unknown"),
        "price_usd": price,
        "unit": money.get("unit", "unit"),
        "projection": {
            "month_1_usd": round(month_1, 2),
            "month_3_usd": round(month_3, 2),
            "month_12_usd": round(month_12, 2),
        },
        "assumptions": [
            f"{customers} paying customers by end of month 1",
            f"monthly churn {churn:.0%}" if billing in ("monthly", "yearly")
            else "one-time sales repeat about 4x over a year",
            "projection from the local corpus, not from measurement",
        ],
    }
    return record


def record_receipt(slug: str, amount: float, *, note: str = "") -> dict:
    """Append a receipt. This is the only revenue fact the hub knows."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "slug": slug,
        "amount": round(float(amount), 2),
        "note": note,
        "operator": config.OPERATOR,
    }
    ledger_path().parent.mkdir(parents=True, exist_ok=True)
    with ledger_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def actuals() -> dict:
    """Gross revenue per slug, from receipts only."""
    totals: dict[str, dict] = {}
    path = ledger_path()
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                slug = entry.get("slug", "?")
                bucket = totals.setdefault(slug, {"gross_usd": 0.0, "customers": 0})
                bucket["gross_usd"] += float(entry.get("amount", 0))
                bucket["customers"] += 1
    for bucket in totals.values():
        bucket["gross_usd"] = round(bucket["gross_usd"], 2)
    return totals
