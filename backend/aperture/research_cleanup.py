"""Previewed, transactional deletion of generated research, never broker audit."""

import hashlib
import json
import gzip

from .domain import ResearchError
from .store import decode

KINDS = {"dataset", "result", "protocol", "job"}
TABLES = {
    "dataset": "datasets",
    "result": "results",
    "protocol": "protocols",
    "job": "jobs",
    "trial": "trials",
}


def inventory(store):
    with store.connect() as db:
        items = []
        protocol_names = {}
        for row in db.execute(
            "SELECT id,kind,created_at,summary FROM results ORDER BY created_at DESC"
        ):
            if row["kind"] not in {"backtest", "review"}:
                continue
            s = json.loads(row["summary"])
            items.append(
                {
                    "kind": "result",
                    "id": row["id"],
                    "category": "Backtests"
                    if row["kind"] == "backtest"
                    else "Allocation reviews",
                    "name": s.get("strategy", {}).get("name", row["kind"]),
                    "detail": f"{s.get('dataset_name', '')} · {s.get('start', s.get('decision_session', ''))}",
                    "created_at": row["created_at"],
                }
            )
        for row in db.execute("SELECT id,summary FROM datasets ORDER BY rowid DESC"):
            s = json.loads(row["summary"])
            items.append(
                {
                    "kind": "dataset",
                    "id": row["id"],
                    "category": "Datasets",
                    "name": s["name"],
                    "detail": f"{'Market + SEC' if s.get('metadata', {}).get('fundamentals') else 'Practice data' if s['kind'] == 'synthetic' else 'Price inputs'} · {s['start']} – {s['end']} · {s['row_count']:,} rows",
                    "created_at": s["created_at"],
                }
            )
        for row in db.execute(
            "SELECT id,body,created_at FROM protocols ORDER BY created_at DESC"
        ):
            p = json.loads(row["body"])
            protocol_names[row["id"]] = p["name"]
            items.append(
                {
                    "kind": "protocol",
                    "id": row["id"],
                    "category": "Validation protocols",
                    "name": p["name"],
                    "detail": p.get("dataset_name", ""),
                    "created_at": row["created_at"],
                }
            )
        for row in db.execute(
            "SELECT * FROM jobs WHERE state IN ('complete','failed') ORDER BY created_at DESC"
        ):
            if row["kind"].startswith("paper_") or row["kind"] == "connection":
                continue
            payload = json.loads(row["payload"])
            items.append(
                {
                    "kind": "job",
                    "id": row["id"],
                    "category": "Validation runs"
                    if row["kind"] == "validation"
                    else "Task history",
                    "name": f"{protocol_names.get(payload.get('protocol_id'), 'Validation')} · {payload.get('phase', 'research')} evaluation"
                    if row["kind"] == "validation"
                    else row["kind"].replace("_", " ").title(),
                    "detail": row["message"],
                    "created_at": row["created_at"],
                }
            )
    return {"items": items}


def _plan(db, targets):
    selected = {kind: set() for kind in TABLES}
    for target in targets:
        kind, identifier = target["kind"], target["id"]
        if kind not in KINDS:
            raise ResearchError("Choose a saved research item.")
        table = TABLES[kind]
        if not db.execute(
            f"SELECT 1 FROM {table} WHERE id=?", (identifier,)
        ).fetchone():
            raise ResearchError(
                "An item has already been deleted. Refresh the workspace."
            )
        selected[kind].add(identifier)
    datasets = {
        r["id"]: json.loads(r["summary"])
        for r in db.execute("SELECT id,summary FROM datasets")
    }
    results = {
        r["id"]: dict(r) for r in db.execute("SELECT id,kind,summary FROM results")
    }
    protocols = {
        r["id"]: {**json.loads(r["body"]), "holdout_state": r["holdout_state"]}
        for r in db.execute("SELECT * FROM protocols")
    }
    jobs = {
        r["id"]: {**dict(r), "payload": json.loads(r["payload"])}
        for r in db.execute("SELECT * FROM jobs")
    }
    trials = {
        r["id"]: dict(r)
        for r in db.execute(
            "SELECT id,protocol_id,job_id,state,summary,label FROM trials"
        )
    }
    # A complete snapshot requires its price parent for SEC refresh. Other
    # lineage IDs are provenance only: newer self-contained vintages can remain.
    while True:
        before = {k: set(v) for k, v in selected.items()}
        for identifier, s in datasets.items():
            meta = s.get("metadata", {})
            parents = {meta.get("price_dataset_id")}
            if parents & selected["dataset"]:
                selected["dataset"].add(identifier)
        for identifier, p in protocols.items():
            if p["dataset_id"] in selected["dataset"]:
                selected["protocol"].add(identifier)
        for identifier, r in results.items():
            s = json.loads(r["summary"])
            if s.get("dataset_id") in selected["dataset"]:
                selected["result"].add(identifier)
        for identifier, j in jobs.items():
            payload = j["payload"]
            if (
                payload.get("dataset_id") in selected["dataset"]
                or payload.get("protocol_id") in selected["protocol"]
                or j["result_id"] in selected["result"]
            ):
                selected["job"].add(identifier)
            if identifier in selected["job"] and j["result_id"]:
                selected["result"].add(j["result_id"])
        for identifier, t in trials.items():
            if (
                t["protocol_id"] in selected["protocol"]
                or t["job_id"] in selected["job"]
            ):
                selected["trial"].add(identifier)
        if selected == before:
            break
    blockers = []
    if any(
        results.get(i, {}).get("kind", "").startswith("paper_")
        or results.get(i, {}).get("kind") == "connection"
        for i in selected["result"]
    ):
        blockers.append("Paper/account records cannot be deleted from research.")
    for identifier in selected["job"]:
        j = jobs[identifier]
        if j["kind"].startswith("paper_") or j["kind"] == "connection":
            blockers.append("This selection includes protected paper/account records.")
        if j["state"] in {"running", "queued"}:
            blockers.append(
                "Wait for the selected background work to finish before deleting it."
            )
    if selected["dataset"]:
        if any(j["state"] in {"queued", "running"} for j in jobs.values()):
            blockers.append(
                "Wait for background work to finish before deleting datasets."
            )
        for row in db.execute("SELECT body FROM paper_plans"):
            p = decode(row[0])
            if p.get("dataset_id") in selected["dataset"]:
                blockers.append(
                    "A selected dataset supports a retained paper trading plan. Its broker audit must be preserved."
                )
        for row in db.execute("SELECT value FROM preferences WHERE key LIKE 'paper_%'"):

            def references(value):
                if isinstance(value, dict):
                    return any(
                        (k.endswith("dataset_id") and v in selected["dataset"])
                        if isinstance(v, str)
                        else references(v)
                        for k, v in value.items()
                    )
                return isinstance(value, list) and any(references(v) for v in value)

            if references(json.loads(row[0])):
                blockers.append(
                    "A selected dataset is still needed by the paper workspace."
                )
    items = []
    for kind, identifiers in selected.items():
        for identifier in sorted(identifiers):
            if kind == "dataset":
                name = datasets[identifier]["name"]
            elif kind == "protocol":
                name = protocols[identifier]["name"]
            elif kind == "result":
                r = results.get(identifier)
                if not r:
                    continue
                s = json.loads(r["summary"])
                name = s.get("strategy", {}).get("name", r["kind"].replace("_", " "))
            elif kind == "trial":
                name = trials[identifier]["label"]
            else:
                name = jobs[identifier]["kind"].replace("_", " ")
            items.append({"kind": kind, "id": identifier, "name": name})
    counts = {k: len(v) for k, v in selected.items() if v}
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "items": items,
                "blockers": sorted(set(blockers)),
                "states": {j: jobs[j]["updated_at"] for j in selected["job"]},
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "items": items,
        "counts": counts,
        "blockers": sorted(set(blockers)),
        "fingerprint": fingerprint,
        "requested_count": len(targets),
        "locked_protocols": sum(
            protocols[p]["holdout_state"] == "locked" for p in selected["protocol"]
        ),
    }, selected


def preview(store, targets):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        return _plan(db, targets)[0]


def delete(store, targets, fingerprint):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        plan, selected = _plan(db, targets)
        if plan["fingerprint"] != fingerprint:
            raise ResearchError(
                "Related research changed. Review a fresh deletion preview before confirming."
            )
        if plan["blockers"]:
            raise ResearchError(" ".join(plan["blockers"]))
        # Deleting a report must never turn an already explored period unseen.
        for identifier in selected["job"]:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            p = json.loads(row["payload"])
            start, end = p.get("start"), p.get("end")
            if row["kind"] == "validation":
                owner = db.execute(
                    "SELECT body FROM protocols WHERE id=?", (p.get("protocol_id"),)
                ).fetchone()
                if owner:
                    owner = json.loads(owner[0])
                    start = (
                        owner["holdout_start"]
                        if p.get("phase") == "holdout"
                        else owner["start"]
                    )
                    end = (
                        owner["end"]
                        if p.get("phase") == "holdout"
                        else owner["development_end"]
                    )
            if row["kind"] in {"backtest", "validation"} and start and end:
                db.execute(
                    "INSERT OR IGNORE INTO research_exposures VALUES (?,?,?,?,?)",
                    (identifier, row["kind"], start, end, row["created_at"]),
                )
        for identifier in selected["trial"]:
            row = db.execute(
                "SELECT summary,created_at FROM trials WHERE id=?", (identifier,)
            ).fetchone()
            s = json.loads(row[0])
            if s.get("start") and s.get("end"):
                db.execute(
                    "INSERT OR IGNORE INTO research_exposures VALUES (?,?,?,?,?)",
                    (identifier, "trial", s["start"], s["end"], row[1]),
                )
        for kind in ("trial", "result", "job", "protocol", "dataset"):
            table = TABLES[kind]
            db.executemany(
                f"DELETE FROM {table} WHERE id=?", [(i,) for i in selected[kind]]
            )
        # Reference-based GC retains every shared input and independent capture.
        referenced = set()

        def scan(value):
            if isinstance(value, str) and len(value) == 64:
                referenced.add(value)
            elif isinstance(value, dict):
                for v in value.values():
                    scan(v)
            elif isinstance(value, list):
                for v in value:
                    scan(v)

        for row in db.execute("SELECT body,raw FROM datasets"):
            scan(decode(row["body"]))
            if row["raw"].startswith(b"@blob:"):
                referenced.add(row["raw"][6:].decode())
                raw = store._read_blob(db, row["raw"][6:].decode())
            else:
                raw = gzip.decompress(row["raw"])
            try:
                scan(json.loads(raw))
            except (ValueError, UnicodeError):
                pass  # CSV/other declared source bytes contain no blob manifest.
        for row in db.execute("SELECT body FROM observations"):
            if row[0].startswith(b"@blob:"):
                referenced.add(row[0][6:].decode())
        # Do not collect staging inputs belonging to an unrelated running job.
        if (
            selected["dataset"]
            and not db.execute(
                "SELECT 1 FROM jobs WHERE state IN ('running','queued')"
            ).fetchone()
        ):
            stale = [
                (r[0],)
                for r in db.execute("SELECT digest FROM content_blobs")
                if r[0] not in referenced
            ]
            db.executemany("DELETE FROM content_blobs WHERE digest=?", stale)
        store._exposure_cache.clear()
    return {
        "deleted": plan["counts"],
        "message": "Selected research deleted. Paper records are preserved.",
    }
