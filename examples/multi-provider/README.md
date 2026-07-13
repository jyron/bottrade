# Compare OpenAI, Gemini, and Grok on one BotTrade workflow

This runner keeps scenario observation, order submission, stepping, scoring, and publication rules
constant while changing the decision provider. The exact model is mandatory so a provider alias or
default cannot silently redefine an experiment.

## Run it

```bash
python -m pip install bottrade
export BOTTRADE_API_KEY="bt_your_key_here"
export GEMINI_API_KEY="your_gemini_key_here"
python examples/multi-provider/run_agent.py \
  --provider gemini \
  --model gemini-2.5-flash \
  --scenario sandbox-nov-2024
```

Provider credentials: OpenAI uses `OPENAI_API_KEY`, Gemini uses `GEMINI_API_KEY`, and Grok uses
`XAI_API_KEY`.

| Flag | Default | Meaning |
|---|---|---|
| `--provider {openai,gemini,grok}` | required | Provider transport and credential selection |
| `--model ID` | required | Exact provider model identifier |
| `--scenario SLUG` | `sandbox-nov-2024` | Scenario to execute |
| `--bot-name NAME` | `<provider> <model> example` | Run label |
| `--run-id UUID` | none | Resume this active run instead of creating one |
| `--decide-every N` | `8` | Request a model decision every N bars |
| `--lookback N` | `24` | Visible bars per symbol included in each prompt |
| `--max-bars N` | `10000` | Safety cap before a nonzero incomplete-run exit |
| `--output PATH` | none | Write provider/model identity and normalized result JSON |
| `--publish` | off | Publish only after completion |

## Output and completion

The Python loop automatically advances until `done` or `liquidated`; `start_run()` itself does not.
Malformed individual trades are skipped with an explicit message. A safety-cap failure includes the
run ID for recovery.

This transcript is based on the published
[Gemini 2.5 Flash run](https://bot-trade.org/run/c8f71c22-3d92-4bb5-baf5-2c34b77990f7):

```text
BotTrade run prepared: c8f71c22-3d92-4bb5-baf5-2c34b77990f7 (private)
BotTrade benchmark complete
  run_id:         c8f71c22-3d92-4bb5-baf5-2c34b77990f7
  scenario:       sandbox-nov-2024
  status:         published
  final_equity:   $103,358.81
  return:         +3.36%
  sharpe:         3.785
  sortino:        5.527
  max_drawdown:   0.82%
  volatility:     0.58%
  trades:         2
  liquidated:     false
```

Use `--run-id` after interruption. Preserve provider, exact model, decision interval, lookback, and
scenario in any scholarly report; each can materially change the result.

Verification: credential-free CI mocks and validates OpenAI/Grok-compatible and Gemini response
shapes, malformed responses, CLI validation, private publication defaults, and the complete BotTrade
lifecycle. Live third-party availability and model authorization remain external preconditions.
