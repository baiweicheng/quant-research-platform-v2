"""Versioned S&P rosters. Effective dates and observation times are distinct.

Public historical rosters are retrospective research evidence, not a certified
as-known archive. Never extrapolate either a current roster or a history tail.
"""

import csv
import hashlib
import io
import json
import re
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser

import httpx

from . import calendar
from .domain import Dataset, ResearchError
from .store import Store, now

CURRENT_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HISTORY_URL = "https://raw.githubusercontent.com/fja05680/sp500/master/S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv"
HISTORY_NOTE = "Retrospective public S&P 500 rosters: effective-date filtering is applied, but original announcement timestamps, historical security identities, delisted prices and sector histories are not certified. Not survivorship-safe."
MAX_SYMBOLS = 1500
MAX_BARS = 4_000_000


def symbols(values, *, allow_empty=False):
    result = sorted(set(s.strip().upper() for s in values if s.strip()))
    if (
        (not result and not allow_empty)
        or len(result) > MAX_SYMBOLS
        or any(not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", s) for s in result)
    ):
        raise ResearchError(
            f"Use up to {MAX_SYMBOLS:,} US stock symbols with letters, digits, dots or hyphens."
        )
    return result


class ConstituentTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.cell = None
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "table" and (self.depth or dict(attrs).get("id") == "constituents"):
            self.depth += 1
        if self.depth == 1:
            if tag == "tr":
                self.row = []
            elif tag in ("td", "th"):
                self.cell = []

    def handle_data(self, data):
        if self.depth == 1 and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.depth == 1:
            if tag in ("td", "th") and self.cell is not None:
                self.row.append("".join(self.cell).strip())
                self.cell = None
            elif tag == "tr" and self.row:
                self.rows.append(self.row)
        if tag == "table" and self.depth:
            self.depth -= 1


def parse_current(text):
    parser = ConstituentTable()
    parser.feed(text)
    rows = parser.rows
    if not rows or rows[0][:3] != ["Symbol", "Security", "GICS Sector"]:
        raise ResearchError(
            "S&P 500 source table changed. Existing membership is unchanged."
        )
    members = []
    for row in rows[1:]:
        if len(row) != 8 or not re.fullmatch(r"\d{1,10}", row[6]):
            raise ResearchError(
                "S&P 500 source contains an incomplete constituent record."
            )
        symbol = symbols([row[0]])[0]
        if not row[1] or not row[2] or symbol == "SPY":
            raise ResearchError("S&P 500 source contains an invalid constituent.")
        members.append(
            {
                "symbol": symbol,
                "name": row[1],
                "sector": row[2],
                "cik": row[6].zfill(10),
            }
        )
    if not 490 <= len(members) <= 520 or len({m["symbol"] for m in members}) != len(
        members
    ):
        raise ResearchError(
            "S&P 500 roster is incomplete or duplicated; expected roughly 500 securities, including share classes."
        )
    return sorted(members, key=lambda m: m["symbol"])


def parse_history(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    if reader.fieldnames != ["date", "tickers"]:
        raise ResearchError("Historical S&P 500 source format changed.")
    rosters = []
    try:
        for row in reader:
            if len(rosters) >= 15000 or None in row or not row.get("tickers"):
                raise ValueError("incomplete row")
            day = date.fromisoformat(row["date"])
            raw = row["tickers"].split(",")
            names = symbols(raw)
            if not 450 <= len(names) <= 550 or len(names) != len(raw) or "SPY" in names:
                raise ValueError("incomplete or duplicate roster")
            if (
                rosters and row["date"] <= rosters[-1]["effective"]
            ) or day > date.today():
                raise ValueError("unordered, duplicate or future date")
            rosters.append({"effective": str(day), "symbols": names})
    except (ValueError, TypeError, csv.Error) as error:
        raise ResearchError(f"Historical S&P 500 source is invalid: {error}.") from None
    if len(rosters) < 2:
        raise ResearchError("Historical membership needs at least two dated rosters.")
    return rosters


def summary(snapshot):
    if not snapshot:
        return None
    return {k: v for k, v in snapshot.items() if k not in ("rosters", "members")}


def refresh(store: Store, kind: str, client=None):
    if kind not in ("current", "historical"):
        raise ResearchError("Choose current or historical S&P 500 membership.")
    url = CURRENT_URL if kind == "current" else HISTORY_URL
    owned = client is None
    client = client or httpx.Client(timeout=45, follow_redirects=False)
    try:
        try:
            response = client.get(
                url,
                headers={
                    "User-Agent": "ApertureResearch/0.2 (local educational research)"
                },
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise ResearchError(
                "S&P 500 membership could not be refreshed. Existing snapshots are unchanged; no fallback roster was substituted."
            ) from None
        if len(response.content) > 16 * 1024 * 1024:
            raise ResearchError("Membership response exceeded the 16 MB limit.")
        captured = now()
        body = {
            "kind": kind,
            "captured_at": captured,
            "source": url,
            "source_digest": hashlib.sha256(response.content).hexdigest(),
            "knowledge_basis": "observed_current"
            if kind == "current"
            else "retrospective_effective_dates",
        }
        if kind == "current":
            members = parse_current(response.text)
            previous = store.membership(kind)
            old = {m["symbol"] for m in previous["members"]} if previous else set()
            names = {m["symbol"] for m in members}
            # Current-screen decisions occur now using the latest completed
            # price session. This is never permission for a historical test.
            effective = calendar.latest_complete(datetime.fromisoformat(captured))
            body.update(
                members=members,
                member_count=len(members),
                coverage_start=str(effective),
                coverage_end=str(effective),
                added=sorted(names - old) if previous else [],
                removed=sorted(old - names),
                initial=previous is None,
            )
        else:
            rosters = parse_history(response.text)
            body.update(
                rosters=rosters,
                member_count=len(rosters[-1]["symbols"]),
                coverage_start=rosters[0]["effective"],
                coverage_end=rosters[-1]["effective"],
                roster_count=len(rosters),
                limitation=HISTORY_NOTE,
            )
        body["id"] = hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()
        ).hexdigest()[:24]
        return store.save_membership(body, response.content)
    finally:
        if owned:
            client.close()


def fresh(store, kind):
    snapshot = store.membership(kind)
    if snapshot and datetime.now(timezone.utc) - datetime.fromisoformat(
        snapshot["captured_at"]
    ) < timedelta(hours=24):
        return snapshot
    return refresh(store, kind)


def historical_names(snapshot, day):
    if not snapshot["coverage_start"] <= str(day) <= snapshot["coverage_end"]:
        raise ResearchError(
            f"Historical S&P 500 membership covers {snapshot['coverage_start']} through {snapshot['coverage_end']}. Refresh membership or choose dates inside this range; the last roster is never extrapolated."
        )
    index = bisect_right([r["effective"] for r in snapshot["rosters"]], str(day)) - 1
    return set(snapshot["rosters"][index]["symbols"])


def resolve(store, payload, start, end):
    # Legacy internal paper requests deliberately retain their explicitly
    # approved, frozen list. Membership refresh cannot widen an approval.
    mode = payload.get("universe", "custom")
    extra = symbols(payload.get("symbols", []), allow_empty=mode != "custom")
    if mode == "custom":
        return sorted(set(extra) | {"SPY"}), None, {}
    if mode not in ("sp500_current", "sp500_historical"):
        raise ResearchError("Choose an S&P 500 universe or an explicit custom list.")
    kind = "historical" if mode == "sp500_historical" else "current"
    snapshot = fresh(store, kind)
    audit = {**snapshot, "mode": mode, "additional_symbols": extra}
    if kind == "historical":
        # Validate both boundaries before any stock downloads. Include the
        # roster in force at the start plus each in-range effective change.
        names = historical_names(snapshot, start) | historical_names(snapshot, end)
        for row in snapshot["rosters"]:
            if str(start) < row["effective"] <= str(end):
                names.update(row["symbols"])
        # Only the needed timeline travels with a price snapshot; the complete
        # original archive remains retrievable by its immutable membership ID.
        index = (
            bisect_right([r["effective"] for r in snapshot["rosters"]], str(start)) - 1
        )
        audit["rosters"] = [
            r for r in snapshot["rosters"][index:] if r["effective"] <= str(end)
        ]
        audit["coverage_start"], audit["coverage_end"] = str(start), str(end)
        sectors = {}
    else:
        names = {m["symbol"] for m in snapshot["members"]}
        sectors = {m["symbol"]: m["sector"] for m in snapshot["members"]}
    result = sorted(names | set(extra) | {"SPY"})
    if len(result) > MAX_SYMBOLS:
        raise ResearchError(
            "The union of historical members and extra symbols exceeds 1,500. Choose a shorter period."
        )
    return result, audit, sectors


def eligible(dataset: Dataset, decision: date):
    audit = dataset.metadata.get("membership")
    if not audit:
        return set(dataset.bars) - {"SPY"}
    if audit["kind"] == "current":
        if str(decision) < audit["coverage_start"]:
            raise ResearchError(
                "This snapshot contains today's S&P 500 members, not historical membership. Choose Historical S&P 500 members in Data for a historical backtest."
            )
        captured = datetime.fromisoformat(audit["captured_at"])
        if decision > (captured + timedelta(days=7)).date():
            raise ResearchError(
                "S&P 500 roster was not yet observed or is over seven days old at this decision. Refresh membership and download a new snapshot."
            )
        names = {m["symbol"] for m in audit["members"]}
    else:
        names = historical_names(audit, decision)
    # Extras are an explicitly retrospective supplement and remain labelled
    # as such; they never replace or remove the core roster.
    return (names | set(audit["additional_symbols"])) - {"SPY"}


def validate_coverage(dataset, start, end):
    audit = dataset.metadata.get("membership")
    if not audit:
        return
    if audit["kind"] == "current":
        raise ResearchError(
            "Current S&P 500 membership is for current reviews only. Historical backtests require Historical S&P 500 members; today's roster cannot be backdated."
        )
    historical_names(audit, start)
    historical_names(audit, end)
    by_day = {s: {b.session for b in bars} for s, bars in dataset.bars.items()}
    for day in calendar.sessions(start, end):
        missing = sorted(
            s for s in historical_names(audit, day) if day not in by_day.get(s, set())
        )
        if missing:
            raise ResearchError(
                f"Historical S&P 500 coverage is incomplete on {day}: {', '.join(missing[:12])}. Departed or missing members cannot be dropped from the backtest. Supply supported historical prices/identities before running."
            )
