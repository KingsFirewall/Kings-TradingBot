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

## 3. Copy this repo to the EliteBook

Easiest: `git clone` it there once it has a remote, or copy the folder via
USB/network share for now.

## 4. Install dependencies

```powershell
cd ai-forex-trader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install MetaTrader5
```

`MetaTrader5` is commented out of `requirements.txt` because it has no macOS
build and would fail `pip install` on the Mac dev machine — install it
explicitly here.

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
not the `MOCK-SERVER` values you saw on the Mac.

## 8. First three tests (PRD section 39)

Once the MCP server is wired into your AI agent (Claude Code/Codex) on this
machine, run these prompts and confirm each one is backed by real MT5 data
(check the `source`/`timestamp` fields in the tool output):

1. "Give me my Exness account balance, equity, free margin, and current open
   positions."
2. "Give me the current bid, ask and spread for EURUSD and the last 100 H1
   candles."
3. "Analyze EURUSD H1 using the data you just retrieved. Do not trade."

Only after all three pass should any trading tool be added — and even then,
only against a DEMO account first.
