"""Transactional local persistence. Immutable inputs and results travel together."""

import gzip
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, date
from pathlib import Path
from uuid import uuid4

from .domain import AnnualStatement, Bar, Dataset, ResearchError, decimal


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> bytes:
    return gzip.compress(json.dumps(value, separators=(",", ":")).encode(), mtime=0)


def decode(value):
    return json.loads(gzip.decompress(value))


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
                INSERT OR IGNORE INTO schema_version VALUES (1);
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
                    summary TEXT NOT NULL, body BLOB NOT NULL, raw BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    state TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, result_id TEXT);
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL,
                    summary TEXT NOT NULL, body BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL,
                    resource TEXT NOT NULL, fetched_at TEXT NOT NULL,
                    digest TEXT NOT NULL, body BLOB NOT NULL);
                CREATE INDEX IF NOT EXISTS observations_resource ON observations(provider,resource,fetched_at);
                CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT OR IGNORE INTO schema_version VALUES (2);
                CREATE TABLE IF NOT EXISTS protocols (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, body TEXT NOT NULL,
                    holdout_state TEXT NOT NULL DEFAULT 'locked');
                CREATE TABLE IF NOT EXISTS trials (
                    id TEXT PRIMARY KEY, protocol_id TEXT NOT NULL, job_id TEXT NOT NULL,
                    label TEXT NOT NULL, phase TEXT NOT NULL, state TEXT NOT NULL,
                    created_at TEXT NOT NULL, summary TEXT NOT NULL, body BLOB);
                CREATE TABLE IF NOT EXISTS memberships (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, captured_at TEXT NOT NULL,
                    body BLOB NOT NULL, raw BLOB NOT NULL);
                INSERT OR IGNORE INTO schema_version VALUES (4);
            """)
        self.path.chmod(0o600)
        from .paper import initialize

        initialize(self)

    def save_membership(self, body: dict, raw: bytes) -> dict:
        with self.connect() as db:
            db.execute(
                "INSERT INTO memberships VALUES (?,?,?,?,?)",
                (
                    body["id"],
                    body["kind"],
                    body["captured_at"],
                    encode(body),
                    gzip.compress(raw, mtime=0),
                ),
            )
        return body

    def membership(self, kind: str, identifier: str | None = None) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM memberships WHERE kind=? AND (? IS NULL OR id=?) ORDER BY captured_at DESC, rowid DESC LIMIT 1",
                (kind, identifier, identifier),
            ).fetchone()
        return decode(row[0]) if row else None

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save_dataset(self, dataset: Dataset, raw: bytes, warnings: list[str]) -> dict:
        days = sorted({bar.session for rows in dataset.bars.values() for bar in rows})
        summary = dict(
            id=dataset.id,
            name=dataset.name,
            kind=dataset.kind,
            revision=dataset.revision,
            source=dataset.source,
            digest=dataset.digest,
            symbols=sorted(dataset.bars),
            symbol_count=len(dataset.bars),
            row_count=sum(len(rows) for rows in dataset.bars.values()),
            start=str(days[0]),
            end=str(days[-1]),
            created_at=now(),
            warnings=warnings,
            metadata=dataset.metadata,
        )
        body = {
            "summary": summary,
            "sectors": dataset.sectors,
            "metadata": dataset.metadata,
            "fundamentals": {
                symbol: [
                    {
                        **vars(statement),
                        "start": str(statement.start),
                        "end": str(statement.end),
                        "filed": str(statement.filed),
                        "available_at": statement.available_at.isoformat(),
                        **{
                            key: str(getattr(statement, key))
                            if getattr(statement, key) is not None
                            else None
                            for key in ("assets", "gross_profit", "eps")
                        },
                    }
                    for statement in statements
                ]
                for symbol, statements in dataset.fundamentals.items()
            },
            "bars": [
                {
                    **vars(bar),
                    "session": str(bar.session),
                    "pay_date": str(bar.pay_date) if bar.pay_date else None,
                    "available_at": bar.available_at.isoformat()
                    if bar.available_at
                    else None,
                    **{
                        key: str(getattr(bar, key))
                        for key in ("open", "high", "low", "close", "split", "dividend")
                    },
                }
                for rows in dataset.bars.values()
                for bar in rows
            ],
        }
        with self.connect() as db:
            existing = db.execute(
                "SELECT summary FROM datasets WHERE digest=?", (dataset.digest,)
            ).fetchone()
            if existing:
                return {**json.loads(existing[0]), "already_imported": True}
            db.execute(
                "INSERT INTO datasets VALUES (?,?,?,?,?)",
                (
                    dataset.id,
                    dataset.digest,
                    json.dumps(summary),
                    encode(body),
                    gzip.compress(raw, mtime=0),
                ),
            )
        return summary

    def datasets(self) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT summary FROM datasets ORDER BY rowid DESC"
                )
            ]

    def dataset(self, identifier: str) -> Dataset:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM datasets WHERE id=?", (identifier,)
            ).fetchone()
        if not row:
            raise ResearchError("That dataset was not found. Choose one from Data.")
        body = decode(row[0])
        summary = body["summary"]
        # Preserve requested securities with zero returned bars, such as a
        # current member whose listing began after a historical download period.
        bars: dict[str, list[Bar]] = {s: [] for s in summary["symbols"]}
        for item in body["bars"]:
            item["session"] = date.fromisoformat(item["session"])
            item["pay_date"] = (
                date.fromisoformat(item["pay_date"]) if item["pay_date"] else None
            )
            item["available_at"] = (
                datetime.fromisoformat(item["available_at"])
                if item["available_at"]
                else None
            )
            for key in ("open", "high", "low", "close", "split", "dividend"):
                item[key] = decimal(item[key])
            bar = Bar(**item)
            bars.setdefault(bar.symbol, []).append(bar)
        fundamentals = {}
        for symbol, statements in body.get("fundamentals", {}).items():
            normalized = []
            for statement in statements:
                for key in ("start", "end", "filed"):
                    statement[key] = date.fromisoformat(statement[key])
                statement["available_at"] = datetime.fromisoformat(
                    statement["available_at"]
                )
                for key in ("assets", "gross_profit", "eps"):
                    statement[key] = (
                        decimal(statement[key]) if statement[key] is not None else None
                    )
                statement["issues"] = tuple(statement.get("issues", ()))
                normalized.append(AnnualStatement(**statement))
            fundamentals[symbol] = tuple(normalized)
        return Dataset(
            identifier,
            summary["name"],
            summary["kind"],
            summary["revision"],
            {
                s: tuple(sorted(rows, key=lambda b: b.session))
                for s, rows in bars.items()
            },
            body["sectors"],
            summary["source"],
            summary["digest"],
            body.get("metadata", {}),
            fundamentals,
        )

    def preference(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute(
                "SELECT value FROM preferences WHERE key=?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else default

    def set_preference(self, key: str, value):
        with self.connect() as db:
            db.execute(
                "INSERT INTO preferences VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    def observe(self, provider: str, resource: str, raw: bytes) -> str:
        import hashlib

        identifier = str(uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO observations VALUES (?,?,?,?,?,?)",
                (
                    identifier,
                    provider,
                    resource,
                    now(),
                    hashlib.sha256(raw).hexdigest(),
                    gzip.compress(raw, mtime=0),
                ),
            )
        return identifier

    def cached(
        self, provider: str, resource: str, seconds: int
    ) -> tuple[dict, str] | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT id,fetched_at,body FROM observations WHERE provider=? AND resource=? ORDER BY fetched_at DESC LIMIT 1",
                (provider, resource),
            ).fetchone()
        if (
            row
            and (
                datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
            ).total_seconds()
            < seconds
        ):
            return json.loads(gzip.decompress(row["body"])), row["id"]
        return None

    def enqueue(self, kind: str, payload: dict) -> dict:
        packed = json.dumps(payload, sort_keys=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if kind == "backtest":
                from .experiments import guard

                guard(db, payload["start"], payload["end"])
            duplicate = db.execute(
                "SELECT * FROM jobs WHERE kind=? AND payload=? AND state IN ('queued','running')",
                (kind, packed),
            ).fetchone()
            if duplicate:
                return dict(duplicate)
            identifier, timestamp = str(uuid4()), now()
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    kind,
                    packed,
                    "queued",
                    0,
                    "Waiting for the local worker",
                    timestamp,
                    timestamp,
                    None,
                ),
            )
            return dict(
                db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            )

    def jobs(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,kind,state,progress,message,created_at,updated_at,result_id FROM jobs ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            return [dict(row) for row in rows]

    def claim(self) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE jobs SET state='running',updated_at=?,message='Starting',progress=1 WHERE id=?",
                    (now(), row["id"]),
                )
                return {**dict(row), "payload": json.loads(row["payload"])}
        return None

    def progress(self, identifier: str, value: int, message: str):
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET progress=?,message=?,updated_at=? WHERE id=? AND state='running'",
                (value, message, now(), identifier),
            )

    def fail(self, identifier: str, message: str):
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='failed',message=?,updated_at=? WHERE id=?",
                (message, now(), identifier),
            )

    def recover(self):
        # Called only while holding the worker's exclusive OS lock.
        with self.connect() as db:
            db.execute("UPDATE trials SET state='interrupted' WHERE state='running'")
            db.execute(
                "UPDATE jobs SET state='failed',message='The local worker stopped during this task. Nothing partial was saved; run it again.',updated_at=? WHERE state='running'",
                (now(),),
            )

    def finish(self, job: dict, body: dict):
        identifier, timestamp = str(uuid4()), now()
        body = {**body, "id": identifier, "created_at": timestamp}
        summary = {
            key: body[key]
            for key in (
                "id",
                "created_at",
                "dataset_id",
                "dataset_name",
                "dataset_kind",
                "strategy",
            )
            if key in body
        }
        for key in (
            "start",
            "end",
            "trade_count",
            "decision_session",
            "execute_session",
        ):
            if key in body:
                summary[key] = body[key]
        if "windows" in body:
            summary["metrics"] = body["windows"]["All"]["metrics"]
        with self.connect() as db:
            db.execute(
                "INSERT INTO results VALUES (?,?,?,?,?)",
                (identifier, job["kind"], timestamp, json.dumps(summary), encode(body)),
            )
            db.execute(
                "UPDATE jobs SET state='complete',progress=100,message='Ready to review',updated_at=?,result_id=? WHERE id=?",
                (timestamp, identifier, job["id"]),
            )
            if body.get("completion_message"):
                db.execute(
                    "UPDATE jobs SET message=? WHERE id=?",
                    (body["completion_message"], job["id"]),
                )

    def results(self, kind: str) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT summary FROM results WHERE kind=? ORDER BY created_at DESC",
                    (kind,),
                )
            ]

    def result(self, identifier: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM results WHERE id=?", (identifier,)
            ).fetchone()
        if not row:
            raise ResearchError("That saved result was not found.")
        return decode(row[0])
