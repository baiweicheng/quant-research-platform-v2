"""Reset generated research in one transaction while retaining the paper audit."""

import gzip
import hashlib
import json
import logging
import sqlite3

from .config import PAPER_URL
from .domain import ResearchError
from .research_cleanup import record_exposures
from .store import decode

CONFIRMATION = "RESET WORKSPACE"
LOG = logging.getLogger(__name__)
DELETION_KEYS = {
    "datasets": "id",
    "results": "id",
    "jobs": "id",
    "protocols": "id",
    "trials": "id",
    "memberships": "id",
    "observations": "id",
    "content_blobs": "digest",
    "parsed_filings": "key",
    "preferences": "key",
}


def identifiers(db, table, key="id"):
    return {row[0] for row in db.execute(f"SELECT {key} FROM {table}")}


def collect_references(value, references):
    if isinstance(value, str):
        references.add(value.removeprefix("@blob:"))
    elif isinstance(value, dict):
        for item in value.values():
            collect_references(item, references)
    elif isinstance(value, list):
        for item in value:
            collect_references(item, references)


def paper_observation(provider, resource):
    prefix = PAPER_URL + "/v2/"
    # Research also uses Alpaca's paper host for stock identity metadata.
    account_resource = resource.removeprefix(prefix).split("?", 1)[0].split("/", 1)[0]
    return provider == "alpaca-paper" or (
        resource.startswith(prefix)
        and account_resource in {"account", "orders", "positions"}
    )


def paper_dependencies(store, db):
    refs = set()
    paper_results = set()
    paper_jobs = set()
    index_config = False
    for row in db.execute("SELECT key,value FROM preferences WHERE key GLOB 'paper_*'"):
        value = json.loads(row["value"])
        collect_references(value, refs)
        if row["key"] == "paper_config" and value and value.get("universe") == "sp500":
            index_config = True
    if index_config:
        current = db.execute(
            "SELECT id FROM memberships WHERE kind='current' ORDER BY captured_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if current:
            refs.add(current[0])
    for row in db.execute("SELECT body FROM paper_plans"):
        collect_references(decode(row[0]), refs)
    for table in ("paper_approvals", "paper_orders"):
        for row in db.execute(f"SELECT body FROM {table}"):
            collect_references(json.loads(row[0]), refs)
    for row in db.execute(
        "SELECT id,payload,result_id FROM jobs WHERE kind GLOB 'paper_*' OR kind='connection'"
    ):
        paper_jobs.add(row["id"])
        paper_results.add(row["result_id"])
        collect_references(json.loads(row["payload"]), refs)
    for row in db.execute("SELECT id,kind FROM results"):
        if row["kind"].startswith("paper_") or row["kind"] == "connection":
            paper_results.add(row["id"])
    for identifier in paper_results - {None}:
        row = db.execute(
            "SELECT body FROM results WHERE id=?", (identifier,)
        ).fetchone()
        if row:
            collect_references(decode(row[0]), refs)

    retained = {}
    # Keep sources needed by paper snapshots, including any required parent snapshot.
    for table in ("datasets", "memberships"):
        known = identifiers(db, table)
        preserved = set()
        waiting = known & (refs | identifiers(db, f"retained_paper_{table}"))
        while waiting:
            parents = set()
            for identifier in waiting:
                row = db.execute(
                    f"SELECT body,raw FROM {table} WHERE id=?", (identifier,)
                ).fetchone()
                body = decode(row["body"])
                collect_references(body, refs)
                if table == "datasets":
                    parents.add(body.get("metadata", {}).get("price_dataset_id"))
                raw = row["raw"]
                if raw.startswith(b"@blob:"):
                    digest = raw[6:].decode()
                    refs.add(digest)
                    raw = store._read_blob(db, digest)
                else:
                    raw = gzip.decompress(raw)
                try:
                    collect_references(json.loads(raw), refs)
                except (ValueError, UnicodeError):
                    pass  # Plain CSV captures have no blob manifest.
            preserved.update(waiting)
            waiting = (known & parents) - preserved
        retained[table] = preserved
    keep_observations = set()
    for row in db.execute(
        "SELECT id,provider,resource,digest,substr(body,1,6) AS format FROM observations"
    ):
        if row["id"] in refs or paper_observation(row["provider"], row["resource"]):
            keep_observations.add(row["id"])
            if row["format"] == b"@blob:":
                refs.add(row["digest"])
    return {
        **retained,
        "content_blobs": identifiers(db, "content_blobs", "digest") & refs,
        "observations": keep_observations,
        "results": paper_results,
        "jobs": paper_jobs,
    }


def _plan(store, db):
    keep = paper_dependencies(store, db)
    selected = {
        table: identifiers(db, table, key) - keep.get(table, set())
        for table, key in DELETION_KEYS.items()
        if table != "preferences"
    }
    selected["preferences"] = {
        row[0]
        for row in db.execute(
            "SELECT key FROM preferences WHERE key GLOB 'annual-facts-v1:*'"
        )
    }
    paper_inputs = {table: keep[table] for table in ("datasets", "memberships")}
    blockers = []
    if db.execute(
        "SELECT 1 FROM jobs WHERE state IN ('queued','running') LIMIT 1"
    ).fetchone():
        blockers.append(
            "Wait for background work to finish, then refresh the reset preview."
        )
    counts = {key: len(values) for key, values in selected.items()}
    hidden = {
        table: ids - identifiers(db, f"retained_paper_{table}")
        for table, ids in paper_inputs.items()
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "operation": "workspace reset v1",
                "delete": {key: sorted(values) for key, values in selected.items()},
                "retain": {
                    key: sorted(values - {None}) for key, values in keep.items()
                },
                "archive": {key: sorted(values) for key, values in hidden.items()},
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return (
        {
            "counts": counts,
            "retained_paper_inputs": {
                key: len(values) for key, values in paper_inputs.items()
            },
            "blockers": blockers,
            "has_changes": any(counts.values()) or any(hidden.values()),
            "fingerprint": fingerprint,
        },
        selected,
        hidden,
    )


def preview(store):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        return _plan(store, db)[0]


def reset(store, fingerprint, confirmation):
    if confirmation != CONFIRMATION:
        raise ResearchError(f"Type {CONFIRMATION} to confirm the reset.")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        plan, selected, hidden = _plan(store, db)
        if plan["blockers"]:
            raise ResearchError(" ".join(plan["blockers"]))
        if fingerprint != plan["fingerprint"]:
            raise ResearchError(
                "Workspace data changed. Review a fresh preview before confirming."
            )
        record_exposures(db, selected["jobs"], selected["trials"])
        for table, values in hidden.items():
            db.executemany(
                f"INSERT INTO retained_paper_{table} VALUES (?)", ((v,) for v in values)
            )
        for table, key in DELETION_KEYS.items():
            db.executemany(
                f"DELETE FROM {table} WHERE {key}=?", ((v,) for v in selected[table])
            )
    store._exposure_cache.clear()
    if plan["has_changes"]:
        # Deletion is already committed. Reclaim its disk space without
        # reporting a failed reset if another reader delays compaction.
        try:
            with store.connect() as db:
                db.execute("VACUUM")
                db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            LOG.warning(
                "Workspace reset completed, but SQLite compaction could not finish.",
                exc_info=True,
            )
    return {
        "deleted": plan["counts"],
        "message": "Research workspace reset. Paper trading history is preserved.",
    }
