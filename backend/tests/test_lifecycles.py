from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from aperture import calendar, membership
from aperture.backtest import run
from aperture.coverage import plan
from aperture.domain import Bar, Dataset, Policy, Portfolio
from aperture.lifecycles import terminal_events
from aperture.research_data import security_events

START, END = date(2024, 5, 6), date(2024, 5, 24)
EXIT, EXECUTE = date(2024, 5, 9), date(2024, 5, 13)


def dataset(last_quote=EXECUTE, event=None, reentry=False):
    days = calendar.sessions(date(2023, 1, 3), END)
    prices = {}
    for symbol in ["ABC", "SAFE", "NEW"]:
        prices[symbol] = tuple(
            Bar(
                symbol,
                day,
                *([D(80 if symbol == "ABC" and day < date(2024, 1, 1) else 100)] * 4),
                10000,
            )
            for day in days
            if symbol != "ABC" or day <= last_quote
        )
    rosters = [
        {"effective": "2023-01-03", "symbols": ["ABC", "SAFE"]},
        {"effective": str(EXIT), "symbols": ["SAFE"]},
    ]
    if reentry:
        rosters.append({"effective": "2024-05-20", "symbols": ["ABC", "SAFE"]})
    return Dataset(
        "lifecycle",
        "Captured lifecycle fixture",
        "imported",
        1,
        prices,
        {s: "Industrials" for s in prices},
        "Independent fixture",
        "digest",
        metadata={
            "membership": {
                "kind": "historical",
                "coverage_start": "2023-01-03",
                "coverage_end": str(END),
                "rosters": rosters,
                "additional_symbols": [],
            },
            "input_issues": [],
            "corporate_actions": [event] if event else [],
        },
    )


def coverage(ds, **options):
    return plan(
        ds,
        START,
        END,
        "momentum",
        options.get("dividend_model", "ex_date"),
        "coverage_limited",
        options.get("frequency", "weekly"),
    )


def merger(kind="cash_mergers", **kw):
    return {
        "id": "completed",
        "source": "ABC",
        "effective": str(EXIT),
        "kind": kind,
        "cash": "120",
        "target": None,
        "ratio": "0",
        "pay_date": None,
        **kw,
    }


def simulate(ds, start=START):
    return run(
        ds,
        "momentum",
        start,
        END,
        D(10000),
        Policy(
            positions=1,
            max_weight=D(1),
            sector_cap=D(1),
            cash_reserve=D(0),
            slippage_bps=D(0),
            fee_bps=D(0),
        ),
        dividend_model="ex_date",
        coverage_mode="coverage_limited",
    )


def test_departure_needs_prices_through_ordinary_execution_then_stops():
    ds = dataset()
    audit = coverage(ds)
    assert audit["excluded_count"] == 0
    assert audit["holding_windows"]["ABC"] == [
        {"symbol": "ABC", "start": str(START), "end": str(EXECUTE)}
    ]
    result = simulate(ds)
    abc = [t for t in result["trades"] if t["symbol"] == "ABC"]
    assert [t["session"] for t in abc] == ["2024-05-07", "2024-05-13"]
    assert [t["side"] for t in abc] == ["Buy", "Sell"]
    assert "research_exclusions" not in ds.metadata
    assert "_research_terminal_events" not in ds.metadata
    assert "_research_terminal_events" not in result["input_audit"]


def test_missing_departure_execution_is_not_an_assumed_last_close_sale():
    ds = dataset(date(2024, 5, 10))
    audit = coverage(ds)
    assert audit["excluded_count"] == 1 and audit["excluded"][0]["symbol"] == "ABC"
    assert "2024-05-13" in audit["excluded"][0]["reasons"][0]
    assert coverage(ds, frequency="daily")["excluded_count"] == 0
    assert coverage(ds, frequency="monthly")["excluded_count"] == 1


def test_cash_conversion_uses_contractual_cash_without_a_source_quote():
    ds = dataset(date(2024, 5, 8), merger())
    assert coverage(ds)["excluded_count"] == 0
    assert "ABC" not in membership.eligible(ds, EXIT)
    result = simulate(ds)
    quantity = D(next(t for t in result["trades"] if t["symbol"] == "ABC")["quantity"])
    assert D(
        next(r for r in result["curve"] if r["session"] == str(EXIT))["equity"]
    ) == D(10000) + quantity * D(20)
    assert not any(
        t["symbol"] == "ABC" and t["side"] == "Sell" for t in result["trades"]
    )


def test_merger_recipient_prices_and_action_issues_are_checked_until_exit():
    ds = dataset(
        date(2024, 5, 8),
        merger("stock_and_cash_mergers", target="NEW", ratio="2", cash="20"),
    )
    assert coverage(ds)["excluded_count"] == 0
    missing = replace(
        ds,
        bars={
            **ds.bars,
            "NEW": tuple(b for b in ds.bars["NEW"] if b.session != EXECUTE),
        },
    )
    audit = coverage(missing)
    assert audit["excluded_count"] == 1
    assert any(
        "Merger recipient NEW" in r and str(EXECUTE) in r
        for r in audit["excluded"][0]["reasons"]
    )
    blocked = replace(
        ds,
        metadata={
            **ds.metadata,
            "input_issues": [
                dict(
                    symbol="NEW",
                    start=str(EXIT),
                    end=str(EXIT),
                    kind="identity",
                    reason="Unverified recipient identity",
                )
            ],
        },
    )
    assert "Unverified recipient" in coverage(blocked)["excluded"][0]["reasons"][0]
    result = simulate(ds)
    quantity = D(next(t for t in result["trades"] if t["symbol"] == "ABC")["quantity"])
    assert D(
        next(r for r in result["curve"] if r["session"] == str(EXIT))["equity"]
    ) == D(10000) + quantity * D(120)
    assert any(
        t["symbol"] == "NEW" and t["session"] == str(EXECUTE) and t["side"] == "Sell"
        for t in result["trades"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"cash": "0"},
        {"unpriced_consideration": "CVR"},
        {"kind": "stock_mergers", "target": "", "ratio": "1"},
    ],
)
def test_incomplete_or_contingent_consideration_stays_excluded(change):
    ds = dataset(date(2024, 5, 8), merger(**change))
    assert not terminal_events(ds) and coverage(ds)["excluded_count"] == 1


def test_prices_before_conversion_and_later_reentry_cannot_be_hidden():
    ds = dataset(date(2024, 5, 7), merger())
    assert coverage(ds)["excluded_count"] == 1
    ds = dataset(date(2024, 5, 8), merger(), reentry=True)
    assert not terminal_events(ds) and coverage(ds)["excluded_count"] == 1
    ds = dataset(END, merger())
    assert not terminal_events(ds)


def test_holiday_conversion_is_applied_on_first_exchange_session():
    p = Portfolio(D(0), {"ABC": D(10)})
    security_events(
        p, date(2024, 5, 28), [merger(effective="2024-05-27")], {}, "ex_date"
    )
    assert not p.positions and p.receivables == [(date(2024, 5, 28), D(1200))]


def test_strict_mode_checks_the_identity_of_received_nonmember_shares():
    from aperture.domain import ResearchError

    ds = dataset(
        date(2024, 5, 8), merger("stock_mergers", target="NEW", ratio="1", cash="0")
    )
    ds = replace(
        ds,
        metadata={
            **ds.metadata,
            "input_issues": [
                dict(
                    symbol="NEW",
                    start=str(EXIT),
                    end=str(EXIT),
                    kind="identity",
                    reason="Unknown recipient",
                )
            ],
        },
    )
    with pytest.raises(ResearchError, match="incoming.*NEW"):
        run(
            ds,
            "momentum",
            START,
            END,
            D(10000),
            Policy(positions=1, max_weight=D(1), sector_cap=D(1), cash_reserve=D(0)),
            dividend_model="ex_date",
            coverage_mode="strict",
        )
