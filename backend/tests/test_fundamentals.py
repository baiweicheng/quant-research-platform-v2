from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from aperture import calendar
from aperture.api import create_app
from aperture.backtest import run
from aperture.domain import Bar, Dataset, Policy, ResearchError
from aperture.fundamentals import as_of, attach, filing_available, inputs, normalize
from aperture.signals import rank
from aperture.store import Store
from aperture.worker import process_one
from filing_fixtures import cover, evidence

CIK = "0000000001"
ACC = "0000000001-23-000001"


def fact(value, *, instant=False, **extra):
    return {
        "val": value,
        "start": "2022-01-01",
        "end": "2022-12-31",
        "filed": "2023-02-10",
        "accn": ACC,
        "form": "10-K",
        **({"start": None} if instant else {}),
        **extra,
    }


def source():
    values = {
        "Assets": fact(200, instant=True),
        "Revenues": fact(100),
        "CostOfRevenue": fact(60),
        "EarningsPerShareDiluted": fact(4),
    }
    return {
        "cik": 1,
        "facts": {
            "us-gaap": {
                tag: {
                    "units": {
                        "USD/shares" if tag == "EarningsPerShareDiluted" else "USD": [
                            value
                        ]
                    }
                }
                for tag, value in values.items()
            }
        },
    }


def statements(company=None, tickers=None):
    company = company or source()
    return normalize(
        "ABC",
        CIK,
        company,
        {"tickers": tickers or ["ABC"], "entityType": "operating"},
        evidence(company, multi=bool(tickers and len(tickers) > 1)),
    )[0]


@pytest.fixture
def dataset():
    days = calendar.sessions(date(2022, 1, 3), date(2024, 8, 30))
    bars = tuple(
        Bar("ABC", day, *([D(100) + D(i) / 10] * 4), 10000)
        for i, day in enumerate(days)
    )
    return Dataset(
        "base",
        "Prices",
        "imported",
        1,
        {"ABC": bars},
        {"ABC": "A"},
        "Fixture",
        "prices",
        fundamentals={"ABC": statements()},
    )


def test_exact_units_and_matched_annual_filing_period():
    company = source()
    gaap = company["facts"]["us-gaap"]
    gaap["Assets"]["units"]["USD"].append(fact(999, instant=True, end="2021-12-31"))
    gaap["Revenues"]["units"]["USD"].append(fact(999, start="2022-10-01"))
    gaap["GrossProfit"] = {"units": {"EUR": [fact(999)]}}
    rows = statements(company)
    assert len(rows) == 1
    assert rows[0].assets == 200 and rows[0].gross_profit == 40 and rows[0].eps == 4
    # A cost from another accession must not be subtracted from this revenue.
    gaap["CostOfRevenue"]["units"]["USD"][0]["accn"] = "0000000001-23-000002"
    assert all(row.gross_profit is None for row in statements(company))


def test_ambiguous_fact_is_excluded_without_fallback_to_a_favorable_tag():
    company = source()
    company["facts"]["us-gaap"]["GrossProfit"] = {
        "units": {"USD": [fact(40), fact(80)]}
    }
    row = statements(company)[0]
    assert row.gross_profit is None
    assert any("Conflicting GrossProfit" in issue for issue in row.issues)


def test_filing_date_is_not_same_day_and_amendment_is_not_retroactive():
    company = source()
    original = statements(company)[0]
    assert as_of((original,), date(2023, 2, 10)) is None
    assert as_of((original,), date(2023, 2, 13)) == original
    assert filing_available(date(2025, 7, 3)) == calendar.available_time(
        date(2025, 7, 7)
    )
    for tag, value in company["facts"]["us-gaap"].items():
        unit = next(iter(value["units"]))
        item = value["units"][unit][0]
        value["units"][unit].append(
            {
                **item,
                "val": item["val"] * 2,
                "filed": "2023-03-01",
                "accn": "0000000001-23-000002",
                "form": "10-K/A",
            }
        )
    revised = statements(company)
    assert as_of(revised, date(2023, 2, 28)) == original
    assert as_of(revised, date(2023, 3, 1)) == original
    assert as_of(revised, date(2023, 3, 2)).eps == 8
    assert as_of(revised, date(2024, 8, 30)) is None  # stale fiscal end


def test_split_units_use_only_known_post_filing_actions(dataset):
    decision = date(2023, 8, 31)
    changed = replace(
        dataset,
        bars={
            "ABC": tuple(
                replace(b, split=D(2))
                if b.session == date(2023, 6, 1)
                else replace(b, split=D(10))
                if b.session == date(2024, 1, 2)
                else b
                for b in dataset.bars["ABC"]
            )
        },
    )
    values, reason = inputs(changed, "ABC", decision)
    assert reason is None and values["eps_asof"] == 2
    assert values["earnings_yield"] == D(2) / next(
        b.close for b in changed.bars["ABC"] if b.session == decision
    )
    truncated = replace(
        changed,
        bars={
            "ABC": tuple(
                b for b in changed.bars["ABC"] if b.session >= date(2023, 3, 1)
            )
        },
    )
    values, _ = inputs(truncated, "ABC", decision)
    assert (
        "earnings_yield" not in values and "history after" in values["valuation_issue"]
    )


def test_multiclass_does_not_apply_entity_eps_to_arbitrary_share_class(dataset):
    rows = statements(tickers=["ABC", "ABC.B"])
    assert rows[0].eps is None and rows[0].gross_profit == 40
    changed = replace(dataset, fundamentals={"ABC": rows})
    assert len(rank(changed, "quality", date(2023, 8, 31))[0]) == 1
    assert rank(changed, "value_momentum", date(2023, 8, 31))[0] == []


def test_hybrid_requires_both_inputs_and_future_facts_do_not_change_past(dataset):
    decision = date(2023, 8, 31)
    original = rank(dataset, "value_momentum", decision)
    assert len(original[0]) == 1
    future = replace(
        statements()[0],
        filed=date(2024, 2, 1),
        available_at=filing_available(date(2024, 2, 1)),
        eps=D(999),
        accession="0000000001-24-000001",
    )
    changed = replace(dataset, fundamentals={"ABC": (*statements(), future)})
    assert rank(changed, "value_momentum", decision) == original
    negative = replace(
        dataset, fundamentals={"ABC": (replace(statements()[0], eps=D(-1)),)}
    )
    assert rank(negative, "value_momentum", decision)[0] == []
    missing = replace(dataset, fundamentals={})
    with pytest.raises(ResearchError, match="Add SEC"):
        rank(missing, "quality", decision)


def test_percentile_blend_has_average_ties_and_no_single_factor_fallback(dataset):
    decision = date(2023, 8, 31)
    bars = {
        symbol: tuple(replace(b, symbol=symbol) for b in dataset.bars["ABC"])
        for symbol in ("AAA", "BBB", "CCC", "DDD")
    }
    fundamentals = {
        symbol: (
            replace(statements()[0], symbol=symbol, gross_profit=D(gross), eps=D(eps)),
        )
        for symbol, gross, eps in [
            ("AAA", 80, 2),
            ("BBB", 40, 4),
            ("CCC", 40, 4),
            ("DDD", 90, -1),
        ]
    }
    changed = replace(dataset, bars=bars, fundamentals=fundamentals)
    ranked, excluded = rank(changed, "quality_value", decision)
    assert [r.symbol for r in ranked] == ["AAA", "BBB", "CCC"]
    assert (
        ranked[0].score == 0.5 and ranked[2].score == 0.5
    )  # tied combined ranks, lexical tie break
    assert ranked[1].components["percentiles"] == {
        "profitability": 0.25,
        "earnings_yield": 0.75,
    }
    assert excluded[0]["symbol"] == "DDD"


class FixtureProvider:
    observations = ["public-fixture-observation"]

    def get(self, provider, url, **kwargs):
        if "tickers_exchange" in url:
            return {"fields": ["cik", "ticker"], "data": [[1, "ABC"]]}
        if "submissions" in url:
            return {
                "cik": 1,
                "tickers": ["ABC"],
                "entityType": "operating",
                "filings": {
                    "recent": {
                        "accessionNumber": [ACC],
                        "filingDate": ["2023-02-10"],
                        "primaryDocument": ["annual.htm"],
                    }
                },
            }
        return deepcopy(source())

    def document(self, url):
        return cover()


def test_enrichment_is_immutable_idempotent_and_worker_results_serialize(
    dataset, tmp_path
):
    store = Store(tmp_path / "db.sqlite")
    base = replace(dataset, fundamentals={})
    store.save_dataset(base, b"prices", [])
    saved = attach(store, base.id, lambda *args: None, FixtureProvider())
    enriched = store.dataset(saved["id"])
    assert store.dataset(base.id).fundamentals == {}
    assert enriched.fundamentals == dataset.fundamentals
    assert attach(store, enriched.id, lambda *args: None, FixtureProvider())[
        "already_imported"
    ]
    assert len(store.datasets()) == 2
    row = saved["metadata"]["fundamentals"]["coverage"][0]
    assert (
        "filed_share_classes" not in row
        and len(row["filed_share_classes_digest"]) == 64
    )
    with TestClient(create_app(store.path, None)) as client:
        screen = client.get("/api/state").json()
        screen_row = next(d for d in screen["datasets"] if d["id"] == saved["id"])[
            "metadata"
        ]["fundamentals"]["coverage"][0]
        assert "filed_share_classes" not in screen_row
        exported = client.get(f"/api/datasets/{saved['id']}/metadata").json()
        proof = exported["metadata"]["fundamentals"]["coverage"][0][
            "filed_share_classes"
        ][0]
        assert proof["accession"] == ACC and proof["compatible"]
    store.enqueue(
        "backtest",
        {
            "dataset_id": enriched.id,
            "strategy_id": "value_momentum",
            "start": "2023-08-01",
            "end": "2023-09-29",
            "capital": "100000",
        },
    )
    assert process_one(store)
    assert store.jobs()[0]["state"] == "complete", store.jobs()[0]["message"]
    result = store.result(store.results("backtest")[0]["id"])
    assert (
        result["decisions"][0]["signals"][0]["components"]["filing"]["accession"] == ACC
    )
    assert result["input_audit"]["price_dataset_id"] == base.id
    with TestClient(create_app(store.path, None)) as client:
        native = client.get(f"/api/results/{result['id']}?download=true").json()
        assert native["input_audit"]["fundamentals"]["coverage"][0][
            "filed_share_classes"
        ][0]["compatible"]


def test_future_filings_do_not_change_historical_backtest(dataset):
    decision_end = date(2023, 9, 29)
    future = replace(
        statements()[0],
        filed=date(2024, 1, 1),
        available_at=filing_available(date(2024, 1, 1)),
        eps=D(999),
    )
    changed = replace(dataset, fundamentals={"ABC": (*statements(), future)})
    before = run(
        dataset, "quality_value", date(2023, 8, 1), decision_end, D(100000), Policy()
    )
    after = run(
        changed, "quality_value", date(2023, 8, 1), decision_end, D(100000), Policy()
    )
    assert before["curve"] == after["curve"] and before["trades"] == after["trades"]


def test_api_fundamental_queue_gates_and_end_to_end(monkeypatch, tmp_path, dataset):
    from sector_fixtures import stub_sectors

    stub_sectors(monkeypatch)
    monkeypatch.setenv("SEC_USER_AGENT", "Aperture test contact@example.com")
    app = create_app(tmp_path / "db.sqlite", None)
    base = replace(dataset, fundamentals={})
    app.state.store.save_dataset(base, b"prices", [])
    monkeypatch.setattr(
        "aperture.fundamentals.attach",
        lambda store, identifier, progress, **kw: attach(
            store, identifier, progress, FixtureProvider(), **kw
        ),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/fundamentals/base", headers={"X-Aperture-Client": "1"}
        )
        assert response.status_code == 202
        assert process_one(app.state.store)
        assert app.state.store.jobs()[0]["state"] == "complete"
        datasets = client.get("/api/state").json()["datasets"]
        assert len(datasets) == 3
        assert datasets[0]["metadata"]["sector_classification"]["classified_count"] == 1


def test_old_price_gap_blocks_valuation_even_when_signal_warmup_is_complete(dataset):
    decision = date(2023, 8, 31)
    changed = replace(
        dataset,
        bars={
            "ABC": tuple(
                b for b in dataset.bars["ABC"] if b.session != date(2023, 3, 1)
            )
        },
    )
    assert len(rank(changed, "quality", decision)[0]) == 1
    ranked, excluded = rank(changed, "quality_value", decision)
    assert not ranked and "split units cannot be verified" in excluded[0]["reason"]


def test_staleness_boundary_and_quarterly_eps_are_not_annual(dataset):
    row = statements()[0]
    from datetime import timedelta

    boundary = row.end + timedelta(days=550)
    session = calendar.sessions(boundary - timedelta(days=5), boundary)[-1]
    assert as_of((row,), session) is not None
    assert as_of((row,), calendar.next_session(boundary)) is None
    company = source()
    company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0][
        "start"
    ] = "2022-10-01"
    assert all(s.eps is None for s in statements(company))


def test_same_version_conflicting_annual_durations_are_not_arbitrarily_selected():
    row = statements()[0]
    conflicting = replace(row, start=date(2022, 1, 15))
    assert as_of((row, conflicting), date(2023, 8, 31)) is None


def test_no_supported_statements_does_not_publish_a_partial_snapshot(dataset, tmp_path):
    class EmptyProvider(FixtureProvider):
        def get(self, provider, url, **kwargs):
            result = super().get(provider, url, **kwargs)
            if "companyfacts" in url:
                result["facts"] = {"ifrs-full": {}}
            return result

    store = Store(tmp_path / "db.sqlite")
    base = replace(dataset, fundamentals={})
    store.save_dataset(base, b"prices", [])
    with pytest.raises(ResearchError, match="No supported annual SEC"):
        attach(store, base.id, lambda *args: None, EmptyProvider())
    assert len(store.datasets()) == 1 and store.dataset(base.id).fundamentals == {}


def test_unsafe_factor_ratio_aborts_instead_of_saving_nonfinite_scores(dataset):
    changed = replace(
        dataset,
        fundamentals={
            "ABC": (replace(statements()[0], gross_profit=D("1e400"), assets=D(1)),)
        },
    )
    with pytest.raises(ResearchError, match="unsafe factor ratio"):
        rank(changed, "quality", date(2023, 8, 31))
