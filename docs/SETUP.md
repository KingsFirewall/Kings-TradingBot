# Setup — HP EliteBook (Windows)

This gets the real MT5 read-only pipeline working: `Exness MT5 → MCP → AI agent`.
No trading tools exist at this stage — this is purely for reading account and
market data.

## 1. Install MT5 and log into Exness

1. Download the MT5 terminal (from Exness's own download page for your
   account, or the generic MetaTrader 5 installer — either works, since MT5
   itself is broker-agnostic and you log into Exness's servers afterward).
2. Install and open it.
3. File → Login to Trade Account → enter your Exness login, password, and
   **server** (read this from your Exness account email/portal — don't
   guess it, Exness runs multiple server clusters e.g. `Exness-MT5Trial`,
   `Exness-MT5Real`, etc. and yours may differ).
4. Confirm you can see live prices in the Market Watch panel — this proves
   the terminal itself is connected before we touch any code.

Your Exness password lives only in the MT5 terminal's own login state from
here on. It is never entered into this project's code or config.

## 2. Install Python on the EliteBook

Download Python 3.10+ from python.org (Windows installer) — check "Add
python.exe to PATH" during install. Verify:

```powershell
python --version
```

## 3. Clone the repo

```powershell
git clone https://github.com/KingsFirewall/Kings-TradingBot.git
cd Kings-TradingBot
```

It's a private repo, so you'll authenticate. Cleanest is `winget install
GitHub.cli` then `gh auth login` (GitHub.com → HTTPS → Yes → browser) —
after that both `git clone` and `git push` just work, with no token to
paste or rotate.

## 4. Install dependencies

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

That includes `MetaTrader5` — it carries a `sys_platform == "win32"` marker,
so it installs here and is skipped on other platforms. No separate step.

## 5. Configure

```powershell
copy .env.example .env
```

Edit `.env`:

```
MT5_CLIENT_MODE=real
```

Leave `MT5_TERMINAL_PATH` blank if MT5 is already running and logged in —
the `MetaTrader5` package attaches to the running terminal via
`mt5.initialize()`, it doesn't need the path in that case.

## 6. Run it

With the MT5 terminal open and logged in:

```powershell
python mcp\server.py
```

If it exits immediately with an `MT5ConnectionError`, the message will tell
you whether MT5 isn't running, isn't logged in, or the package isn't
installed — read it, don't guess.

## 7. Verify with MCP Inspector

Requires Node.js on the EliteBook too:

```powershell
npx @modelcontextprotocol/inspector --cli python mcp\server.py --method tools/call --tool-name get_account
```

You should see your **real** Exness balance, equity, and server name back —
not the `MOCK-SERVER` placeholder values that `MT5_CLIENT_MODE=mock`
returns.

## 8. Set up the economic calendar (optional but recommended)

MT5 ships an economic calendar that the Python package can't reach. To
expose it as a tool, install `mql5/CalendarExporter.mq5` — full walkthrough
in `docs/CALENDAR.md`, including the timezone verification step you should
not skip.

If you skip this, `get_calendar_events` returns a clear error and the other
seven tools work normally.

## 9. Wire the MCP server into your AI agent

**In VSCode (or any Claude Code session opened at the repo root)** this is
already done — `.mcp.json` in the project root declares the server:

```json
{
  "mcpServers": {
    "mt5-readonly": {
      "command": ".venv/Scripts/python.exe",
      "args": ["mcp/server.py"]
    }
  }
}
```

Claude Code detects it on first open and asks you to approve the project's
MCP servers. Say yes, then run `/mcp` and confirm `mt5-readonly` is
connected with 8 tools.

The paths are relative to the repo root and point at the venv's
`python.exe` deliberately — the system Python has no `MetaTrader5`, so the
server would fail to start or silently serve mock data.

If the relative path doesn't resolve in your setup, register it explicitly
with absolute paths instead:

```powershell
claude mcp add mt5-readonly -- C:\path\to\Kings-TradingBot\.venv\Scripts\python.exe C:\path\to\Kings-TradingBot\mcp\server.py
```

For Codex or another MCP client, point it at the same command via that
client's own config.

## 10. First three tests (PRD section 39)

With the MCP server wired in, run these prompts and confirm each one is
backed by real MT5 data (check the `source`/`timestamp` fields in the tool
output):

1. "Give me my Exness account balance, equity, free margin, and current open
   positions."
2. "Give me the current bid, ask and spread for EURUSD and the last 100 H1
   candles."
3. "Analyze EURUSD H1 using the data you just retrieved. Do not trade."

Only after all three pass should any trading tool be added — and even then,
only against a DEMO account first.
