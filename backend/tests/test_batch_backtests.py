import json

import pytest
from fastapi.testclient import TestClient

from aperture.api import create_app
from aperture.domain import ResearchError
from aperture.ingest import parse_csv
from aperture.worker import process_one
from test_storage_api import CSV, HEADER


@pytest.fixture
def batch(tmp_path):
    app = create_app(tmp_path / "batch.sqlite3", None)
    dataset, raw, warnings = parse_csv(CSV, "Captured inputs", "Independent fixture")
    app.state.store.save_dataset(dataset, raw, warnings)
    payload = {
        "dataset_id": dataset.id,
        "strategy_ids": ["momentum", "low_volatility"],
        "start": "2025-01-06",
        "end": "2025-01-07",
        "capital": "123456",
        "coverage_mode": "coverage_limited",
        "dividend_model": "ex_date",
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
        json={**payload, "strategy_ids": ["low_volatility", "momentum", "momentum"]},
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


@pytest.mark.parametrize(
    "change",
    [
        {"strategy_ids": []},
        {"strategy_ids": ["momentum", "unknown"]},
        {"strategy_ids": ["momentum", "value_momentum"]},
        {"dataset_id": "deleted"},
        {"start": "2024-01-01"},
        {"capital": "NaN"},
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
