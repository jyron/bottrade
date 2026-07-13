# AI Hedge Fund adapter

This adapter runs [`virattt/ai-hedge-fund`](https://github.com/virattt/ai-hedge-fund)
against a BotTrade scenario and records its exact identity in `AgentInfo`.

## Setup

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
git checkout 09dd33167bd6b4ea63ae32e7246e70e80632cc81
poetry install
poetry run pip install 'bottrade[ai-hedge-fund]'
export BOTTRADE_API_KEY="bt_your_key_here"
```

Run technical mode using BotTrade-visible bars:

```bash
python /absolute/path/to/bottrade/examples/ai-hedge-fund/adapter.py \
  --mode technical \
  --scenario tech-2024-q2
```

Run the upstream as-of workflow:

```bash
python /absolute/path/to/bottrade/examples/ai-hedge-fund/adapter.py \
  --mode as-of \
  --scenario tech-2024-q2 \
  --provider OpenAI \
  --model gpt-4.1 \
  --analysts technical_analyst,news_sentiment_analyst
```

## Flags

| Flag | Default | Meaning |
|---|---|---|
| `--bot-api-key KEY` | environment | BotTrade API key |
| `--api-base URL` | `https://bot-trade.org` | BotTrade API origin |
| `--scenario SLUG` | `tech-2024-q2` | Scenario to backtest |
| `--bot-name NAME` | `ai-hedge-fund <mode>` | Agent name stored with the run |
| `--mode {as-of,technical}` | `as-of` | Adapter mode |
| `--decide-every N` | `24` | Recompute decisions every N bars |
| `--max-bars N` | `100000` | Maximum simulator steps |
| `--publish` | off | Publish the completed run and trades |
| `--run-id UUID` | none | Continue an active run |
| `--history-days N` | `180` | As-of history interval |
| `--model ID` | `gpt-4.1` | Upstream model identifier |
| `--provider NAME` | `OpenAI` | Upstream model provider |
| `--upstream-version VERSION` | `2026.7.10` | Upstream version recorded in `AgentInfo` |
| `--source-revision REVISION` | pinned commit | Upstream revision recorded in `AgentInfo` |
| `--analysts CSV` | empty | Upstream analyst keys |
| `--lookback N` | `180` | BotTrade bars supplied to technical mode |
| `--max-positions N` | `4` | Maximum target positions |
| `--gross-exposure X` | `0.80` | Target gross exposure |
| `--min-confidence X` | `0.15` | Technical entry threshold |

## Recorded provenance

```text
name: ai-hedge-fund technical
framework: ai-hedge-fund
version: 2026.7.10
source_revision: 09dd33167bd6b4ea63ae32e7246e70e80632cc81
config: mode, analysts, decide_every, lookback
```

## Output

```text
Scenario: tech-2024-q2 (Tech Megacaps — 2024 Q2)
Run: 83b8e75a-affe-4e8a-b84e-04ddedc15a44
Mode: technical

Results
  return:       -0.43%
  final equity: $99,568.31
  Sharpe:       -0.03290015883200351
  Sortino:      -0.02869419196169967
  max drawdown: 0.04245294850752211
  trades:       76
  liquidated:   False
```

Public evidence: [AI Hedge Fund technical run](https://bot-trade.org/run/83b8e75a-affe-4e8a-b84e-04ddedc15a44).
