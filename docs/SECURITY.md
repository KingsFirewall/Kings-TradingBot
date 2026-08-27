# Security

## Credentials

- Your Exness password is entered **once, directly into the MT5 terminal
  itself**. It is never read, stored, or passed by any code in this repo.
- `RealMT5Client` connects via `mt5.initialize()`, which attaches to an
  already-running, already-logged-in terminal — it takes no credentials.
- `.env` is for local, non-secret config only (`MT5_CLIENT_MODE`,
  `TRADING_MODE`). It's gitignored. If a future stage adds a database or
  Telegram bot, those tokens go in `.env` locally and a proper secret
  manager (Windows Credential Manager / cloud secret store) in production —
  never in source.

## Network exposure

- The MCP server runs over **stdio only** (`mcp.run(transport="stdio")`).
  It is not bound to a network port and is not reachable from outside the
  machine it runs on. Keep it that way — don't switch to `sse` or
  `streamable-http` transport without a specific reason and matching
  authentication.

## What's NOT built yet (so don't assume it's covered)

- No trading tools exist, so there's no order-execution attack surface yet.
- No database yet — nothing is persisted outside the running process.
- No dashboard/API yet — nothing is web-exposed.

Update this file as each of those gets added.
