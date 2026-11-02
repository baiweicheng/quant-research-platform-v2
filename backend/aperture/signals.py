"""Price signals with an explicit historical decision cutoff."""

from datetime import date, timedelta
from math import isfinite
from statistics import stdev

from . import calendar
from .domain import Bar, Dataset, RankedStock, ResearchError, strategy


def total_return_levels(bars: tuple[Bar, ...] | list[Bar]) -> list[float]:
    """Economic ex-date return index; this is not the portfolio cash ledger.

    Dividends are quoted per post-split share when both events share a date.
    Raw historical prices must be as-traded, never already split-adjusted.
    """
    if not bars:
        return []
    result = [1.0]
    for before, current in zip(bars, bars[1:]):
        gross = float(current.split * (current.close + current.dividend) / before.close)
        level = result[-1] * gross
        if not isfinite(level) or level <= 0:
            raise ResearchError(
                "Price/action units produce an unsafe return calculation. Check the dataset's price and corporate-action conventions."
            )
        result.append(level)
    return result


def rank(
    dataset: Dataset, identifier: str, decision: date
) -> tuple[list[RankedStock], list[dict]]:
    strategy(identifier)
    cutoff = calendar.available_time(decision)
    expected = calendar.sessions(decision - timedelta(days=740), decision)[-253:]
    ranked: list[RankedStock] = []
    excluded: list[dict] = []
    for symbol, all_bars in sorted(dataset.bars.items()):
        if symbol == "SPY":
            continue
        by_day = {
            bar.session: bar
            for bar in all_bars
            if bar.session <= decision
            and (bar.available_at is None or bar.available_at <= cutoff)
        }
        if len(expected) < 253 or any(day not in by_day for day in expected):
            excluded.append(
                {
                    "symbol": symbol,
                    "reason": "Needs 253 complete sessions available by this decision.",
                }
            )
            continue
        bars = [by_day[day] for day in expected]
        if sum(bar.volume for bar in bars[-20:]) == 0:
            excluded.append({"symbol": symbol, "reason": "No recent trading volume."})
            continue
        levels = total_return_levels(bars)
        if identifier == "momentum":
            score = levels[-22] / levels[-253] - 1
            if score <= 0:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Nonpositive 12–1 momentum; the unused allocation stays in cash.",
                    }
                )
                continue
        else:
            changes = [after / before - 1 for before, after in zip(levels, levels[1:])]
            score = -stdev(changes)
        if isfinite(score):
            ranked.append(
                RankedStock(symbol, score, dataset.sectors.get(symbol, "Unknown"))
            )
    return sorted(ranked, key=lambda item: (-item.score, item.symbol)), excluded
