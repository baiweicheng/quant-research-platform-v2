"""Transactional local persistence. Immutable inputs and results travel together."""

import gzip
import hashlib
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
        self._exposure_cache = {}
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
                CREATE INDEX IF NOT EXISTS observations_digest ON observations(digest);
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
                CREATE TABLE IF NOT EXISTS content_blobs (
                    digest TEXT PRIMARY KEY, body BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS research_exposures (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, start TEXT NOT NULL,
                    end TEXT NOT NULL, created_at TEXT NOT NULL);
                INSERT OR IGNORE INTO schema_version VALUES (6);
                INSERT OR IGNORE INTO schema_version VALUES (7);
                CREATE TABLE IF NOT EXISTS parsed_filings (
                    key TEXT PRIMARY KEY, digest TEXT NOT NULL, body BLOB NOT NULL);
                INSERT OR IGNORE INTO schema_version VALUES (8);
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

    @staticmethod
    def _blob(db, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        if db.execute(
            "SELECT 1 FROM content_blobs WHERE digest=?", (digest,)
        ).fetchone():
            return digest
        db.execute(
            "INSERT OR IGNORE INTO content_blobs VALUES (?,?)",
            (digest, gzip.compress(raw, mtime=0)),
        )
        return digest

    @staticmethod
    def _read_blob(db, digest):
        row = db.execute(
            "SELECT body FROM content_blobs WHERE digest=?", (digest,)
        ).fetchone()
        if row is None:
            raise ResearchError(
                "A shared snapshot block is missing. Restore the complete workspace database from backup."
            )
        raw = gzip.decompress(row[0])
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ResearchError(
                "A shared snapshot block failed its content hash check. Restore the complete workspace database from backup."
            )
        return raw

    def _share_bars(self, db, body):
        if "bar_chunks" in body:
            return
        chunks = {}
        for bar in body.pop("bars"):
            key = (bar["symbol"], bar["session"][:7])
            chunks.setdefault(key, []).append(bar)
        body["bar_chunks"] = [
            self._blob(
                db,
                json.dumps(
                    sorted(rows, key=lambda row: row["session"]),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode(),
            )
            for _, rows in sorted(chunks.items())
        ]

    def _share_fundamentals(self, db, body):
        if "fundamental_chunks" not in body:
            body["fundamental_chunks"] = {
                s: self._blob(
                    db, json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
                )
                for s, rows in body.pop("fundamentals", {}).items()
            }

    def share_dataset_storage(self, identifier):
        """Convert legacy physical storage atomically; logical inputs/digest stay identical."""
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM datasets WHERE id=?", (identifier,)
            ).fetchone()
            if row is None:
                raise ResearchError("That dataset was not found.")
            body = decode(row[0])
            if "bar_chunks" not in body or "fundamental_chunks" not in body:
                self._share_bars(db, body)
                self._share_fundamentals(db, body)
                db.execute(
                    "UPDATE datasets SET body=? WHERE id=?", (encode(body), identifier)
                )

    def capture_source(self, raw: bytes) -> str:
        """Retain a normalized acquisition input once, even without a dataset row."""
        with self.connect() as db:
            return self._blob(db, raw)

    def save_dataset(self, dataset: Dataset, raw: bytes, warnings: list[str]) -> dict:
        with self.connect() as db:
            existing = db.execute(
                "SELECT summary FROM datasets WHERE digest=?", (dataset.digest,)
            ).fetchone()
            if existing:
                return {**json.loads(existing[0]), "already_imported": True}
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
        }
        with self.connect() as db:
            existing = db.execute(
                "SELECT summary FROM datasets WHERE digest=?", (dataset.digest,)
            ).fetchone()
            if existing:
                return {**json.loads(existing[0]), "already_imported": True}
            body["bar_chunks"] = []
            for symbol, rows in sorted(dataset.bars.items()):
                if any(bar.symbol != symbol for bar in rows):
                    raise ResearchError(
                        "Stored bar identity does not match its security series."
                    )
                block = {
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
                                for key in (
                                    "open",
                                    "high",
                                    "low",
                                    "close",
                                    "split",
                                    "dividend",
                                    "research_dividend",
                                    "research_distribution",
                                )
                            },
                        }
                        for bar in rows
                    ]
                }
                self._share_bars(db, block)
                body["bar_chunks"].extend(block["bar_chunks"])
            self._share_fundamentals(db, body)
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

    def save_metadata_snapshot(self, identifier, digest, sectors, metadata, raw, note):
        """Derive a vintage while reusing exact shared prices and filings.

        Only classification/metadata change; the parent and saved results stay
        immutable. This avoids materializing millions of identical price rows.
        """
        with self.connect() as db:
            existing = db.execute(
                "SELECT summary FROM datasets WHERE digest=?", (digest,)
            ).fetchone()
            if existing:
                return {**json.loads(existing[0]), "already_imported": True}
            row = db.execute(
                "SELECT body FROM datasets WHERE id=?", (identifier,)
            ).fetchone()
            if row is None:
                raise ResearchError("The parent snapshot was not found.")
            body = decode(row[0])
            summary = {
                **body["summary"],
                "id": digest[:24],
                "digest": digest,
                "revision": body["summary"]["revision"] + 1,
                "created_at": now(),
                "metadata": metadata,
                "warnings": list(dict.fromkeys([*body["summary"]["warnings"], note])),
            }
            body.update(summary=summary, metadata=metadata, sectors=sectors)
            self._share_bars(db, body)
            self._share_fundamentals(db, body)
            db.execute(
                "INSERT INTO datasets VALUES (?,?,?,?,?)",
                (
                    summary["id"],
                    digest,
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

    def _bar_items(self, chunks):
        # Decompress and convert one month at a time; do not retain a second
        # universe-sized list of price dictionaries beside the Bar objects.
        with self.connect() as db:
            for digest in chunks:
                yield from json.loads(self._read_blob(db, digest))

    def dataset(self, identifier: str) -> Dataset:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM datasets WHERE id=?", (identifier,)
            ).fetchone()
            if not row:
                raise ResearchError("That dataset was not found. Choose one from Data.")
            body = decode(row[0])
            if "fundamental_chunks" in body:
                body["fundamentals"] = {
                    s: json.loads(self._read_blob(db, digest))
                    for s, digest in body["fundamental_chunks"].items()
                }
        summary = body["summary"]
        # Preserve requested securities with zero returned bars, such as a
        # current member whose listing began after a historical download period.
        bars: dict[str, list[Bar]] = {s: [] for s in summary["symbols"]}
        items = (
            self._bar_items(body["bar_chunks"])
            if "bar_chunks" in body
            else iter(body["bars"])
        )
        for item in items:
            item["session"] = date.fromisoformat(item["session"])
            item["pay_date"] = (
                date.fromisoformat(item["pay_date"]) if item["pay_date"] else None
            )
            item["available_at"] = (
                datetime.fromisoformat(item["available_at"])
                if item["available_at"]
                else None
            )
            for key in (
                "open",
                "high",
                "low",
                "close",
                "split",
                "dividend",
                "research_dividend",
                "research_distribution",
            ):
                if key not in item:
                    continue
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
        identifier = str(uuid4())
        with self.connect() as db:
            digest = self._blob(db, raw)
            db.execute(
                "UPDATE observations SET body=? WHERE digest=? AND substr(body,1,6)!=?",
                (b"@blob:" + digest.encode(), digest, b"@blob:"),
            )
            db.execute(
                "INSERT INTO observations VALUES (?,?,?,?,?,?)",
                (
                    identifier,
                    provider,
                    resource,
                    now(),
                    digest,
                    b"@blob:" + digest.encode(),
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
            packed = row["body"]
            if packed.startswith(b"@blob:"):
                with self.connect() as db:
                    raw = self._read_blob(db, packed[6:].decode())
            else:
                raw = gzip.decompress(packed)
            return json.loads(raw), row["id"]
        return None

    def filing_evidence(self, key: str):
        """Reuse derived evidence only while its captured source fingerprints match.

        Parsed rows are disposable caches. A parser/identity change uses a new
        key; missing, changed or damaged dependencies force normal verification.
        """
        with self.connect() as db:
            row = db.execute(
                "SELECT digest,body FROM parsed_filings WHERE key=?", (key,)
            ).fetchone()
            if row is None or hashlib.sha256(row["body"]).hexdigest() != row["digest"]:
                return None
            try:
                value = decode(row["body"])
                sources = value["sources"]
                if not sources or not isinstance(value["proof"], dict):
                    return None
                for source in sources:
                    current = db.execute(
                        "SELECT id,digest FROM observations WHERE provider=? AND resource=? ORDER BY fetched_at DESC,rowid DESC LIMIT 1",
                        (source["provider"], source["resource"]),
                    ).fetchone()
                    original = db.execute(
                        "SELECT digest FROM observations WHERE id=?", (source["id"],)
                    ).fetchone()
                    if (
                        current is None
                        or original is None
                        or current["digest"] != source["digest"]
                        or original["digest"] != source["digest"]
                    ):
                        return None
                return value
            except (KeyError, TypeError, ValueError, OSError, EOFError):
                return None

    def save_filing_evidence(self, key: str, proof: dict, observation_ids: list[str]):
        with self.connect() as db:
            sources = []
            for identifier in dict.fromkeys(observation_ids):
                row = db.execute(
                    "SELECT id,provider,resource,digest FROM observations WHERE id=?",
                    (identifier,),
                ).fetchone()
                if row is None:
                    return
                sources.append(dict(row))
            if not sources:
                return
            body = encode({"proof": proof, "sources": sources})
            db.execute(
                "INSERT INTO parsed_filings VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET digest=excluded.digest,body=excluded.body",
                (key, hashlib.sha256(body).hexdigest(), body),
            )

    def enqueue(self, kind: str, payload: dict) -> dict:
        packed = json.dumps(payload, sort_keys=True)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if kind == "backtest":
                from .experiments import guard

                guard(db, payload["start"], payload["end"])
            if (
                payload.get("dataset_id")
                and not db.execute(
                    "SELECT 1 FROM datasets WHERE id=?", (payload["dataset_id"],)
                ).fetchone()
            ):
                raise ResearchError(
                    "That dataset is no longer available. Refresh Data and choose a saved snapshot."
                )
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
                """UPDATE jobs SET state='failed',message=CASE
                    WHEN kind IN ('download','fundamentals','dataset_update') THEN
                    'The local worker stopped during this task. Completed snapshots and verified filing checks are retained. Retry in Data; an unfinished price snapshot can use Complete SEC download.'
                    ELSE 'The local worker stopped during this task. No partial calculation result was saved; run it again.'
                    END,updated_at=? WHERE state='running'""",
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
            "engine_version",
            "start",
            "end",
            "trade_count",
            "decision_session",
            "execute_session",
            "exposure",
            "sector_classification",
        ):
            if key in body:
                summary[key] = body[key]
        if isinstance(body.get("coverage"), dict) and "mode" in body["coverage"]:
            summary["coverage"] = {
                k: body["coverage"][k] for k in ("mode", "excluded_count")
            }
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
            summaries = [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT summary FROM results WHERE kind=? ORDER BY created_at DESC",
                    (kind,),
                )
            ]
            if kind == "backtest":
                from .exposure import summarize

                for result in summaries:
                    if "exposure" not in result:
                        identifier = result["id"]
                        if identifier not in self._exposure_cache:
                            row = db.execute(
                                "SELECT body FROM results WHERE id=?", (identifier,)
                            ).fetchone()
                            self._exposure_cache[identifier] = summarize(decode(row[0]))
                        result["exposure"] = self._exposure_cache[identifier]
            return summaries

    def result(self, identifier: str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT body FROM results WHERE id=?", (identifier,)
            ).fetchone()
        if not row:
            raise ResearchError("That saved result was not found.")
        return decode(row[0])
