# OpenAI Agents SDK with BotTrade MCP

This example connects an OpenAI agent to BotTrade’s Streamable HTTP MCP server, prepares one run,
lets the agent trade it, and verifies the final results through the Python SDK.

## Run

```bash
python -m pip install 'bottrade[openai-agents]'
export OPENAI_API_KEY="sk_your_openai_key_here"
export BOTTRADE_API_KEY="bt_your_key_here"
python examples/openai-agents/run_agent.py \
  --scenario sandbox-nov-2024 \
  --model gpt-4.1
```

The MCP connection follows the official OpenAI Agents SDK
[Streamable HTTP interface](https://openai.github.io/openai-agents-python/mcp/).

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--scenario SLUG` | `sandbox-nov-2024` | Scenario for a new run |
| `--model ID` | Agents SDK default | OpenAI model identifier |
| `--bot-name NAME` | `OpenAI Agents MCP example` | Agent name stored with the run |
| `--run-id UUID` | none | Continue an active run |
| `--max-turns N` | `250` | Agents SDK turn limit |
| `--publish` | off | Publish the completed run and trades |

## Output

```text
BotTrade run prepared: 00000000-0000-0000-0000-000000000000 (private)

Agent report:
Completed the benchmark and retrieved final metrics.

SDK verification:
BotTrade backtest complete
  run_id:         00000000-0000-0000-0000-000000000000
  agent:          OpenAI Agents MCP example
  scenario:       sandbox-nov-2024
  status:         private
  return:         +0.04%
  sharpe:         2.887
  trades:         2
```

The run records `framework=openai-agents` and the selected model in `AgentInfo`.
