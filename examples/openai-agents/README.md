# Backtest an OpenAI Agents SDK trading agent through MCP

This example connects the OpenAI Agents SDK directly to BotTrade's remote Streamable HTTP
MCP server. BotTrade tools handle scenario discovery, market observation, run state,
orders, stepping, scoring, and optional publication.

The implementation follows the current OpenAI Agents SDK
[Streamable HTTP MCP interface](https://openai.github.io/openai-agents-python/mcp/).

## Setup

```bash
pip install 'bottrade[openai-agents]'
export OPENAI_API_KEY=<your-openai-key>
export BOTTRADE_API_KEY=<your-bottrade-key>
python examples/openai-agents/run_agent.py --scenario sandbox-nov-2024
```

| Variable | Required | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` | yes | OpenAI model calls made by the Agents SDK |
| `BOTTRADE_API_KEY` | yes | Bearer authentication sent to BotTrade MCP |

Pass `--model <model-id>` to override the Agents SDK default. The script does not hardcode
a model identifier so repository code does not silently change benchmark configuration.

## Expected output

The final agent response should include the run ID, scenario, return, Sharpe, Sortino, max
drawdown, and trade count. The run remains private unless `--publish` is supplied.

## Troubleshooting

- Run `run_sandbox_smoke_test` through another MCP client to confirm account auth.
- Increase `max_turns` in the example only if a larger scenario genuinely requires it.
- If MCP tool discovery changes, treat the live server tool list as authoritative.

Public evidence: [Claude Opus 4.8, Tech 2024 Q2](https://bot-trade.org/run/2418b6d3-3d8f-44c4-b17a-b07336ad916d).
