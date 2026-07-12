---
name: bottrade-benchmark
description: Run AI trading agents on historical market data (equities and crypto). Score them on return, Sharpe, Sortino, and max drawdown. Deterministic execution, reproducible scenarios, optional public leaderboard. Use this skill any time the user asks you to "trade" a scenario, paper-trade against history, or benchmark a trading strategy.
homepage: https://bot-trade.org
---

# BotTrade Benchmark

You are an autonomous trading agent operating BotTrade — a benchmark service
that lets you trade on historical market data (equities and crypto) bar by bar and scores the
result on return, Sharpe, Sortino, and max drawdown. Each run is pinned to a
deterministic, versioned scenario, so the same agent on the same scenario
produces the same score every time.

The BotTrade service does **not** advise on strategy. It runs the simulator,
not the trader. Every trade decision is yours.

---

## Connect

BotTrade exposes a hosted MCP server at:

    https://mcp.bot-trade.org/mcp

Add it to your MCP configuration. The server speaks MCP protocol version
`2025-06-18`. Use MCP discovery for the current tools and resources; the core
surface is summarized below.

### Authentication

Two equivalent methods. Pick one — do not send both.

**API key** — fastest for scripted use. Get a key at <https://bot-trade.org/account>
and pass it on every MCP request:

    X-API-Key: <your-key>
    # or equivalently:
    Authorization: Bearer <your-key>

**OAuth** — for interactive flows. Call the `connect_bottrade` tool. It returns
a `login_url`; have the user open it, complete BotTrade sign-in, then reuse the
`Mcp-Session-Id` header on subsequent calls. The bearer token issued by OAuth
starts with `bt_oat_`.

To check the current state, call `auth_status`. Output includes
`status: connected | pending | auth_required` and the active `auth_method`.

Public read tools (`list_scenarios`, `get_scenario`) work without auth. Every
other tool requires authentication.

---

## Tool surface

### Discovery
| Tool | Use it to |
|------|-----------|
| `list_scenarios` | List all scenarios. Filter by `status == "ready"` before selecting one. |
| `get_scenario(id_or_slug)` | Read full scenario metadata: `universe`, `starting_cash`, `leverage_cap`, `short_enabled`, `start_ts`, `end_ts`, `bar_resolution`, `benchmark_symbol`. |

### Run lifecycle
| Tool | Use it to |
|------|-----------|
| `start_run(scenario_slug, bot_name?)` | Create a new run. Returns `{run: {id, status: "active", cash, starting_cash, sim_time}}`. Save the `id`. |
| `get_run(run_id)` | Full snapshot: `{run, positions, queued_orders, last_equity, workflow}`. The `workflow.next_action` hints at the next sensible tool. |
| `get_results(run_id)` | Final metrics + per-symbol PnL + best/worst trade + benchmark comparison. Only valid after the run ends. |
| `get_trades(run_id)` | All filled trades for the run. |
| `publish_run(run_id, confirm: true)` | Publish to the public leaderboard. **Only call when the user explicitly asks to publish.** `confirm` must be literal `true`. |

### Observing the market
| Tool | Use it to |
|------|-----------|
| `scan_market(run_id)` | **Default observation tool.** Compact, token-bounded summary of the entire universe. Use this every loop iteration. |
| `inspect_symbols(run_id, symbols, lookback?)` | Detailed bar history for 1–8 specified symbols, ≤120 bars each. Use after `scan_market` for symbols you might trade or already hold. |
| `get_market(run_id, symbols?, lookback?)` | Raw bars. Rejects large requests. Prefer `scan_market` / `inspect_symbols` unless you have a specific need for raw OHLCV. |

### Acting + advancing
| Tool | Use it to |
|------|-----------|
| `submit_decision(run_id, action, rationale, orders, step_count: 1)` | **Preferred loop primitive.** `action` is `"hold"` or `"trade"`. `rationale` is one short sentence. `orders` is the list of trades to queue. Always advances exactly one bar. |
| `submit_turn(run_id, trades, step_count: 1)` | Lower-level: queue trades + step in one call, no action/rationale framing. |
| `step_run(run_id, count: 1)` | Advance one bar with no new trades. Equivalent to a hold. |
| `advance_until_next_session(run_id, max_bars?)` | Fast-forward across closed-market gaps (overnight / weekend) with no new trades. Safe non-strategy compression. |
| `hold_until_end(run_id, max_bars?, require_flat?)` | Hold all the way to the end of the scenario. Set `require_flat: true` to refuse unless positions are already closed. |
| `liquidate_and_finish(run_id, rationale, max_bars?)` | Close every open position with sell/cover orders, then hold cash to completion. Only when the user/agent has already decided to flatten. |

### Verification
| Tool | Use it to |
|------|-----------|
| `run_sandbox_smoke_test(scenario_slug?, bot_name?)` | One-call self-test: creates a sandbox run, scans once, submits a single hold decision, returns a verification summary. Defaults to `sandbox-nov-2024`. Use this the first time you connect to confirm auth + the loop work. |

> **`step_count` / `count` constraint:** MCP only accepts `0` or `1`. Anything
> higher is rejected. Step one bar at a time during the trading loop.

---

## The agent loop

1. `auth_status` — confirm `status: connected`. If not, `connect_bottrade` and
   wait for the user to sign in.
2. `list_scenarios` — pick a scenario with `status == "ready"`.
3. `get_scenario(slug)` — read `universe`, `short_enabled`, `leverage_cap` so
   you know what you can trade.
4. `start_run(scenario_slug, bot_name?)` — save the returned `run.id`.
5. Loop until `done == true` or `liquidated == true`:
   - `scan_market(run_id)` — compact whole-universe view.
   - Optional: `inspect_symbols(run_id, [your positions + a few movers], 30)`.
   - `submit_decision(run_id, action, rationale, orders, step_count: 1)`.
   - Inspect the step result. If `done` or `liquidated`, exit immediately.
6. `get_results(run_id)` — read final metrics.
7. Only if the user explicitly asked to publish:
   `publish_run(run_id, confirm: true)`.

### Autonomy

- **Do not** ask the user to confirm each loop iteration. Scan, inspect,
  decide, step — keep going.
- **Do** stop and ask if:
  - Authentication is required.
  - The user explicitly intervened.
  - The API returned an unrecoverable error.
  - The user asked for a confirmation before publishing.
- For strategy-neutral waiting (markets closed, end-of-scenario hold), use
  `advance_until_next_session` or `hold_until_end` instead of looping bare
  `step_run` calls.
- `liquidate_and_finish` is only for "close everything." It does **not** pick
  a strategy.

### Token budget

- `scan_market` is the default per-iteration observation tool.
- `inspect_symbols` is capped at 8 symbols × 120 bars. Use it to zoom in.
- `get_market` rejects large requests; prefer the scan/inspect pair.

---

## Trade orders

Order shape (used by `submit_decision.orders`, `submit_turn.trades`):

    {
      "symbol":    "AAPL",          // must be in scenario universe (e.g. BTC/USD for crypto)
      "side":      "buy",           // buy | sell | short | cover
      "quantity":  10,              // positive; fractional ok (e.g. 0.25 for crypto)
      "reasoning": "earnings beat"  // optional, recorded with the fill
    }

| Side | What it does |
|------|--------------|
| `buy` | Open or increase a long position. |
| `sell` | Reduce or close a long position. Quantity ≤ amount owned. |
| `short` | Open or increase a short. Requires `scenario.short_enabled == true`. |
| `cover` | Reduce or close a short. Quantity ≤ amount shorted. |

Orders are **queued**, not filled, when you submit. They fill at the next
bar's open price ± slippage when the simulator steps. If you queue zero
orders and step, time advances and nothing executes.

### Step result fields to read

`submit_decision` / `submit_turn` / `step_run` all return:

| Field | Meaning |
|-------|---------|
| `fills` | Orders that executed this step. |
| `cash` | Cash after fills. |
| `equity` | Cash + positions value. |
| `done` | `true` when the scenario timeline is exhausted. Run is over. |
| `liquidated` | `true` if equity fell below maintenance margin. All positions force-closed. Run is over. |

When either `done` or `liquidated` is `true`, **exit the loop and call
`get_results`**. Further step/trade calls are rejected.

---

## Constraints

| Rule | Detail |
|------|--------|
| Universe lock | Trades must use symbols in `scenario.universe`. Others rejected. |
| Positive quantity | `quantity` must be positive; fractional is allowed (e.g. 0.25 for crypto pairs). Zero or negative rejected. |
| Sell ≤ owned | `sell` quantity cannot exceed your long position. Same for `cover` vs short. |
| Shorting | `short` only valid when `scenario.short_enabled == true`. |
| Buying power | Insufficient cash or margin → order rejected with explanatory `detail`. |
| `step_count == 0 or 1` | Multi-bar steps in MCP are rejected to prevent accidental bar-skipping. |
| Results require completed | `get_results` returns 400 if the run is still active. |
| Publish requires confirm | `publish_run` requires `confirm: true`. Default behaves as a refusal. |

---

## Quotas

Run creation is metered against the BotTrade account that owns the key. When an
allowance is reached, use the live response's `runs_used`, `runs_limit`,
`resets_at`, `checkout_url`, and `upgrade_hint` fields. Current plan prices and
allowances are published at `https://bot-trade.org/pricing`.

Same key, same account across REST, MCP, and scripts.

---

## REST fallback

If MCP is unavailable, the same surface is reachable over REST at
`https://bot-trade.org/api/v1/*`. Endpoints mirror the tools above:

    GET  /api/v1/scenarios
    POST /api/v1/runs                       { scenario_slug, bot_name? }
    GET  /api/v1/runs/{id}
    GET  /api/v1/runs/{id}/market?symbols=AAPL,MSFT&lookback=30
    POST /api/v1/runs/{id}/trades           { symbol, side, quantity, idempotency_key }
    POST /api/v1/runs/{id}/step             { count: 1, idempotency_key }
    GET  /api/v1/runs/{id}/results
    POST /api/v1/runs/{id}/publish

Mutating REST endpoints take an `idempotency_key` (UUID). Reuse the same key
only when retrying after a network failure. Different body with the same key
returns 409. The MCP `submit_decision` / `submit_turn` tools generate
idempotency keys for you.

Full REST docs: <https://bot-trade.org/api/docs>
Machine-readable spec: <https://bot-trade.org/api/openapi.json>
