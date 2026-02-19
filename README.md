
# Porsche 911 (992.1) Monitoring Agent

A small Python monitoring agent that scans car listing sites and alerts you when **Porsche 911 (992.1) Coupe / Carrera 4 GTS** listings match your requirements.

## What this repo contains
- Docs-first specification in Markdown (see `TASK.md` and `REQUIREMENTS.md`).
- A minimal, extendable architecture for sources, filters, storage, and notifications.

## Quick start
1. Create a virtual environment
2. Install deps
3. Copy `.env.example` to `.env` and set Telegram/email settings
4. Edit `config.yaml` and `criteria.json`
5. Run: `python -m porsche_monitor run`

## Outputs
- `reports/latest.md` – human readable report
- `data/monitor.db` – stateful SQLite DB

## Notes
Be mindful of website Terms of Service and rate limits. See `LEGAL_ETIQUETTE.md`.
