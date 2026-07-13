# Evaluate `virattt/ai-hedge-fund` with BotTrade

The adapter runs inside an upstream [`virattt/ai-hedge-fund`](https://github.com/virattt/ai-hedge-fund)
checkout. BotTrade owns scenario time, simulation, fills, portfolio state, and scoring. The adapter
now delegates all BotTrade HTTP behavior to the maintained typed SDK.

- `technical`: upstream technical functions receive only BotTrade-visible OHLCV bars.
- `as-of`: upstream’s full workflow receives the active scenario date and locally configured model
  and data providers. External inputs are caller-owned and therefore self-attested.

## Reproducible setup

```bash
git clone https://github.com/virattt/ai-hedge-fund.git
cd ai-hedge-fund
git checkout 09dd33167bd6b4ea63ae32e7246e70e80632cc81  # v2026.7.10 verified by CI
poetry install
poetry run pip install 'bottrade[ai-hedge-fund]'
export BOTTRADE_API_KEY="bt_your_key_here"
python /absolute/path/to/bottrade/examples/ai-hedge-fund/adapter.py \
  --mode technical \
  --scenario tech-2024-q2
```

The CI compatibility target is upstream `v2026.7.10` at immutable commit
`09dd33167bd6b4ea63ae32e7246e70e80632cc81`. Record `git rev-parse HEAD`, adapter version,
scenario slug/version, flags, and run ID. The adapter
targets upstream’s `src.main.run_hedge_fund` and `src.agents.technicals` interfaces, not the separate
experimental `v2` `AlphaModel` surface.

| Flag | Default | Applies to | Meaning |
|---|---|---|---|
| `--bot-api-key KEY` | environment | both | Prefer `BOTTRADE_API_KEY`; legacy `BOT_API_KEY` also works |
| `--api-base URL` | `https://bot-trade.org` | both | BotTrade API origin |
| `--scenario SLUG` | `tech-2024-q2` | both | Scenario to run |
| `--bot-name NAME` | `ai-hedge-fund <mode>` | both | Run label |
| `--mode {as-of,technical}` | `as-of` | both | Strategy/input boundary |
| `--decide-every N` | `24` | both | Recompute decisions every N bars |
| `--max-bars N` | `100000` | both | Safety cap; incomplete runs fail visibly |
| `--publish` | off | both | Publish only after completion |
| `--run-id UUID` | none | both | Resume an existing active run |
| `--history-days N` | `180` | as-of | External history interval passed upstream |
| `--model ID` | `gpt-4.1` | as-of | Upstream model identifier |
| `--provider NAME` | `OpenAI` | as-of | Upstream provider identifier |
| `--analysts CSV` | empty | as-of | Comma-separated upstream analyst keys |
| `--lookback N` | `180` | technical | BotTrade bars supplied; minimum 130 |
| `--max-positions N` | `4` | technical | Maximum target positions |
| `--gross-exposure X` | `0.80` | technical | Target gross notional divided by equity, in `(0,1]` |
| `--min-confidence X` | `0.15` | technical | Entry threshold in `[0,1]` |

## Output and completion

The adapter automatically steps through the complete run and fails nonzero if it reaches the safety
cap. This output is from the published
[technical-mode evidence run](https://bot-trade.org/run/83b8e75a-affe-4e8a-b84e-04ddedc15a44):

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

Use `--run-id` after an interruption. Do not change the upstream revision or experimental flags
mid-run. Technical mode’s input boundary is reproducible from BotTrade bars; as-of mode additionally
requires provider/model/data provenance and cannot be independently reconstructed by BotTrade alone.

Verification: CI statically checks the named upstream runner parameters and technical functions at
the pinned revision. It also exercises portfolio mapping, date boundaries, order clamping, all five technical
function calls on synthetic pandas bars, target construction, resume behavior, completion, and
explicit publication through a stateful fake client. It does not falsely claim that arbitrary future
upstream revisions or private external-data subscriptions are continuously available.
