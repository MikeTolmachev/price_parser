from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from .schema import ChangeInfo, FilterResult

log = logging.getLogger(__name__)


def _fmt_price(price: int | None) -> str:
    if price is None:
        return "N/A"
    return f"{price:,} EUR".replace(",", ".")


def _build_message(
    result: FilterResult,
    change: Optional[ChangeInfo] = None,
) -> str:
    l = result.listing
    lines: list[str] = []

    # Header
    if change and change.is_new:
        lines.append("NEW MATCH FOUND")
    elif change and change.is_changed:
        lines.append("LISTING CHANGED")
    else:
        lines.append("Porsche Match")
    lines.append("")

    # Core info
    lines.append(l.title)
    lines.append(f"Price: {_fmt_price(l.price_eur)}")
    lines.append(f"Mileage: {l.mileage_km:,} km".replace(",", ".") if l.mileage_km else "Mileage: N/A")
    lines.append(f"Registration: {l.first_registration or 'N/A'}")
    lines.append(f"Location: {l.location or 'N/A'}")
    if l.dealer_name:
        lines.append(f"Dealer: {l.dealer_name}")
    lines.append(f"Source: {l.source}")
    lines.append("")

    # Change details
    if change and change.is_changed and change.changes:
        lines.append("Changes:")
        for field, (old, new) in change.changes.items():
            if field == "price_eur":
                lines.append(f"  Price: {_fmt_price(old)} -> {_fmt_price(new)}")
            elif field == "status":
                lines.append(f"  Status: {old} -> {new}")
            else:
                lines.append(f"  {field}: {old} -> {new}")
        lines.append("")

    # Status
    lines.append(f"Accident-free: {'Yes' if l.accident_free else 'No' if l.accident_free is False else 'N/A'}")
    lines.append(f"Porsche Approved: {l.porsche_approved_months or 'N/A'} months")
    if l.owners:
        lines.append(f"Owners: {l.owners}")
    lines.append("")

    # Must-have options
    lines.append("Must-have options:")
    for opt, found in result.detected.items():
        if opt in _NICE_NAMES:
            continue
        status = "[+]" if found else "[-]"
        lines.append(f"  {status} {opt}")
    lines.append("")

    # Nice-to-have
    if result.nice_to_have_present:
        lines.append(f"Nice-to-have: {', '.join(result.nice_to_have_present)}")
        lines.append("")

    lines.append(f"Score: {result.score}")
    lines.append(f"Link: {l.url}")

    return "\n".join(lines)


_NICE_NAMES = {
    "90L fuel tank",
    "Surround View / 360 camera",
    "Glass sunroof",
    "PPF / Steinschlagschutzfolie",
}


def send_telegram(
    result: FilterResult,
    chat_id: str,
    change: Optional[ChangeInfo] = None,
) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        log.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
        return

    text = _build_message(result, change)

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=20,
        )
        resp.raise_for_status()
        log.info("Telegram notification sent for: %s", result.listing.title)
    except requests.RequestException:
        log.exception("Failed to send Telegram notification for: %s", result.listing.title)


def should_notify(
    result: FilterResult,
    change: ChangeInfo,
) -> bool:
    if not result.is_match:
        return False
    return change.is_new or change.is_changed
