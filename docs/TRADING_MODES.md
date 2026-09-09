# Trading modes

Three modes, defined by the original PRD. **Only READ_ONLY exists in the
code today** — the other two require the risk engine, which isn't built
yet.

## READ_ONLY (current, and default)

The AI can call any of the 8 tools in `mcp/server.py`: account, symbol,
tick, candles, positions, orders, history, calendar events. There is no
tool that places, modifies, or closes anything. This is enforced by
omission — the tools literally don't exist — not by a flag the AI could
talk its way around.

The same applies on the MQL5 side: `mql5/CalendarExporter.mq5` reads the
terminal's calendar and writes a CSV. Its `OnTick()` is deliberately empty
and it never touches an order.

## CONFIRMATION (not yet built)

Planned: the AI prepares a trade proposal (symbol, direction, entry, SL,
TP, computed position size, estimated loss, reasoning) and a human must
explicitly approve before anything reaches MT5.

## AUTONOMOUS (not yet built)

Planned: the AI can execute trades without per-trade human approval, but
every order still passes through the deterministic risk engine first —
the AI proposes, the risk engine decides, the execution layer only acts on
`RISK_APPROVED = TRUE`.

Requires, before this is enabled at all:
- A tested risk engine (position sizing, daily loss limit, drawdown limit,
  max positions, stop-loss requirement, news blackout — see
  `docs/CALENDAR.md`).
- Demo account validation over a real time period, not just unit tests.
- `TRADING_MODE` and `AUTONOMOUS_TRADING` set by explicit manual config
  change — the agent itself must never be able to flip these.

## Rule for this project going forward

Do not add a trading tool (`place_market_order`, `close_position`, etc.) to
`mcp/server.py` until the risk engine in `risk/` exists and has its own
passing test suite. If you're tempted to skip the risk engine "just for a
demo test," don't — that's exactly the shortcut this architecture exists to
prevent.
