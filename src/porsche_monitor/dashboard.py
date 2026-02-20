"""Streamlit dashboard for browsing Porsche 911 listings."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from porsche_monitor.config import Config
from porsche_monitor.filters import evaluate, load_criteria
from porsche_monitor.schema import FilterResult, Listing
from porsche_monitor.storage import Storage

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = "config/config.yaml"
DEFAULT_CRITERIA = "config/criteria.json"


@st.cache_data(ttl=60)
def _load_config(path: str = DEFAULT_CONFIG) -> dict:
    cfg = Config.from_yaml(path)
    return {"db": cfg.app.database_path}


@st.cache_data(ttl=60)
def _load_criteria(path: str = DEFAULT_CRITERIA) -> dict:
    return load_criteria(path)


@st.cache_data(ttl=60)
def _load_rows(db_path: str) -> list[dict]:
    storage = Storage(db_path)
    return storage.get_all()


@st.cache_data(ttl=60)
def _load_sources_summary(db_path: str) -> dict[str, int]:
    storage = Storage(db_path)
    return storage.get_sources_summary()


@st.cache_data(ttl=60)
def _load_price_history(db_path: str, source: str, source_id: str) -> list[dict]:
    storage = Storage(db_path)
    return storage.get_price_history(source, source_id)


def _row_to_listing(row: dict) -> Listing:
    """Reconstruct a Listing from a DB row, preferring extras JSON."""
    extras = row.get("extras")
    if extras:
        try:
            return Listing.model_validate_json(extras)
        except Exception:
            pass
    return Listing(
        source=row["source"],
        source_id=row["source_id"],
        url=row["url"],
        title=row.get("title") or "Unknown",
        price_eur=row.get("price_eur"),
        mileage_km=row.get("mileage_km"),
    )


def _evaluate_rows(
    rows: list[dict], criteria: dict
) -> list[FilterResult]:
    results: list[FilterResult] = []
    for row in rows:
        listing = _row_to_listing(row)
        fr = evaluate(listing, criteria)
        results.append(fr)
    return results


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _render_match_card(fr: FilterResult) -> None:
    listing = fr.listing
    with st.container(border=True):
        cols = st.columns([1, 2])
        with cols[0]:
            if listing.image_url:
                st.image(listing.image_url, use_container_width=True)
            else:
                st.markdown("*No image*")
        with cols[1]:
            st.markdown(f"**{listing.title}**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Price", f"{listing.price_eur:,} EUR" if listing.price_eur else "N/A")
            m2.metric("Mileage", f"{listing.mileage_km:,} km" if listing.mileage_km else "N/A")
            m3.metric("Score", fr.score)

            if listing.location:
                st.caption(f"Location: {listing.location}")
            if listing.dealer_name:
                st.caption(f"Dealer: {listing.dealer_name}")

            st.link_button("View Listing", listing.url)

            with st.expander("Must-have checklist"):
                for opt, found in fr.detected.items():
                    icon = "+" if found else "-"
                    st.markdown(f"- [{icon}] {opt}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Porsche 911 Monitor",
        page_icon="car",
        layout="wide",
    )
    st.title("Porsche 911 (992.1) Monitor")

    # Load data
    cfg = _load_config()
    db_path = cfg["db"]
    criteria = _load_criteria()
    rows = _load_rows(db_path)
    sources_summary = _load_sources_summary(db_path)

    if not rows:
        st.warning("No listings in database. Run `python -m porsche_monitor run` first.")
        return

    # Check if any rows lack extras
    missing_extras = sum(1 for r in rows if not r.get("extras"))
    if missing_extras:
        st.warning(
            f"{missing_extras} listing(s) lack full data (no extras column). "
            "Re-run the monitor to populate."
        )

    all_results = _evaluate_rows(rows, criteria)

    # ----- Sidebar -----
    with st.sidebar:
        st.header("Filters")

        available_sources = sorted({r.listing.source for r in all_results})
        selected_sources = st.multiselect(
            "Source", available_sources, default=available_sources
        )

        prices = [r.listing.price_eur for r in all_results if r.listing.price_eur]
        if prices:
            price_min_val, price_max_val = min(prices), max(prices)
            price_range = st.slider(
                "Price (EUR)",
                min_value=price_min_val,
                max_value=price_max_val,
                value=(price_min_val, price_max_val),
                step=1000,
            )
        else:
            price_range = (0, 999999)

        mileages = [r.listing.mileage_km for r in all_results if r.listing.mileage_km]
        if mileages:
            km_min_val, km_max_val = min(mileages), max(mileages)
            mileage_range = st.slider(
                "Mileage (km)",
                min_value=km_min_val,
                max_value=km_max_val,
                value=(km_min_val, km_max_val),
                step=1000,
            )
        else:
            mileage_range = (0, 999999)

        sort_by = st.selectbox(
            "Sort by",
            ["Score (high first)", "Price (low first)", "Price (high first)", "Mileage (low first)"],
        )

        show_matches = st.checkbox("Show matches", value=True)
        show_rejected = st.checkbox("Show rejected", value=True)

        with st.expander("Current Criteria"):
            st.json(criteria)

    # ----- Apply filters -----
    filtered: list[FilterResult] = []
    for fr in all_results:
        if fr.listing.source not in selected_sources:
            continue
        p = fr.listing.price_eur
        if p is not None and not (price_range[0] <= p <= price_range[1]):
            continue
        km = fr.listing.mileage_km
        if km is not None and not (mileage_range[0] <= km <= mileage_range[1]):
            continue
        filtered.append(fr)

    # ----- Sort -----
    if sort_by == "Score (high first)":
        filtered.sort(key=lambda f: f.score, reverse=True)
    elif sort_by == "Price (low first)":
        filtered.sort(key=lambda f: f.listing.price_eur or 999999)
    elif sort_by == "Price (high first)":
        filtered.sort(key=lambda f: f.listing.price_eur or 0, reverse=True)
    elif sort_by == "Mileage (low first)":
        filtered.sort(key=lambda f: f.listing.mileage_km or 999999)

    matches = [f for f in filtered if f.is_match]
    rejected = [f for f in filtered if not f.is_match]

    # ----- Summary metrics -----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Listings", len(filtered))
    c2.metric("Matches", len(matches))
    c3.metric("Rejected", len(rejected))
    c4.metric("Active Sources", len(sources_summary))

    # ----- Matches grid -----
    if show_matches:
        st.header(f"Matches ({len(matches)})")
        if matches:
            for i in range(0, len(matches), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    idx = i + j
                    if idx < len(matches):
                        with col:
                            _render_match_card(matches[idx])
        else:
            st.info("No matches found with current filters.")

    # ----- Rejected table -----
    if show_rejected:
        st.header(f"Rejected ({len(rejected)})")
        if rejected:
            table_data = []
            for fr in rejected:
                l = fr.listing
                table_data.append({
                    "Source": l.source,
                    "Title": l.title,
                    "Price (EUR)": f"{l.price_eur:,}" if l.price_eur else "N/A",
                    "Mileage (km)": f"{l.mileage_km:,}" if l.mileage_km else "N/A",
                    "Reasons": "; ".join(fr.reasons[:3]),
                    "URL": l.url,
                })
            st.dataframe(
                table_data,
                use_container_width=True,
                column_config={
                    "URL": st.column_config.LinkColumn("URL", display_text="Open"),
                },
            )
        else:
            st.info("No rejected listings with current filters.")

    # ----- Price History -----
    st.header("Price History")
    listing_labels = {
        f"{fr.listing.source}/{fr.listing.source_id} – {fr.listing.title}": (
            fr.listing.source,
            fr.listing.source_id,
        )
        for fr in filtered
    }
    if listing_labels:
        selected_label = st.selectbox("Select listing", list(listing_labels.keys()))
        if selected_label:
            src, sid = listing_labels[selected_label]
            history = _load_price_history(db_path, src, sid)
            if history:
                import altair as alt
                import pandas as pd

                df = pd.DataFrame(history)
                df["recorded"] = pd.to_datetime(df["recorded"])
                chart = (
                    alt.Chart(df)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("recorded:T", title="Date"),
                        y=alt.Y("price_eur:Q", title="Price (EUR)", scale=alt.Scale(zero=False)),
                        tooltip=["recorded:T", "price_eur:Q"],
                    )
                    .properties(height=300)
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No price history recorded for this listing yet.")


if __name__ == "__main__":
    main()
