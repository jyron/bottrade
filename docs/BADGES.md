# Verified “Tested on BotTrade” badges

A badge represents one published BotTrade run. It links to the public run page containing
the scenario, return, risk metrics, filled trades, positions, and equity path.

```markdown
[![Tested on BotTrade](https://bot-trade.org/run/<RUN_ID>/badge.svg)](https://bot-trade.org/run/<RUN_ID>)
```

Generate the Markdown with the CLI:

```bash
bottrade badge <RUN_ID>
```

Private or nonexistent run IDs return `404`. Badge color reflects only the sign of the
reported return: green for positive, gray for zero, and red for negative. It does not
represent approval, safety, robustness, or expected future performance.
