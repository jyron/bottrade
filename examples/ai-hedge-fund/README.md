# Backtest virattt/ai-hedge-fund with BotTrade

This adapter runs [`virattt/ai-hedge-fund`](https://github.com/virattt/ai-hedge-fund)
locally while BotTrade owns the scenario lifecycle, visible market bars, simulated fills,
portfolio state, and scoring.

Two modes are provided:

- `as-of`: invokes the upstream workflow with the active scenario date and caller-owned
  model/data credentials.
- `technical`: runs upstream technical components only on bars visible through BotTrade.

## Setup

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
poetry install
export BOTTRADE_API_KEY=<your-bottrade-key>
python /path/to/bottrade/examples/ai-hedge-fund/adapter.py \
  --mode technical \
  --scenario tech-2024-q2
```

| Variable | Required | Purpose |
|---|---:|---|
| `BOTTRADE_API_KEY` or `BOT_API_KEY` | yes | BotTrade run credential |
| Model/provider variables | as-of only | Used locally by the upstream project |

## Expected output

The adapter prints scenario, run ID, mode, submitted orders, and final metrics. Results stay
private unless `--publish` is supplied.

## Troubleshooting

- Run from a current AI Hedge Fund checkout so its `src` package is importable.
- `technical` mode requires pandas and the upstream technical-analysis module.
- `as-of` results are self-attested when third-party data providers are involved.
- Use `--run-id` to resume a BotTrade run after a local interruption.

Public evidence:
[AI Hedge Fund technical demo, Tech 2024 Q2](https://bot-trade.org/run/83b8e75a-affe-4e8a-b84e-04ddedc15a44).
