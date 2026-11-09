"""Explicit exploratory coverage policy; complete-input mode stays strict."""

from bisect import bisect_right
from collections import defaultdict
from datetime import timedelta

from . import calendar, membership
from .lifecycles import prepared, terminal_events, event_session
from .domain import ResearchError

MODES = ("strict", "coverage_limited")
WARNING = "Coverage-limited exploratory research: stocks with missing or unverified inputs are excluded using availability over their possible holding windows, including dates after a decision. This can introduce survivorship and selection bias. These results do not represent a complete S&P 500 backtest or establish trading readiness."


def plan(dataset, start, end, identifier, dividend_model, mode, frequency="weekly"):
    if mode not in MODES:
        raise ResearchError("Choose strict full-index or coverage-limited research.")
    dataset = prepared(dataset)
    days = calendar.sessions(start, end)
    required = 20 if identifier in ("quality", "quality_value") else 253
    decisions = sorted(calendar.decision_sessions(days, frequency))
    members = defaultdict(list)
    for day in days:
        for name in membership.eligible(dataset, day):
            members[name].append(day)
    day_positions = {day: index for index, day in enumerate(days)}
    reasons = defaultdict(list)
    windows = {}
    terminals = terminal_events(dataset)
    available = {s: {b.session for b in rows} for s, rows in dataset.bars.items()}

    def liquidation(last_member):
        # A departure does not create an extra trade. Hold through the next
        # ordinary decision and next-session opening execution, when necessary.
        index = bisect_right(decisions, last_member)
        return (
            min(days[-1], calendar.next_session(decisions[index]))
            if index < len(decisions)
            else days[-1]
        )

    def paths(symbol, begin, finish, seen=()):
        if symbol in seen:
            reasons[owner].append(
                f"Cyclic merger consideration involving {symbol}; no terminal value is assumed."
            )
            return []
        event = terminals.get(symbol)
        stop = event_session(event) if event else None
        if stop and begin <= stop <= finish:
            result = [(symbol, begin, stop - timedelta(days=1))]
            if event.get("target"):
                result += paths(event["target"], stop, finish, (*seen, symbol))
            return result
        return [(symbol, begin, finish)]

    if mode == "coverage_limited":
        from .research_data import indexed_issues

        issues = indexed_issues(dataset)
        for owner, member_days in sorted(members.items()):
            # Separate membership spells: a stock cannot be held across a gap
            # after a scheduled exit, but a later re-entry needs its own path.
            spans = []
            begin = last = member_days[0]
            for day in member_days[1:]:
                if day_positions[day] != day_positions[last] + 1:
                    spans.append((begin, liquidation(last)))
                    begin = day
                last = day
            spans.append((begin, liquidation(last)))
            windows[owner] = []
            for begin, finish in spans:
                prior = calendar.sessions(begin - timedelta(days=740), begin)[
                    -required:
                ]
                warmup = prior[0] if prior else begin
                for symbol, first, final in paths(owner, begin, finish):
                    needed = calendar.sessions(first, final)
                    windows[owner].append(
                        {"symbol": symbol, "start": str(first), "end": str(final)}
                    )
                    missing = [
                        d for d in needed if d not in available.get(symbol, set())
                    ]
                    if missing:
                        dependency = (
                            f"Merger recipient {symbol}: " if symbol != owner else ""
                        )
                        reasons[owner].append(
                            f"{dependency}Missing {len(missing)} sessions during a possible holding window; first missing {missing[0]}. No terminal price is assumed."
                        )
                    issue_start = warmup if symbol == owner else first
                    for issue in (issues or {}).get(symbol, ()):
                        if (
                            issue["start"] <= str(final)
                            and issue["end"] >= str(issue_start)
                            and not (
                                issue["kind"] == "cash_payment"
                                and dividend_model != "pay_date"
                            )
                        ):
                            dependency = (
                                f"Merger recipient {symbol}: "
                                if symbol != owner
                                else ""
                            )
                            reasons[owner].append(
                                f"{dependency}{issue['start']}: {issue['reason']}"
                            )
                # Consideration is needed even though the old security has no
                # quote on its conversion session. Incomplete actions still block.
                for issue in (issues or {}).get(owner, ()):
                    if (
                        issue["start"] <= str(finish)
                        and issue["end"] >= str(warmup)
                        and not (
                            issue["kind"] == "cash_payment"
                            and dividend_model != "pay_date"
                        )
                    ):
                        reasons[owner].append(f"{issue['start']}: {issue['reason']}")
                if issues is None and owner in dataset.metadata.get(
                    "unavailable_symbols", {}
                ):
                    reasons[owner].append(
                        dataset.metadata["unavailable_symbols"][owner]
                    )
    return {
        "mode": mode,
        "dividend_model": dividend_model,
        "start": str(days[0]),
        "end": str(days[-1]),
        "frequency": frequency,
        "price_window_policy": "Dated membership through the next scheduled execution, including supported merger consideration; no assumed last-close sale or zero recovery.",
        "holding_windows": windows,
        "universe_count": len(members),
        "excluded_count": len(reasons),
        "excluded": [
            {"symbol": s, "reasons": sorted(set(r))} for s, r in sorted(reasons.items())
        ],
        "warning": WARNING
        if mode == "coverage_limited"
        else "Strict: required historical members and inputs must be complete; gaps stop the calculation.",
    }
