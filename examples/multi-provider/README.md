# OpenAI, Gemini, and Grok agents

This example implements one custom `ProviderAgent` and backtests it through
`bottrade.backtest()`. The provider supplies decisions; BotTrade supplies observations, orders,
execution, stepping, and metrics.

## Run

```bash
python -m pip install bottrade
export BOTTRADE_API_KEY="bt_your_key_here"
export GEMINI_API_KEY="your_gemini_key_here"
python examples/multi-provider/run_agent.py \
  --provider gemini \
  --model gemini-2.5-flash \
  --scenario sandbox-nov-2024
```

Provider keys:

| Provider | Variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Gemini | `GEMINI_API_KEY` |
| Grok | `XAI_API_KEY` |

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--provider {openai,gemini,grok}` | required | Decision provider |
| `--model ID` | required | Exact model identifier |
| `--scenario SLUG` | `sandbox-nov-2024` | Scenario to backtest |
| `--bot-name NAME` | provider and model | Agent name stored with the run |
| `--run-id UUID` | none | Continue an active run |
| `--decide-every N` | `8` | Call the model every N bars |
| `--lookback N` | `24` | Visible bars per symbol |
| `--max-bars N` | `10000` | Maximum simulator steps |
| `--output PATH` | none | Write normalized result JSON |
| `--publish` | off | Publish the completed run and trades |

## Output

```text
BotTrade run prepared: c8f71c22-3d92-4bb5-baf5-2c34b77990f7 (private)
BotTrade backtest complete
  run_id:         c8f71c22-3d92-4bb5-baf5-2c34b77990f7
  agent:          Gemini 2.5 Flash
  scenario:       sandbox-nov-2024
  final_equity:   $103,358.81
  return:         +3.36%
  sharpe:         3.785
  sortino:        5.527
  trades:         2
```

Public evidence: [Gemini 2.5 Flash](https://bot-trade.org/run/c8f71c22-3d92-4bb5-baf5-2c34b77990f7).
