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

## Third-party data

- The economic calendar comes from **MT5's own built-in calendar**, via
  `mql5/CalendarExporter.mq5`. We deliberately do not scrape ForexFactory
  or use a community scraper for it — no public API exists, scraping likely
  breaches their terms, and an unmaintained scraper is a poor dependency for
  a system that will size real positions. Reasoning in `docs/CALENDAR.md`.
- The only file crossing into Python from outside the process is that
  calendar CSV. It's written by our own EA, inside the terminal's data
  folder, on the same machine. `CsvCalendarSource` still validates every row
  and refuses stale files rather than trusting it blindly.

## What's NOT built yet (so don't assume it's covered)

- No trading tools exist, so there's no order-execution attack surface yet.
- No database yet — nothing is persisted outside the running process.
- No dashboard/API yet — nothing is web-exposed.
- **Prompt-injection is not addressed.** It doesn't bite today (read-only
  tools, no execution path), but the moment a trading tool exists the agent
  will be reading market data, calendar text and possibly news, then acting
  with real money. Threat-model that before Stage 3, not after.

Update this file as each of those gets added.
