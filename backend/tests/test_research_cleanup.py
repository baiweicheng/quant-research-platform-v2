import hashlib
import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from aperture.api import create_app
from aperture.domain import ResearchError
from aperture.experiments import create, enqueue, protocol
from aperture.ingest import parse_csv
from aperture.research_cleanup import preview, delete, inventory
from aperture.store import Store, encode, now
from test_experiments import experiment as base_experiment

HEADER = {"X-Aperture-Client": "1"}
CSV = "symbol,date,open,high,low,close,volume\nABC,2025-01-06,100,100,100,100,10000\nABC,2025-01-07,100,100,100,100,10000\n"


@pytest.fixture
def experiment(tmp_path):
    return base_experiment.__wrapped__(tmp_path)


@pytest.fixture
def saved(tmp_path):
    store = Store(tmp_path / "cleanup.sqlite3")
    ds, raw, warnings = parse_csv(CSV, "Prices", "Explicit fixture")
    store.save_dataset(ds, raw, warnings)
    return store, ds


def result(store, dataset, kind="backtest"):
    job = store.enqueue(
        kind,
        {
            "dataset_id": dataset.id,
            "start": "2025-01-06",
            "end": "2025-01-07",
            "strategy_id": "momentum",
        },
    )
    store.finish(
        job,
        {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "start": "2025-01-06",
            "end": "2025-01-07",
            "strategy": {"id": "momentum", "name": "Momentum"},
        },
    )
    with store.connect() as db:
        return db.execute(
            "SELECT result_id FROM jobs WHERE id=?", (job["id"],)
        ).fetchone()[0], job["id"]


def remove(store, targets):
    p = preview(store, targets)
    return delete(store, targets, p["fingerprint"])


def test_delete_result_and_task_preserves_inputs_and_exposure(saved):
    store, ds = saved
    rid, jid = result(store, ds)
    remove(store, [{"kind": "result", "id": rid}])
    assert store.dataset(ds.id) == ds
    assert not store.jobs()
    with pytest.raises(ResearchError, match="not found"):
        store.result(rid)
    with store.connect() as db:
        assert db.execute(
            "SELECT start,end FROM research_exposures WHERE id=?", (jid,)
        ).fetchone()[:] == ("2025-01-06", "2025-01-07")


def test_dataset_cascade_keeps_other_vintages_and_shared_blocks_exact(saved):
    store, ds = saved
    child = replace(
        ds, id="child", digest="child-digest", metadata={"price_dataset_id": ds.id}
    )
    other = replace(ds, id="other", digest="other-digest", name="Other prices")
    store.save_dataset(child, b"child", [])
    store.save_dataset(other, b"other", [])
    result(store, child)
    with store.connect() as db:
        body = bytes(
            db.execute("SELECT body FROM datasets WHERE id='other'").fetchone()[0]
        )
    targets = [{"kind": "dataset", "id": ds.id}]
    p = preview(store, targets)
    assert p["counts"] == {"dataset": 2, "result": 1, "job": 1}
    delete(store, targets, p["fingerprint"])
    assert store.dataset("other") == other
    assert len(store.datasets()) == 1
    with store.connect() as db:
        assert (
            hashlib.sha256(
                db.execute("SELECT body FROM datasets WHERE id='other'").fetchone()[0]
            ).digest()
            == hashlib.sha256(body).digest()
        )


def test_preview_changes_are_rechecked_atomically(saved):
    store, ds = saved
    targets = [{"kind": "dataset", "id": ds.id}]
    p = preview(store, targets)
    result(store, ds)
    with pytest.raises(ResearchError, match="changed"):
        delete(store, targets, p["fingerprint"])
    assert store.dataset(ds.id) == ds
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM results").fetchone()[0] == 1


def test_newer_independent_snapshot_survives_deleting_older_lineage(saved):
    store, ds = saved
    latest = replace(
        ds,
        id="latest",
        digest="latest-digest",
        metadata={
            "sector_parent_dataset_id": ds.id,
            "update": {"parent_dataset_id": ds.id},
        },
    )
    store.save_dataset(latest, b"new-vintage", [])
    rid, _ = result(store, latest, "review")
    remove(store, [{"kind": "dataset", "id": ds.id}])
    assert store.dataset(latest.id) == latest
    assert store.result(rid)["dataset_id"] == latest.id


def test_bulk_preview_unions_dependencies_and_deletes_once(saved):
    store, ds = saved
    rid, jid = result(store, ds, "review")
    targets = [{"kind": "result", "id": rid}, {"kind": "job", "id": jid}]
    assert preview(store, targets)["counts"] == {"result": 1, "job": 1}
    remove(store, targets)
    assert store.dataset(ds.id) == ds and not store.jobs()


def test_cleanup_retains_shared_filing_audit_until_its_last_snapshot_is_deleted(saved):
    from aperture.filing_classes import expand_metadata

    store, ds = saved
    proof = [{"accession": "dated-fixture", "compatible": True}]
    digest = store.capture_source(json.dumps(proof).encode())
    other = replace(
        ds,
        id="audited",
        digest="audited",
        metadata={
            "fundamentals": {
                "coverage": [{"symbol": "ABC", "filed_share_classes_digest": digest}]
            }
        },
    )
    store.save_dataset(other, b"prices", [])
    remove(store, [{"kind": "dataset", "id": ds.id}])
    assert (
        expand_metadata(store, store.dataset(other.id).metadata)["fundamentals"][
            "coverage"
        ][0]["filed_share_classes"]
        == proof
    )
    remove(store, [{"kind": "dataset", "id": other.id}])
    with store.connect() as db:
        assert (
            db.execute(
                "SELECT 1 FROM content_blobs WHERE digest=?", (digest,)
            ).fetchone()
            is None
        )


def test_running_and_queued_jobs_block_dataset_delete(saved):
    store, ds = saved
    targets = [{"kind": "dataset", "id": ds.id}]
    store.enqueue("review", {"dataset_id": ds.id})
    p = preview(store, targets)
    assert p["blockers"]
    with pytest.raises(ResearchError, match="background work"):
        delete(store, targets, p["fingerprint"])
    assert store.dataset(ds.id) == ds


def test_dataset_needed_by_paper_audit_cannot_be_deleted(saved):
    store, ds = saved
    with store.connect() as db:
        db.execute(
            "INSERT INTO paper_plans VALUES (?,?,?,?,?,?)",
            ("p", now(), now(), "complete", "", encode({"dataset_id": ds.id})),
        )
    targets = [{"kind": "dataset", "id": ds.id}]
    p = preview(store, targets)
    assert p["blockers"]
    with pytest.raises(ResearchError, match="paper trading plan"):
        delete(store, targets, p["fingerprint"])
    assert store.dataset(ds.id) == ds


def test_delete_validation_preserves_prior_exposure_and_consumed_state(experiment):
    store, ds, data = experiment
    p = create(store, data)
    development = enqueue(store, p["id"], "development")
    with store.connect() as db:
        db.execute("UPDATE jobs SET state='complete' WHERE id=?", (development["id"],))
    holdout = enqueue(store, p["id"], "holdout", True)
    with store.connect() as db:
        db.execute("UPDATE jobs SET state='failed' WHERE id=?", (holdout["id"],))
    # Deleting the failed evaluation never unlocks a consumed protocol.
    remove(store, [{"kind": "job", "id": holdout["id"]}])
    assert protocol(store, p["id"])["holdout_state"] == "released"
    with pytest.raises(ResearchError, match="already been released"):
        enqueue(store, p["id"], "holdout", True)
    remove(store, [{"kind": "protocol", "id": p["id"]}])
    fresh = create(store, data)
    assert fresh["holdout_label"] == "Previously explored period"
    assert holdout["id"] in fresh["prior_exposures"]


def test_locked_protocol_preview_explains_retirement(experiment):
    store, ds, data = experiment
    p = create(store, data)
    targets = [{"kind": "protocol", "id": p["id"]}]
    assert preview(store, targets)["locked_protocols"] == 1
    remove(store, targets)
    assert not store.results("validation")


def test_api_requires_local_header_and_preview_and_supports_bulk(saved):
    store, ds = saved
    rid, _ = result(store, ds, "review")
    with TestClient(create_app(store.path, None)) as client:
        targets = [{"kind": "result", "id": rid}]
        assert (
            client.post("/api/research/delete", json={"targets": targets}).status_code
            == 403
        )
        assert (
            client.post(
                "/api/research/delete", json={"targets": targets}, headers=HEADER
            ).status_code
            == 422
        )
        p = client.post(
            "/api/research/deletion-preview", json={"targets": targets}, headers=HEADER
        ).json()
        assert (
            client.post(
                "/api/research/delete",
                json={"targets": targets, "fingerprint": p["fingerprint"]},
                headers=HEADER,
            ).status_code
            == 200
        )
        assert (
            client.get("/api/research/library").json()["items"][0]["category"]
            == "Datasets"
        )
        assert (
            client.post(
                "/api/tasks/review",
                json={"dataset_id": ds.id, "strategy_id": "momentum"},
                headers=HEADER,
            ).status_code
            == 202
        )


def test_paper_jobs_and_results_are_protected_even_with_direct_request(saved):
    store, ds = saved
    job = store.enqueue("paper_sync", {})
    store.finish(job, {})
    with store.connect() as db:
        rid = db.execute(
            "SELECT result_id FROM jobs WHERE id=?", (job["id"],)
        ).fetchone()[0]
    assert not any(i["kind"] == "job" for i in inventory(store)["items"])
    for target in [{"kind": "job", "id": job["id"]}, {"kind": "result", "id": rid}]:
        p = preview(store, [target])
        assert p["blockers"]
        with pytest.raises(ResearchError, match="paper|Paper"):
            delete(store, [target], p["fingerprint"])
