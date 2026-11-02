"""Exchange sessions, including holidays, DST and early closes.

The calendar is loaded lazily: displaying saved results never constructs it.
"""

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache


@lru_cache(maxsize=1)
def calendar():
    import exchange_calendars

    return exchange_calendars.get_calendar("XNYS", start="1990-01-01", end="2040-12-31")


def sessions(start: date, end: date) -> list[date]:
    start = max(start, calendar().first_session.date())
    end = min(end, calendar().last_session.date())
    if start > end:
        return []
    return [
        timestamp.date()
        for timestamp in calendar().sessions_in_range(str(start), str(end))
    ]


def next_session(session: date) -> date:
    return calendar().next_session(str(session)).date()


def close_time(session: date) -> datetime:
    return calendar().session_close(str(session)).to_pydatetime()


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
