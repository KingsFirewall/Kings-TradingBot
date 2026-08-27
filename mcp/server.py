"""
Read-only MT5 MCP server — Stage 1/2 of the PRD.

Deliberately exposes NO trading tools. Only account, symbol, tick, candle,
position, order and history lookups. Trading tools are added in a later
stage, after the risk engine exists and only against a DEMO account.

Run with:
    python mcp/server.py

Test with:
    npx @modelcontextprotocol/inspector python mcp/server.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mt5_client import MT5ConnectionError, Timeframe, build_client  # noqa: E402

load_dotenv()

CLIENT_MODE = os.getenv("MT5_CLIENT_MODE", "mock")
client = build_client(CLIENT_MODE)
client.connect()

mcp = MCPServer("mt5-readonly")


def _source_tag() -> dict:
    return {
        "source": "MT5" if CLIENT_MODE == "real" else "MOCK (not real market data)",
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


@mcp.tool()
def get_account() -> dict:
    """Return live Exness account info: balance, equity, margin, leverage, trade permissions."""
    info = client.get_account()
    return {**info.__dict__, **_source_tag()}


@mcp.tool()
def get_symbol_info(symbol: str) -> dict:
    """Return a symbol's trading specification (lot limits, digits, contract size, etc.).
    Always call this before calculating any position size — never guess these values."""
    info = client.get_symbol_info(symbol)
    return {**info.__dict__, **_source_tag()}


@mcp.tool()
def get_tick(symbol: str) -> dict:
    """Return the current bid/ask for a symbol. Never state a price without calling this first."""
    tick = client.get_tick(symbol)
    return {**tick.__dict__, **_source_tag()}


@mcp.tool()
def get_rates(symbol: str, timeframe: Timeframe, count: int) -> dict:
    """Return the last `count` OHLC candles for symbol/timeframe.
    Supported timeframes: M1, M5, M15, M30, H1, H4, D1, W1."""
    candles = client.get_rates(symbol, timeframe, count)
    return {"symbol": symbol, "timeframe": timeframe, "candles": [c.__dict__ for c in candles], **_source_tag()}


@mcp.tool()
def get_positions() -> dict:
    """Return all currently open positions on the account."""
    positions = client.get_positions()
    return {"positions": [p.__dict__ for p in positions], **_source_tag()}


@mcp.tool()
def get_orders() -> dict:
    """Return all currently pending orders on the account."""
    orders = client.get_orders()
    return {"orders": [o.__dict__ for o in orders], **_source_tag()}


@mcp.tool()
def get_trade_history(start_date: str, end_date: str) -> dict:
    """Return closed deals between two ISO 8601 dates, e.g. '2026-08-01' to '2026-08-26'."""
    try:
        deals = client.get_trade_history(start_date, end_date)
    except MT5ConnectionError as e:
        return {"error": str(e), **_source_tag()}
    return {"deals": [d.__dict__ for d in deals], **_source_tag()}


if __name__ == "__main__":
    mcp.run(transport="stdio")
