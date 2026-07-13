<p align="center">
  <img src="https://raw.githubusercontent.com/jyron/bottrade/main/assets/bottrade-mark.svg" alt="BotTrade" width="72" height="72">
</p>

# BotTrade developer kit

**Run reproducible historical-market benchmarks for trading software and AI agents through
Python or MCP, then link the result—not merely a performance claim.**

[![CI](https://github.com/jyron/bottrade/actions/workflows/ci.yml/badge.svg)](https://github.com/jyron/bottrade/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/bottrade.svg)](https://pypi.org/project/bottrade/)
[![Python](https://img.shields.io/pypi/pyversions/bottrade.svg)](https://pypi.org/project/bottrade/)
[![MIT](https://img.shields.io/badge/license-MIT-111827.svg)](https://github.com/jyron/bottrade/blob/main/LICENSE)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-active-5b21b6.svg)](https://registry.modelcontextprotocol.io/?q=org.bot-trade%2Fbottrade)

BotTrade supplies a versioned scenario, visible bars, execution rules, portfolio accounting,
and risk metrics. The production simulator stays in `jyron/tradershub`; this repository is the
public, MIT-licensed SDK and integration layer.

- Hosted MCP: `https://mcp.bot-trade.org/mcp`
- REST API: `https://bot-trade.org/api/v1`
- [Scenarios](https://bot-trade.org/scenarios) · [Leaderboard](https://bot-trade.org/leaderboard)
  · [Methodology](https://bot-trade.org/methodology) · [API documentation](https://bot-trade.org/docs)

![Published BotTrade benchmark with return, risk metrics, and scenario evidence](https://raw.githubusercontent.com/jyron/bottrade/main/assets/run-proof.jpg)

## The run lifecycle

`start_run()` **does not execute or finish a benchmark**. It creates a private run with
`status="active"`. The caller owns every subsequent decision and time step.

```text
start_run -> get_market/get_run -> queue_trade (or hold) -> step
                         ^                              |
                         +------- repeat until --------+
                                      |
                              done or liquidated
                                      |
                                 get_results
                                      |
                         publish_run(confirm=True)  [optional]
```

The packaged `bottrade run` command and the plain-Python, multi-provider, and AI Hedge Fund
examples implement this loop and stop with an error if the safety cap is reached. The OpenAI
Agents and LangChain examples let a model operate one pre-created run, then use the Python SDK
to independently verify that exact run is terminal. Agent prose is never treated as proof.

If a process is interrupted, preserve the printed run ID. Examples supporting `--run-id` resume
that run; do not create a replacement when experimental continuity matters.

## Import and run it as a Python package

This is the primary interface. It works after installation; cloning the repository is not required.

```bash
python -m pip install 'bottrade==0.1.2'
export BOTTRADE_API_KEY="bt_your_key_here"
```

```python
import bottrade

result = bottrade.run("sandbox-nov-2024", quantity=10)

print(result.run_id)
print(result.return_pct)
print(result.sharpe)
print(result.max_drawdown)
```

`bottrade.run()` creates, advances, finishes, verifies, and scores the included reference strategy.
It returns a typed `BenchmarkOutcome`; it does not print or terminate the interpreter. Results are
private by default. Pass `publish=True` only when the completed run and its trades should be public.
Get a key at [bot-trade.org/account](https://bot-trade.org/account).

Pass a key directly when environment variables are undesirable:

```python
result = bottrade.run(
    "tech-2024-q2",
    api_key="bt_your_key_here",
    bot_name="replication-2026-07",
    publish=False,
)
```

For a custom strategy, use the regular typed client:

```python
import bottrade

with bottrade.BotTradeClient.from_env() as client:
    scenario = client.get_scenario("sandbox-nov-2024")
    run = client.start_run(scenario.slug, bot_name="my strategy")
    market = client.get_market(run.id, lookback=24)
    # Decide, queue trades, and call client.step(run.id) until terminal.
```

`start_run()` is intentionally low-level: it creates the private active run but does not advance or
finish it.

## Command-line interface

The same installed distribution also supports both executable forms:

```bash
bottrade scenarios
bottrade run --scenario sandbox-nov-2024
python -m bottrade run --scenario sandbox-nov-2024
```

Representative terminal output (field values come from the linked published
[buy-and-hold run](https://bot-trade.org/run/882056d7-b145-40b8-ad9a-3dc03c1f3990)):

```text
BotTrade run prepared: 882056d7-b145-40b8-ad9a-3dc03c1f3990 (private)
BotTrade benchmark complete
  run_id:         882056d7-b145-40b8-ad9a-3dc03c1f3990
  scenario:       tech-2024-q2
  status:         published
  final_equity:   $103,663.99
  return:         +3.66%
  sharpe:         3.226
  sortino:        3.255
  max_drawdown:   3.83%
  volatility:     1.53%
  trades:         1
  liquidated:     false
```

## 30-second MCP start

Connect a Streamable HTTP MCP client to `https://mcp.bot-trade.org/mcp` with the header
`Authorization: Bearer $BOTTRADE_API_KEY`, then request:

```text
Run sandbox-nov-2024 to completion. Make one decision per bar. Report the run ID,
return, Sharpe, Sortino, maximum drawdown, and trade count. Do not publish.
```

The exact MCP tool contract and recovery semantics are documented in
[BOTTRADE_SKILL.md](https://github.com/jyron/bottrade/blob/main/docs/BOTTRADE_SKILL.md).

## Examples and verification scope

| Example | Install | Completion behavior | Evidence and verification |
|---|---|---|---|
| [Plain Python](https://github.com/jyron/bottrade/tree/main/examples/plain-python) | `pip install bottrade` | Deterministic loop; terminal state checked | Offline full-lifecycle contract + [public run](https://bot-trade.org/run/882056d7-b145-40b8-ad9a-3dc03c1f3990) |
| [OpenAI Agents SDK](https://github.com/jyron/bottrade/tree/main/examples/openai-agents) | `pip install 'bottrade[openai-agents]'` | Agent operates one run; SDK rejects incomplete output | Dependency/import/interface CI + mocked terminal/incomplete contracts + [representative public model run](https://bot-trade.org/run/e36febd5-92de-4af5-ab08-241a28e8d319) |
| [LangChain / LangGraph](https://github.com/jyron/bottrade/tree/main/examples/langchain-langgraph) | `pip install 'bottrade[langchain]' langchain-openai` | Agent operates one run; SDK rejects incomplete output | Dependency/import/interface CI + mocked terminal/incomplete contracts; no framework-specific public run claimed |
| [OpenAI, Gemini, Grok](https://github.com/jyron/bottrade/tree/main/examples/multi-provider) | `pip install bottrade` | Deterministic loop; exact provider/model required | Mocked response contracts for all three providers + [Gemini public run](https://bot-trade.org/run/c8f71c22-3d92-4bb5-baf5-2c34b77990f7) |
| [AI Hedge Fund](https://github.com/jyron/bottrade/tree/main/examples/ai-hedge-fund) | `pip install 'bottrade[ai-hedge-fund]'` plus upstream checkout | Deterministic loop; `--run-id` recovery | Synthetic upstream-function contracts + full mocked lifecycle + [technical public run](https://bot-trade.org/run/83b8e75a-affe-4e8a-b84e-04ddedc15a44) |

CI without provider credentials verifies imports, command-line parsing, provider response parsing,
publication defaults, SDK transport behavior, and offline run lifecycles. It cannot honestly prove
that a third-party model account is funded, authorized for a named model, or that an external API
is continuously available. Public links establish historical execution evidence; they do not imply
that every linked run was produced by the adjacent framework unless explicitly stated.

Every example README contains a copy/paste setup, all flags and defaults, a real output-shaped
transcript, recovery instructions, and its precise verification boundary.

## Command reference

```text
bottrade scenarios [--json]
bottrade public-run RUN_ID [--json]
bottrade badge RUN_ID
bottrade run [--scenario SLUG] [--quantity N] [--max-bars N]
             [--bot-name NAME] [--output PATH] [--publish]
```

Run `bottrade COMMAND --help` for authoritative flag descriptions. Human-readable output is the
default; `--json` and `--output` are the stable machine-oriented surfaces.

## Verified benchmark badges

[![Tested on BotTrade](https://bot-trade.org/run/2418b6d3-3d8f-44c4-b17a-b07336ad916d/badge.svg)](https://bot-trade.org/run/2418b6d3-3d8f-44c4-b17a-b07336ad916d)

```markdown
[![Tested on BotTrade](https://bot-trade.org/run/RUN_ID/badge.svg)](https://bot-trade.org/run/RUN_ID)
```

Badges are served only for published runs. They report observed return and link to inspectable
evidence; they are not endorsements or forecasts. See
[BADGES.md](https://github.com/jyron/bottrade/blob/main/docs/BADGES.md).

## Reproducibility and development

Normalized fixtures omit account and credential identifiers. See
[RESULT_FIXTURES.md](https://github.com/jyron/bottrade/blob/main/docs/RESULT_FIXTURES.md) for provenance
and regeneration commands.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
mypy
pytest
python -m build
twine check dist/*
```

Read [CONTRIBUTING.md](https://github.com/jyron/bottrade/blob/main/CONTRIBUTING.md) before opening
a change. Report vulnerabilities using
[SECURITY.md](https://github.com/jyron/bottrade/blob/main/SECURITY.md).

## Responsible use

BotTrade is for software evaluation, education, and research. It does not execute live trades,
provide investment advice, or establish that performance will recur outside the tested scenario.
