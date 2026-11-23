from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pytest
from aperture import calendar, periodic_income
from aperture.domain import (
    Bar,
    Dataset,
    Policy,
    RankedStock,
    ResearchError,
    paper_strategy,
)
from aperture.earnings_tracker import EarningsTracker, _select, _weights
from aperture.market_capture import EarningsMarketCapture, market_capture


def test_periodic_pairs_use_one_original_accession_and_override_stale_income():
    accession = "0000000001-24-000001"
    base = {"accn": accession, "form": "10-Q", "filed": "2024-05-01"}
    rows = [
        dict(base, start="2024-01-01", end="2024-03-31", val=12),
        dict(base, start="2023-01-01", end="2023-03-31", val=10),
        dict(
            base,
            form="10-Q/A",
            filed="2024-06-01",
            start="2024-01-01",
            end="2024-03-31",
            val=99,
        ),
    ]
    company = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": rows}}}}}
    subs = {
        "filings": {
            "recent": {
                "form": ["10-Q"],
                "accessionNumber": ["0000000001-24-000002"],
                "filingDate": ["2024-08-01"],
                "reportDate": ["2024-06-30"],
            }
        }
    }
    current, missing = periodic_income.normalize(company, subs)
    assert (
        current.income == 12
        and current.previous == 10
        and current.growth == pytest.approx(2 / 12)
    )
    assert missing.income is None and missing.filed == date(2024, 8, 1)
    rows[1]["accn"] = "0000000001-24-000003"
    assert all(r.income is None for r in periodic_income.normalize(company, subs))


@pytest.mark.parametrize(
    ("strategy_id", "model"),
    [
        ("earnings_reaction_tracker", EarningsTracker),
        ("earnings_market_capture", EarningsMarketCapture),
    ],
)
def test_weekly_income_uses_only_completed_prices_and_public_filings(
    strategy_id, model
):
    days = calendar.sessions(date(2023, 1, 3), date(2024, 2, 2))
    day = days[-1]
    prev = days[-2]
    bars = {
        s: tuple(Bar(s, d, *([Decimal(100 + i)] * 4), 1000) for i, d in enumerate(days))
        for s in ("A", "SPY")
    }
    report = periodic_income.IncomeReport(
        day - timedelta(days=9),
        "old",
        "10-Q",
        date(2023, 12, 31),
        date(2023, 10, 1),
        date(2022, 10, 1),
        date(2022, 12, 31),
        "NetIncomeLoss",
        110,
        100,
    )
    filed_today = replace(report, filed=day, accession="future", income=-110)
    ds = Dataset(
        "id",
        "test",
        "imported",
        1,
        bars,
        {"A": "Tech"},
        "test",
        "digest",
        annual_income={
            "A": [
                {
                    "end": "2022-12-31",
                    "available_at": "2023-02-01",
                    "accession": "annual",
                    "cik": "1",
                }
            ]
        },
        periodic_income={"1": [report, filed_today]},
    )
    tracker = model(ds)
    ranked, _, targets, _, audit = tracker.decision(day, Policy())
    assert ranked[0].components["accession"] == "old" and targets == {
        "A": Decimal(".05")
    }
    assert audit["factors"]["periodic_net_income"]["positive"] == 1
    unavailable = replace(
        bars["A"][-2], available_at=calendar.available_time(day) + timedelta(days=1)
    )
    ds = replace(ds, bars={**bars, "A": (*bars["A"][:-2], unavailable, bars["A"][-1])})
    assert not model(ds).decision(prev, Policy())[2]
    assert not model(ds).decision(day, Policy())[2]
    with pytest.raises(ResearchError, match="research only"):
        paper_strategy(strategy_id)


def test_market_capture_measures_relative_returns_in_both_benchmark_tails():
    market = np.array([-0.045, -0.035, -0.025, -0.015, 0.015, 0.025, 0.035, 0.045])
    resilient = np.array([0.01, 0.03, 0.1, 0.1, 0.1, 0.1, -0.03, -0.01])
    offensive = np.array([-0.01, -0.03, -0.1, -0.1, -0.1, -0.1, 0.03, 0.01])
    weak, strong = market_capture(
        market, market[:, None] + np.column_stack((resilient, offensive))
    )
    assert weak == pytest.approx([0.02, -0.02])
    assert strong == pytest.approx([-0.02, 0.02])


def test_tracking_selection_and_weights_respect_identity_and_binding_caps():
    rng = np.random.default_rng(12)
    r = rng.normal(0, 0.01, (252, 20))
    issuer = np.array([str(i // 2) for i in range(20)])
    sectors = np.array(["A"] * 15 + ["B"] * 5)
    tilts = np.linspace(-0.04, 0.04, 20)
    chosen = _select(r[-126:], tilts, sectors, issuer, np.zeros(20, bool), 25)
    assert (
        len(set(issuer[chosen])) == len(chosen)
        and list(sectors[chosen]).count("A") == 6
    )
    names = [RankedStock(str(i), float(tilts[i]), str(sectors[i])) for i in chosen]
    policy = Policy(max_weight=Decimal(".15"), sector_cap=Decimal(".6"))
    targets, _ = _weights(names, r[:, chosen], tilts[chosen], policy)
    assert (
        sum(targets.values()) <= 1 - policy.cash_reserve
        and max(targets.values()) <= policy.max_weight
    )
    assert all(
        sum(targets.get(s.symbol, 0) for s in names if s.sector == g)
        <= policy.sector_cap
        for g in ("A", "B")
    )


def test_reviewed_succession_uses_first_new_filing_and_rejects_later_predecessor():
    from types import SimpleNamespace

    def filing(day, accession):
        return periodic_income.IncomeReport(
            date.fromisoformat(day), accession, "10-Q", date(2024, 3, 31)
        )

    ds = SimpleNamespace(
        metadata={
            "fundamentals": {
                "coverage": [
                    {
                        "symbol": "A",
                        "cik": "2",
                        "predecessor_issuers": [
                            {
                                "cik": "1",
                                "effective": "2024-05-01",
                                "valid_before": "2024-05-01",
                            }
                        ],
                    }
                ]
            }
        },
        periodic_income={
            "1": [filing("2024-04-25", "old"), filing("2024-05-10", "wrong")],
            "2": [filing("2024-04-30", "premature"), filing("2024-05-06", "new")],
        },
    )
    tracker = object.__new__(EarningsTracker)
    tracker.succession = periodic_income.succession_histories(ds)
    assert tracker._report("A", date(2024, 4, 29), None)[1].accession == "old"
    assert tracker._report("A", date(2024, 5, 6), None)[1] is None
    assert tracker._report("A", date(2024, 5, 13), None)[1].accession == "new"


def test_original_statement_requires_matching_pinned_issuer_and_filing_metadata():
    company = {"cik": 831001}
    recent = {
        "form": ["10-Q"],
        "accessionNumber": ["0000831001-26-000045"],
        "filingDate": ["2026-08-06"],
        "reportDate": ["2026-06-30"],
    }
    sub = {"filings": {"recent": recent}}
    (report,) = periodic_income.normalize(company, sub)
    assert report.income == 11616000000 and report.previous == 8083000000
    assert report.source_url.endswith("c-20260630.htm") and report.prior_end == date(
        2025, 6, 30
    )
    assert periodic_income.normalize({"cik": 1}, sub)[0].income is None
    assert periodic_income.normalize(company) == []


def test_common_shareholder_income_fallback_matches_both_periods_on_one_basis():
    accession = "0000000001-24-000002"
    tag = "NetIncomeLossAvailableToCommonStockholdersBasic"
    current = {
        "accn": accession,
        "form": "10-Q",
        "filed": "2024-05-02",
        "start": "2024-01-01",
        "end": "2024-03-31",
        "val": 20,
    }
    previous = {**current, "start": "2023-01-01", "end": "2023-03-31", "val": 15}
    facts = {
        "NetIncomeLoss": {"units": {"USD": [{**current, "val": 22}]}},
        tag: {"units": {"USD": [current, previous]}},
    }
    company = {"facts": {"us-gaap": facts}}
    (report,) = periodic_income.normalize(company)
    assert (report.concept, report.income, report.previous) == (tag, 20, 15)
    facts[tag]["units"]["USD"].remove(previous)
    assert periodic_income.normalize(company)[0].income is None
