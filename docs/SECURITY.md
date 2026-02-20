
# Security

## Secrets
Never commit credentials.
Store them in `.env` (gitignored):
- `TELEGRAM_BOT_TOKEN`
- `SMTP_PASSWORD`

## Data
The agent stores only public listing data and your local state.
