"""Lossless storage compaction. Stop old app versions before using this CLI."""

import argparse
import fcntl
import hashlib
import json
import sqlite3

from .domain import ResearchError
from .store import Store, decode, encode


def _logical(db, store, body):
    """Encoding-independent hash, streamed one month/symbol at a time."""
    digest = hashlib.sha256()
    manifest = {
        k: v
        for k, v in body.items()
        if k not in ("bars", "bar_chunks", "fundamentals", "fundamental_chunks")
    }
    digest.update(json.dumps(manifest, sort_keys=True).encode())
    if "bar_chunks" in body:
        groups = (json.loads(store._read_blob(db, key)) for key in body["bar_chunks"])
    else:
        # Legacy bars are grouped by symbol, in ascending date order. Sort
        # explicitly so the physical month grouping cannot affect verification.
        groups = [sorted(body["bars"], key=lambda b: (b["symbol"], b["session"]))]
    count = 0
    for group in groups:
        for bar in group:
            digest.update(
                json.dumps(bar, sort_keys=True, separators=(",", ":")).encode()
            )
            count += 1
    facts = body.get("fundamentals", {})
    if "fundamental_chunks" in body:
        facts = {
            s: json.loads(store._read_blob(db, key))
            for s, key in body["fundamental_chunks"].items()
        }
    digest.update(json.dumps(facts, sort_keys=True).encode())
    return digest.hexdigest(), count


def compact(store, progress=lambda *a: None, *, vacuum=True):
    with store.path.with_suffix(".worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ResearchError(
                "Close Aperture before compacting storage; its worker is still running."
            ) from None
        return _compact(store, progress, vacuum=vacuum)


def _compact(store, progress, *, vacuum):
    """Verify logical content before/after each atomic conversion; retain all rows."""
    report = {"datasets": 0, "observations": 0}
    with store.connect() as db:
        if db.execute(
            "SELECT 1 FROM jobs WHERE state IN ('running','queued') LIMIT 1"
        ).fetchone():
            raise ResearchError(
                "Finish background work before compacting snapshot storage."
            )
        identifiers = [r[0] for r in db.execute("SELECT id FROM datasets")]
    for identifier in identifiers:
        progress("dataset", identifier)
        with store.connect() as db:
            body = decode(
                db.execute(
                    "SELECT body FROM datasets WHERE id=?", (identifier,)
                ).fetchone()[0]
            )
            before = _logical(db, store, body)
            store._share_bars(db, body)
            store._share_fundamentals(db, body)
            if _logical(db, store, body) != before:
                raise ResearchError(
                    "Compaction content verification failed; this dataset conversion was rolled back."
                )
            db.execute(
                "UPDATE datasets SET body=? WHERE id=?", (encode(body), identifier)
            )
        report["datasets"] += 1
    import gzip

    with store.connect() as db:
        # Work from stable rowids; SQL cursors are exhausted before writes.
        rows = db.execute("SELECT rowid,digest,body FROM observations").fetchall()
        for rowid, digest, packed in rows:
            raw = (
                store._read_blob(db, packed[6:].decode())
                if packed.startswith(b"@blob:")
                else gzip.decompress(packed)
            )
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ResearchError(
                    "Observation hash mismatch; compaction was stopped without replacing this payload."
                )
            if store._blob(db, raw) != digest:
                raise ResearchError("Observation content verification failed.")
            db.execute(
                "UPDATE observations SET body=? WHERE rowid=?",
                (b"@blob:" + digest.encode(), rowid),
            )
            report["observations"] += 1
    if vacuum:
        progress("vacuum", str(store.path))
        with sqlite3.connect(store.path) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            db.execute("VACUUM")
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ResearchError("SQLite integrity check failed after compaction.")
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()
    print(compact(Store(args.db), lambda *a: print(*a, flush=True)))
