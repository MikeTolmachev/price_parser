from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .schema import Listing, FilterResult


def load_criteria(path: str | Path = "criteria.json") -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _contains_any(text: str, needles: list[str]) -> bool:
    t = text.lower()
    return any(n.lower() in t for n in needles)


def _extract_year(listing: Listing) -> Optional[int]:
    if listing.year:
        return listing.year
    if listing.first_registration:
        m = re.search(r"(\d{4})", listing.first_registration)
        if m:
            return int(m.group(1))
    return None


def _is_992_1(listing: Listing) -> bool:
    if listing.generation:
        gen = listing.generation.lower().replace(" ", "")
        if "992.1" in gen or "992i" in gen:
            return True
        if "992.2" in gen or "992ii" in gen:
            return False
    year = _extract_year(listing)
    if year is not None:
        return 2019 <= year <= 2024
    text = f"{listing.title} {listing.options_text}".lower()
    if "992" in text:
        return True
    # Explicit non-992 indicators
    if "991" in text or "997" in text or "996" in text or "964" in text:
        return False
    # Cannot determine generation — assume OK (search URLs pre-filter)
    return True


def _is_target_body(listing: Listing) -> bool:
    """Accept GTS variants (coupe and cabriolet). Reject Targa and non-GTS."""
    text = f"{listing.title} {listing.variant or ''} {listing.body_type or ''}".lower()
    # Reject Targa (not selected in search criteria)
    if "targa" in text:
        return False
    # Must be GTS
    if "gts" in text:
        return True
    return False


# Hard must-haves: these are set as Porsche Finder search filters,
# so listings without them are rejected outright.
HARD_MUST_HAVE_KEYWORDS: dict[str, list[str]] = {
    "Sport Chrono Paket": [
        "sport chrono", "sportchrono", "sport-chrono", "chrono",
    ],
    "Liftsystem Vorderachse (Front Axle Lift)": [
        "liftsystem", "front axle lift", "vorderachs-lift",
        "lift system", "frontaxlelift", "lift",
    ],
    "Hinterachslenkung (Rear-axle steering)": [
        "hinterachslenkung", "rear-axle steering", "rear axle steering",
        "hinterachs-lenkung", "4ws",
    ],
}

# Soft must-haves: desired but only affect score (listing cards often
# don't include full equipment lists).
SOFT_MUST_HAVE_KEYWORDS: dict[str, list[str]] = {
    "Adaptive cruise (Abstandsregeltempostat / InnoDrive)": [
        "abstandsregeltempostat", "innodrive", "adaptive cruise",
        "abstandsregel", "acc", "adaptive tempomat",
    ],
    "LED-Matrix / PDLS Plus": [
        "led-matrix", "led matrix", "pdls plus", "pdls+",
        "dynamic light system plus", "hd-matrix", "hd matrix",
    ],
    "BOSE or Burmester": [
        "bose", "burmester",
    ],
    "Adaptive Sports Seats Plus (18-way)": [
        "18-wege", "18 wege", "adaptive sportsitze",
        "adaptive sport seats plus", "sportsitze plus",
        "18-way", "adaptiv-sportsitze",
    ],
}

NICE_TO_HAVE_KEYWORDS: dict[str, list[str]] = {
    "90L fuel tank": [
        "kraftstoffbehälter 90", "90 l tank", "90-liter",
        "90l tank", "kraftstoffbehaelter 90",
    ],
    "Surround View / 360 camera": [
        "surround view", "360", "surroundview",
    ],
    "Glass sunroof": [
        "schiebe-/hubdach", "hubdach aus glas", "schiebedach",
        "glass sunroof", "panorama", "gsd",
    ],
    "PPF / Steinschlagschutzfolie": [
        "steinschlagschutzfolie", "ppf", "lackschutzfolie",
        "paint protection",
    ],
}


def evaluate(listing: Listing, criteria: dict) -> FilterResult:
    reasons: list[str] = []
    detected: dict[str, bool] = {}
    must_have_missing: list[str] = []
    nice_to_have_present: list[str] = []

    # --- combined text for keyword detection ---

    text = " ".join([
        listing.title,
        listing.options_text,
        " ".join(listing.options_list),
    ]).strip()
    text_lower = text.lower()

    # --- hard filters (reject only when data is definitively bad) ---

    if listing.accident_free is False:
        reasons.append("not accident-free (Unfallfrei required)")

    mileage_max = criteria.get("mileage_km_max", 50000)
    if listing.mileage_km is not None and listing.mileage_km > mileage_max:
        reasons.append(f"mileage {listing.mileage_km} km > {mileage_max} km")

    # Porsche Approved: reject only if explicitly < 12 months.
    # Treat None as unknown (may be on detail page); check title for hints.
    if listing.porsche_approved_months is not None and listing.porsche_approved_months < 12:
        reasons.append(
            f"Porsche Approved {listing.porsche_approved_months} months < 12 months required"
        )
    elif listing.porsche_approved_months is None:
        # Try to detect from title/options text
        if "approved" not in text_lower:
            reasons.append("Porsche Approved not mentioned")

    price_max = criteria.get("price_eur_max")
    if price_max and listing.price_eur is not None and listing.price_eur > price_max:
        reasons.append(f"price {listing.price_eur} EUR > {price_max} EUR")

    owners_max = criteria.get("owners_max", 2)
    if listing.owners is not None and listing.owners > owners_max:
        reasons.append(f"owners {listing.owners} > {owners_max}")

    year_range = criteria.get("years", [2020, 2024])
    year = _extract_year(listing)
    if year is not None and (year < year_range[0] or year > year_range[1]):
        reasons.append(f"year {year} outside {year_range[0]}-{year_range[1]}")

    if not _is_992_1(listing):
        reasons.append("not 992.1 generation")

    if not _is_target_body(listing):
        reasons.append("body type excluded (Targa/non-GTS)")

    # --- equipment option detection ---
    # Listing cards often only have a short title; full equipment lists
    # are only on detail pages.  We consider the data "rich" when
    # options_text has meaningful content (> 20 chars beyond the title).
    has_rich_data = len(listing.options_text) > 20

    # Hard must-haves: reject only when we have equipment data and the
    # option is definitively absent.  With title-only data, detect what
    # we can and let score reflect uncertainty.
    hard_missing: list[str] = []
    for option_name, keywords in HARD_MUST_HAVE_KEYWORDS.items():
        found = _contains_any(text, keywords)
        detected[option_name] = found
        if not found:
            hard_missing.append(option_name)

    if hard_missing and has_rich_data:
        reasons.append(
            f"missing required: {', '.join(hard_missing)}"
        )

    # Soft must-have options (score only)
    for option_name, keywords in SOFT_MUST_HAVE_KEYWORDS.items():
        found = _contains_any(text, keywords)
        detected[option_name] = found
        if not found:
            must_have_missing.append(option_name)

    # --- nice-to-have options ---

    score = 100  # start at 100, deduct for missing options
    for option_name, keywords in NICE_TO_HAVE_KEYWORDS.items():
        found = _contains_any(text, keywords)
        detected[option_name] = found
        if found:
            score += 10
            nice_to_have_present.append(option_name)

    # Deduct for missing options
    score -= len(must_have_missing) * 10
    score -= len(hard_missing) * 15  # hard must-haves weigh more

    # bonus for geo priority
    geo = criteria.get("geo_priority", [])
    if listing.location and geo:
        loc_lower = listing.location.lower()
        for i, city in enumerate(geo):
            if city.lower() in loc_lower:
                score += max(10 - i * 2, 2)
                break

    is_match = len(reasons) == 0

    return FilterResult(
        listing=listing,
        is_match=is_match,
        score=score,
        must_have_missing=must_have_missing,
        nice_to_have_present=nice_to_have_present,
        reasons=reasons,
        detected=detected,
    )
