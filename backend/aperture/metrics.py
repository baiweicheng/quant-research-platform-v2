"""Display statistics use common actual dates; short histories are disclosed."""

from calendar import monthrange
from datetime import date, timedelta
from math import sqrt
from statistics import stdev

PERIODS = ("1W", "1M", "3M", "6M", "YTD", "1Y", "All")


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
