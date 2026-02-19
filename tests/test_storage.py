import tempfile
import os

from porsche_monitor.schema import Listing
from porsche_monitor.storage import Storage


def _make_listing(**overrides) -> Listing:
    defaults = dict(
        source="test",
        source_id="abc123",
        url="https://example.com/1",
        title="Porsche 911 Carrera 4 GTS",
        price_eur=140000,
        mileage_km=20000,
        first_registration="05/2022",
        location="Munich",
        accident_free=True,
        porsche_approved_months=12,
        options_text="Sport Chrono",
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_new_listing_is_new():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        storage = Storage(db_path)
        listing = _make_listing()
        change = storage.upsert_and_diff(listing)
        assert change.is_new is True
        assert change.is_changed is False


def test_same_listing_no_change():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        storage = Storage(db_path)
        listing = _make_listing()
        storage.upsert_and_diff(listing)
        change = storage.upsert_and_diff(listing)
        assert change.is_new is False
        assert change.is_changed is False


def test_price_change_detected():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        storage = Storage(db_path)
        listing1 = _make_listing(price_eur=140000)
        storage.upsert_and_diff(listing1)

        listing2 = _make_listing(price_eur=135000)
        change = storage.upsert_and_diff(listing2)
        assert change.is_new is False
        assert change.is_changed is True
        assert "price_eur" in change.changes
        assert change.changes["price_eur"] == (140000, 135000)
        assert change.previous_price == 140000


def test_count_and_get_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        storage = Storage(db_path)
        storage.upsert_and_diff(_make_listing(source_id="1"))
        storage.upsert_and_diff(_make_listing(source_id="2"))
        assert storage.count() == 2
        rows = storage.get_all()
        assert len(rows) == 2
