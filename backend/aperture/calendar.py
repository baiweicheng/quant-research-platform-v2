"""Exchange sessions, including holidays, DST and early closes.

The calendar is loaded lazily: displaying saved results never constructs it.
"""

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from bisect import bisect_left, bisect_right


@lru_cache(maxsize=1)
def calendar():
    import exchange_calendars

    return exchange_calendars.get_calendar("XNYS", start="1990-01-01", end="2040-12-31")


@lru_cache(maxsize=1)
def _session_dates(source):
    return tuple(timestamp.date() for timestamp in source.sessions)


def sessions(start: date, end: date) -> list[date]:
    days = _session_dates(calendar())
    # A fresh list preserves caller isolation; the immutable exchange calendar
    # is converted to dates once instead of invoking pandas for every signal.
    return list(days[bisect_left(days, start) : bisect_right(days, end)])


def next_session(session: date) -> date:
    return calendar().next_session(str(session)).date()


def close_time(session: date) -> datetime:
    return calendar().session_close(str(session)).to_pydatetime()


def open_time(session: date) -> datetime:
    return calendar().session_open(str(session)).to_pydatetime()


def available_time(session: date) -> datetime:
    # A conservative EOD publication convention, retained in every imported bar.
    return close_time(session) + timedelta(minutes=15)


def latest_complete(now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("A timezone-aware clock is required.")
    recent = sessions(now.date() - timedelta(days=14), now.date())
    return next(
        session for session in reversed(recent) if available_time(session) <= now
    )


def decision_sessions(days: list[date], frequency: str) -> set[date]:
    """Initial decision, then the last actual session in each calendar period."""
    if not days:
        return set()
    if frequency == "daily":
        return set(days)
    groups: dict[tuple[int, ...], date] = {}
    for day in days:
        key = day.isocalendar()[:2] if frequency == "weekly" else (day.year, day.month)
        groups[key] = day
    return {days[0], *groups.values()}


@lru_cache(maxsize=16)
def federal_bank_holidays(year: int) -> frozenset[date]:
    """Conservative funding calendar: federal holidays in addition to XNYS closes."""

    def nth(month, weekday, n):
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))

    fixed = []
    for y in (year - 1, year, year + 1):
        for month, day in ((1, 1), (6, 19), (7, 4), (11, 11), (12, 25)):
            d = date(y, month, day)
            fixed.append(
                d - timedelta(days=1)
                if d.weekday() == 5
                else d + timedelta(days=1)
                if d.weekday() == 6
                else d
            )
    memorial = date(year, 5, 31)
    memorial -= timedelta(days=memorial.weekday())
    return frozenset(
        [d for d in fixed if d.year == year]
        + [
            nth(1, 0, 3),
            nth(2, 0, 3),
            memorial,
            nth(9, 0, 1),
            nth(10, 0, 2),
            nth(11, 3, 4),
        ]
    )


def settlement_session(traded: date) -> date:
    """At least T+1, excluding exchange closes AND federal bank holidays.

    This can reserve cash longer than actual settlement, never deliberately
    early. Broker-specific restrictions remain authoritative.
    """
    day = next_session(traded)
    while day in federal_bank_holidays(day.year):
        day = next_session(day)
    return day
