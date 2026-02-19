from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import Config
from .filters import evaluate, load_criteria
from .notify import send_telegram, should_notify
from .report import render_md, write_report
from .schema import ChangeInfo, FilterResult
from .sources import get_source
from .storage import Storage

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run(config_path: str = "config.yaml", criteria_path: str = "criteria.json") -> None:
    load_dotenv()
    _setup_logging()

    cfg = Config.from_yaml(config_path)
    criteria = load_criteria(criteria_path)

    storage = Storage(cfg.app.database_path)

    results: list[FilterResult] = []
    changes: list[ChangeInfo] = []

    # Fetch from all enabled sources
    for source_name, source_cfg in cfg.sources.items():
        if not source_cfg.enabled:
            log.info("Source '%s' is disabled, skipping", source_name)
            continue
        if not source_cfg.urls:
            log.warning("Source '%s' has no URLs configured, skipping", source_name)
            continue

        try:
            source_cls = get_source(source_name)
        except ValueError as e:
            log.warning("%s", e)
            continue

        source = source_cls(
            urls=source_cfg.urls,
            user_agent=cfg.app.user_agent,
            delay=cfg.app.request_delay_seconds,
        )

        listings = source.fetch()
        log.info("Source '%s' returned %d listings", source_name, len(listings))

        for listing in listings:
            fr = evaluate(listing, criteria)
            change = storage.upsert_and_diff(listing)
            results.append(fr)
            changes.append(change)

            # Send notification if needed
            if should_notify(fr, change):
                tg = cfg.notifications.telegram
                if tg.enabled and tg.chat_id:
                    send_telegram(fr, tg.chat_id, change)

    # Generate report
    md = render_md(results, changes)
    write_report(cfg.app.report_path, md)

    match_count = sum(1 for r in results if r.is_match)
    new_count = sum(1 for c in changes if c.is_new)
    changed_count = sum(1 for c in changes if c.is_changed)

    log.info(
        "Run complete: %d listings, %d matches, %d new, %d changed. "
        "Report written to %s",
        len(results),
        match_count,
        new_count,
        changed_count,
        cfg.app.report_path,
    )


def export(config_path: str = "config.yaml", fmt: str = "md") -> None:
    load_dotenv()
    _setup_logging()

    cfg = Config.from_yaml(config_path)
    storage = Storage(cfg.app.database_path)
    criteria = load_criteria()

    rows = storage.get_all()
    if not rows:
        log.info("No stored listings to export")
        return

    from .schema import Listing

    results: list[FilterResult] = []
    for row in rows:
        listing = Listing(
            source=row["source"],
            source_id=row["source_id"],
            url=row["url"],
            title=row.get("title") or "Unknown",
            price_eur=row.get("price_eur"),
            mileage_km=row.get("mileage_km"),
        )
        fr = evaluate(listing, criteria)
        results.append(fr)

    md = render_md(results)
    write_report(cfg.app.report_path, md)
    log.info("Export complete: %d listings -> %s", len(results), cfg.app.report_path)


def dashboard(port: int = 8501) -> None:
    """Launch the Streamlit dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.py"
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(dashboard_path),
        "--server.port", str(port),
        "--server.headless", "false",
    ]
    log.info("Launching dashboard on port %d", port)
    subprocess.run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="porsche_monitor",
        description="Monitor Porsche 911 (992.1) listings",
    )
    sub = parser.add_subparsers(dest="cmd")

    # run command
    run_parser = sub.add_parser("run", help="Run a single monitoring cycle")
    run_parser.add_argument("--config", default="config.yaml", help="Config file path")
    run_parser.add_argument("--criteria", default="criteria.json", help="Criteria file path")

    # export command
    export_parser = sub.add_parser("export", help="Export stored listings to report")
    export_parser.add_argument("--format", default="md", choices=["md"], help="Export format")
    export_parser.add_argument("--config", default="config.yaml", help="Config file path")

    # dashboard command
    dash_parser = sub.add_parser("dashboard", help="Launch Streamlit dashboard")
    dash_parser.add_argument("--port", type=int, default=8501, help="Server port")

    args = parser.parse_args()

    if args.cmd == "run":
        run(config_path=args.config, criteria_path=args.criteria)
    elif args.cmd == "export":
        export(config_path=args.config, fmt=args.format)
    elif args.cmd == "dashboard":
        dashboard(port=args.port)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
