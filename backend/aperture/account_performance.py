"""Daily broker equity with explicit cash-flow convention, independent SPY inputs."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from . import calendar
from .broker import NY
from .domain import ZERO, ResearchError, decimal
from .metrics import windows

FLOW_TYPES = {"CSD", "CSW", "JNLC"}
SUPPORTED_INCOME = {
    "FILL",
    "DIV",
    "DIVFEE",
    "DIVNRA",
    "DIVCGL",
    "DIVCGS",
    "DIVROC",
    "DIVTXEX",
    "DIVFT",
    "FEE",
    "CFEE",
    "CGD",
    "INT",
    "INTNRA",
    "INTTW",
    "PTC",
    "PTR",
    "CIL",
    "SSP",
}


def build(
    raw: dict, activities: list[dict], dataset=None, latest=None, start=None
) -> dict:
    latest = latest or calendar.latest_complete()
    timestamps, equities = raw.get("timestamp", []), raw.get("equity", [])
    if len(timestamps) != len(equities):
        raise ResearchError("Broker equity-history arrays have different lengths.")
    flows = {}
    uncertain = []
    for a in activities:
        kind = a.get("activity_type")
        stamp = a.get("date") or a.get("transaction_time")
        if start and stamp and str(stamp)[:10] < str(start):
            continue
        if kind not in SUPPORTED_INCOME | FLOW_TYPES:
            uncertain.append(kind)
        if kind not in FLOW_TYPES:
            continue
        stamp = a.get("date") or a.get("transaction_time")
        if not stamp:
            raise ResearchError(
                "A cash-flow activity has no date. Account returns are unavailable."
            )
        day = str(stamp)[:10]
        amount = decimal(a.get("net_amount", "NaN"))
        if kind == "CSD" and amount < ZERO or kind == "CSW" and amount > ZERO:
            raise ResearchError(
                "A deposit/withdrawal sign is ambiguous. Account returns are unavailable."
            )
        flows[day] = flows.get(day, ZERO) + amount
    rows = {}
    for stamp, value in sorted(zip(timestamps, equities)):
        if value is None:
            continue
        day = datetime.fromtimestamp(stamp, UTC).astimezone(NY).date()
        if (
            day > latest
            or (start and day < start)
            or day not in calendar.sessions(day, day)
        ):
            continue
        eq = decimal(value)
        if eq <= ZERO and rows:
            raise ResearchError(
                "The funded account returned to zero/nonpositive equity. Review an account reset before starting a new reporting period."
            )
        if eq > ZERO:
            if str(day) in rows and rows[str(day)] != eq:
                raise ResearchError(
                    "Conflicting daily broker valuations cannot be silently replaced."
                )
            rows[str(day)] = eq
    days = sorted(rows)
    notes = [
        "Actual broker daily equity. Returns use end-of-day net external cash flows; intraday-flow timing is an approximation, not exact time-weighted performance.",
        "Paper fills and valuations are simulated by the broker; research backtests are separate.",
        "Alpaca paper does not credit dividends. SPY includes dividend entitlements; the comparison gap includes this simulator difference and is not pure strategy attribution.",
    ]
    if uncertain:
        return {
            "curve": [],
            "windows": {},
            "notes": notes
            + [
                "Unsupported account transfers/options activity prevents a trustworthy return calculation: "
                + ", ".join(sorted(set(uncertain)))
            ],
            "available": False,
        }
    if not days:
        return {
            "curve": [],
            "windows": {},
            "notes": notes
            + [
                "No completed funded session is available yet. Refresh after the first market close."
            ],
            "available": False,
        }
    curve = []
    unit = Decimal(100)
    spy = (
        {b.session: b for b in dataset.bars.get("SPY", ())}
        if dataset and "SPY" not in dataset.metadata.get("unavailable_symbols", {})
        else {}
    )
    reference_days = calendar.sessions(
        date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    )
    coverage = bool(spy) and all(d in spy for d in reference_days)
    references = {}
    if coverage:
        qty = ZERO
        pending = []
        for i, day in enumerate(reference_days):
            bar = spy[day]
            if i == 0:
                qty = Decimal(100) / bar.close
            else:
                qty *= bar.split
                if bar.dividend > ZERO:
                    pending.append((bar.pay_date, qty * bar.dividend))
                paid = sum((v for pay, v in pending if pay <= day), ZERO)
                pending = [(pay, v) for pay, v in pending if pay > day]
                qty += paid / bar.close
            references[str(day)] = qty * bar.close + sum((v for _, v in pending), ZERO)
    for i, d in enumerate(days):
        if i:
            previous = days[i - 1]
            between = sum((a for day, a in flows.items() if previous < day <= d), ZERO)
            growth = (rows[d] - between) / rows[previous]
            if growth <= ZERO:
                raise ResearchError(
                    "Cash flow or account reset makes the return path invalid. Start a new account tracking period."
                )
            unit *= growth
        reference = references.get(d)
        curve.append(
            {
                "session": d,
                "equity": str(unit),
                "account_equity": str(rows[d]),
                "net_external_flow": str(flows.get(d, ZERO)),
                "benchmark": str(reference) if reference is not None else None,
                "cash": "0",
                "receivable": "0",
            }
        )
    expected = calendar.sessions(
        datetime.fromisoformat(days[0]).date(), datetime.fromisoformat(days[-1]).date()
    )
    if len(expected) != len(days):
        notes.append(
            "Broker history has missing daily valuations; annualized statistics are suppressed."
        )
    if not coverage:
        notes.append(
            "SPY coverage is incomplete for this account interval. Update market data; comparison stays unavailable until dates match."
        )
    display = windows(curve)
    if len(expected) != len(days):
        for w in display.values():
            w["metrics"]["volatility"] = None
    return {
        "available": len(curve) > 1,
        "curve": curve,
        "windows": display,
        "notes": notes,
        "benchmark_model": "SPY raw daily close plus split/dividend entitlements; paid dividends reinvested at that session close, no hypothetical trading fees.",
        "start": days[0],
        "end": days[-1],
        "source": "Alpaca paper daily equity + paginated cash-flow activities",
        "flow_convention": "end_of_day_external_flows",
        "checked_at": datetime.now(UTC).isoformat(),
    }


def refresh(store, broker, dataset=None):
    at = datetime.now(UTC)
    # The API requires a number + duration unit, not an invented period=all.
    raw = broker.read(
        "/v2/account/portfolio/history",
        {"period": "1A", "timeframe": "1D", "extended_hours": "false"},
    )
    timestamps = raw.get("timestamp", [])
    earliest = (
        datetime.fromtimestamp(min(timestamps), UTC).date() if timestamps else at.date()
    )
    activities = broker.activities((earliest - timedelta(days=1)).isoformat())
    snap = store.preference("paper_snapshot", {})
    account_key = snap.get("account_key", "unbound")
    tracking_key = "paper_tracking_" + account_key
    tracking = store.preference(tracking_key)
    if not tracking:
        tracking = str(calendar.latest_complete(at))
        store.set_preference(tracking_key, tracking)
    archive_key = "paper_equity_archive_" + account_key
    archive = store.preference(archive_key, {"rows": {}, "activities": {}})
    for stamp, eq in zip(raw.get("timestamp", []), raw.get("equity", [])):
        day = datetime.fromtimestamp(stamp, UTC).astimezone(NY).date()
        if day >= date.fromisoformat(tracking):
            archive["rows"][str(day)] = {"timestamp": stamp, "equity": eq}
    for a in activities:
        if a.get("id"):
            archive["activities"][a["id"]] = {
                k: a[k]
                for k in (
                    "id",
                    "activity_type",
                    "date",
                    "transaction_time",
                    "net_amount",
                )
                if k in a
            }
    store.observe(
        "alpaca-paper",
        "daily-equity-and-activities",
        json.dumps({"history": raw, "activities": activities}, sort_keys=True).encode(),
    )
    store.set_preference(archive_key, archive)
    rows = [archive["rows"][d] for d in sorted(archive["rows"])]
    merged = {
        "timestamp": [r["timestamp"] for r in rows],
        "equity": [r["equity"] for r in rows],
    }
    result = build(
        merged,
        list(archive["activities"].values()),
        dataset,
        start=date.fromisoformat(tracking),
    )
    result["tracking_start"] = tracking
    result["notes"].append(
        "Reporting begins with the first tracked completed session ("
        + tracking
        + "). Earlier broker history is excluded. Daily observations accumulate locally; downloaded revisions retain a source archive."
    )
    return result
