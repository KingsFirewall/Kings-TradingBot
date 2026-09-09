# Economic calendar

Global news drives forex, so the agent needs to know what is scheduled. This
document covers where that data comes from, how to set it up on the
EliteBook, and — importantly — what it is and is not good for.

## Why not ForexFactory

ForexFactory has **no public API and no developer program**, and the site
sits behind aggressive bot blocking (it returns HTTP 403 to automated
requests). The community MCP servers that expose "ForexFactory data" are
Playwright browser scrapers. That means:

- Scraping it very likely violates their terms of service.
- A scraper breaks without warning when the page changes or the bot
  protection tightens — and it will break at the worst possible moment,
  because high-traffic release times are exactly when protection is
  strictest and when you would be querying.
- The most-cited MCP server for it had 11 stars and was unmaintained.

Unvetted scraped data feeding a system that sizes real positions is the
kind of dependency this project's architecture exists to avoid.

## What we use instead

**MT5 already ships a full economic calendar**, supplied by MetaQuotes, with
event time, currency, importance, and actual/forecast/previous values. No API
key, no subscription, no scraping, no terms-of-service problem. It is already
on the machine you are running the terminal on.

The catch: the Python `MetaTrader5` package exposes **none** of it. The
calendar lives in MQL5 only (`CalendarValueHistory()`,
`CalendarEventById()`, `CalendarCountryById()`, and seven others). So we
bridge it:

```
MT5 terminal calendar
        │  MQL5 Calendar* functions
        ▼
mql5/CalendarExporter.mq5      — EA on a chart, re-exports on a timer
        │  writes MQL5\Files\calendar.csv (atomic: temp file + rename)
        ▼
mcp/calendar_source.py         — CalendarSource interface
        │
        ├── MockCalendarSource  — sample events, runs on any OS
        └── CsvCalendarSource   — reads the exported CSV
                │
                ▼
mcp/server.py get_calendar_events   — read-only MCP tool #8
```

Same interface/mock/real split as `mt5_client.py`, for the same reason: the
news blackout rule in `risk/` can be built and tested on the Mac before any
of this touches a live terminal.

## Setup on the EliteBook

1. **Confirm the calendar is populated.** In MT5: View → Toolbox → Calendar.
   If it is empty, the terminal has not downloaded it yet — leave the
   terminal open and connected for a few minutes.

2. **Install the exporter.** In MetaEditor (F4 from the terminal), open the
   Navigator, right-click `Expert Advisors` → Open Folder. Copy
   `mql5/CalendarExporter.mq5` there, then compile it in MetaEditor (F7).

3. **Attach it to a chart.** Any chart, any symbol — it does not read prices.
   Drag `CalendarExporter` from the Navigator onto a chart. Inputs:

   | Input | Default | Notes |
   |---|---|---|
   | `DaysBack` | 7 | History window |
   | `DaysForward` | 14 | Lookahead window |
   | `RefreshSeconds` | 300 | Re-export interval (clamped to ≥30) |
   | `OutputFileName` | `calendar.csv` | Written to `MQL5\Files\` |
   | `CurrencyFilter` | *(empty)* | e.g. `USD,EUR,GBP`; empty = all |

   The EA does not need "Allow live trading" — it never trades. Check the
   Experts tab for a line like
   `CalendarExporter: wrote 412 events to calendar.csv`.

4. **Find the file.** In the terminal: File → Open Data Folder, then
   `MQL5\Files\calendar.csv`. The path contains a per-installation hash, so
   it cannot be derived from Python — point the reader at it explicitly:

   ```
   MT5_CALENDAR_CSV=C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\<hash>\MQL5\Files\calendar.csv
   ```

   Put that in `.env` alongside `MT5_CLIENT_MODE=real`.

5. **⚠️ Verify the timezone once.** This is the step most likely to be
   wrong, and getting it wrong makes a blackout rule fire at the wrong hour
   or not at all.

   `MqlCalendarValue.time` is in **trade server time**, not UTC. Exness
   servers typically run GMT+2/+3 with DST. The exporter derives the offset
   from the terminal (`TimeCurrent() - TimeGMT()`, snapped to 15 minutes)
   and records it in `MQL5\Files\calendar_meta.csv`.

   To confirm: pick a release you can check independently — say the next US
   NFP, published at 08:30 America/New_York = 12:30 or 13:30 UTC depending
   on DST. Compare against `event_time_utc` in the CSV. If it is off by a
   whole number of hours, the offset derivation is wrong for your broker;
   open an issue rather than fudging the number, because the same offset
   error will silently apply to every event.

## Staleness

`CsvCalendarSource` refuses to serve a CSV older than **60 minutes** by
default and raises instead. If the exporter EA is detached, the terminal is
closed, or the chart is removed, the file quietly stops updating — and
serving day-old rows as "upcoming events" is a worse failure than serving
none, because the agent cannot tell the difference. Pass
`max_age_minutes=0` to disable the check for offline analysis of an old
export.

## What this is actually for

Be clear-eyed here. The temptation is to treat the calendar as an edge —
predict the number, trade the spike. The evidence does not support that for
a system at this stage, and this project makes no profitability claims.

Around high-impact releases, liquidity providers pull quotes. EURUSD
spreads that normally sit at 0.5–1.5 pips **widen 10–50x**. Slippage runs
15+ pips. Most importantly: **stop losses stop being reliable.** Price gaps
straight through the stop level and fills come in well beyond it.

That last point is the one that matters architecturally. The entire design
rests on the risk engine computing a bounded worst-case loss per trade. A
news spike is precisely the condition under which that bound silently
fails — the engine says "risking 1%" and the fill says otherwise.

So the calendar's primary job here is **defensive**, not predictive.

## Banked requirement: the news blackout rule

To be implemented in `risk/`, alongside the daily loss limit and drawdown
limit. Not implemented yet — no risk engine exists, and per
`docs/TRADING_MODES.md` no trading tool may exist before it does.

- **Block new entries** within N minutes either side of a HIGH importance
  event affecting **either** currency in the pair (EURUSD is affected by
  both USD and EUR events). N is a config value; 30 minutes before and 15
  after is a common starting point, and should be validated on a demo
  account rather than assumed.
- **Flag, do not auto-close**, open positions carrying exposure into a
  high-impact event. Closing is a trading action and needs the same risk
  approval as opening.
- **Treat a stale or unavailable calendar as a blackout**, not as "no
  events." Failing open here means the one time the exporter dies is the one
  time the agent trades straight into an NFP print.
- **Widen the required stop distance**, or reduce size, for positions
  legitimately held through a scheduled event.

Feeding events to the agent as context is fine too — but log what it does
with them and check the attribution later, rather than assuming it helps.
