"""Broker-held paper MARKET DAY orders with explicit funding and durable receipts."""

import fcntl
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from . import calendar
from .broker import TERMINAL, ReconciliationPending, SubmissionNotSent
from .domain import CENT, ONE, ZERO, ResearchError, decimal, paper_strategy
from .store import now

VERSION = "paper-broker-market-day-v1"
DELIVERY_MARGIN = timedelta(seconds=10)
ACCEPTED = {
    "accepted",
    "new",
    "pending_new",
    "accepted_for_bidding",
    "partially_filled",
    "filled",
}


def instructions(identifier, cfg, snapshot, changes, targets):
    from .paper import digest

    equity = decimal(snapshot["equity"])
    reserve = equity * decimal(cfg["policy"]["cash_reserve"])
    buys = [c for c in changes if c["side"] == "buy"]
    margin = cfg.get("funding_policy") == "paper_margin"
    sale_reference = sum(
        (decimal(c["max_notional"]) for c in changes if c["side"] == "sell"), ZERO
    )
    available = max(
        ZERO,
        (
            min(
                decimal(snapshot.get("buying_power", "0")),
                decimal(snapshot["cash"]) + sale_reference - reserve,
            )
            if margin
            else min(decimal(snapshot["cash"]), decimal(snapshot["spendable_cash"]))
        )
        - (ZERO if margin else reserve)
        - len(buys) * ONE,
    )
    sectors = {t["symbol"]: t["sector"] for t in targets}
    sectors.update({c["symbol"]: c["sector"] for c in changes})
    values = {p["symbol"]: decimal(p["market_value"]) for p in snapshot["positions"]}
    if margin:
        for c in changes:
            if c["side"] == "sell":
                values[c["symbol"]] = max(
                    ZERO, values.get(c["symbol"], ZERO) - decimal(c["max_notional"])
                )
    by_sector = {}
    for symbol, value in values.items():
        sector = sectors.get(symbol, "Unknown")
        by_sector[sector] = by_sector.get(sector, ZERO) + value
    wants = {}
    for c in buys:
        capacity = max(
            ZERO,
            equity
            * min(decimal(c["target_weight"]), decimal(cfg["policy"]["max_weight"]))
            - values.get(c["symbol"], ZERO),
        )
        wants[c["symbol"]] = min(decimal(c["max_notional"]), capacity)
    for sector in {c["sector"] for c in buys}:
        members = [c["symbol"] for c in buys if c["sector"] == sector]
        total = sum((wants[s] for s in members), ZERO)
        room = max(
            ZERO,
            equity * decimal(cfg["policy"]["sector_cap"]) - by_sector.get(sector, ZERO),
        )
        scale = min(ONE, room / total) if total else ZERO
        for s in members:
            wants[s] *= scale
    total = sum(wants.values(), ZERO)
    scale = min(ONE, available / total) if total else ZERO
    orders, deferred = [], []
    for c in sorted(changes, key=lambda c: (c["side"] != "sell", c["symbol"])):
        request = {
            "symbol": c["symbol"],
            "side": c["side"],
            "type": "market",
            "time_in_force": "day",
            "extended_hours": False,
            "client_order_id": "ap-"
            + digest([identifier, c["symbol"], c["side"], VERSION])[:40],
        }
        if c["side"] == "sell":
            request["qty"] = c["quantity"]
        else:
            amount = (wants[c["symbol"]] * scale).quantize(CENT, rounding="ROUND_DOWN")
            if decimal(c["max_notional"]) - amount >= ONE:
                deferred.append(
                    {
                        "symbol": c["symbol"],
                        "amount": str(decimal(c["max_notional"]) - amount),
                        "reason": "Exceeds available broker buying power, reference cash reserve or capacity. Review on a later launch."
                        if margin
                        else "Needs available cash or capacity; no sale proceeds or assumed sale fills fund this batch. Prepare a fresh review on a later launch.",
                    }
                )
            if amount < ONE:
                continue
            request["notional"] = str(amount)
        orders.append(request)
    return orders, deferred


def fill_check(store, broker, *, performance=True):
    from .paper import account_orders, plans, reconcile

    snapshot = reconcile(store, broker, performance=performance)
    batches = plans(store)
    saved = account_orders(store, snapshot["account_key"], batches=batches)
    update_fill_check(store, snapshot, saved, batches)
    return snapshot


def update_fill_check(store, snapshot, saved, batches):
    from .paper import UNCERTAIN, expected_cash, expected_positions, set_state

    latest_batch = next(
        (p["id"] for p in batches if any(o["plan_id"] == p["id"] for o in saved)), None
    )
    latest_orders = [o for o in saved if o["plan_id"] == latest_batch]
    issues = list(snapshot["issues"])
    if decimal(snapshot["cash"]) < ZERO:
        issues.append(
            f"Simulated margin debit {abs(decimal(snapshot['cash'])):,.2f} USD remains. Review broker cash and any unfinished sells. No automatic liquidation or cash transfer is performed."
        )
    counts = {}
    for o in latest_orders:
        counts[o["state"]] = counts.get(o["state"], 0) + 1
    for p in batches:
        if p.get("config", {}).get("execution_version") != VERSION:
            continue
        own = [o for o in saved if o["plan_id"] == p["id"]]
        if p["state"] in ("complete", "prepared") or not own:
            continue
        if any(o["state"] in TERMINAL - {"filled"} for o in own):
            if p["state"] in ("stopped", "expired", "superseded"):
                continue
            set_state(
                store,
                p["id"],
                "blocked",
                "A staged instruction ended without a full fill. Actual fills are retained. Reconcile before preparing a fresh review.",
                expected_state=p["state"],
            )
        elif len(own) == len(p.get("staged_orders", [])) and all(
            o["state"] == "filled" for o in own
        ):
            if any(
                decimal((o.get("broker") or {}).get("filled_qty", "0")) <= ZERO
                or decimal((o.get("broker") or {}).get("filled_avg_price") or "0")
                <= ZERO
                for o in own
            ):
                issues.append(
                    "A filled order lacks a positive confirmed quantity/price. Reconcile broker details before continuing."
                )
                if p["state"] not in ("blocked", "stopped", "expired", "superseded"):
                    set_state(
                        store,
                        p["id"],
                        "waiting_reconciliation",
                        issues[-1],
                        expected_state=p["state"],
                    )
                continue
            actual = {
                r["symbol"]: decimal(r["qty"])
                for r in snapshot["positions"]
                if decimal(r["qty"]) != ZERO
            }
            if (
                actual != expected_positions(p, own)
                or abs(decimal(snapshot["cash"]) - expected_cash(p, own)) > ONE
            ):
                issues.append(
                    "Filled orders do not yet reconcile to actual cash/positions. Refresh before another rebalance."
                )
                if p["state"] not in ("blocked", "stopped", "expired", "superseded"):
                    set_state(
                        store,
                        p["id"],
                        "waiting_reconciliation",
                        issues[-1],
                        expected_state=p["state"],
                    )
                continue
            set_state(
                store,
                p["id"],
                "complete",
                "All staged orders filled and broker records reconciled. Actual prices and weights may differ from references."
                + (
                    " A simulated margin debit remains; inspect cash before the next review."
                    if decimal(snapshot["cash"]) < ZERO
                    else ""
                )
                + (
                    " Deferred amounts need a fresh review."
                    if p.get("deferred_buys")
                    else ""
                ),
                expected_state=p["state"],
            )
    if any(o["state"] in UNCERTAIN for o in saved):
        issues.append(
            "A submission is still uncertain. Refresh and review its client reference in the paper order lifecycle."
        )
    result = {
        "checked_at": now(),
        "counts": counts,
        "issues": issues,
        "status": "attention"
        if issues or any(o["state"] in TERMINAL - {"filled"} for o in latest_orders)
        else "checked",
    }
    store.set_preference("paper_fill_check", result)


def execute(store, p, broker, at):
    # API approval and an automatic worker can overlap. Serialize the complete
    # read/check/one-attempt write across processes, then reload current state.
    from .paper import FINAL, plan

    with Path(store.path).with_suffix(".orders.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        p = plan(store, p["id"])
        if p["state"] in FINAL:
            return
        return _execute(store, p, broker, at)


def approve_and_stage(store, identifier, broker=None):
    """A successful manual approval response means broker acceptance, not a queue."""
    from .paper import UTC, Broker, datetime, plan, schedule, set_state

    p = schedule(store, identifier)
    if p["config"]["execution_version"] != VERSION:
        return p
    owned = broker is None
    try:
        broker = broker or Broker()
        for _ in range(len(p["staged_orders"]) + 2):
            execute(store, p, broker, datetime.now(UTC))
            p = plan(store, identifier)
            if p["state"] in ("broker_staged", "complete"):
                return p
            if p["state"] in ("blocked", "expired", "stopped"):
                raise ResearchError(p["message"])
        raise ResearchError(
            "Staging is incomplete. Reconcile the saved client references before continuing."
        )
    except ResearchError as error:
        current = plan(store, identifier)
        if current["state"] not in ("blocked", "expired", "stopped"):
            set_state(
                store,
                identifier,
                "blocked",
                str(error),
                expected_state=current["state"],
            )
        raise
    except Exception:
        message = "Broker acceptance could not be confirmed. Reconcile saved client references; no assumed remainder or duplicate will be sent."
        set_state(store, identifier, "blocked", message)
        raise ResearchError(message) from None
    finally:
        if owned and broker is not None:
            broker.close()


def _execute(store, p, broker, at):
    from .paper import (
        approval,
        configuration,
        expected_cash,
        expected_positions,
        order_write_lock,
        orders,
        reconcile,
        require_runnable_plan,
        set_state,
    )

    require_runnable_plan(p)
    intended = p["staged_orders"]
    count = len(orders(store, p["id"]))
    snap = (
        reconcile(store, broker, staging=True)
        if 0 < count < len(intended)
        else fill_check(store, broker, performance=False)
    )
    cfg = configuration(store)
    allowed = approval(store, cfg, snap)
    if not cfg or cfg["hash"] != p["config_hash"] or cfg["paused"] or not allowed:
        raise ResearchError(
            "Matching paper approval is absent or paused. Already accepted broker orders remain active until filled or canceled."
        )
    if paper_strategy(cfg["strategy_id"])["version"] != cfg["strategy_version"]:
        raise ResearchError(
            "The strategy version changed. Obtain fresh paper approval before staging."
        )
    if cfg["mode"] == "automatic" and not allowed["allow_automatic"]:
        raise ResearchError("Automatic paper submission is not approved.")
    if (
        snap["account_key"] != p["account_key"]
        or allowed["account_key"] != p["account_key"]
        or snap["issues"]
    ):
        raise ResearchError(
            "Resolve paper account identity/issues before staging orders."
        )
    own = orders(store, p["id"])
    known = {o["client_id"] for o in own}
    if any(o.get("client_order_id") not in known for o in snap["open_orders"]):
        raise ResearchError(
            "An external open order changed the account. Reconcile before staging."
        )
    if any(o["state"] in {"unknown", "submitting"} for o in own):
        raise ResearchError(
            "A submission outcome is uncertain. Reconcile by client ID; no blind retry or duplicate order is allowed."
        )
    if any(o["state"] in TERMINAL - {"filled"} for o in own):
        raise ResearchError(
            "A broker order failed or expired. Actual partial fills remain; prepare a fresh review after reconciliation."
        )
    actual = {
        r["symbol"]: decimal(r["qty"])
        for r in snap["positions"]
        if decimal(r["qty"]) != ZERO
    }
    if actual != expected_positions(p, own):
        raise ReconciliationPending(
            "Positions differ from confirmed fills; waiting for a consistent broker snapshot before any further submission."
        )
    if abs(decimal(snap["cash"]) - expected_cash(p, own)) > ONE:
        raise ResearchError(
            "Account cash changed beyond confirmed fills. Reconcile and prepare a fresh review."
        )
    remaining = [r for r in intended if r["client_order_id"] not in known]
    if not remaining:
        if all(o["state"] == "filled" for o in own):
            # fill_check alone marks completion after cash/position comparison.
            return
        elif all(o["state"] in ACCEPTED for o in own):
            set_state(
                store,
                p["id"],
                "broker_staged",
                f"All {len(own)} orders accepted by Alpaca for {p['execute_session']}. You may close Aperture; accepted orders remain active. Fills will be checked next launch."
                + (
                    " Any deferred amounts were not submitted."
                    if p.get("deferred_buys")
                    else ""
                ),
                expected_state=p["state"],
            )
        else:
            raise ReconciliationPending(
                "Waiting for explicit broker acceptance before reporting the batch staged."
            )
        return
    deadline = calendar.open_time(date.fromisoformat(p["execute_session"]))
    from .paper import UTC
    from .paper import datetime as wall_clock

    expired = (
        "The staging deadline has passed. Existing accepted orders remain at Alpaca. "
        "Reconcile and prepare a fresh review for remaining instructions."
    )
    if max(at, wall_clock.now(UTC)) + DELIVERY_MARGIN >= deadline:
        set_state(
            store,
            p["id"],
            "expired",
            expired,
            expected_state=p["state"],
        )
        return
    request = remaining[0]
    broker.asset(request["symbol"])
    if request["side"] == "buy":
        # Freeze spending independently of sells. Reserve every unfilled order.
        paid = {
            o["client_id"]: decimal((o.get("broker") or {}).get("filled_qty", "0"))
            * decimal((o.get("broker") or {}).get("filled_avg_price") or "0")
            for o in own
            if o["side"] == "buy"
        }

        def outstanding(r):
            return max(
                ZERO,
                decimal(r.get("notional", "0")) - paid.get(r["client_order_id"], ZERO),
            )

        reserved = sum(
            (
                outstanding(r)
                for r in intended
                if r["side"] == "buy"
                and r["client_order_id"] != request["client_order_id"]
            ),
            ZERO,
        )
        broker_reserved = sum(
            (
                outstanding(r)
                for r in intended
                if any(
                    o["client_id"] == r["client_order_id"]
                    and o["state"] not in TERMINAL
                    for o in own
                )
            ),
            ZERO,
        )
        floor = decimal(p["account"]["equity"]) * decimal(cfg["policy"]["cash_reserve"])
        margin = cfg.get("funding_policy") == "paper_margin"
        available = (
            min(
                decimal(p["account"].get("buying_power", "0"))
                - sum(paid.values(), ZERO)
                if margin
                else decimal(p["account"]["spendable_cash"]) - sum(paid.values(), ZERO),
                decimal(snap.get("buying_power", "0")) + broker_reserved
                if margin
                else min(
                    decimal(snap["spendable_cash"]) + broker_reserved,
                    decimal(snap["cash"]),
                ),
            )
            - (ZERO if margin else floor)
            - reserved
            - len([r for r in intended if r["side"] == "buy"])
        )
        if decimal(request["notional"]) > available:
            raise ResearchError(
                "Broker buying power no longer covers the frozen batch and reserves. Reconcile before a fresh review."
                if margin
                else "Available cash no longer covers the frozen batch and reserves; no borrowing or anticipated sells fund these buys."
            )

    def check_permission():
        if configuration(store) != cfg or not approval(store, cfg, snap):
            raise SubmissionNotSent(
                "Paper settings or approval changed before submission."
            )

    def save_receipt(state, response):
        with store.connect() as db:
            db.execute(
                """UPDATE paper_orders SET state=?,body=?,updated_at=?
                   WHERE client_id=? AND state='submitting'""",
                (
                    state,
                    json.dumps({"request": request, "broker": response}),
                    now(),
                    request["client_order_id"],
                ),
            )

    with order_write_lock(store):
        check_permission()
        # Request is frozen into the plan. Persist before exactly one network attempt.
        with store.connect() as db:
            db.execute(
                "INSERT INTO paper_orders VALUES (?,?,?,?,?,?,?)",
                (
                    request["client_order_id"],
                    p["id"],
                    request["symbol"],
                    request["side"],
                    "submitting",
                    json.dumps({"request": request, "broker": None}),
                    now(),
                ),
            )
        try:
            clock_start = time.monotonic()
            try:
                clock = broker.clock()
                stamp = datetime.fromisoformat(clock["timestamp"])
                opening = datetime.fromisoformat(clock["next_open"])
                if (
                    stamp.tzinfo is None
                    or opening.tzinfo is None
                    or type(clock["is_open"]) is not bool
                ):
                    raise ValueError
            except (ResearchError, KeyError, ValueError, TypeError) as error:
                raise SubmissionNotSent(
                    "The broker session clock could not be verified. This order was not sent."
                ) from error

            def before_send():
                check_permission()
                broker_now = stamp + timedelta(seconds=time.monotonic() - clock_start)
                if max(wall_clock.now(UTC), broker_now) + DELIVERY_MARGIN >= deadline:
                    raise SubmissionNotSent(expired)
                if clock["is_open"] or opening != deadline or stamp >= opening:
                    raise SubmissionNotSent(
                        "Alpaca does not confirm the intended upcoming regular open. This order was not sent."
                    )

            response, status = broker.submit(request, before_send=before_send)
        except SubmissionNotSent as error:
            save_receipt("not_sent", {"reason": str(error)})
            if str(error) == expired:
                set_state(store, p["id"], "expired", expired, expected_state=p["state"])
                return
            raise
        save_receipt((response or {}).get("status", "unknown"), response)
    if status == "unknown":
        raise ResearchError(
            "Submission outcome is uncertain. Reconcile the saved client ID before doing anything else; no duplicate retry will be sent."
        )
    if (response or {}).get("status") not in ACCEPTED:
        raise ResearchError(
            "Broker did not confirm acceptance. Inspect any already accepted orders at Alpaca; no automatic resubmission."
        )
    set_state(
        store,
        p["id"],
        "staging",
        f"Broker accepted {len(own) + 1} of {len(intended)} instructions. Keep Aperture open until all orders are confirmed staged.",
        expected_state=p["state"],
    )
