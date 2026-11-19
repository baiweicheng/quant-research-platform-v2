"""Price signals with an explicit historical decision cutoff."""

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby, pairwise
from math import fsum, isfinite, log, sqrt
from statistics import fmean, median, stdev

from . import annual_income, calendar
from .domain import Bar, Dataset, RankedStock, ResearchError, strategy
from .fundamentals import FUNDAMENTAL_STRATEGIES, inputs
from .membership import eligible
from .sectors import sectors_on

SESSION_STRENGTH = "session_strength_liquidity"
MARKET_ROTATION = "earnings_market_regime"


def percentile_ranks(values):
    ranks = {}
    below = 0
    for _, peers in groupby(sorted(values, key=values.get), key=values.get):
        peers = list(peers)
        percentile = (
            (below + (len(peers) - 1) / 2) / (len(values) - 1)
            if len(values) > 1
            else 0.5
        )
        ranks.update(dict.fromkeys(peers, percentile))
        below += len(peers)
    return ranks


def session_moves(bars, cutoffs):
    return {
        bar.session: (
            log(float(bar.open / previous.close)),
            log(float(bar.close / bar.open)),
        )
        for previous, bar in pairwise(bars)
        if bar.split == 1
        and not (bar.dividend or bar.research_dividend or bar.research_distribution)
        and (bar.available_at is None or bar.available_at <= cutoffs[bar.session])
    }


def session_strength(bars, cutoffs, market_moves):
    daytime = []
    followthrough = []
    confirmation_start = bars[-63].session
    for session, (overnight, regular) in session_moves(bars[-85:], cutoffs).items():
        if session not in market_moves:
            continue
        spy_overnight, spy_regular = market_moves[session]
        relative_overnight = overnight - spy_overnight
        relative_regular = regular - spy_regular
        daytime.append(min(0.12, max(-0.12, relative_regular)))
        if (
            session >= confirmation_start
            and relative_overnight > 0
            and relative_regular > 0
        ):
            followthrough.append(min(0.12, relative_overnight + relative_regular))
    return {
        "daytime_relative_log_return": fsum(daytime),
        "overnight_followthrough_log_return": fsum(followthrough),
    }


def market_regime(bars):
    levels = total_return_levels(bars)
    average_gap = levels[-1] / fmean(levels[-100:]) - 1
    short_return = levels[-1] / levels[-22] - 1
    state = ("weak", "mixed", "strong")[int(average_gap > 0) + int(short_return > 0)]
    return {"state": state, "average_gap": average_gap, "short_return": short_return}


def total_return_levels(bars: tuple[Bar, ...] | list[Bar]) -> list[float]:
    """Economic ex-date return index; this is not the portfolio cash ledger.

    Dividends are quoted per post-split share when both events share a date.
    Raw historical prices must be as-traded, never already split-adjusted.
    """
    if not bars:
        return []
    result = [1.0]
    for before, current in zip(bars, bars[1:]):
        gross = float(
            current.split
            * (
                current.close
                + (current.research_dividend or current.dividend)
                + current.research_distribution
            )
            / before.close
        )
        level = result[-1] * gross
        if not isfinite(level) or level <= 0:
            raise ResearchError(
                "Price/action units produce an unsafe return calculation. Check the dataset's price and corporate-action conventions."
            )
        result.append(level)
    return result


def median_dollar_volume(bars: Iterable[Bar]) -> Decimal | None:
    marks = [bar.close * bar.volume for bar in bars if bar.volume > 0]
    return median(marks) if len(marks) >= 10 else None


def liquid_momentum_components(bars: list[Bar], dollar_volume: Decimal) -> dict | None:
    levels = total_return_levels(bars[:-21])
    changes = [b / a - 1 for a, b in pairwise(levels)]
    long_return = levels[-1] / levels[0] - 1
    short_return = levels[-1] / levels[-106] - 1
    long_volatility = stdev(changes) * sqrt(252)
    short_volatility = stdev(changes[-105:]) * sqrt(252)
    if not long_volatility or not short_volatility:
        return None
    return {
        "momentum": long_return,
        "six_month_momentum": short_return,
        "momentum_volatility": long_volatility,
        "six_month_volatility": short_volatility,
        "median_dollar_volume": str(dollar_volume),
    }


def rank(
    dataset: Dataset,
    identifier: str,
    decision: date,
    exit_only: set[str] | None = None,
    *,
    factor_audit: dict | None = None,
) -> tuple[list[RankedStock], list[dict]]:
    recipe = strategy(identifier)
    fundamental = identifier in FUNDAMENTAL_STRATEGIES
    uses_income = recipe.get("requires_annual_income", False)
    if fundamental and not dataset.fundamentals:
        raise ResearchError(
            "Add SEC fundamentals to this market dataset in Data first. Price-only inputs cannot run this strategy."
        )
    if uses_income and not dataset.annual_income:
        raise ResearchError(annual_income.MISSING_INPUTS)
    cutoff = calendar.available_time(decision)
    required = 20 if identifier in ("quality", "quality_value") else 253
    expected = calendar.sessions(decision - timedelta(days=740), decision)[-required:]
    expected_days = set(expected)
    ranked: list[RankedStock] = []
    excluded: list[dict] = []
    liquid_candidates: list[tuple[Decimal, str, list[Bar]]] = []
    new_research = identifier in (SESSION_STRENGTH, MARKET_ROTATION)
    market_state = None
    market_moves = {}
    daily_cutoffs = {}
    research_exclusions = set(dataset.metadata.get("research_exclusions", []))
    members = eligible(dataset, decision) - (exit_only or set()) - research_exclusions
    if factor_audit is not None and fundamental:
        factor_audit.update(
            {
                "members": len(members - {"SPY"}),
                "assessed": 0,
                "factors": {
                    key: {"positive": 0, "nonpositive": 0, "unavailable": 0}
                    for key in (
                        {
                            "quality": ("profitability",),
                            "quality_value": ("profitability", "earnings_yield"),
                            "value_momentum": ("earnings_yield",),
                        }[identifier]
                    )
                },
            }
        )
    if factor_audit is not None and uses_income:
        factor_audit.update(
            members=len(members - {"SPY"}),
            assessed=0,
            factors={
                "annual_net_income": {"positive": 0, "nonpositive": 0, "unavailable": 0}
            },
        )
    from .research_data import blocked_inputs, indexed_issues

    issue_index = indexed_issues(dataset)

    blocked = blocked_inputs(
        dataset,
        members | {"SPY"} if new_research else members,
        expected[0] if expected else decision,
        decision,
        "signals",
        issue_index=issue_index,
    )
    if blocked:
        raise ResearchError(
            "Required universe members have unavailable/unverified data: "
            + ", ".join(sorted(blocked)[:12])
            + ". See Data for the per-stock reasons; they cannot be omitted from ranking."
        )
    if new_research:
        market = {
            bar.session: bar
            for bar in dataset.bars.get("SPY", ())
            if bar.session in expected_days
            and (bar.available_at is None or bar.available_at <= cutoff)
        }
        if len(market) != required:
            raise ResearchError(
                f"This strategy needs {required} complete SPY sessions available by {decision}. "
                "Choose a dataset with SPY and enough warm-up history."
            )
        market_bars = [market[day] for day in expected]
        if identifier == MARKET_ROTATION:
            market_state = market_regime(market_bars)
            if factor_audit is not None:
                factor_audit["market_regime"] = market_state
        else:
            daily_cutoffs = {
                day: calendar.available_time(day) for day in expected[-84:]
            }
            market_moves = session_moves(market_bars[-85:], daily_cutoffs)
    sectors = sectors_on(dataset, decision)
    audit = dataset.metadata.get("membership")
    if (
        audit
        and audit["kind"] == "combined"
        and not dataset.metadata.get("sector_classification")
    ):
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
                    "reason": "Excluded by the saved coverage-limited research policy; see the complete coverage audit."
                    if symbol in research_exclusions
                    else "Not an S&P 500 member on this decision date.",
                }
            )
            continue
        by_day = {
            bar.session: bar
            for bar in all_bars
            if bar.session in expected_days
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
        if identifier == "liquidity_weighted_momentum":
            dollar_volume = median_dollar_volume(bars[-20:])
            if dollar_volume is None:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Needs 10 positive-volume sessions in the latest 20.",
                    }
                )
            else:
                liquid_candidates.append((dollar_volume, symbol, bars))
            continue
        if uses_income:
            dollar_volume = median_dollar_volume(bars[-20:])
            if dollar_volume is None:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Needs 10 positive-volume sessions in the latest 20.",
                    }
                )
                continue
            report = annual_income.as_of(
                dataset.annual_income.get(symbol, ()), decision, cutoff
            )
            income = (
                Decimal(report["net_income"])
                if report and "net_income" in report
                else None
            )
            if factor_audit is not None:
                factor_audit["assessed"] += 1
                status = (
                    "unavailable"
                    if income is None
                    else "positive"
                    if income > 0
                    else "nonpositive"
                )
                factor_audit["factors"]["annual_net_income"][status] += 1
            if new_research:
                components = {"median_dollar_volume": str(dollar_volume)}
                if income is not None:
                    components["annual_income"] = report
                if identifier == SESSION_STRENGTH:
                    components.update(
                        session_strength(bars, daily_cutoffs, market_moves)
                    )
                else:
                    assert market_state is not None
                    state = market_state["state"]
                    components["market_state"] = state
                    if state == "weak" and income is not None:
                        growth = (
                            income - Decimal(report["previous_net_income"])
                        ) / Decimal(report["beginning_assets"])
                        components["income_growth"] = max(-1.0, min(1.0, float(growth)))
                    if state != "weak":
                        levels = total_return_levels(bars)
                        lookback = 63 if state == "mixed" else 252
                        components["stock_return"] = (
                            levels[-1] / levels[-lookback - 1] - 1
                        )
                        if state == "mixed":
                            components["above_200_session_average"] = (
                                levels[-1] / fmean(levels[-200:]) - 1
                            )
                if report:
                    components["issuer"] = report["cik"]
                ranked.append(
                    RankedStock(symbol, 0.0, sectors.get(symbol, "Unknown"), components)
                )
                continue
            if income is None or income <= 0:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Latest annual filing has no supported comparable net income."
                        if income is None
                        else "Reported annual net income must be positive.",
                    }
                )
                continue
            levels = total_return_levels(bars)
            average = sum(levels[-200:]) / 200
            if levels[-1] <= average:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Total-return level must be above its 200-session average.",
                    }
                )
                continue
            ranked.append(
                RankedStock(
                    symbol,
                    float(dollar_volume),
                    sectors.get(symbol, "Unknown"),
                    {
                        "median_dollar_volume": str(dollar_volume),
                        "above_200_session_average": levels[-1] / average - 1,
                        "annual_income": report,
                    },
                )
            )
            continue
        if fundamental:
            components, reason = inputs(
                dataset, symbol, decision, issue_index=issue_index
            )
            if identifier == "value_momentum":
                levels = total_return_levels(bars)
                components["momentum"] = levels[-22] / levels[-253] - 1
            factors = {
                "quality": ("profitability",),
                "quality_value": ("profitability", "earnings_yield"),
                "value_momentum": ("earnings_yield", "momentum"),
            }[identifier]
            if factor_audit is not None:
                factor_audit["assessed"] += 1
                for key, counts in factor_audit["factors"].items():
                    status = (
                        "unavailable"
                        if components.get(key) is None
                        else "positive"
                        if components[key] > 0
                        else "nonpositive"
                    )
                    counts[status] += 1
            if reason or any(components.get(key, 0) <= 0 for key in factors):
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": reason
                        or (
                            components.get("profitability_issue")
                            if "profitability" in factors
                            and components.get("profitability", 0) <= 0
                            and components.get("profitability_issue")
                            else None
                        )
                        or (
                            components.get("valuation_issue")
                            if "earnings_yield" in factors
                            and components.get("earnings_yield", 0) <= 0
                            and components.get("valuation_issue")
                            else None
                        )
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
    if identifier == "liquidity_weighted_momentum":
        liquid_candidates.sort(key=lambda item: (-item[0], item[1]))
        for dollar_volume, symbol, bars in liquid_candidates[:100]:
            components = liquid_momentum_components(bars, dollar_volume)
            if components is None:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "Daily return volatility is zero in a momentum window.",
                    }
                )
                continue
            score = (
                components["momentum"] / components["momentum_volatility"]
                + components["six_month_momentum"] / components["six_month_volatility"]
            ) / 2
            if score > 0 and isfinite(score):
                ranked.append(
                    RankedStock(
                        symbol, score, sectors.get(symbol, "Unknown"), components
                    )
                )
            else:
                excluded.append(
                    {
                        "symbol": symbol,
                        "reason": "A positive blended momentum score is required.",
                    }
                )
        excluded.extend(
            {
                "symbol": symbol,
                "reason": "Outside the 100 stocks with highest recent median dollar volume.",
            }
            for _, symbol, _ in liquid_candidates[100:]
        )
    if fundamental:
        factors = {
            "quality": ("profitability",),
            "quality_value": ("profitability", "earnings_yield"),
            "value_momentum": ("earnings_yield", "momentum"),
        }[identifier]
        factor_ranks = {
            key: percentile_ranks(
                {stock.symbol: stock.components[key] for stock in ranked}
            )
            for key in factors
        }
        scored = []
        for stock in ranked:
            percentiles = {key: factor_ranks[key][stock.symbol] for key in factors}
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
    if new_research:
        state = market_state["state"] if market_state else None
        return rank_annual_research(ranked, excluded, state)
    ranked.sort(key=lambda item: (-item.score, item.symbol))
    if uses_income:
        issuers = set()
        unique = []
        for stock in ranked:
            cik = stock.components["annual_income"]["cik"]
            if cik in issuers:
                excluded.append(
                    {
                        "symbol": stock.symbol,
                        "reason": "This issuer is represented by another eligible share class.",
                    }
                )
            else:
                issuers.add(cik)
                unique.append(stock)
        ranked = unique
    return ranked, excluded


def rank_annual_research(candidates, excluded, state):
    volume = {
        s.symbol: Decimal(s.components["median_dollar_volume"]) for s in candidates
    }
    liquid = sorted(candidates, key=lambda s: (-volume[s.symbol], s.symbol))
    limit_liquidity = state in (None, "weak")
    if state is None:
        weights = {
            "median_dollar_volume": 0.55,
            "daytime_relative_log_return": 0.35,
            "overnight_followthrough_log_return": 0.10,
        }
    elif state == "weak":
        weights = {}
    else:
        liquidity_weight = 0.4 if state == "mixed" else 0.8
        weights = {
            "median_dollar_volume": liquidity_weight,
            "stock_return": 1 - liquidity_weight,
        }
    percentiles = {
        field: percentile_ranks(
            {stock.symbol: float(stock.components[field]) for stock in candidates}
        )
        for field in weights
    }
    ranked = []
    issuers = set()
    for index, stock in enumerate(liquid):
        components = stock.components
        entity = components.get("issuer", stock.symbol)
        income = components.get("annual_income")
        reason = None
        if limit_liquidity and index >= 100:
            reason = "Outside the 100 stocks with highest recent median dollar volume."
        elif state in (None, "strong") and (
            income is None or Decimal(income["net_income"]) <= 0
        ):
            reason = "Positive comparable annual net income is required."
        elif state == "weak" and "income_growth" not in components:
            reason = "Comparable current and prior annual net income is required."
        elif state == "mixed" and components["above_200_session_average"] <= 0:
            reason = "Total-return level must be above its 200-session average."
        elif entity in issuers:
            reason = "This issuer is represented by a more liquid eligible share class."
        if reason:
            excluded.append({"symbol": stock.symbol, "reason": reason})
            continue
        issuers.add(entity)
        score = (
            components["income_growth"]
            if state == "weak"
            else sum(
                weight * percentiles[field][stock.symbol]
                for field, weight in weights.items()
            )
        )
        ranked.append(RankedStock(stock.symbol, score, stock.sector, components))
    ranked.sort(key=lambda s: (-s.score, -volume[s.symbol], s.symbol))
    if state == "mixed":
        return ranked, excluded
    counts: dict[str, int] = {}
    selected = []
    for stock in ranked:
        count = counts.get(stock.sector, 0)
        if count >= 5:
            excluded.append(
                {
                    "symbol": stock.symbol,
                    "reason": "Five higher-ranked stocks already represent this sector.",
                }
            )
            continue
        selected.append(stock)
        counts[stock.sector] = count + 1
    return selected, excluded
