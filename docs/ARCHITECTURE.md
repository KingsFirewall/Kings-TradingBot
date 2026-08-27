# Architecture

```
AI Agent (Claude Code / Codex)
        │  MCP over stdio
        ▼
mcp/server.py            — tool definitions, no business logic
        │
        ▼
mcp/mt5_client.py        — MT5Client interface
        │
        ├── MockMT5Client   — fixed fake data, runs on any OS
        └── RealMT5Client   — wraps official MetaTrader5 package, Windows-only
                │
                ▼
        MT5 terminal (logged into Exness)
                │
                ▼
              Exness
```

## Why the client is split into an interface + two implementations

The `MetaTrader5` Python package only runs on Windows (native IPC with the
terminal). Everything else in this project — the MCP tool definitions, and
later the risk engine, backtester, and dashboard — is plain Python that
should be developed and tested without needing a Windows box or a live
Exness connection. `MockMT5Client` makes that possible: same interface,
fake data, runs anywhere. Swapping `MT5_CLIENT_MODE=real` on a Windows
machine with MT5 running is the only thing that changes.

## Why every tool response carries `source` and `timestamp`

PRD rule (section 34): the AI must never state a market fact without a
traceable source. Baking `source`/`timestamp` into every tool's return
value at the server layer means this is structurally guaranteed rather than
something the AI has to remember to mention.

## What's deliberately not here yet

Risk engine, position sizing, execution/trading tools, database, dashboard,
notifications, backtesting, multi-agent orchestration. These come in later
stages, in the order laid out in `docs/TRADING_MODES.md` and the original
PRD — building them now, before the read-only pipeline is proven against a
real account, would be building on an unverified foundation.
