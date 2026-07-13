<p align="center">
  <img src="https://raw.githubusercontent.com/jyron/bottrade/main/assets/bottrade-mark.svg" alt="BotTrade" width="72" height="72">
</p>

# BotTrade Python SDK

**Backtest any Python trading agent on a versioned historical-market benchmark.**

[![CI](https://github.com/jyron/bottrade/actions/workflows/ci.yml/badge.svg)](https://github.com/jyron/bottrade/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/bottrade.svg)](https://pypi.org/project/bottrade/)
[![Python](https://img.shields.io/pypi/pyversions/bottrade.svg)](https://pypi.org/project/bottrade/)
[![MIT](https://img.shields.io/badge/license-MIT-111827.svg)](https://github.com/jyron/bottrade/blob/main/LICENSE)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-active-5b21b6.svg)](https://registry.modelcontextprotocol.io/?q=org.bot-trade%2Fbottrade)

## Quick start

```bash
python -m pip install 'bottrade==0.2.0'
export BOTTRADE_API_KEY="bt_your_key_here"
```

Create `my_agent.py`:

```python
import bottrade


def decide(observation: bottrade.Observation):
    symbol = observation.scenario.benchmark_symbol or observation.scenario.universe[0]
    bars = observation.bars[symbol]

    if observation.position(symbol):
        return bottrade.hold("Position is open")

    if len(bars) >= 2 and bars[-1].close > bars[-2].close:
        return bottrade.buy(symbol, quantity=10, reasoning="Positive one-bar momentum")

    return bottrade.hold("Waiting for momentum")


result = bottrade.backtest(
    decide,
    scenario="sandbox-nov-2024",
    agent_info=bottrade.AgentInfo(
        name="My momentum agent",
        framework="python",
        version="1.0",
    ),
)

print(result.run_id)
print(result.return_pct)
print(result.sharpe)
print(result.max_drawdown)
```

Run it:

```bash
python my_agent.py
```

`backtest()` calls the agent, submits its orders, advances the scenario, computes final metrics,
and returns a typed `BacktestResult`.

Get an API key at [bot-trade.org/account](https://bot-trade.org/account).

## Agent decisions

An agent receives one `Observation` and returns an order, a list of orders, or `hold()`.

```python
return bottrade.buy("AAPL", quantity=10, reasoning="Breakout")
return bottrade.sell("AAPL", quantity=5, reasoning="Reduce exposure")
return bottrade.short("TSLA", quantity=2, reasoning="Bearish signal")
return bottrade.cover("TSLA", quantity=2, reasoning="Close short")
return bottrade.hold("No signal")
```

Multiple orders:

```python
return [
    bottrade.buy("AAPL", quantity=10),
    bottrade.buy("MSFT", quantity=5),
]
```

Each order owns its symbol, side, quantity, and reasoning.

## Observation reference

```python
observation.scenario       # Scenario metadata and universe
observation.sim_time       # Current simulated timestamp
observation.cash           # Available cash
observation.positions      # Current positions
observation.bars           # Visible OHLCV bars by symbol
observation.step_number    # Current runner step
observation.position("SPY")
```

Bars are typed objects:

```python
latest = observation.bars["SPY"][-1]
print(latest.open, latest.high, latest.low, latest.close, latest.volume)
```

## Stateful agents

```python
import bottrade


class MovingAverageAgent:
    def decide(self, observation: bottrade.Observation):
        symbol = "SPY"
        closes = [bar.close for bar in observation.bars[symbol]]
        average = sum(closes) / len(closes)

        if closes[-1] > average and observation.position(symbol) is None:
            return bottrade.buy(symbol, quantity=10)

        return bottrade.hold()


result = bottrade.backtest(
    MovingAverageAgent(),
    scenario="sandbox-nov-2024",
    lookback=20,
)
```

## Async agents

```python
import asyncio
import bottrade


async def decide(observation: bottrade.Observation):
    signal = await get_model_signal(observation)
    if signal == "buy":
        return bottrade.buy("SPY", quantity=10)
    return bottrade.hold()


async def main():
    result = await bottrade.backtest_async(decide, scenario="sandbox-nov-2024")
    print(result.return_pct)


asyncio.run(main())
```

## Agent provenance

Attach reproducible identity to every run:

```python
info = bottrade.AgentInfo(
    name="AI Hedge Fund technical",
    framework="ai-hedge-fund",
    model="gpt-4.1",
    version="2026.7.10",
    source_url="https://github.com/virattt/ai-hedge-fund",
    source_revision="09dd33167bd6b4ea63ae32e7246e70e80632cc81",
    config={"analysts": ["technical_analyst"], "lookback": 180},
)

result = bottrade.backtest(agent, scenario="tech-2024-q2", agent_info=info)
```

Published run pages display this identity with the benchmark evidence.

## Runner options

```python
result = bottrade.backtest(
    agent,
    scenario="tech-2024-q2",
    lookback=50,
    decide_every=1,
    max_steps=10_000,
    resume_run_id=None,
    publish=False,
)
```

| Option | Meaning |
|---|---|
| `scenario` | Ready scenario slug |
| `lookback` | Visible bars per symbol at each decision |
| `decide_every` | Call the agent every N bars |
| `max_steps` | Maximum simulator steps for this invocation |
| `resume_run_id` | Continue an existing active run |
| `publish` | Publish the completed run and trades |

## Command line

Export a function or agent object from a module:

```bash
bottrade backtest my_agent:decide --scenario sandbox-nov-2024
python -m bottrade backtest my_agent:decide --scenario sandbox-nov-2024
```

Add provenance:

```bash
bottrade backtest my_agent:decide \
  --scenario tech-2024-q2 \
  --name "My momentum agent" \
  --framework python \
  --agent-version 1.0 \
  --source-revision abc123
```

Run `bottrade backtest --help` for the complete command reference.

## Explicit reference strategy

```python
import bottrade
from bottrade.strategies import buy_and_hold

result = bottrade.backtest(
    buy_and_hold(quantity=10, symbol="SPY"),
    scenario="sandbox-nov-2024",
)
```

Here, `quantity` configures the selected buy-and-hold agent.

## Integrations

| Integration | Example |
|---|---|
| Plain Python | [Custom momentum agent](https://github.com/jyron/bottrade/tree/main/examples/plain-python) |
| OpenAI Agents SDK | [Streamable HTTP MCP agent](https://github.com/jyron/bottrade/tree/main/examples/openai-agents) |
| LangChain / LangGraph | [MultiServerMCPClient agent](https://github.com/jyron/bottrade/tree/main/examples/langchain-langgraph) |
| OpenAI, Gemini, Grok | [Multi-provider agent](https://github.com/jyron/bottrade/tree/main/examples/multi-provider) |
| AI Hedge Fund | [AI Hedge Fund adapter](https://github.com/jyron/bottrade/tree/main/examples/ai-hedge-fund) |

## Result object

```python
result.run_id
result.agent_info
result.scenario
result.return_pct
result.final_equity
result.sharpe
result.sortino
result.max_drawdown
result.trade_count
result.published
```

Publish a result with `publish=True`, then embed its evidence badge:

```markdown
[![Tested on BotTrade](https://bot-trade.org/run/RUN_ID/badge.svg)](https://bot-trade.org/run/RUN_ID)
```

## Low-level client

Use `session()` for explicit observation, submission, and stepping:

```python
import bottrade

info = bottrade.AgentInfo(name="My manual agent", framework="python")

with bottrade.session("sandbox-nov-2024", agent_info=info) as run:
    while run.active:
        observation = run.observe()
        run.submit(decide(observation))
        run.step()

    results = run.results()
```

`BotTradeClient` exposes scenario discovery, run creation, observations, orders, stepping, results,
publication, public runs, URLs, and badges. `AsyncBotTradeClient` provides the same operations with
`async` methods.

```python
import bottrade

with bottrade.BotTradeClient.from_env() as client:
    scenarios = client.list_scenarios()
    print([scenario.slug for scenario in scenarios])
```

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy
pytest
python -m build
twine check dist/*
```

BotTrade is designed for software evaluation, education, and research.
