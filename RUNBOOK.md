
# Runbook

## Local run
```bash
python -m porsche_monitor run
```

## Scheduling with cron (Linux/macOS)
Example (every 30 minutes):
```cron
*/30 * * * * cd /path/to/repo && . .venv/bin/activate && python -m porsche_monitor run
```

## Troubleshooting
- If a source breaks (HTML changed), disable it in `config.yaml`.
- Check logs in `logs/`.
- Run `python -m porsche_monitor run --debug`.

## Data reset
Delete `data/monitor.db` to start clean.
