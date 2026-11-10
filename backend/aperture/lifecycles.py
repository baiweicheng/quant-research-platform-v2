"""Supported security cessations and the price paths a portfolio can need."""

from datetime import date, timedelta
from dataclasses import replace

from . import calendar
from .domain import ZERO, decimal

MERGERS = {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"}


def event_session(event):
    day = date.fromisoformat(event["effective"])
    return calendar.sessions(day, day + timedelta(days=10))[0]


def recipients(event):
    """Stock consideration as (symbol, shares per source share) pairs.

    Reviewed multi-security conversions list every recipient explicitly;
    native vendor instructions carry at most one target.
    """
    if event.get("targets"):
        return [(t["symbol"], decimal(t["ratio"])) for t in event["targets"]]
    if event.get("target"):
        return [(event["target"], decimal(event.get("ratio", 0)))]
    return []


def zero_recovery(event):
    """Only a reviewed cancellation may end a holding without consideration."""
    evidence = event.get("reviewed_evidence") or {}
    return bool(
        evidence.get("zero_recovery")
        and event["kind"] == "cash_mergers"
        and decimal(event.get("cash", 0)) == ZERO
        and not recipients(event)
    )


def complete_consideration(event):
    """A conversion needs a verified recipient/ratio or cash amount.

    A reviewed failure with no equity recovery is the only zero-value case.
    """
    if event.get("unpriced_consideration"):
        return False
    cash = decimal(event.get("cash", 0))
    stock = recipients(event)
    if cash < ZERO or any(ratio <= ZERO or not symbol for symbol, ratio in stock):
        return False
    if event["kind"] == "cash_mergers":
        return cash > ZERO or zero_recovery(event)
    return bool(stock)


def terminal_events(dataset):
    """Only complete conversions followed by no further source quotes.

    Later quotes or a new index entry under the same ticker require separate
    identity work. They cannot silently become a permanently ceased security.
    Missing sessions before the conversion remain coverage errors.
    """
    if "_research_terminal_events" in dataset.metadata:
        return dataset.metadata["_research_terminal_events"]
    from .historical_timing import verified_nontrading_tail

    result = {}
    audit = dataset.metadata.get("membership") or {}
    history = audit.get("historical", {}) if audit.get("kind") == "combined" else audit
    rosters = history.get("rosters", []) if history else []
    for event in dataset.metadata.get("corporate_actions", []):
        if event["kind"] not in MERGERS or event.get("unpriced_consideration"):
            continue
        source = event["source"]
        rows = dataset.bars.get(source, ())
        effective = event_session(event)
        if (
            not rows
            or (
                rows[-1].session >= effective
                and not verified_nontrading_tail(event, rows)
            )
            or any(symbol == source for symbol, _ in recipients(event))
            or not complete_consideration(event)
        ):
            continue
        previous = False
        reentry = False
        for roster in rosters:
            present = source in roster["symbols"]
            if present and not previous and roster["effective"] > str(effective):
                reentry = True
                break
            previous = present
        if reentry:
            continue
        if source not in result or effective < event_session(result[source]):
            result[source] = event
    return result


def prepared(dataset):
    return replace(
        dataset,
        metadata={
            **dataset.metadata,
            "_research_terminal_events": terminal_events(dataset),
        },
    )


def closed_names(dataset, decision):
    return {
        s for s, e in terminal_events(dataset).items() if event_session(e) <= decision
    }
