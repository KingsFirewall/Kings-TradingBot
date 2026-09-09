# ai-forex-trader

Infrastructure for connecting an AI agent to an Exness MT5 account through
MCP. This is **not** a trading strategy and makes no profitability claims —
see `docs/` for the full safety model.

## Current stage: Stage 1/2 — read-only MCP

Implemented so far:

- `mcp/mt5_client.py` — MT5 client interface, with a `MockMT5Client` (fake
  data, runs anywhere) and a `RealMT5Client` (wraps the official
  `MetaTrader5` package, Windows-only).
- `mcp/calendar_source.py` — economic calendar interface, with a
  `MockCalendarSource` and a `CsvCalendarSource` that reads the export from
  `mql5/CalendarExporter.mq5`.
- `mql5/CalendarExporter.mq5` — EA that dumps MT5's built-in economic
  calendar to CSV, because the Python `MetaTrader5` package doesn't expose
  it. Read-only; never trades. See `docs/CALENDAR.md`.
- `mcp/server.py` — MCP server exposing 8 **read-only** tools: `get_account`,
  `get_symbol_info`, `get_tick`, `get_rates`, `get_positions`, `get_orders`,
  `get_trade_history`, `get_calendar_events`.

**No trading tools exist yet.** They come after the risk engine (see
`docs/TRADING_MODES.md`) and only against a DEMO account.

## Quickstart (Windows — the trading machine)

MT5 runs on Windows only, so that's where this project runs. Full
walkthrough in `docs/SETUP.md`; the short version, in PowerShell:

```powershell
git clone https://github.com/KingsFirewall/Kings-TradingBot.git
cd Kings-TradingBot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m pytest tests\ -v
```

That runs against mock data and needs no MT5. To point it at your live
Exness account, set `MT5_CLIENT_MODE=real` in `.env` with the MT5 terminal
open and logged in, then:

```powershell
python mcp\server.py
```

Inspect the live tool list over real MCP stdio (needs Node.js):

```powershell
npx @modelcontextprotocol/inspector --cli python mcp\server.py --method tools/list
```

## Why there's still a mock

`MockMT5Client` and `MockCalendarSource` aren't a second-OS workaround —
they're what makes the test suite fast, deterministic, and runnable without
the terminal open and logged in. Tests that depend on a live broker
connection fail for reasons that have nothing to do with your code. The real
clients are exercised on the trading machine; the mocks pin the contract
they have to satisfy.

## Docs

- `docs/SETUP.md` — EliteBook / Windows setup walkthrough
- `docs/ARCHITECTURE.md` — system design
- `docs/SECURITY.md` — credential handling
- `docs/CALENDAR.md` — economic calendar: why not ForexFactory, how the MQL5
  bridge works, and the banked news blackout rule
- `docs/TRADING_MODES.md` — READ_ONLY / CONFIRMATION / AUTONOMOUS and how
  trading tools get added
