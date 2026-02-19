"""Porsche Finder (finder.porsche.com) source.

Supports two response modes:
1. JSON API responses (if the URL hits the Porsche Finder API directly)
2. HTML pages with embedded __NEXT_DATA__ or listing cards
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


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(float(str(val).replace(".", "").replace(",", "").replace("€", "").replace(" ", "").strip()))
    except (ValueError, TypeError):
        return None


def _extract_approved_months(text: str) -> Optional[int]:
    text_lower = text.lower()
    if "porsche approved" not in text_lower:
        return None
    m = re.search(r"(\d+)\s*monat", text_lower)
    if m:
        return int(m.group(1))
    if "porsche approved" in text_lower:
        return 12
    return None


def _parse_vehicle_json(item: dict, base_url: str) -> Optional[Listing]:
    try:
        vid = str(
            item.get("id")
            or item.get("vehicleId")
            or item.get("listingId")
            or item.get("vin", "")
        )
        if not vid:
            return None

        title_parts = []
        for key in ("modelYear", "year"):
            if item.get(key):
                title_parts.append(str(item[key]))
        for key in ("modelDescription", "modelName", "title", "name", "model"):
            if item.get(key):
                title_parts.append(str(item[key]))
                break
        for key in ("variant", "trimLevel", "derivative"):
            if item.get(key):
                title_parts.append(str(item[key]))
                break

        title = " ".join(title_parts) or item.get("title", "Porsche 911")

        price = _safe_int(
            item.get("price")
            or item.get("listPrice")
            or (item.get("prices", {}) or {}).get("retail")
            or (item.get("pricing", {}) or {}).get("value")
        )

        mileage = _safe_int(
            item.get("mileage")
            or item.get("mileageKm")
            or (item.get("mileageInfo", {}) or {}).get("value")
        )

        reg = (
            item.get("firstRegistration")
            or item.get("registrationDate")
            or item.get("firstRegistrationDate")
        )

        year_val = _safe_int(item.get("modelYear") or item.get("year"))

        loc_parts = []
        for key in ("city", "location", "dealerCity"):
            if item.get(key):
                loc_parts.append(str(item[key]))
                break
        for key in ("country", "dealerCountry"):
            if item.get(key):
                loc_parts.append(str(item[key]))
                break
        location = ", ".join(loc_parts) if loc_parts else None
        if not location:
            dealer = item.get("dealer") or item.get("dealerInfo") or {}
            if isinstance(dealer, dict):
                location = dealer.get("city") or dealer.get("location")

        url = item.get("url") or item.get("detailUrl") or item.get("link")
        if url and not url.startswith("http"):
            url = urljoin(base_url, url)
        if not url:
            url = f"https://finder.porsche.com/de/de-DE/detail/{vid}"

        options_text = ""
        options_list: list[str] = []
        for key in ("equipment", "equipmentList", "options", "features"):
            raw_eq = item.get(key)
            if isinstance(raw_eq, list):
                for eq in raw_eq:
                    if isinstance(eq, str):
                        options_list.append(eq)
                    elif isinstance(eq, dict):
                        options_list.append(
                            eq.get("name") or eq.get("label") or eq.get("description") or str(eq)
                        )
                break
            elif isinstance(raw_eq, str):
                options_text = raw_eq
                break
        if not options_text and options_list:
            options_text = ", ".join(options_list)

        accident_free = None
        status_raw = item.get("accidentFree") or item.get("unfallfrei")
        if isinstance(status_raw, bool):
            accident_free = status_raw

        full_text = json.dumps(item, ensure_ascii=False).lower()
        if accident_free is None:
            if "unfallfrei" in full_text:
                accident_free = True
            elif "unfallfahrzeug" in full_text:
                accident_free = False

        approved_months = _extract_approved_months(full_text)
        if approved_months is None and "porsche approved" in full_text:
            approved_months = 12

        owners = _safe_int(item.get("owners") or item.get("numberOfOwners") or item.get("previousOwners"))

        generation = item.get("generation") or item.get("modelGeneration")
        body_type = item.get("bodyType") or item.get("body")
        variant = item.get("variant") or item.get("trimLevel") or item.get("derivative")
        dealer_name = None
        dealer_info = item.get("dealer") or item.get("dealerInfo") or {}
        if isinstance(dealer_info, dict):
            dealer_name = dealer_info.get("name") or dealer_info.get("dealerName")
        elif isinstance(dealer_info, str):
            dealer_name = dealer_info

        image_url = None
        images = item.get("images") or item.get("imageUrls") or item.get("photos")
        if isinstance(images, list) and images:
            first = images[0]
            image_url = first if isinstance(first, str) else (first.get("url") if isinstance(first, dict) else None)
        elif isinstance(item.get("imageUrl"), str):
            image_url = item["imageUrl"]

        listing_status = item.get("status") or item.get("availability")
        if isinstance(listing_status, str):
            listing_status = listing_status.lower()
        else:
            listing_status = "available"

        return Listing(
            source="porsche_finder",
            source_id=vid,
            url=url,
            title=title,
            price_eur=price,
            mileage_km=mileage,
            first_registration=str(reg) if reg else None,
            year=year_val,
            location=location,
            accident_free=accident_free,
            porsche_approved_months=approved_months,
            owners=owners,
            generation=generation,
            body_type=body_type,
            variant=variant,
            options_text=options_text,
            options_list=options_list,
            status=listing_status,
            image_url=image_url,
            dealer_name=dealer_name,
            raw=item,
        )
    except Exception:
        log.exception("Failed to parse Porsche Finder vehicle JSON: %s", item.get("id", "?"))
        return None


class PorscheFinderSource(Source):
    name = "porsche_finder"

    def _parse_response(self, url: str, response: requests.Response) -> List[Listing]:
        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:
            return self._parse_json(url, response.json())

        return self._parse_html(url, response.text)

    def _parse_json(self, base_url: str, data: Any) -> List[Listing]:
        items: list[dict] = []

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("results", "vehicles", "items", "data", "listings", "hits"):
                val = data.get(key)
                if isinstance(val, list):
                    items = val
                    break
            if not items and "content" in data:
                content = data["content"]
                if isinstance(content, list):
                    items = content
                elif isinstance(content, dict):
                    for key in ("results", "vehicles", "items"):
                        val = content.get(key)
                        if isinstance(val, list):
                            items = val
                            break

        listings: List[Listing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = _parse_vehicle_json(item, base_url)
            if listing:
                listings.append(listing)

        log.info("[porsche_finder] Parsed %d listings from JSON", len(listings))
        return listings

    def _parse_html(self, base_url: str, html: str) -> List[Listing]:
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: __NEXT_DATA__ (Next.js embedded JSON)
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            try:
                data = json.loads(next_data.string)
                props = data.get("props", {}).get("pageProps", {})
                for key in ("searchResults", "results", "vehicles", "listings", "initialData"):
                    val = props.get(key)
                    if val is not None:
                        if isinstance(val, dict):
                            for sub_key in ("results", "items", "vehicles", "hits"):
                                sub_val = val.get(sub_key)
                                if isinstance(sub_val, list):
                                    listings = self._parse_json(base_url, sub_val)
                                    if listings:
                                        return listings
                            listings = self._parse_json(base_url, val)
                            if listings:
                                return listings
                        elif isinstance(val, list):
                            listings = self._parse_json(base_url, val)
                            if listings:
                                return listings
                # Try the whole pageProps
                listings = self._parse_json(base_url, props)
                if listings:
                    return listings
            except json.JSONDecodeError:
                log.warning("[porsche_finder] Failed to parse __NEXT_DATA__ JSON")

        # Strategy 2: JSON-LD structured data
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_ld_scripts:
            if not script.string:
                continue
            try:
                ld = json.loads(script.string)
                if isinstance(ld, dict) and ld.get("@type") in ("Vehicle", "Car", "Product"):
                    listing = self._parse_json_ld_vehicle(ld, base_url)
                    if listing:
                        return [listing]
                elif isinstance(ld, list):
                    results = []
                    for entry in ld:
                        if isinstance(entry, dict) and entry.get("@type") in ("Vehicle", "Car", "Product"):
                            listing = self._parse_json_ld_vehicle(entry, base_url)
                            if listing:
                                results.append(listing)
                    if results:
                        return results
            except json.JSONDecodeError:
                continue

        # Strategy 3: embedded JSON in script tags
        for script in soup.find_all("script"):
            if not script.string:
                continue
            text = script.string.strip()
            for pattern in [
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'window\.__DATA__\s*=\s*({.+?});',
                r'var\s+initialData\s*=\s*({.+?});',
            ]:
                m = re.search(pattern, text, re.DOTALL)
                if m:
                    try:
                        embedded = json.loads(m.group(1))
                        listings = self._parse_json(base_url, embedded)
                        if listings:
                            return listings
                    except json.JSONDecodeError:
                        continue

        # Strategy 4: HTML listing cards
        return self._parse_html_cards(soup, base_url)

    def _parse_json_ld_vehicle(self, ld: dict, base_url: str) -> Optional[Listing]:
        try:
            vid = str(ld.get("sku") or ld.get("vehicleIdentificationNumber") or ld.get("@id") or "")
            if not vid:
                return None

            offers = ld.get("offers", {})
            price = _safe_int(offers.get("price") if isinstance(offers, dict) else None)

            return Listing(
                source="porsche_finder",
                source_id=vid,
                url=ld.get("url") or base_url,
                title=ld.get("name", "Porsche 911"),
                price_eur=price,
                mileage_km=_safe_int(ld.get("mileageFromOdometer", {}).get("value") if isinstance(ld.get("mileageFromOdometer"), dict) else ld.get("mileageFromOdometer")),
                first_registration=ld.get("dateVehicleFirstRegistered"),
                year=_safe_int(ld.get("modelDate") or ld.get("vehicleModelDate")),
                location=None,
                options_text=ld.get("description", ""),
                raw=ld,
            )
        except Exception:
            log.exception("[porsche_finder] Failed to parse JSON-LD vehicle")
            return None

    def _parse_html_cards(self, soup: BeautifulSoup, base_url: str) -> List[Listing]:
        listings: List[Listing] = []

        # Try common card selectors for Porsche Finder
        card_selectors = [
            {"attrs": {"data-testid": re.compile(r"vehicle-card|listing-card|result-card")}},
            {"class_": re.compile(r"vehicle-card|listing-card|result-card|search-result")},
            {"tag": "article"},
        ]

        cards = []
        for sel in card_selectors:
            tag = sel.pop("tag", "div")
            cards = soup.find_all(tag, **sel)
            if cards:
                break

        if not cards:
            cards = soup.find_all("a", href=re.compile(r"/detail/|/vehicle/"))

        for card in cards:
            try:
                link = card if card.name == "a" else card.find("a", href=True)
                href = link["href"] if link else None
                if href and not href.startswith("http"):
                    href = urljoin(base_url, href)

                vid_match = re.search(r"/details?/([^/?#]+)", href or "")
                vid = vid_match.group(1) if vid_match else None
                if not vid:
                    vid_match = re.search(r"/vehicle/([^/?#]+)", href or "")
                    vid = vid_match.group(1) if vid_match else str(hash(href))[:12]

                title_el = card.find(["h2", "h3", "h4"]) or card.find(class_=re.compile(r"title|name|model"))
                title = title_el.get_text(strip=True) if title_el else "Porsche 911"

                price_el = card.find(class_=re.compile(r"price")) or card.find(string=re.compile(r"[\d.]+\s*€"))
                price_text = price_el.get_text(strip=True) if price_el else ""
                price = _safe_int(re.sub(r"[^\d]", "", price_text)) if price_text else None

                km_el = card.find(class_=re.compile(r"mileage|km")) or card.find(string=re.compile(r"[\d.]+\s*km"))
                km_text = km_el.get_text(strip=True) if km_el else ""
                km_match = re.search(r"([\d.]+)\s*km", km_text.replace(".", ""))
                mileage = int(km_match.group(1)) if km_match else None

                loc_el = card.find(class_=re.compile(r"location|city|dealer"))
                location = loc_el.get_text(strip=True) if loc_el else None

                full_text = card.get_text(" ", strip=True)

                listing = Listing(
                    source="porsche_finder",
                    source_id=vid or str(len(listings)),
                    url=href or base_url,
                    title=title,
                    price_eur=price,
                    mileage_km=mileage,
                    location=location,
                    options_text=full_text,
                    raw={"html_text": full_text},
                )
                listings.append(listing)
            except Exception:
                log.exception("[porsche_finder] Failed to parse HTML card")
                continue

        log.info("[porsche_finder] Parsed %d listings from HTML cards", len(listings))
        return listings
