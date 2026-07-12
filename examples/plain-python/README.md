# Backtest a Python trading strategy with BotTrade

This smallest complete BotTrade example starts a historical-market benchmark, buys the
scenario benchmark symbol, advances every bar, and prints risk-aware results.

## Setup

```bash
pip install bottrade
export BOTTRADE_API_KEY=<your-key>
python examples/plain-python/run_strategy.py --scenario sandbox-nov-2024
```

| Variable | Required | Purpose |
|---|---:|---|
| `BOTTRADE_API_KEY` | yes | BotTrade account credential |
| `BOTTRADE_API` | no | Override the default `https://bot-trade.org` API base |

## Expected output

```text
run:      <run-id>
return:   +1.23%
sharpe:   0.81
drawdown: 0.04
private:  add --publish only when you want public evidence
```

Add `--publish` only when the completed run should appear publicly. A published run can
use the [verified badge](../../docs/BADGES.md).

Use `--output artifacts/result.json` to write a CI-friendly result artifact without
publishing it.

## Troubleshooting

- `AuthenticationRequired`: set `BOTTRADE_API_KEY` in the same shell.
- `402`: the account's monthly run allowance is exhausted; see the live response.
- An active run after interruption can be inspected with the SDK's `get_run` method.

Public evidence: [Buy & Hold (SPY), Tech 2024 Q2](https://bot-trade.org/run/882056d7-b145-40b8-ad9a-3dc03c1f3990).
