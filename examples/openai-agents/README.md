# OpenAI Agents SDK + BotTrade Streamable HTTP MCP

The script follows the official OpenAI Agents SDK
[MCP interface](https://openai.github.io/openai-agents-python/mcp/). It creates exactly one private
run through the SDK, lets the agent operate that run through MCP, then independently verifies the
same run through the SDK. The agent is forbidden from starting or publishing runs.

## Run it

```bash
python -m pip install 'bottrade[openai-agents]'
export OPENAI_API_KEY="sk_your_openai_key_here"
export BOTTRADE_API_KEY="bt_your_key_here"
python examples/openai-agents/run_agent.py \
  --scenario sandbox-nov-2024 \
  --model gpt-4.1
```

| Flag | Default | Meaning |
|---|---|---|
| `--scenario SLUG` | `sandbox-nov-2024` | Scenario for a newly created run |
| `--model ID` | Agents SDK default | Exact OpenAI model override; record it for reproducibility |
| `--bot-name NAME` | `OpenAI Agents MCP example` | Run label |
| `--run-id UUID` | none | Resume this active run; no replacement is created |
| `--max-turns N` | `250` | Agents SDK turn limit; must be positive |
| `--publish` | off | SDK publishes only after terminal verification |

`OPENAI_API_KEY` and `BOTTRADE_API_KEY` are required. MCP authentication is an
`Authorization: Bearer` header sent to `https://mcp.bot-trade.org/mcp`.

## Output and completion

The script does not assume that an agent saying “finished” means it finished. The final section is
printed only after `get_run` reports a terminal status and `get_results` succeeds:

```text
BotTrade run prepared: 00000000-0000-0000-0000-000000000000 (private)

Agent report (untrusted until verification):
Completed the requested benchmark and retrieved final metrics.

SDK verification:
BotTrade benchmark complete
  run_id:         00000000-0000-0000-0000-000000000000
  scenario:       sandbox-nov-2024
  status:         private
  bars_advanced:  n/a
  final_equity:   $100,043.40
  return:         +0.04%
  sharpe:         2.887
  sortino:        3.482
  max_drawdown:   0.02%
  trades:         2
  liquidated:     false
```

The numeric shape is drawn from this [published GPT-4o Mini run](https://bot-trade.org/run/e36febd5-92de-4af5-ab08-241a28e8d319); it is representative evidence, not a claim that this exact script produced that historical run.

If the model stops early, the program exits nonzero with the active run ID. Resume it using
`--run-id`; raising `--max-turns` changes the execution budget and should be recorded.

Verification: CI installs and imports the current declared Agents SDK interface, checks `--help`,
and tests terminal and incomplete-run contracts without credentials. Live model availability,
account credit, and model access cannot be proven in credential-free CI.
