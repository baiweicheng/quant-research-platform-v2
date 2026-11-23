from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest
from aperture import calendar
from aperture.backtest import run
from aperture.domain import (
    Bar,
    Dataset,
    Policy,
    ResearchError,
    backtest_policy,
    paper_strategy,
)
from aperture.liquidity_breadth import STRATEGY_ID, LiquidityBreadth


def test_price_only_backtest_matches_cutoff_and_portfolio_caps():
    days = calendar.sessions(date(2023, 1, 3), date(2024, 2, 6))
    decision = days[-3]
    names = ["SPY", *(f"S{i:02d}" for i in range(30))]
    bars = {}
    for j, symbol in enumerate(names):
        rows = []
        for i, session in enumerate(days):
            close = Decimal(2000 - i * (j % 3 + 1) + (i % 7) * (j + 1)) / 10
            rows.append(
                Bar(symbol, session, close, close, close, close, 1000 * (j + 1))
            )
        bars[symbol] = tuple(rows)
    sectors = {stock: str(i % 5) for i, stock in enumerate(names[1:])}
    dataset = Dataset("id", "test", "imported", 1, bars, sectors, "test", "digest")
    policy = backtest_policy("higher")
    ranked, _, targets, _, _ = LiquidityBreadth(dataset).decision(decision, policy)
    assert len(targets) == len(ranked) == 25
    assert "SPY" not in targets
    assert max(targets.values()) <= policy.max_weight
    assert sum(targets.values()) <= 1 - policy.cash_reserve
    assert all(
        sum(targets[s] for s in targets if sectors[s] == sector) <= policy.sector_cap
        for sector in set(sectors.values())
    )
    assert all(stock.components["market_breadth"] == 0 for stock in ranked)
    assert all(stock.components["beta_sizing_strength"] == 2 for stock in ranked)
    result = run(dataset, STRATEGY_ID, decision, days[-1], Decimal(100_000), policy)
    first = result["decisions"][0]
    assert first["session"] == str(decision)
    assert first["execute_session"] == str(days[-2])
    assert first["targets"] == {s: str(w) for s, w in targets.items()}
    assert result["calendar_year_returns"]

    name = next(iter(targets))
    future = calendar.available_time(decision) + timedelta(minutes=1)
    late = replace(bars[name][-3], available_at=future)
    late_bars = {**bars, name: (*bars[name][:-3], late, *bars[name][-2:])}
    without_late = LiquidityBreadth(replace(dataset, bars=late_bars))
    assert name not in without_late.decision(decision, Policy())[2]
    with pytest.raises(ResearchError, match="research only"):
        paper_strategy(STRATEGY_ID)
