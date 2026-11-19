from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from aperture.api import create_app
from aperture.domain import ResearchError
from aperture.ingest import parse_csv
from aperture.research_cleanup import inventory
from aperture.store import Store, encode, now
from aperture.workspace_reset import CONFIRMATION, preview, reset
from test_research_cleanup import CSV, HEADER, result


@pytest.fixture
def workspace(tmp_path):
    store = Store(tmp_path / "reset.sqlite3")
    dataset, raw, warnings = parse_csv(CSV, "Research prices", "Reset test")
    store.save_dataset(dataset, raw, warnings)
    return store, dataset


def test_workspace_reset_protects_paper_history_and_hides_its_input_snapshots(
    workspace,
):
    store, research = workspace
    paper_observation = store.observe(
        "alpaca-paper", "daily-equity-and-activities", b'{"equity":100}'
    )
    required_observation = store.observe(
        "alpaca", "paper-source-bar", b"source used by plan"
    )
    removed_observation = store.observe("sec", "research-filing", b"discarded source")
    store.observe(
        "alpaca", "https://paper-api.alpaca.markets/v2/assets/ABC?{}", b"stock identity"
    )
    store.save_filing_evidence("filing-proof", {"value": 10}, [removed_observation])
    store.set_preference("annual-facts-v1:123", {"signature": "cached"})
    store.set_preference("watchlist", {"symbols": ["ABC"]})
    store.set_preference("paper_performance", {"curve": [{"equity": "100"}]})
    store.save_membership(
        {"id": "confirmed", "kind": "current", "captured_at": now()}, b"paper roster"
    )
    store.save_membership(
        {"id": "old", "kind": "historical", "captured_at": now()}, b"research roster"
    )
    parent = replace(research, id="price-parent", digest="parent-digest")
    store.save_dataset(parent, b"paper prices", [])
    audited = replace(
        research,
        id="paper-input",
        digest="paper-digest",
        metadata={
            "price_dataset_id": parent.id,
            "previous_dataset_id": research.id,
            "observation_ids": [required_observation],
        },
    )
    store.save_dataset(audited, b"paper fundamentals", [])
    result_id, job_id = result(store, research)
    paper_job = store.enqueue("paper_prepare", {})
    store.finish(
        paper_job, {"dataset_id": audited.id, "observation_id": paper_observation}
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO paper_plans VALUES (?,?,?,?,?,?)",
            (
                "plan",
                now(),
                now(),
                "complete",
                "fixture",
                encode({"dataset_id": audited.id, "membership_id": "confirmed"}),
            ),
        )
        db.execute(
            "INSERT INTO paper_orders VALUES (?,?,?,?,?,?,?)",
            ("client", "plan", "ABC", "buy", "filled", "{}", now()),
        )
        db.execute(
            "INSERT INTO paper_approvals VALUES (?,?,?,?,?,?)",
            ("approval", now(), "hash", "fixture", "{}", None),
        )
        db.execute(
            "INSERT INTO paper_events(created_at,message) VALUES (?,?)",
            (now(), "Order filled"),
        )
        db.execute(
            "INSERT INTO protocols VALUES (?,?,?,?)", ("study", now(), "{}", "locked")
        )
        db.execute(
            "INSERT INTO trials VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "trial",
                "study",
                job_id,
                "Test",
                "development",
                "complete",
                now(),
                '{"start":"2025-01-06","end":"2025-01-07"}',
                None,
            ),
        )
        audit_before = {
            t: [tuple(r) for r in db.execute(f"SELECT * FROM {t}")]
            for t in ("paper_plans", "paper_orders", "paper_approvals", "paper_events")
        }
    plan = preview(store)
    assert plan["counts"]["datasets"] == 1
    assert plan["counts"]["observations"] == 2
    assert plan["retained_paper_inputs"] == {"datasets": 2, "memberships": 1}
    assert reset(store, plan["fingerprint"], CONFIRMATION)["deleted"] == plan["counts"]
    assert store.datasets() == []
    assert inventory(store) == {"items": []}
    assert store.dataset(audited.id) == audited
    assert store.dataset(parent.id) == parent
    assert store.membership("current") is None
    assert store.membership("current", include_paper=True)["id"] == "confirmed"
    assert store.membership("current", "confirmed")["id"] == "confirmed"
    assert store.membership("historical") is None
    assert store.preference("watchlist") == {"symbols": ["ABC"]}
    assert store.preference("paper_performance") == {"curve": [{"equity": "100"}]}
    assert [j["id"] for j in store.jobs()] == [paper_job["id"]]
    assert store.cached("alpaca-paper", "daily-equity-and-activities", 300)[0] == {
        "equity": 100
    }
    assert store.preference("annual-facts-v1:123") is None
    assert store.filing_evidence("filing-proof") is None
    with pytest.raises(ResearchError, match="not found"):
        store.result(result_id)
    with pytest.raises(ResearchError, match="no longer available"):
        store.enqueue(
            "backtest",
            {"dataset_id": audited.id, "start": "2025-01-06", "end": "2025-01-07"},
        )
    with store.connect() as db:
        for table, rows in audit_before.items():
            assert [tuple(row) for row in db.execute(f"SELECT * FROM {table}")] == rows
        assert {r[0] for r in db.execute("SELECT id FROM observations")} == {
            paper_observation,
            required_observation,
        }
        assert {r[0] for r in db.execute("SELECT id FROM research_exposures")} == {
            job_id,
            "trial",
        }
        assert not db.execute("SELECT 1 FROM protocols").fetchone()
        assert not db.execute("SELECT 1 FROM trials").fetchone()
    assert not preview(store)["has_changes"]
    assert store.save_dataset(audited, b"explicit reimport", [])["already_imported"]
    assert [d["id"] for d in store.datasets()] == [audited.id]


def test_workspace_reset_server_requires_confirmation_and_a_fresh_idle_preview(
    workspace,
):
    store, dataset = workspace
    with TestClient(create_app(store.path, None)) as client:
        path = "/api/workspace/reset"
        first = client.get(path + "-preview").json()
        payload = {"fingerprint": first["fingerprint"], "confirmation": CONFIRMATION}
        assert client.post(path, json=payload).status_code == 403
        assert (
            client.post(
                path, headers=HEADER, json={**payload, "confirmation": "RESET"}
            ).status_code
            == 422
        )
        job = store.enqueue("download", {})
        blocked = client.get(path + "-preview").json()
        assert blocked["blockers"]
        assert (
            client.post(
                path,
                headers=HEADER,
                json={**payload, "fingerprint": blocked["fingerprint"]},
            ).status_code
            == 422
        )
        store.fail(job["id"], "Fixture failed")
        stale = client.post(path, headers=HEADER, json=payload)
        assert stale.status_code == 422 and "fresh preview" in stale.json()["detail"]
        assert store.dataset(dataset.id) == dataset
        last = client.get(path + "-preview").json()
        updated = client.post(
            path, headers=HEADER, json={**payload, "fingerprint": last["fingerprint"]}
        )
        assert updated.status_code == 200, updated.text
        assert client.get("/api/state").json()["datasets"] == []
        with store.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM content_blobs").fetchone()[0] == 0
