"""One persistent compute worker; navigation never runs a simulation."""

import argparse
import fcntl
import logging
import time
from datetime import date
from pathlib import Path

from . import __version__, calendar
from .backtest import run
from .domain import Policy, ResearchError, decimal, strategy
from .ingest import practice_dataset
from .portfolio import target_weights
from .signals import rank
from .store import Store

LOG = logging.getLogger(__name__)


def execute(store: Store, job: dict):
    payload = job["payload"]
    update = lambda value, message: store.progress(job["id"], value, message)
    if job["kind"] == "practice":
        update(15, "Building the fictional practice universe")
        dataset, raw, warnings = practice_dataset()
        saved = store.save_dataset(dataset, raw, warnings)
        store.finish(
            job,
            {
                "dataset_id": saved["id"],
                "dataset_name": saved["name"],
                "dataset_kind": "synthetic",
            },
        )
        return
    dataset = store.dataset(payload["dataset_id"])
    update(5, "Validating immutable inputs")
    identifier = payload["strategy_id"]
    recipe = strategy(identifier)
    policy = Policy()
    if job["kind"] == "backtest":
        body = run(
            dataset,
            identifier,
            date.fromisoformat(payload["start"]),
            date.fromisoformat(payload["end"]),
            decimal(payload["capital"]),
            policy,
            progress=update,
        )
    elif job["kind"] == "review":
        latest = calendar.latest_complete()
        end = max(bar.session for rows in dataset.bars.values() for bar in rows)
        if end != latest:
            raise ResearchError(
                f"Dataset ends {end}; the latest completed session is {latest}. Import updated data before preparing a current review."
            )
        ranked, excluded = rank(dataset, identifier, latest)
        targets, notes = target_weights(ranked, policy)
        if not targets:
            notes.append("No stocks currently qualify. The allocation is 100% cash.")
        body = {
            "engine_version": __version__,
            "input_contract": "as-traded-v1",
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "dataset_kind": dataset.kind,
            "source_digest": dataset.digest,
            "strategy": recipe,
            "decision_session": str(latest),
            "execute_session": str(calendar.next_session(latest)),
            "capital": "100000",
            "cash_weight": str(1 - sum(targets.values())),
            "targets": [
                {
                    "symbol": symbol,
                    "weight": str(weight),
                    "sector": dataset.sectors.get(symbol, "Unknown"),
                }
                for symbol, weight in targets.items()
            ],
            "excluded": excluded,
            "eligible": len(ranked),
            "notes": notes,
            "status": "research_only",
            "policy": {key: str(value) for key, value in vars(policy).items()},
        }
    else:
        raise ResearchError("Unknown background task.")
    store.finish(job, body)


def process_one(store: Store) -> bool:
    job = store.claim()
    if job is None:
        return False
    try:
        execute(store, job)
    except ResearchError as error:
        store.fail(job["id"], str(error))
    except Exception:
        LOG.exception("Task %s failed", job["id"])
        store.fail(
            job["id"],
            "An unexpected calculation error occurred. No partial result was saved. See the local worker log.",
        )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="var/aperture.sqlite3")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    lock_path = Path(args.db).with_suffix(".worker.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("A worker is already running for this database.")
        store = Store(args.db)
        store.recover()
        while True:
            if not process_one(store):
                time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass  # A deliberate terminal stop is not an application error.
