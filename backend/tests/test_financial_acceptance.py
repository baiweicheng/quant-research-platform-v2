"""Independent, small-number acceptance cases for signal/allocation arithmetic."""

from datetime import date
from decimal import Decimal as D
from math import sqrt

import pytest
from aperture import calendar
from aperture.domain import Bar, Dataset, Policy, RankedStock
from aperture.portfolio import target_weights
from aperture.signals import rank


def test_momentum_50_percent_ignores_the_last_month_price_shock():
    days = calendar.sessions(date(2024, 1, 2), date(2025, 6, 30))[-253:]
    rows = []
    for i, day in enumerate(days):
        close = D(100) if i == 0 else D(150) if i <= 231 else D(1000)
        rows.append(
            Bar(
                "ABC",
                day,
                *([close] * 4),
                10000,
                available_at=calendar.available_time(day),
            )
        )
    ds = Dataset(
        "known",
        "Known endpoints",
        "imported",
        1,
        {"ABC": tuple(rows)},
        {"ABC": "A"},
        "hand-calculated",
        "known",
    )
    scored, excluded = rank(ds, "momentum", days[-1])
    assert excluded == [] and scored[0].score == pytest.approx(0.5, abs=1e-12)


def test_low_volatility_matches_alternating_ten_percent_sample_deviation():
    days = calendar.sessions(date(2024, 1, 2), date(2025, 6, 30))[-253:]
    price = D(100)
    rows = []
    steady = []
    for i, day in enumerate(days):
        if i:
            price *= D("1.1") if i % 2 else D(".9")
        rows.append(Bar("VARIABLE", day, *([price] * 4), 10000))
        steady.append(Bar("STEADY", day, *([D(100)] * 4), 10000))
    ds = Dataset(
        "known",
        "Known returns",
        "imported",
        1,
        {"VARIABLE": tuple(rows), "STEADY": tuple(steady)},
        {},
        "hand-calculated",
        "known",
    )
    scored, _ = rank(ds, "low_volatility", days[-1])
    assert [r.symbol for r in scored] == ["STEADY", "VARIABLE"]
    assert scored[0].score == 0
    # 126 returns of +0.1 and 126 of -0.1: mean 0; squared deviations total 2.52.
    assert scored[1].score == pytest.approx(-sqrt(2.52 / 251), abs=1e-12)


def test_known_sector_waterfilling_leaves_65_percent_cash_without_cap_relaxation():
    names = [RankedStock(f"T{i}", 1, "Technology") for i in range(6)] + [
        RankedStock("I0", 0.5, "Industrials"),
        RankedStock("I1", 0.4, "Industrials"),
    ]
    weights, _ = target_weights(names, Policy())
    # Six tech names share 25%; the two industrial names each stop at 5%.
    assert all(weights[f"T{i}"] == D(".041666666") for i in range(6))
    assert weights["I0"] == weights["I1"] == D(".05")
    assert 1 - sum(weights.values()) == D(".650000004")
