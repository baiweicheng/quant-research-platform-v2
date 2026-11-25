"""Display statistics use common actual dates; short histories are disclosed."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby
from math import sqrt
from statistics import stdev

PERIODS = ("1W", "1M", "3M", "6M", "YTD", "1Y", "All")


def costs_by_session(
    trades: list[dict], fixed_slippage: Decimal | None
) -> dict[str, Decimal] | None:
    costs: dict[str, Decimal] = {}
    for fill in trades:
        if "slippage_cost" in fill:
            slippage = Decimal(fill["slippage_cost"])
        else:
            # Older fixed-cost results save the execution price after slippage.
            if fixed_slippage is None:
                return None
            price = Decimal(fill["price"])
            multiplier = 1 + (
                fixed_slippage if fill["side"] == "Buy" else -fixed_slippage
            )
            slippage = Decimal(fill["quantity"]) * abs(price - price / multiplier)
        session = fill["session"]
        costs[session] = (
            costs.get(session, Decimal(0)) + Decimal(fill["fee"]) + slippage
        )
    return costs


def windows_with_attribution(result: dict) -> dict:
    """Add back the direct debits on the saved holdings path for each period."""
    policy = result.get("policy", {})
    fixed_slippage = (
        Decimal(policy["slippage_bps"]) / 10_000
        if policy.get("cost_model", "fixed") == "fixed" and "slippage_bps" in policy
        else None
    )
    strategy_costs = costs_by_session(result["trades"], fixed_slippage)
    if strategy_costs is None:
        return result["windows"]
    benchmark_costs = (
        costs_by_session(result["benchmark_trades"], fixed_slippage)
        if "benchmark_trades" in result
        else None
    )
    dividends_by_session = result.get("dividend_income_by_session")
    curve = result["curve"]
    last = curve[-1]
    output = {}
    for period, window in result["windows"].items():
        first = curve[window["start_index"]]
        if first["session"] == last["session"]:
            output[period] = window
            continue
        start, end = first["session"], last["session"]
        initial = Decimal(first["equity"])
        net = Decimal(last["equity"]) - initial
        # The starting close already reflects that session's trades.
        cost = sum(
            (value for day, value in strategy_costs.items() if start < day <= end),
            Decimal(0),
        )
        gross = net + cost
        attribution = {
            "stock_gain": str(gross),
            "trading_cost_impact": str(-cost),
            "net_change": str(net),
            "stock_return": float(gross / initial),
            "trading_cost_contribution": float(-cost / initial),
            "net_return": float(net / initial),
        }
        if dividends_by_session is not None:
            dividends = sum(
                (
                    Decimal(amount)
                    for day, amount in dividends_by_session.items()
                    if start < day <= end
                ),
                Decimal(0),
            )
            price_change = gross - dividends
            attribution["dividend_breakdown"] = {
                "dividend_income": str(dividends),
                "dividend_contribution": float(dividends / initial),
                "stock_value_change": str(price_change),
                "stock_value_contribution": float(price_change / initial),
            }
        if (
            benchmark_costs is not None
            and window["metrics"]["benchmark_return"] is not None
        ):
            spy_initial = Decimal(first["benchmark"])
            spy_cost = sum(
                value for day, value in benchmark_costs.items() if start < day <= end
            )
            attribution["benchmark_gross_return"] = float(
                (Decimal(last["benchmark"]) - spy_initial + spy_cost) / spy_initial
            )
        output[period] = {**window, "return_attribution": attribution}
    return output


def subtract_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 - months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def summarize(curve: list[dict]) -> dict:
    if len(curve) < 2:
        return {
            "return": None,
            "benchmark_return": None,
            "difference": None,
            "drawdown": None,
            "volatility": None,
            "cagr": None,
        }
    values = [float(row["equity"]) for row in curve]
    result = values[-1] / values[0] - 1
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    returns = [current / previous - 1 for previous, current in zip(values, values[1:])]
    benchmark = None
    if all(row.get("benchmark") is not None for row in curve):
        benchmark = float(curve[-1]["benchmark"]) / float(curve[0]["benchmark"]) - 1
    elapsed = (
        date.fromisoformat(curve[-1]["session"])
        - date.fromisoformat(curve[0]["session"])
    ).days
    return {
        "return": result,
        "benchmark_return": benchmark,
        "difference": None if benchmark is None else result - benchmark,
        "drawdown": drawdown,
        "volatility": stdev(returns) * sqrt(252) if len(returns) >= 20 else None,
        "cagr": (values[-1] / values[0]) ** (365.25 / elapsed) - 1
        if elapsed >= 365
        else None,
    }


def windows(curve: list[dict]) -> dict:
    if not curve:
        return {}
    end = date.fromisoformat(curve[-1]["session"])
    beginnings = {
        "1W": end - timedelta(days=7),
        "1M": subtract_months(end, 1),
        "3M": subtract_months(end, 3),
        "6M": subtract_months(end, 6),
        "YTD": date(end.year, 1, 1),
        "1Y": subtract_months(end, 12),
        "All": date.fromisoformat(curve[0]["session"]),
    }
    output = {}
    for name, start in beginnings.items():
        # Include the last valuation on/before the boundary when available. This
        # captures the full first return, rather than dropping the first session.
        boundary = [
            index
            for index, row in enumerate(curve)
            if date.fromisoformat(row["session"]) <= start
        ]
        index = boundary[-1] if boundary else 0
        subset = curve[index:]
        output[name] = {
            "start": subset[0]["session"],
            "end": subset[-1]["session"],
            "start_index": index,
            "limited": start < date.fromisoformat(curve[0]["session"]),
            "metrics": summarize(subset),
        }
    return output


def calendar_year_returns(curve: list[dict]) -> list[dict]:
    if not curve:
        return []
    starting = curve[0]
    years = []
    for year, observations in groupby(curve, key=lambda row: row["session"][:4]):
        final = list(observations)[-1]
        net = Decimal(final["equity"]) / Decimal(starting["equity"]) - 1
        spy = (
            Decimal(final["benchmark"]) / Decimal(starting["benchmark"]) - 1
            if final["benchmark"] is not None and starting["benchmark"] is not None
            else None
        )
        years.append(
            {
                "year": year,
                "start": starting["session"],
                "end": final["session"],
                "return": float(net),
                "benchmark_return": None if spy is None else float(spy),
                "difference": None if spy is None else float(net - spy),
            }
        )
        starting = final
    return years
