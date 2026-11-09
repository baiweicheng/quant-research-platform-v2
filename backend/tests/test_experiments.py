from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from aperture import calendar
from aperture.api import create_app
from aperture.backtest import run
from aperture.domain import Bar, Dataset, Policy, ResearchError
from aperture.experiments import create, enqueue, history, protocol, trial
from aperture.store import Store
from aperture.worker import process_one
from fastapi.testclient import TestClient

HEADER = {"X-Aperture-Client": "1"}


@pytest.fixture
def experiment(tmp_path):
    store = Store(tmp_path / "research.sqlite")
    days = calendar.sessions(date(2022, 1, 3), date(2025, 1, 10))
    rows = tuple(
        Bar(
            "ABC",
            d,
            *([D(100) + D(i) / 10] * 4),
            10000,
            available_at=calendar.available_time(d),
        )
        for i, d in enumerate(days)
    )
    ds = Dataset(
        "d",
        "Known path",
        "imported",
        1,
        {"ABC": rows},
        {"ABC": "A"},
        "Independent fixture",
        "fixture",
    )
    store.save_dataset(ds, b"fixture", [])
    payload = {
        "name": "Frozen study",
        "hypothesis": "Persistent momentum should survive higher costs.",
        "dataset_id": "d",
        "strategy_id": "momentum",
        "start": "2023-02-01",
        "holdout_start": "2024-08-01",
        "end": "2025-01-10",
        "capital": "100000",
    }
    return store, ds, payload


def test_protocol_dates_frozen_disjoint_folds_and_fingerprint(experiment):
    store, ds, data = experiment
    p = create(store, data)
    assert p["source_digest"] == ds.digest and p["strategy"]["version"] == "1.0.0"
    assert p["holdout_state"] == "locked" and p["prior_exposures"] == []
    assert len(p["fingerprint"]) == 64
    assert p["folds"][0]["train_end"] < p["folds"][0]["start"]
    assert all(a["end"] < b["start"] for a, b in zip(p["folds"], p["folds"][1:]))
    assert p["folds"][-1]["end"] < p["holdout_start"]
    assert protocol(Store(store.path), p["id"]) == p


def test_holdout_guards_other_snapshots_and_all_api_backtests(experiment):
    store, _, data = experiment
    p = create(store, data)
    with pytest.raises(ResearchError, match="locked holdout"):
        store.enqueue(
            "backtest",
            {
                "dataset_id": "different",
                "strategy_id": "low_volatility",
                "start": "2024-09-01",
                "end": "2024-10-01",
            },
        )
    app = create_app(store.path, None)
    with TestClient(app) as c:
        r = c.post(
            "/api/tasks/backtest",
            json={k: data[k] for k in ("dataset_id", "strategy_id", "start", "end")},
            headers=HEADER,
        )
        assert r.status_code == 422 and "locked holdout" in r.json()["detail"]
        batch = c.post(
            "/api/tasks/backtests",
            json={
                "dataset_id": data["dataset_id"],
                "strategy_ids": ["momentum", "low_volatility"],
                "start": data["start"],
                "end": data["end"],
            },
            headers=HEADER,
        )
        assert batch.status_code == 422 and "locked holdout" in batch.json()["detail"]
        assert store.jobs() == []
    assert protocol(store, p["id"])["holdout_state"] == "locked"


def test_existing_failed_and_pending_attempts_disclose_exposure(experiment):
    store, _, data = experiment
    old = store.enqueue(
        "backtest",
        {
            "dataset_id": "d",
            "strategy_id": "momentum",
            "start": "2024-09-01",
            "end": "2025-01-10",
        },
    )
    p = create(store, data)
    assert p["prior_exposures"] == [old["id"]]
    assert p["holdout_label"] == "Previously explored period"


def test_insufficient_periods_or_fundamentals_rejected(experiment):
    store, _, data = experiment
    for changes in (
        {"holdout_start": "2025-01-01"},
        {"start": "2024-05-01"},
        {"end": "2026-01-01"},
        {"strategy_id": "value_momentum"},
        {"capital": "NaN"},
    ):
        with pytest.raises(ResearchError):
            create(store, {**data, **changes})


def test_validation_results_trials_once_only_and_restart(experiment):
    store, _, data = experiment
    p = create(store, data)
    with pytest.raises(ResearchError, match="Complete development"):
        enqueue(store, p["id"], "holdout", True)
    enqueue(store, p["id"], "development")
    with pytest.raises(ResearchError, match="already has"):
        enqueue(store, p["id"], "development")
    assert process_one(store)
    assert store.jobs()[0]["state"] == "complete", store.jobs()
    trials = history(store, p["id"])
    assert len(trials) == 8 and all(t["state"] == "complete" for t in trials)
    baseline = trial(store, trials[0]["id"])
    assert baseline["source_digest"] == "fixture"
    assert all(d["session"] < p["holdout_start"] for d in baseline["decisions"])
    stressed = next(t for t in trials if t["label"].startswith("Higher costs"))
    assert (
        stressed["metrics"]["return"] < baseline["windows"]["All"]["metrics"]["return"]
    )
    with pytest.raises(ResearchError, match="Acknowledge"):
        enqueue(store, p["id"], "holdout")
    enqueue(store, p["id"], "holdout", True)
    assert protocol(Store(store.path), p["id"])["holdout_state"] == "released"
    with pytest.raises(ResearchError, match="already has"):
        enqueue(store, p["id"], "holdout", True)
    process_one(store)
    assert len(history(store, p["id"])) == 9
    with pytest.raises(ResearchError, match="already been released"):
        enqueue(store, p["id"], "holdout", True)
    with pytest.raises(ResearchError, match="Further tuning"):
        enqueue(store, p["id"], "development")


def test_failed_trial_and_interruption_remain_in_registry(experiment, monkeypatch):
    store, _, data = experiment
    p = create(store, data)

    def fail(*args, **kwargs):
        raise ResearchError("Missing held-stock price.")

    monkeypatch.setattr("aperture.experiments.run", fail)
    enqueue(store, p["id"], "development")
    process_one(store)
    assert history(store)[0]["state"] == "failed"
    assert "Missing held-stock" in history(store)[0]["error"]
    with pytest.raises(ResearchError, match="no completed"):
        trial(store, history(store)[0]["id"])
    with store.connect() as db:
        db.execute("UPDATE trials SET state='running'")
    store.recover()
    assert history(store)[0]["state"] == "interrupted"


def test_future_final_data_cannot_change_development(experiment):
    store, ds, data = experiment
    p = create(store, data)
    enqueue(store, p["id"], "development")
    process_one(store)
    first = [trial(store, t["id"]) for t in history(store)]
    changed = replace(
        ds,
        id="changed",
        digest="changed",
        bars={
            "ABC": tuple(
                replace(b, open=D(9999), high=D(9999), low=D(9999), close=D(9999))
                if str(b.session) >= p["holdout_start"]
                else b
                for b in ds.bars["ABC"]
            )
        },
    )
    store.save_dataset(changed, b"changed", [])
    original_run = run(
        ds,
        "momentum",
        date.fromisoformat(p["start"]),
        date.fromisoformat(p["development_end"]),
        D(100000),
        Policy(),
    )
    changed_run = run(
        changed,
        "momentum",
        date.fromisoformat(p["start"]),
        date.fromisoformat(p["development_end"]),
        D(100000),
        Policy(),
    )
    assert original_run["curve"] == changed_run["curve"]
    assert original_run["decisions"] == changed_run["decisions"]
    # Same locked protocol can rerun development, but its immutable input stays fixed.
    enqueue(store, p["id"], "development")
    process_one(store)
    again = [trial(store, t["id"]) for t in history(store)[8:]]
    assert [r["curve"] for r in first] == [r["curve"] for r in again]
    assert [r["decisions"] for r in first] == [r["decisions"] for r in again]


def test_retire_unlocks_dates_without_deleting_evidence(experiment):
    from aperture.experiments import retire

    store, _, data = experiment
    p = create(store, data)
    assert retire(store, p["id"])["holdout_state"] == "retired"
    store.enqueue("backtest", {"start": "2024-09-01", "end": "2024-10-01"})
    assert protocol(store, p["id"])["fingerprint"] == p["fingerprint"]
    with pytest.raises(ResearchError, match="Further tuning"):
        enqueue(store, p["id"], "development")
