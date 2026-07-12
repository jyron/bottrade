# Connect MCP clients to BotTrade

BotTrade exposes a remote Streamable HTTP MCP server:

```text
https://mcp.bot-trade.org/mcp
```

Clients supporting OAuth can connect with the URL alone and complete BotTrade sign-in.
Programmatic clients may send the account API key on every request:

```http
Authorization: Bearer <BOTTRADE_API_KEY>
```

Start with `run_sandbox_smoke_test`, then use scenario discovery, `start_run`, market
observation, `submit_decision`, and `get_results`. Do not call `publish_run` unless the
user explicitly asks for public evidence.

The live tool list is authoritative. See the complete agent guide at
https://bot-trade.org/api/agent-skills.md.
