from datetime import date
from decimal import Decimal as D

import pytest
from hypothesis import given, settings, strategies as st

from aperture.domain import Bar, Policy, Portfolio, RankedStock, ResearchError
from aperture.ledger import apply_actions, buy, rebalance, sell
from aperture.portfolio import target_weights
from aperture.signals import total_return_levels

DAY = date(2025, 1, 6)


def bar(day=DAY, price="100", **kwargs):
    p = D(price)
    return Bar("ABC", day, p, p, p, p, 1000, **kwargs)


def test_split_and_dividend_entitlement_are_not_cash_until_pay_date():
    p = Portfolio(D(200), {"ABC": D(10)})
    event = bar(price="49", split=D(2), dividend=D(1), pay_date=date(2025, 1, 8))
    apply_actions(p, DAY, {"ABC": event})
    assert p.positions == {"ABC": D(20)}
    assert p.cash == 200
    assert p.receivables == [(date(2025, 1, 8), D(20))]
    assert p.value({"ABC": D(49)}) == 1200  # 200 cash + 980 stock + 20 entitlement
    zero = Policy(fee_bps=D(0), slippage_bps=D(0))
    sell(p, "ABC", D(49), D(20), zero, DAY)
    assert p.cash == 1180 and p.value({}) == 1200  # seller retains entitlement
    apply_actions(p, date(2025, 1, 8), {})
    assert p.cash == 1200 and p.receivables == []


def test_buying_on_ex_date_does_not_receive_dividend():
    p = Portfolio(D(1000))
    event = bar(price="99", dividend=D(1), pay_date=date(2025, 1, 8))
    apply_actions(p, DAY, {"ABC": event})
    buy(p, "ABC", D(99), D(500), Policy(), DAY)
    apply_actions(p, date(2025, 1, 8), {"ABC": bar(date(2025, 1, 8), "99")})
    assert p.receivables == []
    assert p.cash < 501


def test_total_return_index_does_not_double_adjust_split():
    bars = [
        bar(date(2025, 1, 3), "100"),
        bar(price="49", split=D(2), dividend=D(1), pay_date=DAY),
    ]
    assert total_return_levels(bars) == [
        1,
        1,
    ]  # no economic return across 2-for-1 and $1 dividend


def test_unsafe_numeric_price_history_fails_explicitly():
    with pytest.raises(ResearchError, match="unsafe return"):
        total_return_levels([bar(date(2025, 1, 3), "1e-500"), bar(price="1e500")])


def test_missing_held_price_blocks_instead_of_inventing_delisting_exit():
    with pytest.raises(ResearchError, match="cannot be silently removed"):
        apply_actions(Portfolio(D(0), {"ABC": D(10)}), DAY, {})


@given(st.integers(100, 1000000), st.integers(1, 10000), st.integers(0, 500))
@settings(max_examples=80)
def test_buy_then_sell_preserves_cash_and_costs(capital, price, bps):
    p = Portfolio(D(capital))
    policy = Policy(fee_bps=D(bps), slippage_bps=D(bps))
    record = buy(p, "ABC", D(price), D(capital), policy, DAY)
    assert p.cash >= 0
    if record:
        bought = D(record["quantity"])
        sold = sell(p, "ABC", D(price), bought, policy, DAY)
        expected = (
            D(capital)
            - D(record["notional"])
            - D(record["fee"])
            + D(sold["notional"])
            - D(sold["fee"])
        )
        assert p.cash == expected and p.cash <= capital
        assert p.positions == {}


@given(st.integers(1, 70), st.integers(1, 10), st.integers(1, 20), st.integers(5, 50))
def test_target_constraints_never_relax(count, sectors, stock_percent, sector_percent):
    ranked = [
        RankedStock(f"S{i}", -float(i), f"Sector{i % sectors}") for i in range(count)
    ]
    policy = Policy(
        positions=min(count, 100),
        max_weight=D(stock_percent) / 100,
        sector_cap=D(sector_percent) / 100,
    )
    weights, _ = target_weights(ranked, policy)
    assert sum(weights.values()) <= D(".98")
    assert all(0 < w <= policy.max_weight for w in weights.values())
    for sector in range(sectors):
        assert (
            sum(
                weights.get(s.symbol, D(0))
                for s in ranked
                if s.sector == f"Sector{sector}"
            )
            <= policy.sector_cap
        )


def test_infeasible_caps_leave_cash_and_unknown_is_shared_bucket():
    ranked = [RankedStock(f"S{i}", i, "Unknown") for i in range(10)]
    weights, notes = target_weights(ranked, Policy())
    assert sum(weights.values()) == D(".25")
    assert any("75.0%" in note for note in notes)


@pytest.mark.parametrize("research_income", [False, True])
@pytest.mark.parametrize("fees,slippage", [("0", "0"), ("1", "5")])
def test_cash_shortfall_is_shared_by_equal_targets(research_income, fees, slippage):
    p = Portfolio(D(1000))
    if research_income:
        p.research_income_value = D(1000)
    else:
        p.receivables = [(date(2025, 1, 8), D(1000))]
    bars = {s: bar() for s in ("AAA", "ZZZ")}
    policy = Policy(
        max_weight=D(".5"), sector_cap=D(1), fee_bps=D(fees), slippage_bps=D(slippage)
    )
    trades = rebalance(p, {"AAA": D(".49"), "ZZZ": D(".49")}, bars, policy, DAY)
    assert [t["symbol"] for t in trades] == ["AAA", "ZZZ"]
    assert p.positions["AAA"] == p.positions["ZZZ"]
    assert p.cash >= D(2000) * policy.cash_reserve


def test_cash_shortfall_follows_buy_need_not_ticker_order():
    policy = Policy(max_weight=D(1), sector_cap=D(1), fee_bps=D(0), slippage_bps=D(0))

    # Half the basket is an unavailable entitlement; budgets must split 1:3.
    # Renaming the economically larger target cannot change either fill.
    def fill(small, large):
        p = Portfolio(D(1000), receivables=[(date(2025, 1, 8), D(1000))])
        rebalance(
            p,
            {small: D(".245"), large: D(".735")},
            {small: bar(), large: bar()},
            policy,
            DAY,
        )
        return p.positions[small], p.positions[large], p.cash

    a, b, cash = fill("AAA", "ZZZ")
    assert (a, b, cash) == fill("ZZZ", "AAA")
    assert abs((b * 100 + D(".01")) / (a * 100 + D(".01")) - 3) < D(".00001")
    assert cash >= D(40)


@given(st.integers(100, 1000000), st.integers(1, 500))
def test_simulated_rebalance_uses_cash_and_respects_target_caps(capital, price):
    policy = Policy()
    p = Portfolio(D(capital))
    targets = {f"S{i}": D(".04") for i in range(24)}
    bars = {s: Bar(s, DAY, *([D(price)] * 4), 100000) for s in targets}
    rebalance(p, targets, bars, policy, DAY)
    equity = p.value({s: D(price) for s in targets})
    assert p.cash >= D(capital) * policy.cash_reserve
    assert all(q * price / equity <= D(".04") for q in p.positions.values())


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_policy_blocked(value):
    with pytest.raises(ResearchError):
        Policy(max_weight=D(value))
