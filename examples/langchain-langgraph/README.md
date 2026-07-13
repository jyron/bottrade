# LangChain/LangGraph with BotTrade MCP

This example loads BotTrade tools through `MultiServerMCPClient`, prepares one run, lets the
LangGraph-backed agent trade it, and verifies the final results through the Python SDK.

## Run

```bash
python -m pip install 'bottrade[langchain]' langchain-openai
export OPENAI_API_KEY="sk_your_openai_key_here"
export BOTTRADE_API_KEY="bt_your_key_here"
python examples/langchain-langgraph/run_agent.py \
  --model openai:gpt-4.1 \
  --scenario sandbox-nov-2024
```

The MCP client follows the current
[LangChain MCP adapter interface](https://docs.langchain.com/oss/python/langchain/mcp).

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--model PROVIDER:ID` | required | LangChain model string |
| `--scenario SLUG` | `sandbox-nov-2024` | Scenario for a new run |
| `--bot-name NAME` | `LangChain MCP example` | Agent name stored with the run |
| `--run-id UUID` | none | Continue an active run |
| `--recursion-limit N` | `300` | LangGraph recursion limit |
| `--publish` | off | Publish the completed run and trades |

## Output

```text
BotTrade run prepared: 00000000-0000-0000-0000-000000000000 (private)

Agent report:
The benchmark reached completion.

SDK verification:
BotTrade backtest complete
  run_id:         00000000-0000-0000-0000-000000000000
  agent:          LangChain MCP example
  scenario:       sandbox-nov-2024
  status:         private
  final_equity:   $101,250.00
  return:         +1.25%
```

The run records `framework=langchain-langgraph` and the selected model in `AgentInfo`.
