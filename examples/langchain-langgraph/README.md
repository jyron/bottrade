# LangChain/LangGraph + BotTrade MCP

This example uses `MultiServerMCPClient` and `create_agent` exactly as documented by the current
[LangChain MCP adapter](https://docs.langchain.com/oss/python/langchain/mcp). BotTrade remains the
source of market, portfolio, and run state.

## Run it

```bash
python -m pip install 'bottrade[langchain]' langchain-openai
export OPENAI_API_KEY="sk_your_openai_key_here"
export BOTTRADE_API_KEY="bt_your_key_here"
python examples/langchain-langgraph/run_agent.py \
  --model openai:gpt-4.1 \
  --scenario sandbox-nov-2024
```

| Flag | Default | Meaning |
|---|---|---|
| `--model PROVIDER:ID` | required | LangChain model string; install its provider integration |
| `--scenario SLUG` | `sandbox-nov-2024` | Scenario for a newly created run |
| `--bot-name NAME` | `LangChain MCP example` | Run label |
| `--run-id UUID` | none | Resume one active run; no replacement is created |
| `--recursion-limit N` | `300` | LangGraph recursion limit; must be positive |
| `--publish` | off | SDK publishes only after terminal verification |

`BOTTRADE_API_KEY` and the selected provider’s key are required.

## Output and completion

The model operates one pre-created run. The script then verifies it independently. A normal output
has the same two-stage structure below; numbers are illustrative placeholders because this project
does not claim a framework-specific public run yet:

```text
BotTrade run prepared: 00000000-0000-0000-0000-000000000000 (private)

Agent report (untrusted until verification):
The run reached completion and final results were retrieved.

SDK verification:
BotTrade benchmark complete
  run_id:         00000000-0000-0000-0000-000000000000
  scenario:       sandbox-nov-2024
  status:         private
  bars_advanced:  n/a
  final_equity:   $<reported by BotTrade>
  return:         <reported by BotTrade>
  trades:         <reported by BotTrade>
```

If the graph hits its recursion limit or the run remains active, the script exits nonzero and names
the run. Resume with `--run-id`. Do not hide loops by increasing the limit without inspecting tool
calls.

Verification: CI installs the declared LangChain dependencies, imports the example, checks its CLI,
and tests the shared terminal-state gate offline. It does not claim a live LangChain result until a
framework-attributed public run exists.
