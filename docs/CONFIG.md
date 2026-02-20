
# Configuration

## Files
- `criteria.json` – filtering rules (single source of truth)
- `config.yaml` – sources, schedule, notifications
- `.env` – secrets (Telegram token, SMTP password)

## Example `config.yaml`
```yaml
app:
  timezone: Europe/Berlin
  report_path: reports/latest.md
  database_path: data/monitor.db
  user_agent: "porsche-monitor/0.1 (+contact: you@example.com)"
  request_delay_seconds: 4

sources:
  porsche_finder:
    enabled: true
    urls:
      - "https://finder.porsche.com/de/de-DE/search?model=911"

  mobile_de:
    enabled: true
    urls:
      - "https://suchen.mobile.de/fahrzeuge/search.html?..."

notifications:
  telegram:
    enabled: true
    chat_id: "123456789"
```
