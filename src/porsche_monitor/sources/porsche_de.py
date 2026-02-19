"""porsche.de source.

Handles the official Porsche website pre-owned / Porsche Approved pages.
These often share an API or data format with finder.porsche.com.
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
from .porsche_finder import _parse_vehicle_json, _safe_int
from ..schema import Listing

log = logging.getLogger(__name__)


class PorscheDeSource(Source):
    name = "porsche_de"

    def __init__(self, urls: list[str], user_agent: str, delay: float = 4.0) -> None:
        super().__init__(urls, user_agent, delay)
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json",
            "Referer": "https://www.porsche.com/",
        })

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
            for key in ("vehicles", "results", "items", "data", "listings"):
                val = data.get(key)
                if isinstance(val, list):
                    items = val
                    break
            if not items:
                # Nested structure common in Porsche APIs
                for top_key in ("response", "content", "payload"):
                    sub = data.get(top_key)
                    if isinstance(sub, dict):
                        for key in ("vehicles", "results", "items"):
                            val = sub.get(key)
                            if isinstance(val, list):
                                items = val
                                break
                    if items:
                        break

        listings: List[Listing] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = _parse_vehicle_json(item, base_url)
            if listing:
                listing.source = "porsche_de"
                listings.append(listing)

        log.info("[porsche_de] Parsed %d listings from JSON", len(listings))
        return listings

    def _parse_html(self, base_url: str, html: str) -> List[Listing]:
        soup = BeautifulSoup(html, "html.parser")
        listings: List[Listing] = []

        # Check for embedded JSON data (common in Porsche SPA pages)
        for script in soup.find_all("script"):
            if not script.string:
                continue
            text = script.string.strip()

            # Try __NEXT_DATA__
            if script.get("id") == "__NEXT_DATA__":
                try:
                    data = json.loads(text)
                    props = data.get("props", {}).get("pageProps", {})
                    for key in ("vehicles", "results", "listings", "searchResults"):
                        val = props.get(key)
                        if isinstance(val, list):
                            result = self._parse_json(base_url, val)
                            if result:
                                return result
                        elif isinstance(val, dict):
                            for sub_key in ("items", "results", "vehicles"):
                                sub_val = val.get(sub_key)
                                if isinstance(sub_val, list):
                                    result = self._parse_json(base_url, sub_val)
                                    if result:
                                        return result
                except json.JSONDecodeError:
                    continue

            # Try embedded JSON patterns
            for pattern in [
                r'window\.__PRELOADED_STATE__\s*=\s*({.+?});',
                r'window\.__INITIAL_DATA__\s*=\s*({.+?});',
                r'"vehicles"\s*:\s*(\[.+?\])',
            ]:
                m = re.search(pattern, text, re.DOTALL)
                if m:
                    try:
                        embedded = json.loads(m.group(1))
                        result = self._parse_json(base_url, embedded)
                        if result:
                            return result
                    except json.JSONDecodeError:
                        continue

        # Check for iframes pointing to finder.porsche.com
        iframes = soup.find_all("iframe", src=re.compile(r"finder\.porsche\.com"))
        if iframes:
            log.info("[porsche_de] Page contains iframe to finder.porsche.com")
            for iframe in iframes:
                iframe_url = iframe["src"]
                if not iframe_url.startswith("http"):
                    iframe_url = urljoin(base_url, iframe_url)
                try:
                    resp = self._get(iframe_url)
                    return self._parse_html(iframe_url, resp.text)
                except Exception:
                    log.exception("[porsche_de] Failed to fetch iframe URL: %s", iframe_url)

        # Check for links to finder.porsche.com
        finder_links = soup.find_all("a", href=re.compile(r"finder\.porsche\.com"))
        if finder_links:
            log.info(
                "[porsche_de] Page links to finder.porsche.com – "
                "consider using porsche_finder source with these URLs: %s",
                [l["href"] for l in finder_links[:3]],
            )

        # Try HTML card parsing as fallback
        cards = soup.find_all("article") or soup.find_all(
            "div", class_=re.compile(r"vehicle|listing|result|card")
        )
        for card in cards:
            try:
                link = card.find("a", href=True)
                href = link["href"] if link else None
                if href and not href.startswith("http"):
                    href = urljoin(base_url, href)

                title_el = card.find(["h2", "h3", "h4"])
                title = title_el.get_text(strip=True) if title_el else "Porsche 911"

                full_text = card.get_text(" ", strip=True)
                price_match = re.search(r"([\d.]+)\s*€", full_text.replace(".", ""))
                mileage_match = re.search(r"([\d.]+)\s*km", full_text.replace(".", ""))

                vid = re.search(r"/details?/([^/?#]+)", href or "")
                if not vid:
                    vid = re.search(r"/(\w{8,})", href or "")
                source_id = vid.group(1) if vid else str(hash(href or len(listings)))[:12]

                listings.append(Listing(
                    source="porsche_de",
                    source_id=source_id,
                    url=href or base_url,
                    title=title,
                    price_eur=_safe_int(price_match.group(1)) if price_match else None,
                    mileage_km=_safe_int(mileage_match.group(1)) if mileage_match else None,
                    options_text=full_text,
                    raw={"html_text": full_text},
                ))
            except Exception:
                log.exception("[porsche_de] Failed to parse HTML card")
                continue

        log.info("[porsche_de] Parsed %d listings from HTML", len(listings))
        return listings
