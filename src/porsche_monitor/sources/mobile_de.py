"""Mobile.de source.

Parses HTML search result pages from suchen.mobile.de.

NOTE: mobile.de uses aggressive Imperva/Incapsula bot detection.
The curl_cffi library (with Chrome TLS impersonation) is used as
the primary HTTP backend; cloudscraper/requests is the fallback.
If blocked, the source logs a warning and returns 0 listings.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .base import Source
from ..schema import Listing

try:
    from curl_cffi import requests as cffi_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False

log = logging.getLogger(__name__)

BASE_URL = "https://suchen.mobile.de"

_BLOCKED_MARKERS = (
    "Zugriff verweigert",
    "Access denied",
    "sec-if-cpt-container",
    "sec-bc-tile-container",
)


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d]", "", str(val))
        return int(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def _extract_approved_months(text: str) -> Optional[int]:
    text_lower = text.lower()
    if "porsche approved" not in text_lower:
        return None
    m = re.search(r"(\d+)\s*monat", text_lower)
    return int(m.group(1)) if m else 12


def _is_blocked(html: str) -> bool:
    """Detect bot-protection challenge or access-denied pages."""
    return any(marker in html for marker in _BLOCKED_MARKERS)


def _parse_listing_card(card: Tag, base_url: str) -> Optional[Listing]:
    try:
        # Extract listing ID from data attribute or link
        link = card.find("a", href=True)
        href = link["href"] if link else None
        if href and not href.startswith("http"):
            href = urljoin(base_url, href)

        # Mobile.de listing IDs are in the URL: /fahrzeuge/details.html?id=XXXXXXX
        vid = None
        if href:
            id_match = re.search(r"id=(\d+)", href)
            if id_match:
                vid = id_match.group(1)
            else:
                id_match = re.search(r"/(\d{6,})", href)
                if id_match:
                    vid = id_match.group(1)

        data_id = card.get("data-ad-id") or card.get("data-listing-id") or card.get("id", "")
        if not vid:
            vid = str(data_id).replace("result-listing-", "") if data_id else None

        if not vid:
            return None

        # Title
        title_el = (
            card.find(class_=re.compile(r"headline|title|h3"))
            or card.find(["h2", "h3", "h4"])
            or card.find("a", class_=re.compile(r"link--muted"))
        )
        title = title_el.get_text(strip=True) if title_el else "Porsche 911"

        # Price
        price = None
        price_el = card.find(class_=re.compile(r"price-block|price|gross"))
        if price_el:
            price_text = price_el.get_text(strip=True)
            price = _safe_int(price_text)
        if price is None:
            price_match = re.search(r"([\d.]+)\s*€", card.get_text())
            if price_match:
                price = _safe_int(price_match.group(1))

        # Mileage
        mileage = None
        full_text = card.get_text(" ", strip=True)
        km_match = re.search(r"([\d.]+)\s*km", full_text.replace(".", ""))
        if km_match:
            mileage = _safe_int(km_match.group(1))

        # Registration date
        reg_match = re.search(r"EZ\s*(\d{2}/\d{4})", full_text)
        first_reg = reg_match.group(1) if reg_match else None

        # Location
        loc_el = card.find(class_=re.compile(r"seller-info|location|city"))
        location = loc_el.get_text(strip=True) if loc_el else None
        if not location:
            loc_match = re.search(r"(?:DE-|AT-|CH-)\d{5}\s+(\w+)", full_text)
            if loc_match:
                location = loc_match.group(1)

        # Accident status
        text_lower = full_text.lower()
        accident_free = None
        if "unfallfrei" in text_lower:
            accident_free = True
        elif "unfallfahrzeug" in text_lower:
            accident_free = False

        approved = _extract_approved_months(text_lower)

        # Dealer name
        dealer_el = card.find(class_=re.compile(r"seller-name|dealer"))
        dealer_name = dealer_el.get_text(strip=True) if dealer_el else None

        # Image
        img = card.find("img")
        image_url = None
        if img:
            image_url = img.get("data-src") or img.get("src")

        return Listing(
            source="mobile_de",
            source_id=vid,
            url=href or f"https://suchen.mobile.de/fahrzeuge/details.html?id={vid}",
            title=title,
            price_eur=price,
            mileage_km=mileage,
            first_registration=first_reg,
            location=location,
            accident_free=accident_free,
            porsche_approved_months=approved,
            options_text=full_text,
            image_url=image_url,
            dealer_name=dealer_name,
            raw={"html_text": full_text},
        )
    except Exception:
        log.exception("[mobile_de] Failed to parse listing card")
        return None


class MobileDeSource(Source):
    name = "mobile_de"

    def __init__(self, urls: list[str], user_agent: str, delay: float = 4.0) -> None:
        super().__init__(urls, user_agent, delay)
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.mobile.de/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def _fetch_with_curl_cffi(self, url: str) -> Optional[str]:
        """Try fetching with curl_cffi (Chrome TLS impersonation)."""
        if not _HAS_CURL_CFFI:
            return None
        try:
            resp = cffi_requests.get(
                url,
                impersonate="chrome",
                timeout=30,
                headers={
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": "https://www.mobile.de/",
                },
            )
            if resp.status_code == 200 and not _is_blocked(resp.text):
                log.info("[mobile_de] curl_cffi succeeded for %s", url)
                return resp.text
            log.warning(
                "[mobile_de] curl_cffi got %d but page is blocked/challenge for %s",
                resp.status_code, url,
            )
        except Exception:
            log.warning("[mobile_de] curl_cffi request failed for %s", url)
        return None

    def fetch(self) -> List[Listing]:
        """Fetch with curl_cffi first, fall back to cloudscraper/requests."""
        all_listings: List[Listing] = []

        for i, url in enumerate(self.urls):
            if i > 0 and self.delay:
                time.sleep(self.delay)

            log.info("[mobile_de] Fetching %s", url)

            # Try curl_cffi first (better TLS fingerprinting)
            html = self._fetch_with_curl_cffi(url)
            if html:
                listings = self._parse_html(url, html)
                log.info("[mobile_de] Got %d listings from %s", len(listings), url)
                all_listings.extend(listings)
                continue

            # Fall back to cloudscraper/requests session
            try:
                resp = self._get(url)
                if _is_blocked(resp.text):
                    log.warning(
                        "[mobile_de] Bot detection active – mobile.de blocked access. "
                        "This is a known limitation; mobile.de uses aggressive Imperva "
                        "bot protection. Listings from other sources still work."
                    )
                    continue
                listings = self._parse_response(url, resp)
                log.info("[mobile_de] Got %d listings from %s", len(listings), url)
                all_listings.extend(listings)
            except Exception:
                log.warning(
                    "[mobile_de] Request blocked (403/challenge). mobile.de uses "
                    "aggressive bot detection that blocks automated access. "
                    "Skipping this source."
                )

        return all_listings

    def _parse_html(self, url: str, html: str) -> List[Listing]:
        """Parse HTML string directly."""
        soup = BeautifulSoup(html, "html.parser")
        return self._parse_soup(soup, url)

    def _parse_response(self, url: str, response: requests.Response) -> List[Listing]:
        soup = BeautifulSoup(response.text, "html.parser")
        return self._parse_soup(soup, url)

    def _parse_soup(self, soup: BeautifulSoup, url: str) -> List[Listing]:
        listings: List[Listing] = []

        # Strategy 1: JSON-LD structured data
        json_ld = self._extract_json_ld(soup)
        if json_ld:
            return json_ld

        # Strategy 2: parse listing cards
        card_selectors = [
            {"class_": re.compile(r"cBox-body--resultitem|result-item|listing-item")},
            {"attrs": {"data-ad-id": True}},
            {"attrs": {"data-listing-id": True}},
            {"class_": re.compile(r"result-list-entry")},
        ]

        cards: list[Tag] = []
        for sel in card_selectors:
            cards = soup.find_all("div", **sel)
            if not cards:
                cards = soup.find_all("article", **sel)
            if cards:
                break

        if not cards:
            # Fallback: find links to detail pages
            detail_links = soup.find_all("a", href=re.compile(r"details\.html\?id="))
            seen_ids: set[str] = set()
            for link in detail_links:
                parent = link.find_parent(["div", "article", "li"])
                if parent:
                    id_match = re.search(r"id=(\d+)", link["href"])
                    lid = id_match.group(1) if id_match else ""
                    if lid and lid not in seen_ids:
                        seen_ids.add(lid)
                        cards.append(parent)

        for card in cards:
            listing = _parse_listing_card(card, url)
            if listing:
                listings.append(listing)

        log.info("[mobile_de] Parsed %d listings from HTML", len(listings))
        return listings

    def _extract_json_ld(self, soup: BeautifulSoup) -> Optional[List[Listing]]:
        scripts = soup.find_all("script", type="application/ld+json")
        results: List[Listing] = []
        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") not in ("Vehicle", "Car", "Product", "Offer"):
                        continue
                    vid = str(item.get("sku") or item.get("vehicleIdentificationNumber") or "")
                    if not vid:
                        continue
                    offers = item.get("offers", {})
                    price = _safe_int(offers.get("price") if isinstance(offers, dict) else None)
                    results.append(Listing(
                        source="mobile_de",
                        source_id=vid,
                        url=item.get("url", ""),
                        title=item.get("name", "Porsche 911"),
                        price_eur=price,
                        options_text=item.get("description", ""),
                        raw=item,
                    ))
            except json.JSONDecodeError:
                continue
        return results if results else None
