# Backtest a LangChain or LangGraph trading agent through BotTrade MCP

This example loads BotTrade's remote MCP tools with `MultiServerMCPClient`. LangChain's
agent runtime is built on LangGraph, giving the benchmark loop a stateful orchestration
surface while BotTrade remains the source of scenario and portfolio state.

The connection shape follows the current
[LangChain MCP adapter documentation](https://docs.langchain.com/oss/python/langchain/mcp).

## Setup

Install the model integration matching the model string you intend to benchmark:

```bash
pip install 'bottrade[langchain]' langchain-openai
export OPENAI_API_KEY=<your-openai-key>
export BOTTRADE_API_KEY=<your-bottrade-key>
python examples/langchain-langgraph/run_agent.py \
  --model openai:<exact-model-id> \
  --scenario sandbox-nov-2024
```

| Variable | Required | Purpose |
|---|---:|---|
| `BOTTRADE_API_KEY` | yes | BotTrade MCP bearer authentication |
| Provider API key | yes | Selected LangChain model integration |

## Expected output

The last agent message reports the completed run's risk and return metrics. Publication is
disabled unless `--publish` is supplied.

## Troubleshooting

- Always pass an exact `--model` string supported by the installed LangChain integration.
- If the graph reaches its recursion limit, inspect repeated tool calls before raising it.
- Keep the BotTrade API key in the environment, never in committed connection config.

Public evidence: [BotTrade leaderboard](https://bot-trade.org/leaderboard).
