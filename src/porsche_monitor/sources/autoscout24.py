"""AutoScout24 (autoscout24.de) source.

Parses listings from AutoScout24 via __NEXT_DATA__ embedded JSON.
The site uses Next.js SSR with listing data in props.pageProps.listings.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import Source
from ..schema import Listing

log = logging.getLogger(__name__)

BASE = "https://www.autoscout24.de"
MAX_PAGES = 20  # safety cap to avoid runaway pagination


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d]", "", str(val))
        return int(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def _parse_listing_item(item: dict) -> Optional[Listing]:
    """Parse a single AutoScout24 listing from __NEXT_DATA__ JSON."""
    try:
        vid = item.get("id", "")
        if not vid:
            return None

        vehicle = item.get("vehicle", {})
        tracking = item.get("tracking", {})
        location = item.get("location", {})
        seller = item.get("seller", {})
        price_info = item.get("price", {})

        # Title: combine variant + modelVersionInput
        variant = vehicle.get("variant", "")
        model_version = vehicle.get("modelVersionInput", "")
        subtitle = vehicle.get("subtitle", "")
        title = model_version or variant or "Porsche 911"
        if subtitle:
            title = f"{title} – {subtitle}"

        # Price from tracking (clean int) or formatted
        price = _safe_int(tracking.get("price"))
        if price is None:
            price = _safe_int(price_info.get("priceFormatted"))

        # Mileage from tracking (clean int)
        mileage = _safe_int(tracking.get("mileage"))
        if mileage is None:
            mileage = _safe_int(vehicle.get("mileageInKm"))

        # First registration from tracking ("MM-YYYY") or vehicleDetails
        first_reg = tracking.get("firstRegistration", "")
        if first_reg:
            first_reg = first_reg.replace("-", "/")

        # Year extraction
        year = None
        if first_reg:
            year_match = re.search(r"(\d{4})", first_reg)
            year = int(year_match.group(1)) if year_match else None

        # Location
        city = location.get("city", "")
        country = location.get("countryCode", "")
        loc_str = f"{city}, {country}" if city else country or None

        # URL (relative -> absolute)
        url = item.get("url", "")
        if url and not url.startswith("http"):
            url = urljoin(BASE, url)

        # Seller / dealer
        dealer_name = seller.get("companyName") or seller.get("contactName")

        # Image
        images = item.get("images", [])
        image_url = images[0] if images else None

        # Options from vehicleDetails
        vehicle_details = item.get("vehicleDetails", [])
        options_parts: list[str] = []
        for detail in vehicle_details:
            data = detail.get("data", "")
            label = detail.get("ariaLabel", "")
            if data and label:
                options_parts.append(f"{label}: {data}")

        # Combine subtitle + model version for options text
        options_text = ", ".join(filter(None, [subtitle, ", ".join(options_parts)]))

        return Listing(
            source="autoscout24",
            source_id=str(vid),
            url=url or f"{BASE}/angebote/-id{vid}",
            title=title,
            price_eur=price,
            mileage_km=mileage,
            first_registration=first_reg if first_reg else None,
            year=year,
            location=loc_str,
            variant=variant,
            options_text=options_text,
            image_url=image_url,
            dealer_name=dealer_name,
            raw=item,
        )
    except Exception:
        log.exception("[autoscout24] Failed to parse listing item: %s", item.get("id", "?"))
        return None


class AutoScout24Source(Source):
    name = "autoscout24"

    def __init__(self, urls: list[str], user_agent: str, delay: float = 4.0) -> None:
        super().__init__(urls, user_agent, delay)
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.autoscout24.de/",
        })

    def fetch(self) -> List[Listing]:
        """Override to handle AutoScout24 pagination (?page=N)."""
        import time
        all_listings: List[Listing] = []
        seen_ids: set[str] = set()

        for base_url in self.urls:
            page = 1
            while page <= MAX_PAGES:
                url = base_url if page == 1 else f"{base_url}&page={page}" if "?" in base_url else f"{base_url}?page={page}"
                if all_listings and self.delay:
                    time.sleep(self.delay)
                try:
                    log.info("[autoscout24] Fetching page %d: %s", page, url)
                    resp = self._get(url)
                    page_listings, total_pages = self._parse_response_with_pages(url, resp)

                    new_on_page = 0
                    for listing in page_listings:
                        if listing.source_id not in seen_ids:
                            seen_ids.add(listing.source_id)
                            all_listings.append(listing)
                            new_on_page += 1

                    log.info(
                        "[autoscout24] Page %d/%d: %d new listings (total: %d)",
                        page, total_pages or "?", new_on_page, len(all_listings),
                    )

                    if not page_listings or (total_pages and page >= total_pages):
                        break
                    page += 1
                except Exception:
                    log.exception("[autoscout24] Failed to fetch page %d: %s", page, url)
                    break

        return all_listings

    def _parse_response_with_pages(
        self, url: str, response: requests.Response
    ) -> tuple[List[Listing], Optional[int]]:
        """Parse response and return (listings, total_pages)."""
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        if next_data_tag and next_data_tag.string:
            try:
                data = json.loads(next_data_tag.string)
                page_props = data.get("props", {}).get("pageProps", {})
                total_pages = page_props.get("numberOfPages")
                raw_listings = page_props.get("listings", [])

                if isinstance(raw_listings, list):
                    listings: List[Listing] = []
                    for item in raw_listings:
                        if isinstance(item, dict):
                            listing = _parse_listing_item(item)
                            if listing:
                                listings.append(listing)
                    return listings, total_pages
            except json.JSONDecodeError:
                log.warning("[autoscout24] Failed to parse __NEXT_DATA__ JSON")

        return self._parse_response(url, response), None

    def _parse_response(self, url: str, response: requests.Response) -> List[Listing]:
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Primary: extract from __NEXT_DATA__
        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        if next_data_tag and next_data_tag.string:
            try:
                data = json.loads(next_data_tag.string)
                page_props = data.get("props", {}).get("pageProps", {})
                raw_listings = page_props.get("listings", [])

                if isinstance(raw_listings, list) and raw_listings:
                    listings: List[Listing] = []
                    for item in raw_listings:
                        if not isinstance(item, dict):
                            continue
                        listing = _parse_listing_item(item)
                        if listing:
                            listings.append(listing)
                    log.info(
                        "[autoscout24] Parsed %d/%d listings from __NEXT_DATA__",
                        len(listings), len(raw_listings),
                    )
                    return listings
            except json.JSONDecodeError:
                log.warning("[autoscout24] Failed to parse __NEXT_DATA__ JSON")

        # Fallback: JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            if not script.string:
                continue
            try:
                ld = json.loads(script.string)
                if isinstance(ld, dict) and "@graph" in ld:
                    ld = ld["@graph"]
                items = ld if isinstance(ld, list) else [ld]
                results: List[Listing] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") in ("Vehicle", "Car", "Product"):
                        vid = str(item.get("sku") or item.get("vehicleIdentificationNumber") or "")
                        if vid:
                            offers = item.get("offers", {})
                            price = _safe_int(offers.get("price") if isinstance(offers, dict) else None)
                            results.append(Listing(
                                source="autoscout24",
                                source_id=vid,
                                url=item.get("url") or url,
                                title=item.get("name", "Porsche 911"),
                                price_eur=price,
                                options_text=item.get("description", ""),
                                raw=item,
                            ))
                if results:
                    log.info("[autoscout24] Parsed %d listings from JSON-LD", len(results))
                    return results
            except json.JSONDecodeError:
                continue

        log.warning("[autoscout24] No listings found in response from %s", url)
        return []
