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

## Quickstart (this machine — mock mode)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # MT5_CLIENT_MODE=mock by default
python -m pytest tests/ -v
```

Inspect the live tool list over real MCP stdio:

```bash
npx @modelcontextprotocol/inspector --cli python mcp/server.py --method tools/list
```

## Running against real Exness data (Windows only)

See `docs/SETUP.md` for the full EliteBook walkthrough. Summary:

1. Install MT5, log into your Exness account in the terminal itself (never
   store the password in this repo).
2. Install Windows Python 3.10+, `pip install -r requirements.txt`, then
   `pip install MetaTrader5` (Windows-only package, commented out of
   `requirements.txt` for that reason).
3. Set `MT5_CLIENT_MODE=real` in `.env`.
4. `python mcp/server.py`

## Docs

- `docs/SETUP.md` — EliteBook / Windows setup walkthrough
- `docs/ARCHITECTURE.md` — system design
- `docs/SECURITY.md` — credential handling
- `docs/CALENDAR.md` — economic calendar: why not ForexFactory, how the MQL5
  bridge works, and the banked news blackout rule
- `docs/TRADING_MODES.md` — READ_ONLY / CONFIRMATION / AUTONOMOUS and how
  trading tools get added
