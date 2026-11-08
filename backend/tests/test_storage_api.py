import pytest
from fastapi.testclient import TestClient

from aperture import __version__
from aperture.api import create_app
from aperture.domain import ResearchError
from aperture.ingest import parse_csv
from aperture.store import Store
from aperture.worker import process_one

CSV = "symbol,date,open,high,low,close,volume,sector\nABC,2025-01-06,100,102,99,101,10000,Industrials\nABC,2025-01-07,101,103,100,102,12000,Industrials\n"
HEADER = {"X-Aperture-Client": "1"}


def test_atomic_idempotent_import_and_restart(tmp_path):
    path = tmp_path / "db.sqlite"
    store = Store(path)
    dataset, raw, warnings = parse_csv(CSV, "Prices", "Independent fixture")
    saved = store.save_dataset(dataset, raw, warnings)
    duplicate = store.save_dataset(dataset, raw, warnings)
    assert duplicate["already_imported"] is True
    restarted = Store(path)
    assert len(restarted.datasets()) == 1
    assert restarted.dataset(saved["id"]) == dataset


@pytest.mark.parametrize(
    "csv, message",
    [
        (CSV + CSV.splitlines()[1] + "\n", "Duplicate"),
        (CSV.replace("2025-01-06", "2025-01-05"), "completed US equity session"),
        (CSV.replace(",102,99,", ",90,99,"), "OHLC"),
        (CSV.replace(",100,102,", ",NaN,102,"), "finite"),
        ("a,b\n1,2\n", "CSV needs"),
        (CSV.replace(",10000,", ",-1,"), "volume"),
        (CSV.replace("volume,sector", "volume,close"), "unique"),
        (
            CSV.replace("10000,Industrials", "10000,Industrials,extra"),
            "number of values",
        ),
        ('"unclosed', "header could not be parsed"),
    ],
)
def test_invalid_rows_are_actionable_and_not_saved(csv, message):
    with pytest.raises(ResearchError, match=message):
        parse_csv(csv, "Prices", "fixture")


def test_dividends_require_pay_dates():
    text = "symbol,date,open,high,low,close,volume,dividend\nABC,2025-01-06,99,99,99,99,1000,1\n"
    with pytest.raises(ResearchError, match="pay date"):
        parse_csv(text, "Dividend", "fixture")


def test_ambiguous_or_late_availability_not_assumed_known():
    text = (
        CSV.replace("volume,sector", "volume,sector,available_at")
        .replace("10000,Industrials", "10000,Industrials,2025-01-06T21:14:00Z")
        .replace("12000,Industrials", "12000,Industrials,2025-01-07T21:15:00Z")
    )
    with pytest.raises(ResearchError, match="cannot precede"):
        parse_csv(text, "Timing", "fixture")


def test_review_staleness_fails_in_worker_without_publishing_plan(tmp_path):
    store = Store(tmp_path / "test.sqlite")
    dataset, raw, warnings = parse_csv(CSV, "Old prices", "fixture")
    store.save_dataset(dataset, raw, warnings)
    store.enqueue("review", {"dataset_id": dataset.id, "strategy_id": "momentum"})
    process_one(store)
    assert store.jobs()[0]["state"] == "failed"
    assert "Import updated data" in store.jobs()[0]["message"]
    assert store.results("review") == []


def test_jobs_duplicate_safe_failure_recovery_and_result_persistence(tmp_path):
    store = Store(tmp_path / "test.sqlite")
    with pytest.raises(ResearchError, match="no longer available"):
        store.enqueue("review", {"dataset_id": "missing", "strategy_id": "momentum"})
    dataset, raw, warnings = parse_csv(CSV, "Old prices", "fixture")
    store.save_dataset(dataset, raw, warnings)
    one = store.enqueue("review", {"dataset_id": dataset.id, "strategy_id": "momentum"})
    assert (
        store.enqueue("review", {"strategy_id": "momentum", "dataset_id": dataset.id})[
            "id"
        ]
        == one["id"]
    )
    process_one(store)
    assert store.jobs()[0]["state"] == "failed"
    assert store.results("review") == []
    two = store.enqueue("practice", {})
    store.claim()
    store.recover()
    assert next(j for j in store.jobs() if j["id"] == two["id"])["state"] == "failed"


def test_api_boundaries_and_real_background_backtest(tmp_path):
    app = create_app(tmp_path / "app.sqlite", None)
    with TestClient(app) as client:
        assert client.get("/api/state").json()["runs"] == []
        assert client.post("/api/practice").status_code == 403
        assert (
            client.get("/api/state", headers={"host": "evil.example"}).status_code
            == 400
        )
        body = {
            "name": "Fixture",
            "source": "Hand-created",
            "price_basis": "as_traded",
            "csv": CSV,
        }
        response = client.post("/api/datasets", json=body, headers=HEADER)
        assert response.status_code == 201, response.text
        identifier = response.json()["id"]
        payload = {
            "dataset_id": identifier,
            "strategy_id": "momentum",
            "start": "2025-01-06",
            "end": "2025-01-07",
            "capital": "100000",
        }
        response = client.post("/api/tasks/backtest", json=payload, headers=HEADER)
        assert response.status_code == 202, response.text
        assert len(client.get("/api/state").json()["jobs"]) == 1
        assert process_one(app.state.store)
        state = client.get("/api/state").json()
        assert state["jobs"][0]["state"] == "complete"
        result = client.get(f"/api/results/{state['runs'][0]['id']}").json()
        assert result["trade_count"] == 0  # warm-up absent, not manufactured
        assert result["engine_version"] == __version__
        assert result["input_contract"] == "as-traded-v1"
        assert result["windows"]["All"]["metrics"]["return"] == 0
        assert result["notes"]
        assert (
            client.post(
                "/api/tasks/backtest",
                json={**payload, "strategy_id": "value_momentum"},
                headers=HEADER,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/tasks/backtest",
                json={**payload, "capital": "NaN"},
                headers=HEADER,
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/datasets",
                json={**body, "price_basis": "adjusted"},
                headers=HEADER,
            ).status_code
            == 422
        )


def test_screen_projections_preserve_full_export_and_dated_audit(tmp_path):
    from aperture.presentation import dataset_view

    app = create_app(tmp_path / "presentation.sqlite3")
    client = TestClient(app)
    store = app.state.store
    source = {
        "id": "data",
        "metadata": {
            "input_issues": [{"symbol": "OLD", "reason": "Unverified"}],
            "membership": {
                "mode": "historical",
                "historical": {"rosters": ["large"]},
                "additional_symbols": ["ABC"],
            },
            "identity_resolution": {"ABC": {"reviewed_alias": "PRE", "raw": "large"}},
            "coverage": [{"symbol": "ABC", "reason": "captured coverage"}],
            "fundamentals": {
                "coverage": [],
                "observation_ids": ["captured-source"],
                "source_hashes": {"ABC": "exact-fingerprint"},
            },
        },
    }
    assert (
        dataset_view({"metadata": {"membership": None}})["metadata"]["membership"]
        is None
    )
    assert dataset_view({"metadata": None})["metadata"] == {}
    brief = dataset_view(source)
    assert "input_issues" not in brief["metadata"]
    assert "historical" not in brief["metadata"]["membership"]
    assert brief["metadata"]["coverage"] == source["metadata"]["coverage"]
    assert source["metadata"]["input_issues"]  # Never mutate the capture.
    assert "observation_ids" not in brief["metadata"]["fundamentals"]
    assert "source_hashes" not in brief["metadata"]["fundamentals"]
    assert (
        source["metadata"]["fundamentals"]["source_hashes"]["ABC"]
        == "exact-fingerprint"
    )
    body = {
        "curve": [],
        "trades": [{"sequence": i} for i in range(100)],
        "trade_count": 100,
        "input_audit": source,
        "decisions": [
            {
                "session": "2026-11-04",
                "eligible": 1,
                "signals": [{"symbol": "ABC"}],
                "exclusions": [{"symbol": "OLD", "reason": "Missing data"}],
            }
        ],
    }
    job = store.enqueue("download", {})
    store.finish(job, body)
    identifier = store.jobs()[0]["result_id"]
    full = client.get(f"/api/results/{identifier}").json()
    view = client.get(f"/api/results/{identifier}?view=true").json()
    assert len(view["trades"]) == 50 and view["trade_count"] == 100
    assert view["trades"] == full["trades"][-50:]
    assert "input_audit" not in view and "signals" not in view["decisions"][0]
    assert (
        client.get(f"/api{view['audit_path']}/decisions/2026-11-04").json()
        == full["decisions"][0]
    )
    assert (
        client.get(f"/api{view['audit_path']}/decisions/2026-11-03").status_code == 422
    )
    export = client.get(f"/api/results/{identifier}?download=true")
    assert "attachment" in export.headers["content-disposition"]
    assert export.json() == full


def test_queuing_sec_refresh_uses_summary_without_loading_full_price_history(
    tmp_path, monkeypatch
):
    from aperture.config import Settings

    path = tmp_path / "queue.sqlite3"
    store = Store(path)
    dataset, raw, warnings = parse_csv(CSV, "Prices", "fixture")
    store.save_dataset(dataset, raw, warnings)
    monkeypatch.setattr(
        "aperture.api.settings", lambda: Settings(sec_agent="test test@example.com")
    )
    monkeypatch.setattr(
        Store,
        "dataset",
        lambda *a: pytest.fail("A UI queue action loaded the full price history"),
    )
    response = TestClient(create_app(path)).post(
        f"/api/fundamentals/{dataset.id}", headers=HEADER
    )
    assert response.status_code == 202
    assert store.jobs()[0]["kind"] == "fundamentals"
