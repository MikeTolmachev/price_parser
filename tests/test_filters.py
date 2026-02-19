import json
from pathlib import Path

from porsche_monitor.schema import Listing
from porsche_monitor.filters import load_criteria, evaluate


def _criteria() -> dict:
    return json.loads(Path("criteria.json").read_text(encoding="utf-8"))


def _make_listing(**overrides) -> Listing:
    defaults = dict(
        source="test",
        source_id="1",
        url="https://example.com/1",
        title="Porsche 911 992.1 Carrera 4 GTS",
        price_eur=140000,
        mileage_km=20000,
        first_registration="05/2022",
        year=2022,
        location="Munich",
        accident_free=True,
        porsche_approved_months=12,
        owners=1,
        options_text=(
            "Sport Chrono Paket, Liftsystem Vorderachse, "
            "Hinterachslenkung, Abstandsregeltempostat, "
            "LED-Matrix, BOSE, 18-Wege Adaptive Sportsitze Plus"
        ),
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_perfect_match():
    c = _criteria()
    listing = _make_listing()
    r = evaluate(listing, c)
    assert r.is_match
    assert len(r.reasons) == 0
    assert len(r.must_have_missing) == 0


def test_mileage_too_high():
    c = _criteria()
    listing = _make_listing(mileage_km=60000)
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("mileage" in reason for reason in r.reasons)


def test_price_too_high():
    c = _criteria()
    listing = _make_listing(price_eur=200000)
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("price" in reason for reason in r.reasons)


def test_not_accident_free():
    c = _criteria()
    listing = _make_listing(accident_free=False)
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("accident" in reason for reason in r.reasons)


def test_missing_porsche_approved():
    c = _criteria()
    listing = _make_listing(porsche_approved_months=6)
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("Porsche Approved" in reason for reason in r.reasons)


def test_too_many_owners():
    c = _criteria()
    listing = _make_listing(owners=4)
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("owners" in reason for reason in r.reasons)


def test_missing_hard_must_have_rejects_with_rich_data():
    """Missing a hard must-have rejects when full equipment data is available."""
    c = _criteria()
    # Rich options_text (>20 chars) but missing hard must-haves
    listing = _make_listing(
        options_text="BOSE, LED-Matrix, Abstandsregeltempostat, 18-Wege Adaptive Sportsitze Plus, Sitzheizung"
    )
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("missing required" in reason for reason in r.reasons)


def test_missing_hard_must_have_passes_with_title_only():
    """Title-only listings pass (can't confirm equipment from card title)."""
    c = _criteria()
    listing = _make_listing(options_text="")
    r = evaluate(listing, c)
    # Should still match on hard filters (unknown equipment is not rejected)
    assert not any("missing required" in reason for reason in r.reasons)


def test_missing_soft_must_have_lowers_score():
    """Missing soft must-haves (ACC, BOSE, etc.) only reduces score."""
    c = _criteria()
    full = _make_listing()
    r_full = evaluate(full, c)
    # Has hard must-haves but missing soft ones
    partial = _make_listing(
        options_text="Sport Chrono Paket, Liftsystem, Hinterachslenkung"
    )
    r_partial = evaluate(partial, c)
    assert r_partial.is_match  # still matches (soft options missing)
    assert len(r_partial.must_have_missing) > 0
    assert r_partial.score < r_full.score


def test_nice_to_have_scoring():
    c = _criteria()
    listing = _make_listing(
        options_text=(
            "Sport Chrono Paket, Liftsystem Vorderachse, "
            "Hinterachslenkung, Abstandsregeltempostat, "
            "LED-Matrix, BOSE, 18-Wege Adaptive Sportsitze Plus, "
            "Surround View, Kraftstoffbehälter 90 l"
        ),
    )
    r = evaluate(listing, c)
    assert r.is_match
    assert r.score > 0
    assert len(r.nice_to_have_present) >= 2


def test_gts_cabriolet_accepted():
    """GTS Cabriolet is a valid variant."""
    c = _criteria()
    listing = _make_listing(title="Porsche 911 992.1 Carrera 4 GTS Cabriolet")
    r = evaluate(listing, c)
    assert not any("body type" in reason.lower() for reason in r.reasons)


def test_targa_excluded():
    c = _criteria()
    listing = _make_listing(title="Porsche 911 992.1 Targa 4 GTS")
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("body type" in reason.lower() for reason in r.reasons)


def test_non_gts_excluded():
    c = _criteria()
    listing = _make_listing(title="Porsche 911 992.1 Carrera 4S")
    r = evaluate(listing, c)
    assert not r.is_match
    assert any("body type" in reason.lower() for reason in r.reasons)


def test_geo_scoring():
    c = _criteria()
    listing_munich = _make_listing(location="Munich")
    listing_far = _make_listing(location="Hamburg")

    r_munich = evaluate(listing_munich, c)
    r_far = evaluate(listing_far, c)

    assert r_munich.score > r_far.score
