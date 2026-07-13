# Complete a BotTrade benchmark with plain Python

This reference strategy buys the scenario benchmark symbol, advances one bar at a time, verifies
terminal state, and fetches scored results. It requires no model provider.

## Run it

From a clone of this repository:

```bash
python -m pip install bottrade
export BOTTRADE_API_KEY="bt_your_key_here"
python examples/plain-python/run_strategy.py --scenario sandbox-nov-2024
```

Without cloning, use the equivalent packaged command: `bottrade run --scenario sandbox-nov-2024`.

| Flag | Default | Meaning |
|---|---|---|
| `--scenario SLUG` | `sandbox-nov-2024` | Ready scenario to run |
| `--quantity N` | `10` | Positive quantity of the benchmark symbol |
| `--max-bars N` | `10000` | Safety cap; exits nonzero rather than claiming completion |
| `--bot-name NAME` | `Python buy-and-hold example` | Private run label and eventual public name |
| `--output PATH` | none | Write normalized JSON without publishing |
| `--publish` | off | Explicitly publish the completed run and its trades |

`BOTTRADE_API_KEY` (or legacy `BOT_API_KEY`) is required. `BOTTRADE_API` optionally overrides the
default API origin.

## Output and completion

The script automatically finishes the run. `start_run()` alone does not. This transcript uses
metrics from the published [SPY reference run](https://bot-trade.org/run/882056d7-b145-40b8-ad9a-3dc03c1f3990):

```text
BotTrade run prepared: 882056d7-b145-40b8-ad9a-3dc03c1f3990 (private)
BotTrade benchmark complete
  run_id:         882056d7-b145-40b8-ad9a-3dc03c1f3990
  scenario:       tech-2024-q2
  status:         published
  final_equity:   $103,663.99
  return:         +3.66%
  sharpe:         3.226
  sortino:        3.255
  max_drawdown:   3.83%
  volatility:     1.53%
  trades:         1
  liquidated:     false
```

Your run ID and metrics will differ. Without `--publish`, the output says `status: private` and no
public URL is created.

## Failure and recovery

The run ID is created before stepping. If the process is interrupted, inspect it with
`BotTradeClient.get_run(run_id)`. This minimal reference intentionally has no resume flag; preserve
the ID for audit or implement a strategy-specific resume policy rather than silently starting over.

Verification: CI executes the complete workflow against a stateful fake API, including order,
steps, terminal-state check, scoring, private default, and explicit publication. The public link
above provides independently inspectable live evidence.
