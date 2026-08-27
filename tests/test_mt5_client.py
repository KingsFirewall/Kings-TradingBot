"""Unit tests for the mock MT5 client and the read-only MCP tool functions.

These run on any machine (no real MT5/Windows needed) and validate the
contract the real client must also satisfy: every response carries the
fields the risk engine and journal will later depend on.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from mt5_client import MockMT5Client  # noqa: E402


def test_get_account_shape():
    client = MockMT5Client()
    info = client.get_account()
    assert info.currency == "USD"
    assert info.balance >= 0
    assert isinstance(info.trade_allowed, bool)


def test_get_symbol_info_has_position_sizing_fields():
    client = MockMT5Client()
    info = client.get_symbol_info("EURUSD")
    # These are the exact fields position sizing (section 13 of the PRD) needs.
    for field in ("min_lot", "max_lot", "lot_step", "tick_size", "tick_value", "contract_size"):
        assert getattr(info, field) > 0, f"{field} must be positive"


def test_get_tick_ask_gte_bid():
    client = MockMT5Client()
    tick = client.get_tick("EURUSD")
    assert tick.ask >= tick.bid


def test_get_rates_count_and_order():
    client = MockMT5Client()
    candles = client.get_rates("EURUSD", "H1", 10)
    assert len(candles) == 10
    times = [c.time for c in candles]
    assert times == sorted(times), "candles must be chronological"


def test_get_positions_empty_on_fresh_mock_account():
    client = MockMT5Client()
    assert client.get_positions() == []


def test_mcp_tools_tag_every_response_with_source_and_timestamp():
    """Guards the anti-hallucination rule (PRD section 34): every market claim
    must be traceable to a source and timestamp, never asserted from memory."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))
    import importlib
    import os

    os.environ["MT5_CLIENT_MODE"] = "mock"
    import server

    importlib.reload(server)

    for result in (
        server.get_account(),
        server.get_symbol_info("EURUSD"),
        server.get_tick("EURUSD"),
        server.get_positions(),
    ):
        assert "source" in result
        assert "timestamp" in result
        assert "MOCK" in result["source"]
