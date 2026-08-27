"""
MT5 client abstraction.

MT5Client is the interface the MCP server talks to. RealMT5Client wraps the
official `MetaTrader5` package and only works on Windows with a running,
logged-in MT5 terminal. MockMT5Client returns fixed sample data so the rest
of the stack (MCP server, tests, future risk engine) can be built and tested
on any machine before real MT5 access exists.

Read-only for now: no order placement here. Trading tools come in a later
stage per the PRD, after the risk engine exists.
"""

from __future__ import annotations

import abc
import datetime as dt
import platform
from dataclasses import dataclass, field
from typing import Literal

Timeframe = Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]


@dataclass
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    leverage: int
    currency: str
    trade_allowed: bool


@dataclass
class SymbolInfo:
    symbol: str
    min_lot: float
    max_lot: float
    lot_step: float
    point: float
    digits: int
    contract_size: float
    spread: float
    trade_mode: str
    stop_level: float
    tick_size: float
    tick_value: float


@dataclass
class Tick:
    symbol: str
    bid: float
    ask: float
    timestamp: str  # ISO 8601, UTC


@dataclass
class Candle:
    time: str  # ISO 8601, UTC
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Position:
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    floating_pnl: float


@dataclass
class Order:
    ticket: int
    symbol: str
    type: str
    volume: float
    price: float
    status: str


@dataclass
class Deal:
    ticket: int
    symbol: str
    direction: str
    volume: float
    price: float
    profit: float
    commission: float
    swap: float
    time: str


class MT5ConnectionError(RuntimeError):
    """Raised when the MT5 terminal is unreachable or not logged in."""


class MT5Client(abc.ABC):
    @abc.abstractmethod
    def connect(self) -> None: ...

    @abc.abstractmethod
    def get_account(self) -> AccountInfo: ...

    @abc.abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolInfo: ...

    @abc.abstractmethod
    def get_tick(self, symbol: str) -> Tick: ...

    @abc.abstractmethod
    def get_rates(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]: ...

    @abc.abstractmethod
    def get_positions(self) -> list[Position]: ...

    @abc.abstractmethod
    def get_orders(self) -> list[Order]: ...

    @abc.abstractmethod
    def get_trade_history(self, start_date: str, end_date: str) -> list[Deal]: ...


class MockMT5Client(MT5Client):
    """Deterministic fake data. Never presented to the AI as real market data —
    the MCP server tags every mock response so it can't be confused with a live
    Exness feed (see server.py SOURCE field)."""

    def connect(self) -> None:
        return None

    def get_account(self) -> AccountInfo:
        return AccountInfo(
            login=00000000,
            server="MOCK-SERVER",
            balance=10000.00,
            equity=10000.00,
            margin=0.0,
            free_margin=10000.00,
            leverage=100,
            currency="USD",
            trade_allowed=False,
        )

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        return SymbolInfo(
            symbol=symbol,
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01,
            point=0.00001,
            digits=5,
            contract_size=100000.0,
            spread=1.2,
            trade_mode="FULL",
            stop_level=0.0,
            tick_size=0.00001,
            tick_value=1.0,
        )

    def get_tick(self, symbol: str) -> Tick:
        return Tick(
            symbol=symbol,
            bid=1.10000,
            ask=1.10012,
            timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        )

    def get_rates(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]:
        now = dt.datetime.now(dt.timezone.utc)
        candles = []
        price = 1.10000
        for i in range(count):
            t = now - dt.timedelta(hours=count - i)
            candles.append(
                Candle(
                    time=t.isoformat(),
                    open=price,
                    high=price + 0.0005,
                    low=price - 0.0005,
                    close=price + 0.0001,
                    volume=100,
                )
            )
            price += 0.0001
        return candles

    def get_positions(self) -> list[Position]:
        return []

    def get_orders(self) -> list[Order]:
        return []

    def get_trade_history(self, start_date: str, end_date: str) -> list[Deal]:
        return []


class RealMT5Client(MT5Client):
    """Wraps the official MetaTrader5 package. Windows-only — the package has
    no macOS/Linux build because it talks to the terminal via native IPC."""

    def __init__(self) -> None:
        if platform.system() != "Windows":
            raise MT5ConnectionError(
                "RealMT5Client requires Windows and a running MT5 terminal. "
                "Use MT5_CLIENT_MODE=mock on this machine."
            )
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError as e:
            raise MT5ConnectionError(
                "The MetaTrader5 package is not installed. Run: pip install MetaTrader5"
            ) from e
        self._mt5 = mt5

    def connect(self) -> None:
        if not self._mt5.initialize():
            raise MT5ConnectionError(
                f"MT5 initialize() failed: {self._mt5.last_error()}. "
                "Is the MT5 terminal running and logged into Exness?"
            )
        account_info = self._mt5.account_info()
        if account_info is None:
            raise MT5ConnectionError(
                "MT5 initialized but no account is logged in. "
                "Log into your Exness account in the MT5 terminal first."
            )

    def get_account(self) -> AccountInfo:
        info = self._mt5.account_info()
        if info is None:
            raise MT5ConnectionError("Could not read account info from MT5.")
        return AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            leverage=info.leverage,
            currency=info.currency,
            trade_allowed=bool(info.trade_allowed),
        )

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        info = self._mt5.symbol_info(symbol)
        if info is None:
            raise MT5ConnectionError(
                f"Symbol '{symbol}' not found on this broker. "
                "Query the actual symbol list instead of guessing the name — "
                "Exness may use suffixes/prefixes (e.g. EURUSDm)."
            )
        return SymbolInfo(
            symbol=symbol,
            min_lot=info.volume_min,
            max_lot=info.volume_max,
            lot_step=info.volume_step,
            point=info.point,
            digits=info.digits,
            contract_size=info.trade_contract_size,
            spread=info.spread,
            trade_mode=str(info.trade_mode),
            stop_level=info.trade_stops_level,
            tick_size=info.trade_tick_size,
            tick_value=info.trade_tick_value,
        )

    def get_tick(self, symbol: str) -> Tick:
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            raise MT5ConnectionError(f"No tick data for '{symbol}'.")
        return Tick(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            timestamp=dt.datetime.fromtimestamp(tick.time, dt.timezone.utc).isoformat(),
        )

    def get_rates(self, symbol: str, timeframe: Timeframe, count: int) -> list[Candle]:
        tf_map = {
            "M1": self._mt5.TIMEFRAME_M1,
            "M5": self._mt5.TIMEFRAME_M5,
            "M15": self._mt5.TIMEFRAME_M15,
            "M30": self._mt5.TIMEFRAME_M30,
            "H1": self._mt5.TIMEFRAME_H1,
            "H4": self._mt5.TIMEFRAME_H4,
            "D1": self._mt5.TIMEFRAME_D1,
            "W1": self._mt5.TIMEFRAME_W1,
        }
        if timeframe not in tf_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        rates = self._mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, count)
        if rates is None:
            raise MT5ConnectionError(f"Could not fetch rates for '{symbol}' {timeframe}.")
        return [
            Candle(
                time=dt.datetime.fromtimestamp(r["time"], dt.timezone.utc).isoformat(),
                open=r["open"],
                high=r["high"],
                low=r["low"],
                close=r["close"],
                volume=int(r["tick_volume"]),
            )
            for r in rates
        ]

    def get_positions(self) -> list[Position]:
        positions = self._mt5.positions_get()
        if positions is None:
            return []
        return [
            Position(
                ticket=p.ticket,
                symbol=p.symbol,
                direction="BUY" if p.type == 0 else "SELL",
                volume=p.volume,
                entry_price=p.price_open,
                current_price=p.price_current,
                stop_loss=p.sl,
                take_profit=p.tp,
                floating_pnl=p.profit,
            )
            for p in positions
        ]

    def get_orders(self) -> list[Order]:
        orders = self._mt5.orders_get()
        if orders is None:
            return []
        return [
            Order(
                ticket=o.ticket,
                symbol=o.symbol,
                type=str(o.type),
                volume=o.volume_current,
                price=o.price_open,
                status="PENDING",
            )
            for o in orders
        ]

    def get_trade_history(self, start_date: str, end_date: str) -> list[Deal]:
        start = dt.datetime.fromisoformat(start_date)
        end = dt.datetime.fromisoformat(end_date)
        deals = self._mt5.history_deals_get(start, end)
        if deals is None:
            return []
        return [
            Deal(
                ticket=d.ticket,
                symbol=d.symbol,
                direction="BUY" if d.type == 0 else "SELL",
                volume=d.volume,
                price=d.price,
                profit=d.profit,
                commission=d.commission,
                swap=d.swap,
                time=dt.datetime.fromtimestamp(d.time, dt.timezone.utc).isoformat(),
            )
            for d in deals
        ]


def build_client(mode: str) -> MT5Client:
    if mode == "mock":
        return MockMT5Client()
    if mode == "real":
        return RealMT5Client()
    raise ValueError(f"Unknown MT5_CLIENT_MODE: {mode!r} (expected 'mock' or 'real')")
