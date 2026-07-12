# Contributing

Thank you for improving BotTrade's public developer kit.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check .
mypy
pytest
```

## Expectations

- Keep examples runnable and private-by-default.
- Never commit BotTrade, model-provider, or market-data-provider credentials.
- Use exact model identifiers in commands; avoid silently changing benchmark configuration.
- Add offline tests for new client behavior and integration contracts.
- Link performance claims to a published BotTrade run.
- Keep financial language descriptive rather than promotional or advisory.

Open an issue before large API or repository-layout changes. Small documentation and test
improvements can go directly to a focused pull request.
