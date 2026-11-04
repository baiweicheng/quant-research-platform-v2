"""Price signals with an explicit historical decision cutoff."""

from datetime import date, timedelta
from decimal import Decimal
from math import isfinite
from statistics import stdev

from . import calendar
from .domain import Bar, Dataset, RankedStock, ResearchError, strategy
from .fundamentals import FUNDAMENTAL_STRATEGIES, inputs
from .membership import eligible


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
    dataset: Dataset, identifier: str, decision: date, exit_only: set[str] | None = None
) -> tuple[list[RankedStock], list[dict]]:
    strategy(identifier)
    fundamental = identifier in FUNDAMENTAL_STRATEGIES
    if fundamental and not dataset.fundamentals:
        raise ResearchError(
            "Add SEC fundamentals to this market dataset in Data first. Price-only inputs cannot run this strategy."
        )
    cutoff = calendar.available_time(decision)
    required = 20 if identifier in ("quality", "quality_value") else 253
    expected = calendar.sessions(decision - timedelta(days=740), decision)[-required:]
    ranked: list[RankedStock] = []
    excluded: list[dict] = []
    members = eligible(dataset, decision) - (exit_only or set())
    blocked = members & dataset.metadata.get("unavailable_symbols", {}).keys()
    if blocked:
        raise ResearchError(
            "Required universe members have unavailable/unverified data: "
            + ", ".join(sorted(blocked)[:12])
            + ". See Data for the per-stock reasons; they cannot be omitted from ranking."
        )
    sectors = dataset.sectors
    audit = dataset.metadata.get("membership")
    if audit and audit["kind"] == "combined":
        history = audit["historical"]
        if (
            not history
            or not history["coverage_start"] <= str(decision) <= history["coverage_end"]
        ):
            # Current classifications apply only to an observed-current review.
            # Historical decisions retain Unknown rather than current GICS.
            sectors = {
                **sectors,
                **{m["symbol"]: m["sector"] for m in audit["current"]["members"]},
            }
    missing = members - dataset.bars.keys()
    if missing:
        raise ResearchError(
            "Universe members have no price history: " + ", ".join(sorted(missing)[:12])
        )
    for symbol, all_bars in sorted(dataset.bars.items()):
        if symbol == "SPY":
            continue
        if symbol not in members:
            excluded.append(
                {
                    "symbol": symbol,
                    "reason": "Not an S&P 500 member on this decision date.",
                }
            )
            continue
        by_day = {
            bar.session: bar
            for bar in all_bars
            if bar.session <= decision
            and (bar.available_at is None or bar.available_at <= cutoff)
        }
        if len(expected) < required or any(day not in by_day for day in expected):
            excluded.append(
                {
                    "symbol": symbol,
                    "reason": f"Needs {required} complete sessions available by this decision.",
                }
            )
            continue
        bars = [by_day[day] for day in expected]
        if sum(bar.volume for bar in bars[-20:]) == 0:
            excluded.append({"symbol": symbol, "reason": "No recent trading volume."})
            continue
        if fundamental:
            components, reason = inputs(dataset, symbol, decision)
            if identifier == "value_momentum":
                levels = total_return_levels(bars)
                components["momentum"] = levels[-22] / levels[-253] - 1
            factors = {
                "quality": ("profitability",),
                "quality_value": ("profitability", "earnings_yield"),
                "value_momentum": ("earnings_yield", "momentum"),
            }[identifier]
            if reason or any(components.get(key, 0) <= 0 for key in factors):
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": reason
                        or components.get("valuation_issue")
                        or "All required factors must be available and positive: "
                        + ", ".join(factors)
                        + ".",
                    }
                )
                continue
            ranked.append(
                RankedStock(symbol, 0.0, sectors.get(symbol, "Unknown"), components)
            )
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
            ranked.append(RankedStock(symbol, score, sectors.get(symbol, "Unknown")))
    if fundamental:
        factors = {
            "quality": ("profitability",),
            "quality_value": ("profitability", "earnings_yield"),
            "value_momentum": ("earnings_yield", "momentum"),
        }[identifier]
        scored = []
        for stock in ranked:
            percentiles = {}
            for key in factors:
                value = stock.components[key]
                below = sum(other.components[key] < value for other in ranked)
                tied = sum(other.components[key] == value for other in ranked)
                percentiles[key] = (
                    (below + (tied - 1) / 2) / (len(ranked) - 1)
                    if len(ranked) > 1
                    else 0.5
                )
            score = (
                float(stock.components["profitability"])
                if identifier == "quality"
                else sum(percentiles.values()) / len(factors)
            )
            if not isfinite(score):
                raise ResearchError(
                    "Fundamental units produce an unsafe factor ratio. Check the source statement before using this dataset."
                )
            audit = {
                key: str(value) if isinstance(value, Decimal) else value
                for key, value in stock.components.items()
            }
            scored.append(
                RankedStock(
                    stock.symbol,
                    score,
                    stock.sector,
                    {**audit, "percentiles": percentiles},
                )
            )
        ranked = scored
    return sorted(ranked, key=lambda item: (-item.score, item.symbol)), excluded
