"""Frozen research protocols, chronological evaluation and visible trial history."""

import hashlib
import json
from dataclasses import replace
from datetime import date
from uuid import uuid4

from . import __version__, calendar
from .backtest import run
from .domain import Policy, ResearchError, decimal, strategy
from .store import Store, decode, encode, now


def protocols(store: Store) -> list[dict]:
    with store.connect() as db:
        return [
            {**json.loads(r["body"]), "holdout_state": r["holdout_state"]}
            for r in db.execute("SELECT * FROM protocols ORDER BY created_at DESC")
        ]


def protocol(store: Store, identifier: str) -> dict:
    match = next((p for p in protocols(store) if p["id"] == identifier), None)
    if not match:
        raise ResearchError("Choose an existing research protocol.")
    return match


def guard(db, start: str, end: str):
    """Calendar-wide protection also covers another snapshot or another strategy."""
    for row in db.execute("SELECT body FROM protocols WHERE holdout_state='locked'"):
        p = json.loads(row[0])
        if start <= p["end"] and end >= p["holdout_start"]:
            raise ResearchError(
                f"This period overlaps the locked holdout for {p['name']}. Use its development dates or release its final test once."
            )


def history(store: Store, identifier: str | None = None) -> list[dict]:
    with store.connect() as db:
        rows = db.execute("SELECT * FROM trials ORDER BY created_at,id").fetchall()
    return [
        {
            **json.loads(r["summary"]),
            **{
                k: r[k]
                for k in (
                    "id",
                    "protocol_id",
                    "job_id",
                    "label",
                    "phase",
                    "state",
                    "created_at",
                )
            },
        }
        for r in rows
        if identifier is None or r["protocol_id"] == identifier
    ]


def trial(store: Store, identifier: str) -> dict:
    with store.connect() as db:
        row = db.execute("SELECT body FROM trials WHERE id=?", (identifier,)).fetchone()
    if not row or row[0] is None:
        raise ResearchError(
            "This trial has no completed result. Inspect its failure in the registry."
        )
    return decode(row[0])


def create(store: Store, data: dict) -> dict:
    if len(data["hypothesis"].strip()) < 10 or not data["name"].strip():
        raise ResearchError(
            "Give the protocol a name and a meaningful hypothesis of at least ten characters."
        )
    ds = store.dataset(data["dataset_id"])
    recipe = strategy(data["strategy_id"])
    start, split, end = (
        date.fromisoformat(data[k]) for k in ("start", "holdout_start", "end")
    )
    days = calendar.sessions(start, end)
    dev = [d for d in days if d < split]
    final = [d for d in days if d >= split]
    available = sorted({b.session for rows in ds.bars.values() for b in rows})
    if (
        not days
        or days[0] < available[0]
        or days[-1] > available[-1]
        or len(dev) < 252
        or len(final) < 63
    ):
        raise ResearchError(
            "Use dataset coverage with at least 252 development sessions and 63 final-test sessions. Keep earlier warm-up data in the snapshot."
        )
    from .fundamentals import FUNDAMENTAL_STRATEGIES

    if recipe["id"] in FUNDAMENTAL_STRATEGIES and not ds.fundamentals:
        raise ResearchError("Add SEC fundamentals to this dataset first.")
    capital = decimal(data.get("capital", "100000"))
    if not 100 <= capital <= 1_000_000_000:
        raise ResearchError("Starting capital must be between $100 and $1 billion.")
    half = len(dev) // 2
    # Fixed recipe, three disjoint forward evaluation windows. No optimizer.
    folds = []
    for i in range(3):
        a = half + (len(dev) - half) * i // 3
        b = half + (len(dev) - half) * (i + 1) // 3
        folds.append(
            {
                "train_start": str(dev[0]),
                "train_end": str(dev[a - 1]),
                "start": str(dev[a]),
                "end": str(dev[b - 1]),
            }
        )
    body = {
        **data,
        "id": str(uuid4()),
        "created_at": now(),
        "start": str(dev[0]),
        "development_end": str(dev[-1]),
        "holdout_start": str(final[0]),
        "end": str(final[-1]),
        "capital": str(capital),
        "strategy": recipe,
        "dataset_name": ds.name,
        "source_digest": ds.digest,
        "engine_version": __version__,
        "policy": {k: str(v) for k, v in vars(Policy()).items()},
        "folds": folds,
        "protocol_version": "chronological-v1",
        "hypothesis": data["hypothesis"].strip(),
    }
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        guard(db, body["start"], body["end"])
        exposed = []
        for j in db.execute(
            "SELECT id,kind,payload FROM jobs WHERE kind IN ('backtest','validation')"
        ):
            payload = json.loads(j["payload"])
            if (
                j["kind"] == "backtest"
                and payload.get("start", "9999") <= body["end"]
                and payload.get("end", "") >= body["holdout_start"]
            ):
                exposed.append(j["id"])
        # Prior trial windows from any protocol are exposure, regardless of outcome.
        for t in db.execute("SELECT id,summary FROM trials"):
            s = json.loads(t["summary"])
            if (
                s.get("start", "9999") <= body["end"]
                and s.get("end", "") >= body["holdout_start"]
            ):
                exposed.append(t["id"])
        body["prior_exposures"] = exposed
        body["holdout_label"] = (
            "Previously explored period"
            if exposed
            else "Reserved final test; outside-workspace exposure unknown"
        )
        body["fingerprint"] = hashlib.sha256(
            json.dumps(body, sort_keys=True).encode()
        ).hexdigest()
        db.execute(
            "INSERT INTO protocols (id,created_at,body) VALUES (?,?,?)",
            (body["id"], body["created_at"], json.dumps(body)),
        )
    return {**body, "holdout_state": "locked"}


def enqueue(
    store: Store, identifier: str, phase: str, acknowledge: bool = False
) -> dict:
    p = protocol(store, identifier)
    if phase == "holdout" and not acknowledge:
        raise ResearchError(
            "Acknowledge that releasing the final test consumes it, even if the task fails."
        )
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        busy = db.execute(
            "SELECT id FROM jobs WHERE kind='validation' AND state IN ('running','queued') AND json_extract(payload,'$.protocol_id')=?",
            (identifier,),
        ).fetchone()
        if busy:
            raise ResearchError(
                "This protocol already has a queued or running evaluation."
            )
        if phase == "development":
            if p["holdout_state"] != "locked":
                raise ResearchError(
                    "The final test has been released. Further tuning requires a new protocol and new unseen data."
                )
            guard(db, p["start"], p["development_end"])
        else:
            completed = db.execute(
                "SELECT 1 FROM jobs WHERE kind='validation' AND state='complete' AND json_extract(payload,'$.protocol_id')=? AND json_extract(payload,'$.phase')='development'",
                (identifier,),
            ).fetchone()
            if not completed:
                raise ResearchError(
                    "Complete development validation before releasing the final test."
                )
            changed = db.execute(
                "UPDATE protocols SET holdout_state='released' WHERE id=? AND holdout_state='locked'",
                (identifier,),
            ).rowcount
            if changed != 1:
                raise ResearchError(
                    "This final test has already been released. Reopen the saved result; do not tune on it."
                )
        job_id, timestamp = str(uuid4()), now()
        payload = {"protocol_id": identifier, "phase": phase}
        db.execute(
            "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?)",
            (
                job_id,
                "validation",
                json.dumps(payload, sort_keys=True),
                "queued",
                0,
                "Waiting for research validation",
                timestamp,
                timestamp,
                None,
            ),
        )
    return {"id": job_id}


def retire(store: Store, identifier: str) -> dict:
    protocol(store, identifier)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        busy = db.execute(
            "SELECT 1 FROM jobs WHERE kind='validation' AND state IN ('queued','running') AND json_extract(payload,'$.protocol_id')=?",
            (identifier,),
        ).fetchone()
        if busy:
            raise ResearchError(
                "Wait for the queued evaluation before retiring its protocol."
            )
        db.execute(
            "UPDATE protocols SET holdout_state='retired' WHERE id=? AND holdout_state='locked'",
            (identifier,),
        )
    return protocol(store, identifier)


def execute(store: Store, job: dict, progress) -> dict:
    p = protocol(store, job["payload"]["protocol_id"])
    ds = store.dataset(p["dataset_id"])
    if (
        ds.digest != p["source_digest"]
        or p["strategy"] != strategy(p["strategy_id"])
        or p["engine_version"] != __version__
    ):
        raise ResearchError(
            "The frozen recipe or engine changed. Create a new protocol; saved results remain available."
        )
    phase = job["payload"]["phase"]
    policy = Policy()
    if phase == "holdout":
        specs = [("Final test", p["holdout_start"], p["end"], policy, "weekly")]
    else:
        specs = [
            ("Development baseline", p["start"], p["development_end"], policy, "weekly")
        ]
        specs += [
            (f"Forward window {i + 1}", f["start"], f["end"], policy, "weekly")
            for i, f in enumerate(p["folds"])
        ]
        specs += [
            (
                "Higher costs: 15 + 1 bps",
                p["start"],
                p["development_end"],
                replace(policy, slippage_bps=decimal(15)),
                "weekly",
            ),
            (
                "Lower stock cap: 3%",
                p["start"],
                p["development_end"],
                replace(policy, max_weight=decimal(".03")),
                "weekly",
            ),
            (
                "Fewer positions: 15",
                p["start"],
                p["development_end"],
                replace(policy, positions=15),
                "weekly",
            ),
            ("Monthly rebalance", p["start"], p["development_end"], policy, "monthly"),
        ]
    saved = []
    for i, (label, start, end, limits, frequency) in enumerate(specs):
        identifier = str(uuid4())
        summary = {
            "start": start,
            "end": end,
            "frequency": frequency,
            "policy": {k: str(v) for k, v in vars(limits).items()},
        }
        with store.connect() as db:
            db.execute(
                "INSERT INTO trials VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    p["id"],
                    job["id"],
                    label,
                    phase,
                    "running",
                    now(),
                    json.dumps(summary),
                    None,
                ),
            )
        try:
            output = run(
                ds,
                p["strategy_id"],
                date.fromisoformat(start),
                date.fromisoformat(end),
                decimal(p["capital"]),
                limits,
                frequency,
                lambda n, text, i=i, label=label: progress(
                    round((i + n / 100) / len(specs) * 95), f"{label}: {text}"
                ),
            )
            output.update(
                id=identifier, created_at=now(), protocol_id=p["id"], trial_label=label
            )
            summary.update(
                metrics=output["windows"]["All"]["metrics"],
                trade_count=output["trade_count"],
                no_trade_decisions=sum(not d["targets"] for d in output["decisions"]),
            )
            with store.connect() as db:
                db.execute(
                    "UPDATE trials SET state='complete',summary=?,body=? WHERE id=?",
                    (json.dumps(summary), encode(output), identifier),
                )
        except Exception as error:
            summary["error"] = (
                str(error)
                if isinstance(error, ResearchError)
                else "Calculation failed; inspect worker log."
            )
            with store.connect() as db:
                db.execute(
                    "UPDATE trials SET state='failed',summary=? WHERE id=?",
                    (json.dumps(summary), identifier),
                )
            raise
        saved.append(identifier)
    return {
        "protocol_id": p["id"],
        "phase": phase,
        "trial_ids": saved,
        "completion_message": f"{len(saved)} research trials saved. Inspect validation and limitations before any strategy approval.",
    }
