import json
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from aperture import calendar
from aperture.api import create_app
from aperture.backtest import run
from aperture.domain import Bar, Dataset, Policy, ResearchError
from aperture.ingest import parse_csv
from aperture.worker import process_one
from fastapi.testclient import TestClient
from test_storage_api import CSV, HEADER


@pytest.fixture
def batch(tmp_path):
    app = create_app(tmp_path / "batch.sqlite3", None)
    dataset, raw, warnings = parse_csv(CSV, "Captured inputs", "Independent fixture")
    dataset = replace(
        dataset,
        metadata={"fundamentals": {"annual_income_count": 1}},
        annual_income={"ABC": [{"net_income": "120"}]},
    )
    app.state.store.save_dataset(dataset, raw, warnings)
    payload = {
        "dataset_id": dataset.id,
        "strategy_ids": ["momentum", "profitable_liquidity_leaders"],
        "start": "2025-01-06",
        "end": "2025-01-07",
        "capital": "123456",
        "coverage_mode": "coverage_limited",
        "dividend_model": "ex_date",
        "cost_profile": "higher",
    }
    return app, TestClient(app), payload


def test_one_submission_keeps_common_inputs_and_saves_independent_results(batch):
    app, client, payload = batch
    response = client.post("/api/tasks/backtests", json=payload, headers=HEADER)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert accepted["count"] == 2
    assert len({j["id"] for j in accepted["jobs"]}) == 2
    for job, identifier in zip(accepted["jobs"], payload["strategy_ids"]):
        assert job["kind"] == "backtest"
        assert json.loads(job["payload"]) == {
            **{k: v for k, v in payload.items() if k != "strategy_ids"},
            "strategy_id": identifier,
        }
    repeated = client.post(
        "/api/tasks/backtests",
        json={
            **payload,
            "strategy_ids": ["profitable_liquidity_leaders", "momentum", "momentum"],
        },
        headers=HEADER,
    ).json()
    assert {j["id"] for j in repeated["jobs"]} == {j["id"] for j in accepted["jobs"]}
    assert len(app.state.store.jobs()) == 2
    assert {j["strategy_id"] for j in app.state.store.jobs()} == set(
        payload["strategy_ids"]
    )
    assert all("payload" not in j for j in app.state.store.jobs())
    assert process_one(app.state.store) and process_one(app.state.store)
    assert all(j["state"] == "complete" for j in app.state.store.jobs())
    results = app.state.store.results("backtest")
    assert {r["strategy"]["id"] for r in results} == set(payload["strategy_ids"])
    assert all(r["dataset_id"] == payload["dataset_id"] for r in results)
    for result in results:
        saved = app.state.store.result(result["id"])
        assert saved["policy"]["cost_model"] == "liquidity-v1"
        assert saved["policy"]["slippage_bps"] == "15"


@pytest.mark.parametrize(
    "change",
    [
        {"strategy_ids": []},
        {"strategy_ids": ["momentum", "unknown"]},
        {"strategy_ids": ["momentum", "value_momentum"]},
        {"dataset_id": "deleted"},
        {"start": "2024-01-01"},
        {"capital": "NaN"},
        {"cost_profile": "invalid"},
        {"end": "2025-01-06"},
    ],
)
def test_invalid_selection_queues_nothing(batch, change):
    app, client, payload = batch
    r = client.post("/api/tasks/backtests", json={**payload, **change}, headers=HEADER)
    assert r.status_code == 422
    assert app.state.store.jobs() == []


def test_transaction_rolls_back_earlier_tasks_when_a_later_input_disappears(batch):
    app, _, payload = batch
    task = {k: v for k, v in payload.items() if k != "strategy_ids"}
    task["strategy_id"] = "momentum"
    with pytest.raises(ResearchError, match="no longer available"):
        app.state.store.enqueue_many(
            "backtest", [task, {**task, "dataset_id": "removed"}]
        )
    assert app.state.store.jobs() == []


@pytest.mark.parametrize("fixed_list", [False, True])
def test_strict_reports_supplement_or_custom_decision_gap_without_blocking(fixed_list):
    days = calendar.sessions(date(2024, 1, 2), date(2025, 2, 4))
    decision, end = days[-2:]
    meta = (
        {"custom_symbols": ["AAA", "BBB"]}
        if fixed_list
        else {
            "membership": {
                "kind": "historical",
                "coverage_start": str(days[0]),
                "coverage_end": str(end),
                "rosters": [{"effective": str(days[0]), "symbols": ["AAA"]}],
                "additional_symbols": ["BBB"],
            }
        }
    )
    ds = Dataset(
        "test",
        "Supplement gap",
        "imported",
        1,
        {
            name: tuple(
                Bar(name, day, *([D(10 + i * inc)] * 4), 10_000)
                for i, day in enumerate(days)
            )
            for name, inc in (("AAA", 1), ("BBB", 2))
        },
        {"AAA": "A", "BBB": "B"},
        "fixture",
        "digest",
        meta,
    )
    clean = run(ds, "momentum", decision, end, D(1000), Policy(positions=1))
    assert set(clean["decisions"][0]["targets"]) == {"BBB"}
    assert not clean["coverage"]["decision_exclusions"]
    gapped = replace(
        ds,
        bars={
            **ds.bars,
            "BBB": tuple(b for b in ds.bars["BBB"] if b.session != decision),
        },
    )
    report = run(gapped, "momentum", decision, end, D(1000), Policy(positions=1))
    assert set(report["decisions"][0]["targets"]) == {"AAA"}
    assert report["coverage"]["excluded_count"] == 0  # No whole-run exclusions.
    assert report["coverage"]["decision_scope"] == (
        "fixed_list" if fixed_list else "supplemental"
    )
    assert report["coverage"]["decision_exclusions"] == [
        {
            "symbol": "BBB",
            "reason": "Needs 253 complete sessions available by this decision.",
            "decisions": 1,
            "first": str(decision),
            "last": str(decision),
        }
    ]
