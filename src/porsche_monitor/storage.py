from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schema import ChangeInfo, Listing

log = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS listings (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    url          TEXT NOT NULL,
    title        TEXT,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    price_eur    INTEGER,
    mileage_km   INTEGER,
    status       TEXT,
    fingerprint  TEXT,
    extras       TEXT,
    PRIMARY KEY (source, source_id)
);
"""

PRICE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS price_history (
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    recorded     TEXT NOT NULL,
    price_eur    INTEGER NOT NULL,
    PRIMARY KEY (source, source_id, recorded)
);
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA_SQL)
        self.conn.execute(PRICE_HISTORY_SQL)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        cols = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(listings)").fetchall()
        }
        migrations = {
            "title": "TEXT",
            "first_seen": "TEXT",
            "mileage_km": "INTEGER",
            "extras": "TEXT",
        }
        for col, typ in migrations.items():
            if col not in cols:
                self.conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {typ}")

    def _fingerprint(self, listing: Listing) -> str:
        m = hashlib.sha256()
        payload = (
            f"{listing.title}|{listing.price_eur}|{listing.mileage_km}|"
            f"{listing.first_registration}|{listing.location}|"
            f"{listing.accident_free}|{listing.porsche_approved_months}|"
            f"{listing.options_text}|{listing.status}"
        ).encode("utf-8")
        m.update(payload)
        return m.hexdigest()

    def upsert_and_diff(self, listing: Listing) -> ChangeInfo:
        fp = self._fingerprint(listing)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        extras = listing.model_dump_json()

        cur = self.conn.execute(
            "SELECT fingerprint, price_eur, status, mileage_km, title "
            "FROM listings WHERE source=? AND source_id=?",
            (listing.source, listing.source_id),
        ).fetchone()

        if cur is None:
            self.conn.execute(
                "INSERT INTO listings"
                "(source, source_id, url, title, first_seen, last_seen, "
                "price_eur, mileage_km, status, fingerprint, extras) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    listing.source,
                    listing.source_id,
                    str(listing.url),
                    listing.title,
                    now,
                    now,
                    listing.price_eur,
                    listing.mileage_km,
                    listing.status,
                    fp,
                    extras,
                ),
            )
            if listing.price_eur is not None:
                self.conn.execute(
                    "INSERT OR IGNORE INTO price_history"
                    "(source, source_id, recorded, price_eur) "
                    "VALUES(?,?,?,?)",
                    (listing.source, listing.source_id, now, listing.price_eur),
                )
            self.conn.commit()
            log.info("New listing: %s (%s)", listing.title, listing.source_id)
            return ChangeInfo(is_new=True)

        changes: dict[str, tuple] = {}
        prev_price = cur["price_eur"]
        prev_status = cur["status"]

        if prev_price is not None and listing.price_eur is not None and prev_price != listing.price_eur:
            changes["price_eur"] = (prev_price, listing.price_eur)

        if prev_status and listing.status and prev_status != listing.status:
            changes["status"] = (prev_status, listing.status)

        is_changed = cur["fingerprint"] != fp

        self.conn.execute(
            "UPDATE listings SET url=?, title=?, last_seen=?, price_eur=?, "
            "mileage_km=?, status=?, fingerprint=?, extras=? "
            "WHERE source=? AND source_id=?",
            (
                str(listing.url),
                listing.title,
                now,
                listing.price_eur,
                listing.mileage_km,
                listing.status,
                fp,
                extras,
                listing.source,
                listing.source_id,
            ),
        )
        if listing.price_eur is not None:
            self.conn.execute(
                "INSERT OR IGNORE INTO price_history"
                "(source, source_id, recorded, price_eur) "
                "VALUES(?,?,?,?)",
                (listing.source, listing.source_id, now, listing.price_eur),
            )
        self.conn.commit()

        if is_changed:
            log.info("Changed listing: %s – %s", listing.title, changes)

        return ChangeInfo(
            is_new=False,
            is_changed=is_changed,
            changes=changes,
            previous_price=prev_price,
            previous_status=prev_status,
        )

    def get_all(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM listings ORDER BY last_seen DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

    def get_sources_summary(self) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT source, COUNT(*) as cnt FROM listings GROUP BY source"
        ).fetchall()
        return {row["source"]: row["cnt"] for row in rows}

    def get_price_history(self, source: str, source_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT recorded, price_eur FROM price_history "
            "WHERE source=? AND source_id=? ORDER BY recorded",
            (source, source_id),
        ).fetchall()
        return [{"recorded": row["recorded"], "price_eur": row["price_eur"]} for row in rows]
