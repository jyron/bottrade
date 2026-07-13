# Custom Python agent

This example backtests a stateful momentum agent through the generic `bottrade.backtest()` runner.

## Run

```bash
python -m pip install bottrade
export BOTTRADE_API_KEY="bt_your_key_here"
python examples/plain-python/run_strategy.py --scenario sandbox-nov-2024
```

The agent receives a typed `Observation`, checks the latest two closes, and returns either
`bottrade.buy(...)` or `bottrade.hold(...)`.

```python
class MomentumAgent:
    def decide(self, observation):
        symbol = observation.scenario.benchmark_symbol
        bars = observation.bars[symbol]

        if observation.position(symbol):
            return bottrade.hold("Position is open")

        if len(bars) >= 2 and bars[-1].close > bars[-2].close:
            return bottrade.buy(symbol, quantity=10)

        return bottrade.hold("Waiting for momentum")
```

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--scenario SLUG` | `sandbox-nov-2024` | Ready scenario slug |
| `--quantity N` | `10` | Shares or units ordered by this momentum agent |
| `--lookback N` | `24` | Visible bars per symbol |
| `--max-steps N` | `10000` | Maximum simulator steps |
| `--resume-run-id UUID` | none | Continue an active run |
| `--output PATH` | none | Write normalized result JSON |
| `--publish` | off | Publish the completed run and trades |

## Output

```text
BotTrade run prepared: 00000000-0000-0000-0000-000000000000 (private)
BotTrade backtest complete
  run_id:         00000000-0000-0000-0000-000000000000
  agent:          Python momentum example
  scenario:       sandbox-nov-2024
  status:         private
  final_equity:   $101,250.00
  return:         +1.25%
  sharpe:         1.100
  sortino:        1.400
  max_drawdown:   2.00%
  trades:         1
```

The script prints the run ID immediately and accepts it through `--resume-run-id` for continuation.

Public evidence: [Buy & Hold (SPY), Tech 2024 Q2](https://bot-trade.org/run/882056d7-b145-40b8-ad9a-3dc03c1f3990).
