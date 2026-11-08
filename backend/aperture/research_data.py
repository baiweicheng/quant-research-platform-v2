"""Dated research inputs, separate economic returns from payment-date cash."""

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from . import calendar, membership
from .domain import Bar, Dataset, ResearchError, ZERO, decimal
from .store import now
from .research_overrides import ALIASES, CONFLICTS
from .action_evidence import (
    verified_continuation,
    supplement_splits,
    VERSION as ACTION_EVIDENCE_VERSION,
)

VERSION = "dated-research-inputs-v2-reviewed-actions"


def input_issues(dataset):
    """Validation derived from captured evidence; never certify quote aliases alone.

    Recovering original-ticker prices does not establish that the action query
    under the later ticker covered all of the original security's distributions.
    """
    issues = list(dataset.metadata.get("input_issues", []))
    for symbol, identity in dataset.metadata.get("identity_resolution", {}).items():
        alias = identity.get("reviewed_alias") if isinstance(identity, dict) else None
        if alias and not identity.get("original_actions_reconciled"):
            issues.append(
                {
                    "symbol": symbol,
                    "start": dataset.metadata.get("download", {}).get(
                        "start", "2016-01-04"
                    ),
                    "end": str(
                        calendar.next_session(date.fromisoformat(alias["until"]))
                    ),
                    "kind": "action",
                    "reason": "Original-ticker prices were recovered, but corporate actions across that ticker transition are not fully reconciled. "
                    + alias["source"],
                }
            )
    for event in dataset.metadata.get("corporate_actions", []):
        if event.get("unpriced_consideration"):
            continue
        cash, ratio = decimal(event.get("cash", 0)), decimal(event.get("ratio", 0))
        if (
            cash < ZERO
            or (event["kind"] == "cash_mergers" and cash <= ZERO)
            or (
                event["kind"] in ("stock_mergers", "stock_and_cash_mergers")
                and (not event.get("target") or ratio <= ZERO)
            )
        ):
            issues.append(
                {
                    "symbol": event["source"],
                    "start": event["effective"],
                    "end": event["effective"],
                    "kind": "action",
                    "reason": "Merger consideration lacks a verified recipient/ratio or cash amount; zero recovery is not assumed.",
                }
            )
    return issues


def indexed_issues(dataset):
    if "input_issues" not in dataset.metadata:
        return None
    index = defaultdict(list)
    for issue in input_issues(dataset):
        index[issue["symbol"]].append(issue)
    return index


def blocked_inputs(dataset, names, start, end, mode="ex_date", *, issue_index=None):
    if "input_issues" not in dataset.metadata:
        return set(names) & dataset.metadata.get("unavailable_symbols", {}).keys()
    issues = (
        (issue for symbol in names for issue in issue_index.get(symbol, ()))
        if issue_index is not None
        else input_issues(dataset)
    )
    return {
        issue["symbol"]
        for issue in issues
        if issue["symbol"] in names
        and issue.get("start", "0001-01-01") <= str(end)
        and issue.get("end", "9999-12-31") >= str(start)
        and not (issue["kind"] == "cash_payment" and mode != "pay_date")
    }


def security_events(portfolio, day, events, bars, model):
    """Verified contractual merger consideration; never invent a terminal price."""
    for event in events:
        if event["effective"] != str(day) or event["kind"] not in (
            "cash_mergers",
            "stock_mergers",
            "stock_and_cash_mergers",
        ):
            continue
        symbol = event["source"]
        quantity = portfolio.positions.get(symbol, ZERO)
        if not quantity:
            continue
        if event.get("unpriced_consideration"):
            raise ResearchError(
                f"{symbol} merger includes unlisted contingent rights ({event['unpriced_consideration']}) without a verified market value. This held position cannot be valued as cash-only."
            )
        cash = decimal(event.get("cash", 0))
        ratio = decimal(event.get("ratio", 0))
        if (
            cash < ZERO
            or (event["kind"] == "cash_mergers" and cash <= ZERO)
            or (
                event["kind"] in ("stock_mergers", "stock_and_cash_mergers")
                and (not event.get("target") or ratio <= ZERO)
            )
        ):
            raise ResearchError(
                f"{symbol}: merger consideration is incomplete or invalid on {day}. A held position cannot be removed at an assumed zero recovery."
            )
        portfolio.positions.pop(symbol)
        if event.get("target"):
            if event["target"] not in bars:
                raise ResearchError(
                    f"Missing merger consideration price: {event['target']} on {day}."
                )
            portfolio.positions[event["target"]] = portfolio.positions.get(
                event["target"], ZERO
            ) + quantity * decimal(event["ratio"])
        if decimal(event.get("cash", "0")):
            pay = event.get("pay_date")
            if model == "pay_date" and (not pay or pay < str(day)):
                raise ResearchError(
                    f"{symbol}: verified merger cash settlement date is unavailable on {day}. Use total-return research or another period."
                )
            pay = max(pay or str(day), str(day))
            portfolio.receivables.append(
                (date.fromisoformat(pay), quantity * decimal(event["cash"]))
            )


def _parse_pages(pages, symbols, first, last):
    output = {symbol: {} for symbol in symbols}
    for page in pages:
        for symbol, rows in page.get("bars", {}).items():
            if symbol not in output:
                raise ResearchError("Unexpected symbol in dated research prices.")
            for row in rows:
                day = (
                    datetime.fromisoformat(row["t"].replace("Z", "+00:00"))
                    .astimezone(ZoneInfo("America/New_York"))
                    .date()
                )
                if not first <= day <= last:
                    continue
                if day in output[symbol]:
                    raise ResearchError(
                        f"Duplicate research price for {symbol} on {day}."
                    )
                volume = decimal(row["v"])
                if volume != volume.to_integral_value():
                    raise ResearchError(
                        f"Fractional source volume for {symbol} on {day}."
                    )
                output[symbol][day] = Bar(
                    symbol,
                    day,
                    *(decimal(row[k]) for k in ("o", "h", "l", "c")),
                    int(volume),
                    available_at=calendar.available_time(day),
                )
    return output


def download(store, payload, progress, provider=None, base=None):
    """Acquire raw prices with dated symbol mapping and complete event evidence."""
    from .providers import Provider, batch_pages
    from .config import PAPER_URL

    api = provider or Provider(store)
    first, last = (
        date.fromisoformat(payload["start"]),
        date.fromisoformat(payload["end"]),
    )
    if first < date(2016, 1, 4) or last > calendar.latest_complete() or first >= last:
        raise ResearchError("Choose a completed-session interval from 2016 onward.")
    try:
        names, audit, sectors = membership.resolve(store, payload, first, last)
        progress(3, "Reading dated identities and corporate-action evidence")
        action_pages = batch_pages(
            api,
            "/v1/corporate-actions",
            {
                "symbols": ",".join(names),
                "start": str(first - timedelta(days=90)),
                "end": str(last + timedelta(days=90)),
                "limit": 1000,
                "data_quality": "all",
            },
            "corporate_actions",
        )
        events = {}
        for page in action_pages:
            for kind, items in page.get("corporate_actions", {}).items():
                for item in items:
                    key = item.get("id")
                    if not key:
                        raise ResearchError(
                            "Corporate action is missing its source identifier."
                        )
                    item = {"kind": kind, **item}
                    if key in events and events[key] != item:
                        raise ResearchError(
                            "Conflicting corporate-action records; no snapshot was published."
                        )
                    events[key] = item
        active = api.get(
            "alpaca",
            PAPER_URL + "/v2/assets",
            {"status": "active", "asset_class": "us_equity"},
            ttl=86400,
        )
        if not isinstance(active, list):
            raise ResearchError("The listing directory changed format.")
        inactive = api.get(
            "alpaca",
            PAPER_URL + "/v2/assets",
            {"status": "inactive", "asset_class": "us_equity"},
            ttl=86400,
        )
        if not isinstance(inactive, list):
            raise ResearchError("The archived listing directory changed format.")
        if any(
            not isinstance(a, dict)
            or not isinstance(a.get("symbol"), str)
            or not isinstance(a.get("id"), str)
            for a in active + inactive
        ):
            raise ResearchError(
                "The listing directory is incomplete or changed format; no snapshot was published."
            )
        listing_candidates = defaultdict(dict)
        for asset in active + inactive:
            listing_candidates[asset["symbol"]][asset.get("id", asset["symbol"])] = (
                asset
            )
        active_names = {a["symbol"] for a in active}
        # A symbol may later be reused by an unrelated issuer. Only connect a
        # rename near the indexed lifetime of that symbol, and follow links in
        # chronological order (e.g. FB -> META must not enter the older META ETF).
        original_history = (
            (audit or {}).get("historical")
            if (audit or {}).get("kind") == "combined"
            else (audit if (audit or {}).get("kind") == "historical" else None)
        )
        original_last = {}
        if original_history:
            for i, roster in enumerate(original_history["rosters"]):
                until = (
                    min(
                        last,
                        date.fromisoformat(
                            original_history["rosters"][i + 1]["effective"]
                        )
                        - timedelta(days=1),
                    )
                    if i + 1 < len(original_history["rosters"])
                    else last
                )
                for name in roster["symbols"]:
                    original_last[name] = until
        renames = sorted(
            [
                e
                for e in events.values()
                if e["kind"] == "name_changes"
                and e.get("old_cusip")
                and e.get("old_cusip") == e.get("new_cusip")
                and (
                    not original_history
                    or e["old_symbol"] not in original_last
                    or date.fromisoformat(e["process_date"])
                    <= original_last[e["old_symbol"]] + timedelta(days=7)
                )
            ],
            key=lambda e: e["process_date"],
        )

        def canonical(symbol, day):
            if symbol in ("DOW", "DD") and str(day) < "2017-09-01":
                return symbol + ".OLD"
            seen = set()
            after = str(day)
            for _ in range(20):
                link = next(
                    (
                        e
                        for e in renames
                        if e["old_symbol"] == symbol and e["process_date"] >= after
                    ),
                    None,
                )
                if not link:
                    return symbol
                if symbol in seen:
                    raise ResearchError("Cyclic historical ticker mapping.")
                seen.add(symbol)
                symbol = link["new_symbol"]
                after = link["process_date"]
            raise ResearchError("Historical ticker chain is too long.")

        if audit:
            audit = json.loads(json.dumps(audit))
            history = (
                audit.get("historical")
                if audit["kind"] == "combined"
                else (audit if audit["kind"] == "historical" else None)
            )
            if history:
                original_id = history.get("id")
                history["rosters"] = [
                    {
                        **r,
                        "symbols": sorted(
                            {canonical(s, r["effective"]) for s in r["symbols"]}
                        ),
                    }
                    for r in history["rosters"]
                ]
                history["identity_basis"] = {
                    "contract": VERSION,
                    "original_membership_id": original_id,
                    "same_cusip_name_changes": renames,
                }
            audit["additional_symbols"] = sorted(
                {canonical(s, last) for s in audit["additional_symbols"]}
            )
        else:
            history = None
        core_current = {
            m["symbol"] for m in (audit or {}).get("current", {}).get("members", [])
        }
        if audit and audit["kind"] == "current":
            core_current = {m["symbol"] for m in audit["members"]}
        renamed = {canonical(s, last) for s in names}
        if history:
            renamed = (
                {s for r in history["rosters"] for s in r["symbols"]}
                | core_current
                | set(audit["additional_symbols"])
                | {"SPY"}
            )
        names = membership.symbols(renamed)
        last_membership = {}
        first_membership = {}
        if history:
            for index, roster in enumerate(history["rosters"]):
                until = (
                    min(
                        last,
                        date.fromisoformat(history["rosters"][index + 1]["effective"])
                        - timedelta(days=1),
                    )
                    if index + 1 < len(history["rosters"])
                    else last
                )
                days = calendar.sessions(
                    max(first, date.fromisoformat(roster["effective"])), until
                )
                if days:
                    for symbol in roster["symbols"]:
                        first_membership.setdefault(symbol, days[0])
                        last_membership[symbol] = days[-1]
        primary_symbols = set(names)
        custom_symbols = list(names) if not audit else None
        normalized_events = []
        dependencies = set()
        spin_events = []
        issues = []

        def issue(symbol, day, reason, kind="action", end=None):
            issues.append(
                {
                    "symbol": symbol,
                    "start": str(day),
                    "end": str(end or day),
                    "kind": kind,
                    "reason": reason,
                }
            )

        for symbol in names:
            rows = list(listing_candidates[symbol].values())
            if not rows:
                issue(
                    symbol,
                    first,
                    "Historical listing identity is unavailable in the captured directory; a raw-symbol fallback is not issuer verification.",
                    "identity",
                    last,
                )
            elif len(rows) > 1 and symbol != "IR":
                issue(
                    symbol,
                    first,
                    "Multiple historical listing identities require dated issuer/share-basis verification.",
                    "identity",
                    last,
                )
            elif any(
                r.get("class") != "us_equity"
                or r.get("exchange")
                not in ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "NYSEARCA")
                for r in rows
            ):
                issue(
                    symbol,
                    first,
                    "A supported US exchange listing identity could not be verified for this historical interval.",
                    "identity",
                    last,
                )
            elif symbol != "SPY" and any(
                re.search(r"\b(ETF|ETN|Fund|iShares|SPDR)\b", r.get("name", ""), re.I)
                for r in rows
            ):
                issue(
                    symbol,
                    first,
                    "The listing directory identifies a fund; historical ordinary-company identity requires verification.",
                    "identity",
                    last,
                )
        for event in events.values():
            kind = event["kind"]
            effective = (
                event.get("ex_date")
                or event.get("effective_date")
                or event.get("process_date")
            )
            if not effective:
                raise ResearchError("Corporate action has no dated effect.")
            day = date.fromisoformat(effective)
            symbol = (
                event.get("symbol")
                or event.get("source_symbol")
                or event.get("acquiree_symbol")
                or event.get("old_symbol")
            )
            if not symbol or not first <= day <= last or kind == "name_changes":
                continue
            symbol = canonical(symbol, day)
            if symbol not in names:
                continue
            record = {
                "id": event["id"],
                "kind": kind,
                "effective": str(day),
                "source": symbol,
                "pay_date": event.get("payable_date"),
                "source_record": event,
            }
            reviewed = verified_continuation(event, api)
            if reviewed and symbol == reviewed["symbol"]:
                normalized_events.append(
                    {
                        **record,
                        "kind": "identity_continuations",
                        "target": symbol,
                        "ratio": "1",
                        "cash": "0",
                        "reviewed_evidence": reviewed,
                    }
                )
                continue
            if kind in ("cash_mergers", "stock_mergers", "stock_and_cash_mergers"):
                target = (
                    event.get("acquirer_symbol") if kind != "cash_mergers" else None
                )
                if target:
                    target = canonical(target, day)
                    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", target):
                        dependencies.add(target)
                    else:
                        record["unpriced_consideration"] = target
                        issue(
                            symbol,
                            day,
                            f"Merger has unlisted contingent consideration: {target}.",
                        )
                        target = None
                record.update(
                    target=target,
                    ratio=str(
                        decimal(event.get("acquirer_rate", 0))
                        / decimal(event.get("acquiree_rate", 1))
                    ),
                    cash=str(
                        event.get("cash_rate", event.get("rate", 0))
                        if kind != "stock_mergers"
                        else 0
                    ),
                )
                if target == symbol and event.get("acquiree_symbol") != event.get(
                    "acquirer_symbol"
                ):
                    issue(
                        symbol,
                        day,
                        "A renamed predecessor has merger consideration requiring a separate verified price/share basis.",
                    )
                if decimal(record["cash"]) and (
                    not record["pay_date"] or record["pay_date"] < str(day)
                ):
                    issue(
                        symbol,
                        day,
                        "Merger cash payment date is unavailable.",
                        "cash_payment",
                    )
                normalized_events.append(record)
            elif kind == "spin_offs":
                child = event.get("new_symbol", "").removesuffix(".WI")
                if not child or decimal(event.get("source_rate", 0)) <= 0:
                    issue(symbol, day, "Spin-off allocation terms are incomplete.")
                    continue
                child = canonical(child, day)
                dependencies.add(child)
                record.update(
                    target=child,
                    ratio=str(
                        decimal(event["new_rate"]) / decimal(event["source_rate"])
                    ),
                )
                spin_events.append(record)
                issue(
                    symbol,
                    day,
                    "Spin-off cash-flow/share-delivery model is not supported in strict payment-date simulation.",
                    "cash_payment",
                )
            elif kind not in (
                "cash_dividends",
                "forward_splits",
                "reverse_splits",
                "stock_dividends",
            ):
                issue(symbol, day, f"Unsupported {kind.replace('_', ' ')}.")
        names = membership.symbols(
            set(names) | dependencies | (set(base.bars) if base else set())
        )
        overlap = (
            max(
                first,
                date.fromisoformat(base.metadata["download"]["end"])
                - timedelta(days=10),
            )
            if base
            else first
        )
        prior_sessions = calendar.sessions(first, overlap - timedelta(days=1))
        query_start = prior_sessions[-1] if prior_sessions else overlap
        if len(names) * len(calendar.sessions(first, last)) > membership.MAX_BARS:
            raise ResearchError("Research acquisition exceeds the 4,000,000-bar limit.")
        groups = defaultdict(list)
        identity = {}
        for symbol in names:
            asof = (
                last
                if symbol in core_current
                or symbol in active_names
                or symbol not in last_membership
                else last_membership[symbol]
            )
            # A formerly indexed ticker with a current unrelated listing must
            # use its indexed vintage, rather than today's symbol mapping.
            if (
                symbol in last_membership
                and symbol not in core_current
                and symbol not in dependencies
            ):
                asof = last_membership[symbol]
            if symbol in ("DOW.OLD", "DD.OLD"):
                asof = date(2017, 8, 31)
            if base and symbol in base.metadata.get("identity_resolution", {}):
                old_identity = base.metadata["identity_resolution"][symbol]
                old_id = old_identity.get("listing_id")
                current_id = next(
                    (a.get("id") for a in active if a["symbol"] == symbol), None
                )
                if old_id and current_id and old_id != current_id:
                    raise ResearchError(
                        f"{symbol}: listing identity changed. Run a full historical identity review before combining prices."
                    )
            begin = query_start if base and symbol in base.bars else first
            groups[(str(asof), str(begin))].append(symbol)
            identity[symbol] = {
                # Historical quotes outside the overlap stay frozen, together
                # with their original-ticker evidence and unresolved action
                # gates. A recent refresh cannot certify that older history.
                **(
                    base.metadata.get("identity_resolution", {}).get(symbol, {})
                    if base and symbol in base.bars
                    else {}
                ),
                "asof": str(asof),
                "candidate_ids": sorted(listing_candidates[symbol]),
                "listing_id": next(
                    (a.get("id") for a in active if a["symbol"] == symbol), None
                ),
                "basis": "Provider dated symbol mapping; permanent historical security identities are not certified",
            }
        bars, adjusted = {}, {}
        acquisition = []
        for index, ((asof, begin), stocks) in enumerate(sorted(groups.items())):
            progress(
                8 + round(index / max(1, len(groups)) * 50),
                f"Downloading dated prices: {len(stocks)} symbols as of {asof}",
            )
            quote_names = {s: s.removesuffix(".OLD") for s in stocks}
            query = {
                "symbols": ",".join(quote_names.values()),
                "timeframe": "1Day",
                "start": begin,
                "end": calendar.close_time(last).isoformat(),
                "feed": "sip",
                "currency": "USD",
                "limit": 10000,
                "sort": "asc",
                "asof": asof,
            }
            raw_pages = batch_pages(
                api, "/v2/stocks/bars", {**query, "adjustment": "raw"}, "bars"
            )
            split_pages = batch_pages(
                api, "/v2/stocks/bars", {**query, "adjustment": "split"}, "bars"
            )
            raw_rows = _parse_pages(
                raw_pages, quote_names.values(), date.fromisoformat(begin), last
            )
            adj_rows = _parse_pages(
                split_pages, quote_names.values(), date.fromisoformat(begin), last
            )
            for symbol, quote_name in quote_names.items():
                bars[symbol] = {
                    d: replace(b, symbol=symbol)
                    for d, b in raw_rows[quote_name].items()
                    if not symbol.endswith(".OLD") or d < date(2017, 9, 1)
                }
                adjusted[symbol] = {
                    d: replace(b, symbol=symbol)
                    for d, b in adj_rows[quote_name].items()
                    if not symbol.endswith(".OLD") or d < date(2017, 9, 1)
                }
            acquisition.append(
                {
                    "query": query,
                    "raw_digest": store.capture_source(
                        json.dumps(raw_pages, sort_keys=True).encode()
                    ),
                    "split_digest": store.capture_source(
                        json.dumps(split_pages, sort_keys=True).encode()
                    ),
                }
            )
        # The retrospective roster sometimes uses a later ticker before its
        # first trade. Recover the original traded label from reviewed evidence.
        for alias in ALIASES:
            symbol, quote_name = alias["symbol"], alias["quote"]
            until = min(last, date.fromisoformat(alias["until"]))
            alias_first = query_start if base and symbol in base.bars else first
            if symbol not in bars or until < alias_first:
                continue
            query = {
                "symbols": quote_name,
                "asof": alias["until"],
                "start": str(alias_first),
                "end": calendar.close_time(until).isoformat(),
                "timeframe": "1Day",
                "feed": "sip",
                "currency": "USD",
                "limit": 10000,
                "sort": "asc",
            }
            for adjustment, dest in (("raw", bars), ("split", adjusted)):
                pages = batch_pages(
                    api, "/v2/stocks/bars", {**query, "adjustment": adjustment}, "bars"
                )
                rows = _parse_pages(pages, [quote_name], alias_first, until)[quote_name]
                dest[symbol] = {d: b for d, b in dest[symbol].items() if d > until}
                dest[symbol].update(
                    {d: replace(b, symbol=symbol) for d, b in rows.items()}
                )
                acquisition.append(
                    {
                        "alias": alias,
                        "adjustment": adjustment,
                        "digest": store.capture_source(
                            json.dumps(pages, sort_keys=True).encode()
                        ),
                    }
                )
            identity[symbol]["reviewed_alias"] = alias
        # New Ingersoll Rand (formerly GDI) is a different equity from the
        # old IR parent, which became TT. Do not use the old equity as warm-up.
        if "IR" in bars and any(
            e["old_symbol"] == "IR" and e["new_symbol"] == "TT" for e in renames
        ):
            bars["IR"] = {d: b for d, b in bars["IR"].items() if d >= date(2020, 3, 2)}
        foreign_names = {
            canonical(e["symbol"], e.get("ex_date") or e["process_date"])
            for e in events.values()
            if e["kind"] == "cash_dividends"
            and e.get("foreign")
            and not e.get("currency")
        }
        dividend_adjusted = {}
        for (asof, begin), stocks in sorted(groups.items()):
            chosen = sorted(set(stocks) & foreign_names)
            if not chosen:
                continue
            query = {
                "symbols": ",".join(chosen),
                "asof": asof,
                "start": begin,
                "end": calendar.close_time(last).isoformat(),
                "timeframe": "1Day",
                "feed": "sip",
                "currency": "USD",
                "adjustment": "dividend",
                "limit": 10000,
                "sort": "asc",
            }
            pages = batch_pages(api, "/v2/stocks/bars", query, "bars")
            dividend_adjusted.update(
                _parse_pages(pages, chosen, date.fromisoformat(begin), last)
            )
            acquisition.append(
                {
                    "dividend_unit_check": query,
                    "digest": store.capture_source(
                        json.dumps(pages, sort_keys=True).encode()
                    ),
                }
            )
        progress(60, "Normalizing ex-date income and contractual corporate actions")
        for event in events.values():
            kind = event["kind"]
            if kind not in (
                "cash_dividends",
                "forward_splits",
                "reverse_splits",
                "stock_dividends",
            ):
                continue
            symbol = event.get("symbol")
            day = date.fromisoformat(event.get("ex_date") or event["process_date"])
            symbol = canonical(symbol, day) if symbol else None
            if symbol not in bars or day not in bars[symbol]:
                continue
            bar = bars[symbol][day]
            if event["id"] in CONFLICTS:
                issue(symbol, day, CONFLICTS[event["id"]])
                continue
            if kind == "cash_dividends":
                if (
                    event.get("currency") not in (None, "", "USD")
                    or event.get("due_bill_on_date")
                    or event.get("due_bill_off_date")
                ):
                    issue(
                        symbol,
                        day,
                        "Dividend has unsupported currency or due-bill terms.",
                    )
                    continue
                amount = decimal(event["rate"])
                pay = event.get("payable_date")
                valid_pay = bool(pay and pay >= str(day))
                if not valid_pay:
                    issue(
                        symbol,
                        day,
                        "Verified dividend payment date is unavailable.",
                        "cash_payment",
                    )
                if (
                    bar.dividend
                    and valid_pay
                    and bar.pay_date != date.fromisoformat(pay)
                ):
                    issue(
                        symbol,
                        day,
                        "Separate same-day dividend payment dates require distinct entitlements.",
                        "cash_payment",
                    )
                    valid_pay = False
                bars[symbol][day] = replace(
                    bar,
                    research_dividend=bar.research_dividend + amount,
                    dividend=bar.dividend + amount if valid_pay else bar.dividend,
                    pay_date=date.fromisoformat(pay) if valid_pay else bar.pay_date,
                )
            else:
                ratio = (
                    decimal(event["rate"])
                    if kind == "stock_dividends"
                    else decimal(event["new_rate"]) / decimal(event["old_rate"])
                )
                if ratio <= ZERO:
                    issue(symbol, day, "Invalid split ratio.")
                else:
                    bars[symbol][day] = replace(bar, split=bar.split * ratio)
        normalized_events.extend(supplement_splits(bars, adjusted, identity, api))
        opening_income = {}
        for event in spin_events:
            day, parent, child = (
                date.fromisoformat(event["effective"]),
                event["source"],
                event["target"],
            )
            if day in bars.get(parent, {}) and day in bars.get(child, {}):
                bar = bars[parent][day]
                opening_income.setdefault(str(day), {})[parent] = str(
                    decimal(opening_income.get(str(day), {}).get(parent, 0))
                    + decimal(event["ratio"]) * bars[child][day].open
                )
                bars[parent][day] = replace(
                    bar,
                    research_distribution=bar.research_distribution
                    + decimal(event["ratio"]) * bars[child][day].close,
                )
            else:
                issue(
                    parent,
                    day,
                    f"Spin-off consideration {child} has no verified ex-date price.",
                )
        for symbol, rows in bars.items():
            for before, after in zip(sorted(rows), sorted(rows)[1:]):
                a, b = rows[before], rows[after]
                if before not in adjusted.get(symbol, {}) or after not in adjusted.get(
                    symbol, {}
                ):
                    issue(symbol, after, "Split-adjusted cross-check is missing.")
                    continue
                pa, pb = adjusted[symbol][before].close, adjusted[symbol][after].close
                half = Decimal("0.005")
                if min(pa, pb) <= half:
                    issue(symbol, after, "Adjusted-price precision is insufficient.")
                    continue
                expected = b.close * b.split / a.close
                if (
                    not (pb - half) / (pa + half) - Decimal("0.00000001")
                    <= expected
                    <= (pb + half) / (pa - half) + Decimal("0.00000001")
                ):
                    issue(
                        symbol,
                        after,
                        "Split terms conflict with the independent adjusted-price series.",
                    )
        # A foreign flag without a currency is not permission to assume USD.
        # Compare the quoted distribution with the USD dividend-adjustment
        # series, allowing only its documented cent rounding uncertainty.
        for symbol in foreign_names:
            rows = bars.get(symbol, {})
            check = dividend_adjusted.get(symbol, {})
            for before, after in zip(sorted(rows), sorted(rows)[1:]):
                b = rows[after]
                if not b.research_dividend:
                    continue
                a = rows[before]
                if (
                    before not in check
                    or after not in check
                    or check[after].close <= Decimal(".005")
                ):
                    issue(symbol, after, "Dividend USD units could not be verified.")
                    continue
                pa, pb = check[before].close, check[after].close
                half = Decimal(".005")
                low = (a.close - b.close * (pa + half) / (pb - half)) / b.split
                high = (a.close - b.close * (pa - half) / (pb + half)) / b.split
                if (
                    not low - Decimal(".00001")
                    <= b.research_dividend
                    <= high + Decimal(".00001")
                ):
                    issue(
                        symbol,
                        after,
                        "Dividend amount conflicts with the USD adjusted-price evidence.",
                    )
        if base:
            old_marks = {
                d: dict(m)
                for d, m in base.metadata.get("research_open_income", {}).items()
                if d < str(overlap)
            }
            for d, marks in opening_income.items():
                old_marks.setdefault(d, {}).update(
                    {
                        s: m
                        for s, m in marks.items()
                        if d >= str(overlap) or s not in base.bars
                    }
                )
            opening_income = old_marks
            issues = [
                {**i, "end": min(i["end"], str(overlap - timedelta(days=1)))}
                for i in base.metadata.get("input_issues", [])
                if i["start"] < str(overlap)
            ] + [
                {
                    **i,
                    "start": max(i["start"], str(overlap))
                    if i["symbol"] in base.bars
                    else i["start"],
                }
                for i in issues
                if i["end"] >= str(overlap) or i["symbol"] not in base.bars
            ]
            for symbol in names:
                fresh = bars[symbol]
                if symbol in base.bars:
                    bars[symbol] = {
                        b.session: b for b in base.bars[symbol] if b.session < overlap
                    }
                    bars[symbol].update(
                        {d: b for d, b in fresh.items() if d >= overlap}
                    )
            normalized_events = [
                e
                for e in base.metadata.get("corporate_actions", [])
                if e["effective"] < str(overlap)
            ] + [
                e
                for e in normalized_events
                if e["effective"] >= str(overlap) or e["source"] not in base.bars
            ]
        expected_days = set(calendar.sessions(first, last))
        unavailable = {}
        for record in issues:
            unavailable.setdefault(record["symbol"], record["reason"])
        health = [
            {
                "symbol": s,
                "rows": len(r),
                "expected": len(expected_days),
                "missing_count": len(expected_days - r.keys()),
                "missing_examples": [
                    str(d) for d in sorted(expected_days - r.keys())[:10]
                ],
                "start": str(min(r)) if r else None,
                "end": str(max(r)) if r else None,
                "reason": unavailable.get(s),
            }
            for s, r in sorted(bars.items())
        ]
        provenance = {
            "contract": VERSION,
            "action_evidence_version": ACTION_EVIDENCE_VERSION,
            "reviewed_action_evidence": [
                event["reviewed_evidence"]
                for event in normalized_events
                if event.get("reviewed_evidence")
            ],
            "parent_digest": base.digest if base else None,
            "query": payload,
            "membership": audit,
            "events_digest": store.capture_source(
                json.dumps(action_pages, sort_keys=True).encode()
            ),
            "prices": acquisition,
            "identity": identity,
            "research_open_income": opening_income,
            "input_issues": issues,
        }
        raw = json.dumps(provenance, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        meta = {
            "provider": "alpaca",
            "feed": "sip",
            "price_basis": "as_traded",
            "normalizer_version": VERSION,
            "action_evidence_version": ACTION_EVIDENCE_VERSION,
            "default_dividend_model": "ex_date",
            "custom_symbols": custom_symbols,
            "input_issues": issues,
            "unavailable_symbols": unavailable,
            "corporate_actions": normalized_events,
            "research_open_income": opening_income,
            "identity_resolution": identity,
            "coverage": health,
            "membership": audit,
            "retrieved_at": now(),
            "observation_ids": list(api.observations),
            "download": {"symbols": names, "start": str(first), "end": str(last)},
            "dependency_symbols": sorted(dependencies - primary_symbols),
            "bundle_role": "prices",
            "update": {
                "parent_dataset_id": base.id,
                "parent_digest": base.digest,
                "overlap_start": str(overlap),
                "end": str(last),
            }
            if base
            else None,
            "series_id": (base.metadata.get("series_id") if base else None)
            or hashlib.sha256(
                json.dumps(
                    {
                        "provider": "alpaca",
                        "name": payload.get("name", "S&P 500"),
                        "start": str(first),
                        "universe": "sp500" if audit else "custom",
                        "symbols": sorted(payload.get("symbols", [])),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:24],
        }
        dataset = Dataset(
            digest[:24],
            payload.get("name") or "S&P 500",
            "imported",
            base.revision + 1 if base else 1,
            {s: tuple(rows[d] for d in sorted(rows)) for s, rows in bars.items()},
            {s: sectors.get(s, "Unknown") for s in names},
            "Alpaca SIP · dated raw prices + primary-source action evidence"
            if any(event.get("reviewed_evidence") for event in normalized_events)
            else "Alpaca SIP · dated raw prices and corporate actions",
            digest,
            meta,
        )
        warnings = [
            membership.HISTORY_NOTE
            if audit
            else "Fixed-list exploratory research; membership history is not certified.",
            "Total-return research reinvests known ex-date distributions at the close. Payment-date cash simulation is a separate stricter mode. Missing prices, ambiguous effective inputs and unsupported terms remain blockers for the affected dates.",
            "Dated ticker mapping and same-CUSIP renames preserve departed companies; original identities/announcement vintages are not certified.",
        ]
        progress(78, "Saving dated research inputs and shared snapshot blocks")
        return store.save_dataset(dataset, raw, warnings)
    except ResearchError:
        raise
    except (KeyError, TypeError, ValueError):
        raise ResearchError(
            "The provider returned incomplete or malformed dated prices/actions. No research snapshot was published; existing snapshots are unchanged."
        ) from None
    finally:
        if provider is None:
            api.close()
