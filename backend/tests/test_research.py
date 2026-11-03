from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from aperture import calendar
from aperture.backtest import run
from aperture.domain import Bar, Dataset, Policy, RankedStock, ResearchError
from aperture.metrics import windows, summarize
from aperture.signals import rank


@pytest.fixture
def history():
    days = calendar.sessions(date(2023, 1, 3), date(2025, 1, 10))
    bars = tuple(
        Bar(
            "ABC",
            day,
            *([D(100) + D(i) / 10] * 4),
            10000,
            available_at=calendar.available_time(day),
        )
        for i, day in enumerate(days)
    )
    return Dataset(
        "test",
        "Test",
        "imported",
        1,
        {"ABC": bars},
        {"ABC": "Industrials"},
        "fixture",
        "hash",
    )


def test_calendar_holidays_early_close_and_after_close_cutoff():
    assert calendar.next_session(date(2025, 7, 3)) == date(2025, 7, 7)
    assert calendar.close_time(date(2026, 11, 27)).hour == 18
    assert calendar.latest_complete(
        datetime(2026, 11, 27, 18, 14, tzinfo=timezone.utc)
    ) == date(2026, 11, 25)
    assert calendar.latest_complete(
        datetime(2026, 11, 27, 18, 16, tzinfo=timezone.utc)
    ) == date(2026, 11, 27)


def test_future_perturbation_cannot_change_historical_signal(history):
    decision = date(2024, 8, 30)
    original, _ = rank(history, "momentum", decision)
    changed = replace(
        history,
        bars={
            "ABC": tuple(
                replace(b, open=D(9999), high=D(9999), low=D(9999), close=D(9999))
                if b.session > decision
                else b
                for b in history.bars["ABC"]
            )
        },
    )
    assert rank(changed, "momentum", decision)[0] == original
    assert len(original) == 1


def test_missing_or_late_observation_is_not_forward_filled(history):
    decision = date(2024, 8, 30)
    late = replace(
        history,
        bars={
            "ABC": tuple(
                replace(
                    b,
                    available_at=calendar.available_time(decision)
                    + timedelta(seconds=1),
                )
                if b.session == decision
                else b
                for b in history.bars["ABC"]
            )
        },
    )
    ranked, excluded = rank(late, "momentum", decision)
    assert ranked == [] and len(excluded) == 1
    gap = replace(
        history,
        bars={"ABC": tuple(b for b in history.bars["ABC"] if b.session != decision)},
    )
    assert rank(gap, "low_volatility", decision)[0] == []


def test_signal_needs_warmup_and_fundamental_strategies_blocked(history):
    assert rank(history, "momentum", date(2023, 3, 1))[0] == []
    with pytest.raises(ResearchError, match="Add SEC fundamentals"):
        rank(history, "value_momentum", date(2024, 8, 30))


def test_engine_uses_following_open_not_decision_close(monkeypatch):
    days = calendar.sessions(date(2025, 1, 6), date(2025, 1, 8))
    bars = (
        Bar("ABC", days[0], *([D(10)] * 4), 1000),
        Bar("ABC", days[1], *([D(20)] * 4), 1000),
        Bar("ABC", days[2], D(20), D(22), D(20), D(22), 1000),
    )
    dataset = Dataset(
        "d", "Gap", "imported", 1, {"ABC": bars}, {"ABC": "A"}, "fixture", "hash"
    )
    monkeypatch.setattr(
        "aperture.backtest.rank", lambda *args: ([RankedStock("ABC", 1, "A")], [])
    )
    result = run(
        dataset,
        "momentum",
        days[0],
        days[-1],
        D(1000),
        Policy(
            positions=1,
            max_weight=D(1),
            sector_cap=D(1),
            cash_reserve=D(0),
            fee_bps=D(0),
            slippage_bps=D(0),
        ),
    )
    assert result["trades"][0]["session"] == str(days[1])
    assert D(result["trades"][0]["price"]) == 20
    assert D(result["curve"][0]["equity"]) == D(result["curve"][1]["equity"]) == 1000
    assert D("1099.99") < D(result["curve"][-1]["equity"]) <= 1100
    assert result["windows"]["All"]["metrics"]["benchmark_return"] is None


def test_backtest_missing_held_price_aborts_not_flatlines(history):
    days = calendar.sessions(date(2024, 8, 1), date(2024, 8, 30))
    broken = replace(
        history,
        bars={"ABC": tuple(b for b in history.bars["ABC"] if b.session != days[-2])},
    )
    with pytest.raises(ResearchError, match="Missing ABC"):
        run(broken, "momentum", days[0], days[-1], D(100000), Policy())


def test_metrics_independent_known_path_and_benchmark_percentage_points():
    curve = [
        {
            "session": str(date(2025, 1, 1) + timedelta(days=i)),
            "equity": str(v),
            "benchmark": str(b),
        }
        for i, (v, b) in enumerate([(100, 100), (120, 110), (90, 105), (110, 108)])
    ]
    metrics = summarize(curve)
    assert metrics["return"] == pytest.approx(0.1)
    assert metrics["drawdown"] == pytest.approx(-0.25)
    assert metrics["difference"] == pytest.approx(0.02)
    assert metrics["volatility"] is None and metrics["cagr"] is None
    periods = windows(curve)
    assert set(periods) == {"1W", "1M", "3M", "6M", "YTD", "1Y", "All"}
    assert periods["1Y"]["limited"] is True
    assert periods["1Y"]["metrics"] == metrics


def test_requested_end_beyond_dataset_rejected(history):
    with pytest.raises(ResearchError, match="coverage"):
        run(
            history, "momentum", date(2024, 8, 1), date(2025, 2, 3), D(100000), Policy()
        )


def test_exact_momentum_horizon_excludes_latest_21_returns():
    days = calendar.sessions(date(2023, 1, 3), date(2024, 6, 28))[-253:]
    rows = tuple(
        Bar("ABC", day, *([D(100) * D("1.001") ** index] * 4), 10000)
        for index, day in enumerate(days)
    )
    dataset = Dataset(
        "d",
        "Known compounding",
        "imported",
        1,
        {"ABC": rows},
        {"ABC": "A"},
        "fixture",
        "hash",
    )
    ranked, excluded = rank(dataset, "momentum", days[-1])
    assert excluded == []
    assert ranked[0].score == pytest.approx(float(D("1.001") ** 231 - 1), abs=1e-12)
    low_vol, _ = rank(dataset, "low_volatility", days[-1])
    assert abs(low_vol[0].score) < 1e-14


def test_full_engine_split_dividend_and_pay_date_preserve_economic_value(monkeypatch):
    days = calendar.sessions(date(2025, 1, 13), date(2025, 1, 17))
    rows = [Bar("ABC", day, *([D(100)] * 4), 1000) for day in days[:2]]
    rows += [
        Bar("ABC", days[2], *([D(49)] * 4), 1000, D(2), D(1), days[3]),
        Bar("ABC", days[3], *([D(49)] * 4), 1000),
        Bar("ABC", days[4], *([D(49)] * 4), 1000),
    ]
    dataset = Dataset(
        "d",
        "Corporate actions",
        "imported",
        1,
        {"ABC": tuple(rows)},
        {"ABC": "A"},
        "fixture",
        "hash",
    )
    monkeypatch.setattr(
        "aperture.backtest.rank", lambda *args: ([RankedStock("ABC", 1, "A")], [])
    )
    result = run(
        dataset,
        "momentum",
        days[0],
        days[-1],
        D(1000),
        Policy(
            positions=1,
            max_weight=D(1),
            sector_cap=D(1),
            cash_reserve=D(0),
            fee_bps=D(0),
            slippage_bps=D(0),
        ),
    )
    assert all(D(row["equity"]) == 1000 for row in result["curve"])
    assert D(result["curve"][2]["receivable"]) > 0
    assert D(result["curve"][3]["receivable"]) == 0
    assert D(result["curve"][3]["cash"]) > D(result["curve"][2]["cash"])
