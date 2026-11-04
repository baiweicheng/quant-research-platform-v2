"""Broker-held paper MARKET DAY orders with explicit funding and durable receipts."""

import json
import fcntl
from datetime import date
from pathlib import Path

from . import calendar
from .broker import TERMINAL, ReconciliationPending
from .domain import CENT, ONE, ZERO, ResearchError, decimal
from .store import now

VERSION = "paper-broker-market-day-v1"
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
    from .paper import orders, plans, reconcile, set_state, expected_positions

    snapshot = reconcile(store, broker, performance=performance)
    saved = orders(store)
    batches = plans(store)
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
        if p["state"] in ("complete", "prepared"):
            continue
        if any(o["state"] in TERMINAL - {"filled"} for o in own):
            set_state(
                store,
                p["id"],
                "blocked",
                "Broker reports a rejected, canceled, expired or replaced order. Actual fills are retained; no remainder is resubmitted. Reconcile before a fresh review.",
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
                set_state(store, p["id"], "waiting_reconciliation", issues[-1])
                continue
            actual = {
                r["symbol"]: decimal(r["qty"])
                for r in snapshot["positions"]
                if decimal(r["qty"]) != ZERO
            }
            expected_cash = decimal(p["account"]["cash"])
            for o in own:
                b = o.get("broker") or {}
                expected_cash += (
                    decimal(b.get("filled_qty", "0"))
                    * decimal(b.get("filled_avg_price") or "0")
                    * (ONE if o["side"] == "sell" else -ONE)
                )
            if (
                actual != expected_positions(p, own)
                or abs(decimal(snapshot["cash"]) - expected_cash) > ONE
            ):
                issues.append(
                    "Filled orders do not yet reconcile to actual cash/positions. Refresh before another rebalance."
                )
                set_state(store, p["id"], "waiting_reconciliation", issues[-1])
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
            )
    result = {
        "checked_at": now(),
        "counts": counts,
        "issues": issues,
        "status": "attention"
        if issues
        or any(o["state"] in TERMINAL - {"filled"} for o in latest_orders)
        or any(o["state"] in {"unknown", "submitting"} for o in saved)
        else "checked",
    }
    store.set_preference("paper_fill_check", result)
    return snapshot


def execute(store, p, broker, at):
    # API approval and an automatic worker can overlap. Serialize the complete
    # read/check/one-attempt write across processes, then reload current state.
    from .paper import plan, FINAL

    with Path(store.path).with_suffix(".orders.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        p = plan(store, p["id"])
        if p["state"] in FINAL:
            return
        return _execute(store, p, broker, at)


def approve_and_stage(store, identifier, broker=None):
    """A successful manual approval response means broker acceptance, not a queue."""
    from .paper import schedule, plan, set_state, Broker, datetime, UTC

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
        set_state(store, identifier, "blocked", str(error))
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
        configuration,
        approval,
        orders,
        expected_positions,
        set_state,
    )

    snap = fill_check(store, broker, performance=False)
    cfg = configuration(store)
    allowed = approval(store, cfg, snap)
    if not cfg or cfg["hash"] != p["config_hash"] or cfg["paused"] or not allowed:
        raise ResearchError(
            "Matching paper approval is absent or paused. Already accepted broker orders remain active until filled or canceled."
        )
    from .domain import strategy

    if strategy(cfg["strategy_id"])["version"] != cfg["strategy_version"]:
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
    expected_cash = decimal(p["account"]["cash"])
    for o in own:
        b = o.get("broker") or {}
        qty = decimal(b.get("filled_qty", "0"))
        if qty:
            if b.get("filled_avg_price") is None:
                raise ReconciliationPending(
                    "Filled quantity lacks an average price; reconcile before continuing."
                )
            expected_cash += (
                qty
                * decimal(b["filled_avg_price"])
                * (ONE if o["side"] == "sell" else -ONE)
            )
    if abs(decimal(snap["cash"]) - expected_cash) > ONE:
        raise ResearchError(
            "Account cash changed beyond confirmed fills. Reconcile and prepare a fresh review."
        )
    intended = p["staged_orders"]
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
            )
        else:
            raise ReconciliationPending(
                "Waiting for explicit broker acceptance before reporting the batch staged."
            )
        return
    if at >= calendar.open_time(date.fromisoformat(p["execute_session"])):
        set_state(
            store,
            p["id"],
            "expired",
            "The staging deadline has passed. Existing accepted orders remain at Alpaca; remaining instructions were not sent. Reconcile and prepare a fresh review.",
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
    if configuration(store) != cfg or not approval(store, cfg, snap):
        raise ResearchError("Paper settings or approval changed before submission.")
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
    response, status = broker.submit(request)
    with store.connect() as db:
        db.execute(
            "UPDATE paper_orders SET state=?,body=?,updated_at=? WHERE client_id=?",
            (
                (response or {}).get("status", "unknown"),
                json.dumps({"request": request, "broker": response}),
                now(),
                request["client_order_id"],
            ),
        )
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
    )
