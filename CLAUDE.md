
# CLAUDE.md (project instructions)

You are working in the **Porsche 911 monitoring agent** repository.

## Coding standards
- Python 3.10+.
- Prefer small, testable functions.
- Type hints everywhere.
- Use Pydantic models for schema validation.

## Repo conventions
- Source code under `src/`.
- One source per file in `src/porsche_monitor/sources/`.
- Configuration files under `config/` (`config.yaml`, `criteria.json`).
- Documentation files under `docs/`.
- Keep parsing logic isolated from HTTP logic.

## Workflow
1. Read `docs/TASK.md` and `config/criteria.json`.
2. Implement schema, then one source (Porsche Finder) end-to-end.
3. Add storage + reporting.
4. Add notifications.
5. Add Mobile.de source.

## Definition of done
- `python -m porsche_monitor run` works.
- Writes `reports/latest.md`.
- Sends a Telegram message when a new match appears.
