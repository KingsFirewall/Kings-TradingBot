"""Unit tests for the economic calendar source.

These run anywhere — no MT5, no Windows, no CalendarExporter.mq5. They pin
the contract the CSV reader must satisfy so the news blackout rule in risk/
can be built and tested before real calendar data exists.
"""

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp"))

from calendar_source import (  # noqa: E402
    CalendarError,
    CsvCalendarSource,
    MockCalendarSource,
    importance_at_least,
)

WIDE_START = "2000-01-01T00:00:00Z"
WIDE_END = "2100-01-01T00:00:00Z"


def _iso(hours_from_now: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours_from_now)).isoformat()


# --- importance ordering ---------------------------------------------------


def test_importance_ordering():
    assert importance_at_least("HIGH", "LOW")
    assert importance_at_least("HIGH", "HIGH")
    assert not importance_at_least("LOW", "HIGH")
    assert importance_at_least("NONE", "NONE")


def test_unknown_importance_is_rejected():
    with pytest.raises(CalendarError):
        importance_at_least("CRITICAL", "LOW")


# --- mock source -----------------------------------------------------------


def test_mock_returns_events_sorted_chronologically():
    events = MockCalendarSource().get_events(WIDE_START, WIDE_END)
    assert events, "mock should produce sample events"
    times = [e.event_time for e in events]
    assert times == sorted(times), "events must be chronological"


def test_min_importance_filters_out_weaker_events():
    src = MockCalendarSource()
    high = src.get_events(WIDE_START, WIDE_END, min_importance="HIGH")
    assert high, "sample data should contain HIGH impact events"
    assert all(e.importance == "HIGH" for e in high)
    assert len(high) < len(src.get_events(WIDE_START, WIDE_END))


def test_currency_filter_is_case_insensitive():
    src = MockCalendarSource()
    lower = src.get_events(WIDE_START, WIDE_END, currencies=["usd"])
    upper = src.get_events(WIDE_START, WIDE_END, currencies=["USD"])
    assert lower and [e.event_id for e in lower] == [e.event_id for e in upper]
    assert all(e.currency == "USD" for e in lower)


def test_window_excludes_events_outside_range():
    src = MockCalendarSource()
    # Sample data spans roughly -26h to +50h; this window should clip both ends.
    windowed = src.get_events(_iso(0), _iso(4))
    assert windowed, "expected at least one event in the next 4 hours"
    assert len(windowed) < len(src.get_events(WIDE_START, WIDE_END))


def test_unreleased_events_have_null_actual():
    """`actual` must be None, not 0.0 — a released value of zero is real data
    and the risk engine has to tell the two apart."""
    upcoming = MockCalendarSource().get_events(_iso(0.5), WIDE_END)
    assert upcoming
    assert all(e.actual is None for e in upcoming)


def test_end_before_start_is_rejected():
    with pytest.raises(CalendarError):
        MockCalendarSource().get_events(_iso(5), _iso(1))


def test_naive_datetimes_are_treated_as_utc():
    """A naive timestamp must not be silently shifted by the host's local
    offset — that would move a blackout window by hours."""
    src = MockCalendarSource()
    naive = src.get_events("2000-01-01T00:00:00", "2100-01-01T00:00:00")
    aware = src.get_events(WIDE_START, WIDE_END)
    assert [e.event_id for e in naive] == [e.event_id for e in aware]


# --- CSV source ------------------------------------------------------------

HEADER = (
    "event_time_utc,currency,event_name,importance,"
    "actual,forecast,previous,revised_previous,event_id,value_id\n"
)


def _write_csv(tmp_path: Path, rows: str, name: str = "calendar.csv") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_csv_parses_quoted_names_containing_commas(tmp_path):
    """Event names like 'Non-Farm Employment Change, s.a.' contain commas;
    if quoting breaks, every following column silently shifts."""
    rows = (
        f'{_iso(2)},"USD","Non-Farm Employment Change, s.a.",HIGH,'
        ",185000.000000,203000.000000,,840030,1\n"
    )
    src = CsvCalendarSource(str(_write_csv(tmp_path, rows)))
    events = src.get_events(WIDE_START, WIDE_END)
    assert len(events) == 1
    assert events[0].name == "Non-Farm Employment Change, s.a."
    assert events[0].importance == "HIGH"
    assert events[0].forecast == 185000.0
    assert events[0].actual is None


def test_csv_missing_file_raises_actionable_error(tmp_path):
    src = CsvCalendarSource(str(tmp_path / "nope.csv"))
    with pytest.raises(CalendarError, match="CalendarExporter"):
        src.get_events(WIDE_START, WIDE_END)


def test_unconfigured_path_says_so_rather_than_blaming_the_exporter():
    """An unset MT5_CALENDAR_CSV and a dead exporter need different fixes,
    so they must not produce the same message."""
    with pytest.raises(CalendarError, match="MT5_CALENDAR_CSV is not set"):
        CsvCalendarSource("").get_events(WIDE_START, WIDE_END)


def test_csv_stale_file_is_refused(tmp_path):
    """Serving day-old data as 'upcoming events' is worse than serving none."""
    import os

    path = _write_csv(tmp_path, f'{_iso(2)},"USD","CPI m/m",HIGH,,0.3,0.2,,840099,2\n')
    old = dt.datetime.now(dt.timezone.utc).timestamp() - (6 * 3600)
    os.utime(path, (old, old))

    with pytest.raises(CalendarError, match="stale"):
        CsvCalendarSource(str(path), max_age_minutes=60).get_events(WIDE_START, WIDE_END)

    # Disabling the check is possible, for offline analysis of an old export.
    assert CsvCalendarSource(str(path), max_age_minutes=0).get_events(WIDE_START, WIDE_END)


def test_csv_malformed_row_raises_rather_than_silently_dropping(tmp_path):
    rows = f'{_iso(2)},"USD","Good Event",HIGH,,0.3,0.2,,840099,2\n' 'not-a-date,"EUR","Bad",HIGH,,,,,1,2\n'
    src = CsvCalendarSource(str(_write_csv(tmp_path, rows)))
    with pytest.raises(CalendarError, match="Malformed calendar row"):
        src.get_events(WIDE_START, WIDE_END)


def test_csv_empty_export_is_valid(tmp_path):
    """A quiet window legitimately has no events; that is not an error."""
    src = CsvCalendarSource(str(_write_csv(tmp_path, "")))
    assert src.get_events(WIDE_START, WIDE_END) == []


# --- MCP tool --------------------------------------------------------------


def test_calendar_tool_tags_source_and_timestamp():
    """Same anti-hallucination guarantee the market-data tools carry."""
    import importlib
    import os

    os.environ["MT5_CLIENT_MODE"] = "mock"
    import server

    importlib.reload(server)

    result = server.get_calendar_events(WIDE_START, WIDE_END, min_importance="HIGH")
    assert "source" in result and "timestamp" in result
    assert "MOCK" in result["source"]
    assert result["events"] and all(e["importance"] == "HIGH" for e in result["events"])
