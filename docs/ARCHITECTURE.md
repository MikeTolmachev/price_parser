
# Architecture

## High level
The agent is split into four concerns:
1. **Sources**: fetch + parse listings from each site.
2. **Normalization**: map site-specific fields into a single `Listing` schema.
3. **Filtering + scoring**: apply your must-have rules and compute a score for nice-to-haves.
4. **State + notifications**: store what was seen, detect changes, send alerts.

## Modules
- `src/porsche_monitor/schema.py` – Pydantic models.
- `src/porsche_monitor/sources/*` – one file per website.
- `src/porsche_monitor/filters.py` – rules + scoring.
- `src/porsche_monitor/storage.py` – SQLite persistence.
- `src/porsche_monitor/notify.py` – Telegram/email.
- `src/porsche_monitor/report.py` – Markdown rendering.
- `src/porsche_monitor/cli.py` – CLI entrypoints.

## Data flow
1. Load `config.yaml` and `criteria.json`.
2. Run all sources (sequential by default).
3. Normalize -> list[Listing].
4. Filter + score.
5. Persist and detect deltas.
6. Write report + notify deltas.
