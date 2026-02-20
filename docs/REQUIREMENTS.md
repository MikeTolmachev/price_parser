
# Requirements

## Functional
- Poll listing sources on demand or on a schedule.
- Parse and normalize listings into a shared schema.
- Apply filtering rules from `criteria.json`.
- Produce a Markdown report of matches and near-matches.
- Notify on **new** matches and on **changes** (price/status/options).

## Non-functional
- Robust to HTML changes (defensive parsing).
- Respectful scraping: retries, backoff, rate limiting.
- Deterministic: same input => same output.
- Local-first: no cloud services required.

## Supported platforms
- macOS / Linux (Windows should work if Python + SQLite are available).
