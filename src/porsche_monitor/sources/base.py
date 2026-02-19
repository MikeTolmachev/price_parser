from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import List

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

try:
    import cloudscraper
    _HAS_CLOUDSCRAPER = True
except ImportError:
    _HAS_CLOUDSCRAPER = False

from ..schema import Listing

log = logging.getLogger(__name__)


def _create_session() -> requests.Session:
    """Create a session that can bypass Cloudflare challenges."""
    if _HAS_CLOUDSCRAPER:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "darwin", "mobile": False},
        )
        scraper.headers.update({
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/json",
        })
        return scraper
    log.warning("cloudscraper not installed – falling back to plain requests.Session")
    session = requests.Session()
    session.headers.update({
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/json",
    })
    return session


class Source(ABC):
    name: str

    def __init__(
        self,
        urls: list[str],
        user_agent: str,
        delay: float = 4.0,
    ) -> None:
        self.urls = urls
        self.session = _create_session()
        # Only set explicit UA if cloudscraper is not managing it
        if not _HAS_CLOUDSCRAPER:
            self.session.headers["User-Agent"] = user_agent
        self.delay = delay

    @abstractmethod
    def _parse_response(self, url: str, response: requests.Response) -> List[Listing]:
        raise NotImplementedError

    @staticmethod
    def _should_retry(exc: BaseException) -> bool:
        """Don't retry on 403/451 (bot-block) – retrying won't help."""
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            if exc.response.status_code in (403, 451):
                return False
        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=30),
        retry=retry_if_exception(_should_retry.__func__),
    )
    def _get(self, url: str) -> requests.Response:
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            if _HAS_CLOUDSCRAPER and isinstance(
                exc, cloudscraper.exceptions.CloudflareChallengeError
            ):
                log.warning("[%s] Cloudflare challenge failed for %s", self.name, url)
            raise

    def fetch(self) -> List[Listing]:
        all_listings: List[Listing] = []
        for i, url in enumerate(self.urls):
            if i > 0 and self.delay:
                log.debug("Sleeping %.1fs between requests", self.delay)
                time.sleep(self.delay)
            try:
                log.info("[%s] Fetching %s", self.name, url)
                resp = self._get(url)
                listings = self._parse_response(url, resp)
                log.info("[%s] Got %d listings from %s", self.name, len(listings), url)
                all_listings.extend(listings)
            except Exception:
                log.exception("[%s] Failed to fetch %s", self.name, url)
        return all_listings
