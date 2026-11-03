"""One persistent compute worker; navigation never runs a simulation."""

import argparse
import fcntl
import logging
import time
from datetime import date, datetime, timezone
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
    if job["kind"] == "membership":
        from .membership import refresh, summary

        update(10, "Refreshing dated S&P 500 membership")
        saved = refresh(store, payload["kind"])
        store.finish(
            job,
            {
                "completion_message": f"Saved {saved['member_count']} S&P 500 securities. Membership details and coverage are available in Data.",
                "membership": summary(saved),
            },
        )
        return
    if job["kind"].startswith("paper_"):
        from .paper import (
            Broker,
            reconcile,
            prepare,
            cancel_pending,
            schedule,
            configuration,
            approval,
        )

        broker = Broker()
        try:
            if job["kind"] == "paper_sync":
                reconcile(store, broker, performance=True)
                body = {
                    "completion_message": "Paper account, orders and daily performance refreshed. No orders submitted."
                }
            elif job["kind"] == "paper_cancel":
                cancel_pending(store, broker)
                body = {
                    "completion_message": "Cancellation requests reconciled. Inspect remaining broker orders in Portfolio."
                }
            elif job["kind"] == "paper_prepare":
                body = prepare(store, job, update, broker)
                if job["payload"].get("automatic"):
                    cfg = configuration(store)
                    allowed = approval(store)
                    if (
                        cfg
                        and cfg["mode"] == "automatic"
                        and not cfg["paused"]
                        and allowed
                        and allowed["allow_automatic"]
                    ):
                        schedule(store, body["plan_id"])
            else:
                raise ResearchError("Unknown paper task.")
            store.finish(job, body)
        finally:
            broker.close()
        return
    if job["kind"] == "validation":
        from .experiments import execute as evaluate

        store.finish(job, evaluate(store, job, update))
        return
    if job["kind"] == "fundamentals":
        from .fundamentals import attach

        saved = attach(store, payload["dataset_id"], update)
        store.finish(
            job,
            {
                "dataset_id": saved["id"],
                "dataset_name": saved["name"],
                "completion_message": f"Saved SEC annual fundamentals alongside prices. {saved['metadata']['fundamentals']['record_count']:,} filing-period records; view coverage and exclusions in Data.",
            },
        )
        return
    if job["kind"] == "download":
        from .providers import download_market

        saved = download_market(store, payload, update)
        store.finish(
            job,
            {
                "dataset_id": saved["id"],
                "dataset_name": saved["name"],
                "dataset_kind": saved["kind"],
                "completion_message": f"Saved {saved['row_count']:,} daily bars for {saved['symbol_count']} symbols. Coverage details are available in Data.",
                "coverage": saved.get("metadata", {}).get("coverage", []),
            },
        )
        return
    if job["kind"] == "connection":
        from .providers import Provider
        from .config import PAPER_URL, DATA_URL

        api = Provider(store)
        try:
            update(10, "Checking paper-account access")
            account = api.get("alpaca", PAPER_URL + "/v2/account", ttl=0)
            if account.get("status") != "ACTIVE" or account.get("currency") != "USD":
                raise ResearchError(
                    "The paper account must be active and denominated in USD."
                )
            latest = calendar.latest_complete()
            sample = api.get(
                "alpaca",
                DATA_URL + "/v2/stocks/bars",
                {
                    "symbols": "SPY",
                    "timeframe": "1Day",
                    "start": str(latest),
                    "end": calendar.close_time(latest).isoformat(),
                    "feed": "sip",
                    "adjustment": "raw",
                    "limit": 10,
                },
            )
            if not sample.get("bars", {}).get("SPY"):
                raise ResearchError(
                    "The consolidated SPY sample was unavailable. Check market-data access before downloading."
                )
            store.finish(
                job,
                {
                    "paper_access": True,
                    "completion_message": "Read-only paper-account and consolidated historical-data checks passed.",
                    "historical_sip_access": True,
                    "checked_at": str(latest),
                },
            )
        finally:
            api.close()
        return
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
                    "components": next(
                        stock.components for stock in ranked if stock.symbol == symbol
                    ),
                }
                for symbol, weight in targets.items()
            ],
            "excluded": excluded,
            "eligible": len(ranked),
            "signals": [
                {
                    "symbol": stock.symbol,
                    "score": stock.score,
                    "components": stock.components,
                }
                for stock in ranked
            ],
            "notes": notes,
            "status": "research_only",
            "policy": {key: str(value) for key, value in vars(policy).items()},
            "input_audit": dataset.metadata,
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
        if job["kind"].startswith("paper_"):
            store.set_preference("paper_error", str(error))
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
        last_tick = 0.0
        while True:
            if time.monotonic() - last_tick >= 5:
                from .paper import tick

                store.set_preference(
                    "worker_seen",
                    datetime.now(timezone.utc).isoformat(),
                )
                try:
                    tick(store)
                except Exception:
                    LOG.exception("Paper reconciliation failed")
                    from .paper import stop

                    stop(store)
                    store.set_preference(
                        "paper_error",
                        "The paper worker encountered an unexpected error. Stop execution and inspect the local log before resuming.",
                    )
                last_tick = time.monotonic()
            if not process_one(store):
                time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass  # A deliberate terminal stop is not an application error.
