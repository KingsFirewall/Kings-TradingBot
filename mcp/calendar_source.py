"""
Economic calendar abstraction.

MT5 ships a full economic calendar, but the Python `MetaTrader5` package
exposes none of the MQL5 Calendar* functions. The bridge is
mql5/CalendarExporter.mq5, an EA that writes the calendar to a CSV inside
MQL5\\Files\\; CsvCalendarSource reads that file.

Same shape as mt5_client.py: an interface, a deterministic mock that runs
anywhere, and a real implementation that only works where MT5 does. That
keeps calendar-dependent work (the news blackout rule in risk/) buildable
and testable on a machine with no MT5 at all.

Read-only. Nothing here decides anything — it reports events. The blackout
rule belongs in risk/, per docs/TRADING_MODES.md.
"""

from __future__ import annotations

import abc
import csv
import datetime as dt
import os
from dataclasses import dataclass
from typing import Literal

Importance = Literal["NONE", "LOW", "MEDIUM", "HIGH"]

# Ordered weakest to strongest so min_importance filtering is a simple
# index comparison.
_IMPORTANCE_ORDER: tuple[str, ...] = ("NONE", "LOW", "MEDIUM", "HIGH")


@dataclass
class CalendarEvent:
    event_time: str  # ISO 8601, UTC
    currency: str
    name: str
    importance: Importance
    actual: float | None
    forecast: float | None
    previous: float | None
    event_id: int


class CalendarError(RuntimeError):
    """Raised when calendar data is unavailable or unreadable."""


def importance_at_least(value: str, minimum: str) -> bool:
    """True if `value` is at least as important as `minimum`."""
    try:
        return _IMPORTANCE_ORDER.index(value) >= _IMPORTANCE_ORDER.index(minimum)
    except ValueError as e:
        raise CalendarError(
            f"Unknown importance {value!r}/{minimum!r}; expected one of {_IMPORTANCE_ORDER}."
        ) from e


class CalendarSource(abc.ABC):
    @abc.abstractmethod
    def get_events(
        self,
        start: str,
        end: str,
        currencies: list[str] | None = None,
        min_importance: Importance = "NONE",
    ) -> list[CalendarEvent]: ...


def _parse_utc(value: str, field: str) -> dt.datetime:
    """Parse an ISO 8601 string to an aware UTC datetime.

    Naive input is treated as UTC rather than local time. Every timestamp
    crossing this boundary is UTC by construction (the exporter converts
    server time before writing), so assuming local here would silently shift
    every comparison by the host's offset.
    """
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise CalendarError(f"{field} is not a valid ISO 8601 datetime: {value!r}") from e
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _filter(
    events: list[CalendarEvent],
    start: str,
    end: str,
    currencies: list[str] | None,
    min_importance: str,
) -> list[CalendarEvent]:
    """Shared window/currency/importance filtering, so the mock and the CSV
    reader cannot drift apart in what they consider a match."""
    start_dt = _parse_utc(start, "start")
    end_dt = _parse_utc(end, "end")
    if end_dt < start_dt:
        raise CalendarError(f"end ({end}) is before start ({start}).")

    wanted = {c.strip().upper() for c in currencies} if currencies else None

    out = [
        e
        for e in events
        if start_dt <= _parse_utc(e.event_time, "event_time") <= end_dt
        and (wanted is None or e.currency.upper() in wanted)
        and importance_at_least(e.importance, min_importance)
    ]
    out.sort(key=lambda e: e.event_time)
    return out


class MockCalendarSource(CalendarSource):
    """Deterministic sample events positioned relative to now, so tests and
    local development have something realistic to filter without needing MT5.

    Tagged as mock by the MCP server exactly like market data is — see
    server.py `_source_tag`.
    """

    def _sample(self) -> list[CalendarEvent]:
        now = dt.datetime.now(dt.timezone.utc)

        def at(hours: float) -> str:
            return (now + dt.timedelta(hours=hours)).isoformat()

        return [
            CalendarEvent(
                event_time=at(-26),
                currency="USD",
                name="ISM Manufacturing PMI",
                importance="MEDIUM",
                actual=48.7,
                forecast=49.2,
                previous=49.0,
                event_id=840010,
            ),
            CalendarEvent(
                event_time=at(-2),
                currency="EUR",
                name="German Ifo Business Climate",
                importance="MEDIUM",
                actual=87.3,
                forecast=87.0,
                previous=86.8,
                event_id=276020,
            ),
            CalendarEvent(
                event_time=at(1.5),
                currency="USD",
                name="Non-Farm Employment Change",
                importance="HIGH",
                actual=None,
                forecast=185000.0,
                previous=203000.0,
                event_id=840030,
            ),
            CalendarEvent(
                event_time=at(3),
                currency="GBP",
                name="BoE Governor Speech",
                importance="HIGH",
                actual=None,
                forecast=None,
                previous=None,
                event_id=826040,
            ),
            CalendarEvent(
                event_time=at(20),
                currency="JPY",
                name="Tokyo Core CPI y/y",
                importance="LOW",
                actual=None,
                forecast=2.1,
                previous=2.2,
                event_id=392050,
            ),
            CalendarEvent(
                event_time=at(50),
                currency="EUR",
                name="ECB Main Refinancing Rate",
                importance="HIGH",
                actual=None,
                forecast=3.25,
                previous=3.25,
                event_id=276060,
            ),
        ]

    def get_events(
        self,
        start: str,
        end: str,
        currencies: list[str] | None = None,
        min_importance: Importance = "NONE",
    ) -> list[CalendarEvent]:
        return _filter(self._sample(), start, end, currencies, min_importance)


class CsvCalendarSource(CalendarSource):
    """Reads the CSV written by mql5/CalendarExporter.mq5.

    The exporter rewrites the file atomically (temp file + rename), so a read
    here always sees a complete snapshot rather than a partial write.
    """

    # Beyond this, the EA has almost certainly stopped running and the file is
    # a stale snapshot. Silently serving day-old "upcoming events" is the worst
    # failure mode for anything that later gates trading on them.
    DEFAULT_MAX_AGE_MINUTES = 60

    def __init__(self, csv_path: str, max_age_minutes: int | None = None) -> None:
        self.csv_path = csv_path
        self.max_age_minutes = (
            self.DEFAULT_MAX_AGE_MINUTES if max_age_minutes is None else max_age_minutes
        )

    def _read(self) -> list[CalendarEvent]:
        # Distinguish "you haven't configured this" from "the exporter isn't
        # running" — they have completely different fixes.
        if not self.csv_path:
            raise CalendarError(
                "MT5_CALENDAR_CSV is not set, so the calendar export can't be located. "
                "Copy the path from MT5 (File -> Open Data Folder, then "
                "MQL5\\Files\\calendar.csv) into .env. See docs/CALENDAR.md."
            )
        if not os.path.exists(self.csv_path):
            raise CalendarError(
                f"Calendar CSV not found at {self.csv_path}. "
                "Is CalendarExporter.mq5 attached to a chart in the MT5 terminal? "
                "See docs/CALENDAR.md."
            )

        age_minutes = (
            dt.datetime.now(dt.timezone.utc).timestamp() - os.path.getmtime(self.csv_path)
        ) / 60
        if self.max_age_minutes > 0 and age_minutes > self.max_age_minutes:
            raise CalendarError(
                f"Calendar CSV at {self.csv_path} is {age_minutes:.0f} minutes old "
                f"(limit {self.max_age_minutes}). The exporter EA has probably stopped. "
                "Refusing to serve stale calendar data."
            )

        events: list[CalendarEvent] = []
        with open(self.csv_path, newline="", encoding="utf-8", errors="replace") as fh:
            for row_num, row in enumerate(csv.DictReader(fh), start=2):
                try:
                    events.append(
                        CalendarEvent(
                            event_time=_parse_utc(
                                row["event_time_utc"], "event_time_utc"
                            ).isoformat(),
                            currency=(row["currency"] or "").strip(),
                            name=(row["event_name"] or "").strip(),
                            importance=(row["importance"] or "NONE").strip().upper(),  # type: ignore[arg-type]
                            actual=_opt_float(row.get("actual")),
                            forecast=_opt_float(row.get("forecast")),
                            previous=_opt_float(row.get("previous")),
                            event_id=int(row["event_id"]),
                        )
                    )
                except (KeyError, ValueError, TypeError, CalendarError) as e:
                    raise CalendarError(
                        f"Malformed calendar row {row_num} in {self.csv_path}: {e}. "
                        "Delete the file and let the exporter rewrite it."
                    ) from e
        return events

    def get_events(
        self,
        start: str,
        end: str,
        currencies: list[str] | None = None,
        min_importance: Importance = "NONE",
    ) -> list[CalendarEvent]:
        return _filter(self._read(), start, end, currencies, min_importance)


def _opt_float(value: str | None) -> float | None:
    """Empty means 'not released yet' / 'no value', which is different from 0.0 —
    a forecast of 0.0 is a real forecast."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return float(value)


def default_csv_path() -> str:
    """Path to the exporter's CSV, from MT5_CALENDAR_CSV.

    There is deliberately no fallback guess: the MQL5\\Files\\ path contains a
    per-installation hash, so any default would be wrong, and pointing the
    reader at a path that will never exist turns a config mistake into a
    confusing "is the EA running?" error.
    """
    return (os.getenv("MT5_CALENDAR_CSV") or "").strip()


def build_calendar_source(mode: str) -> CalendarSource:
    if mode == "mock":
        return MockCalendarSource()
    if mode == "real":
        return CsvCalendarSource(default_csv_path())
    raise ValueError(f"Unknown MT5_CLIENT_MODE: {mode!r} (expected 'mock' or 'real')")
