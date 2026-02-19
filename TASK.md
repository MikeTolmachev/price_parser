# Task for Claude Code: Build a simple monitoring agent for Porsche 911 (992.1) Coupe / Carrera 4 GTS

## Goal
Create a lightweight monitoring agent that checks listing sites on a schedule, filters for **Porsche 911 (992.1) Coupe / Carrera 4 GTS** with predefined requirements, and notifies me when new matching listings appear or existing ones change (price/status).

## Output of this task
- A runnable Python project (3.10+) that:
  1) fetches listings from configured sources,
  2) normalizes listing data,
  3) applies filters,
  4) stores state (seen listings) locally,
  5) sends notifications.
- Markdown docs describing how to configure, run, and extend.

## Requirements (hard)
Use **criteria.json** as the single source of truth for filtering. The agent MUST:
- Match only **992.1** generation listings.
- Match body: **Coupe** OR **Carrera 4 GTS** (also accept “Carrera GTS” if AWD is not mandatory, but prioritize 4 GTS).
- Exclude anything not **Unfallfrei**.
- Exclude listings without **Porsche Approved** (>= 12 months).
- Exclude mileage > 50000 km.
- Prefer 1–2 owners.

### Must-have options
Treat these as required by default:
- Sport Chrono Paket
- Liftsystem Vorderachse (Front Axle Lift)
- Hinterachslenkung (Rear-axle steering)
- Adaptive cruise (Abstandsregeltempostat / InnoDrive)
- LED-Matrix / PDLS Plus
- BOSE or Burmester
- Adaptive Sports Seats Plus (18-way)

### Nice-to-have options
Score listings higher when present:
- 90L fuel tank (Kraftstoffbehälter 90 l)
- Surround View / 360° camera
- Glass sunroof (Schiebe-/Hubdach aus Glas)
- PPF / Steinschlagschutzfolie

## Sources
Implement sources as plugins under `src/porsche_monitor/sources/`:
- Porsche Finder (preferred)
- Mobile.de
- AutoScout24 (optional stub is OK)

Each source should:
- Build a search URL from config
- Fetch with respectful rate limiting
- Parse into the shared `Listing` schema

## Storage
- Use SQLite (file-based) to store:
  - seen listing IDs
  - last-seen timestamp
  - last known price
  - last known status (available/reserved/sold)
  - a hash of important fields (to detect changes)

## Notifications
Implement at least one:
- Telegram Bot (recommended)
- Email via SMTP (optional)

Notification should include:
- Title, price, mileage, year, location
- Accident status, warranty status
- Must-have option matches (✅/❌)
- Direct link

## CLI
Provide a CLI:
- `python -m porsche_monitor run` (single run)
- `python -m porsche_monitor backfill --days 7` (optional)
- `python -m porsche_monitor export --format md` (writes `reports/latest.md`)

## Non-functional
- Clear logs
- Configurable schedule (cron/systemd examples)
- Respect site ToS and robots.txt; implement delays + retry + user-agent.

## Acceptance criteria
- Running `python -m porsche_monitor run` produces a `reports/latest.md` file and sends a notification for any new match.
- Agent does not notify repeatedly for the same listing unless something changed.
- Filters are explainable (include reasons in report for why a listing did/didn’t match).

## Deliverables
Code:
- `src/porsche_monitor/` (main package)
- `src/porsche_monitor/sources/` (source plugins)
- `src/porsche_monitor/filters.py`, `schema.py`, `storage.py`, `notify.py`, `cli.py`

Docs (Markdown):
- `README.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`, `SOURCES.md`, `FILTERS.md`, `CONFIG.md`, `RUNBOOK.md`, `SECURITY.md`, `LEGAL_ETIQUETTE.md`
