"""Supported security cessations and the price paths a portfolio can need."""

from datetime import date, timedelta
from dataclasses import replace

from . import calendar
from .domain import ZERO, decimal

MERGERS = {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"}


def event_session(event):
    day = date.fromisoformat(event["effective"])
    return calendar.sessions(day, day + timedelta(days=10))[0]


def terminal_events(dataset):
    """Only complete conversions followed by no further source quotes.

    Later quotes or a new index entry under the same ticker require separate
    identity work. They cannot silently become a permanently ceased security.
    Missing sessions before the conversion remain coverage errors.
    """
    if "_research_terminal_events" in dataset.metadata:
        return dataset.metadata["_research_terminal_events"]
    result = {}
    audit = dataset.metadata.get("membership") or {}
    history = audit.get("historical", {}) if audit.get("kind") == "combined" else audit
    rosters = history.get("rosters", []) if history else []
    for event in dataset.metadata.get("corporate_actions", []):
        if event["kind"] not in MERGERS or event.get("unpriced_consideration"):
            continue
        source, target = event["source"], event.get("target")
        rows = dataset.bars.get(source, ())
        effective = event_session(event)
        cash, ratio = decimal(event.get("cash", 0)), decimal(event.get("ratio", 0))
        if (
            not rows
            or rows[-1].session >= effective
            or source == target
            or cash < ZERO
            or (event["kind"] == "cash_mergers" and cash <= ZERO)
            or (event["kind"] != "cash_mergers" and (not target or ratio <= ZERO))
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
