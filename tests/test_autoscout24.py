import os
from pathlib import Path

import pytest

from porsche_monitor.sources.autoscout24 import AutoScout24Source


class MockResponse:
    def __init__(self, text: str):
        self.text = text
        self.headers = {"content-type": "text/html"}


HTML_PATH = Path("/tmp/autoscout24.html")


@pytest.mark.skipif(not HTML_PATH.exists(), reason="cached HTML not available")
def test_parse_real_autoscout24_html():
    html = HTML_PATH.read_text(encoding="utf-8")
    source = AutoScout24Source(urls=[], user_agent="test", delay=0)
    listings = source._parse_response("https://www.autoscout24.de/lst/porsche/911", MockResponse(html))

    assert len(listings) > 0
    for l in listings:
        assert l.source == "autoscout24"
        assert l.source_id
        assert l.title
        assert l.url.startswith("https://")
        assert l.price_eur is not None
        assert l.mileage_km is not None


@pytest.mark.skipif(not HTML_PATH.exists(), reason="cached HTML not available")
def test_autoscout24_fields_populated():
    html = HTML_PATH.read_text(encoding="utf-8")
    source = AutoScout24Source(urls=[], user_agent="test", delay=0)
    listings = source._parse_response("https://www.autoscout24.de/lst/porsche/911", MockResponse(html))

    first = listings[0]
    assert first.location is not None
    assert first.dealer_name is not None
    assert first.first_registration is not None
    assert first.year is not None
