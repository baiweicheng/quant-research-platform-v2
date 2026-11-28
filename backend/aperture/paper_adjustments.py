"""Reconcile documented paper account activity against a specific account read."""

from datetime import date, datetime

from .broker import CORPORATE_ACTIVITY, NY, TERMINAL
from .domain import ONE, ZERO, ResearchError, decimal
from .store import now

REVIEW_MESSAGE = "Recent corporate action activity needs a documented broker review before new paper orders."


def reviews(store, account_key):
    return store.preference("paper_adjustments_" + account_key) or {
        "activities": {},
        "plans": {},
    }


def unreviewed_actions(store, snapshot):
    known = reviews(store, snapshot["account_key"])["activities"]
    return [
        a
        for a in snapshot.get("broker_activities", ())
        if a["activity_type"] in CORPORATE_ACTIVITY and a.get("id") not in known
    ]


def guard(store, snapshot):
    issues = [issue for issue in snapshot["issues"] if issue != REVIEW_MESSAGE]
    if unreviewed_actions(store, snapshot):
        issues.append(REVIEW_MESSAGE)
    return {**snapshot, "issues": issues}


def differences(store, p, own, snapshot):
    from .paper import expected_cash, expected_positions

    actual = {r["symbol"]: decimal(r["qty"]) for r in snapshot["positions"]}
    expected = expected_positions(p, own)
    resolution = reviews(store, snapshot["account_key"])["plans"].get(p["id"], {})
    share_adjustments = resolution.get("positions", {})
    deltas = {}
    for symbol in sorted(actual.keys() | expected.keys() | share_adjustments.keys()):
        delta = (
            actual.get(symbol, ZERO)
            - expected.get(symbol, ZERO)
            - decimal(share_adjustments.get(symbol, "0"))
        )
        if delta:
            deltas[symbol] = str(delta.normalize())
    cash = (
        decimal(snapshot["cash"])
        - expected_cash(p, own)
        - decimal(resolution.get("cash", "0"))
    )
    return cash, deltas


def proposed_review(store, snapshot, saved, batches):
    try:
        return _proposed_review(store, snapshot, saved, batches)
    except (ValueError, TypeError, ResearchError):
        return None  # Missing or malformed evidence cannot authorize reconciliation.


def _proposed_review(store, snapshot, saved, batches):
    from .paper import FINAL, digest
    from .staged import VERSION

    if (
        snapshot["open_orders"]
        or any(issue != REVIEW_MESSAGE for issue in snapshot["issues"])
        or any(o["state"] not in TERMINAL | {"planned"} for o in saved)
    ):
        return None
    account_plans = [p for p in batches if p["account_key"] == snapshot["account_key"]]
    p = account_plans[0] if account_plans else None
    if any(
        row["state"] not in FINAL | {"waiting_reconciliation", "broker_staged"}
        for row in account_plans
    ):
        return None
    actions = unreviewed_actions(store, snapshot)
    evidence = list(actions)
    cash = ZERO
    positions = {}
    review_plan = None
    if p and p["state"] != "complete" and p["config"]["execution_version"] == VERSION:
        own = [o for o in saved if o["plan_id"] == p["id"]]
        if own:
            observed = [o.get("broker") or {} for o in own]
            if any(
                o["state"] == "filled"
                and (
                    decimal(r.get("filled_qty") or "0") <= ZERO
                    or decimal(r.get("filled_avg_price") or "0") <= ZERO
                )
                for o, r in zip(own, observed, strict=True)
            ):
                return None
            cash, positions = differences(store, p, own, snapshot)
            if abs(cash) > ONE or positions:
                review_plan = p["id"]
                baseline = datetime.fromisoformat(
                    p["account"].get("checked_at") or p["created_at"]
                ).astimezone(NY)
                order_ids = {r["id"] for r in observed if r.get("id")}
                rows = snapshot.get("broker_activities", ())
                if any(
                    a["activity_type"] == "FILL"
                    and a.get("order_id") not in order_ids
                    and (
                        not a.get("transaction_time")
                        or datetime.fromisoformat(a["transaction_time"]) >= baseline
                    )
                    for a in rows
                ):
                    return None
                used = reviews(store, snapshot["account_key"])["plans"].get(
                    review_plan, {}
                )
                used_ids = used.get("activity_ids", ())
                evidence = [
                    a
                    for a in rows
                    if a["activity_type"] != "FILL"
                    and a.get("id") not in used_ids
                    and a.get("date")
                    and date.fromisoformat(a["date"][:10]) >= baseline.date()
                ]
                corporate = [
                    a for a in evidence if a["activity_type"] in CORPORATE_ACTIVITY
                ]
                if positions and not corporate:
                    return None
                named = {a["symbol"] for a in corporate if a.get("symbol")}
                if positions and named and not named.intersection(positions):
                    return None
                # Cash is tied to the amounts on the actual broker receipts.
                total = sum(
                    (decimal(a.get("net_amount") or "0") for a in evidence), ZERO
                )
                if abs(cash - total) > ONE:
                    return None
                cash = total
                evidence.extend(a for a in actions if a not in evidence)
    if not evidence or any(not a.get("id") or not a.get("date") for a in evidence):
        return None
    if len({a["id"] for a in evidence}) != len(evidence):
        return None
    review = {
        "account_key": snapshot["account_key"],
        "plan_id": review_plan,
        "cash": str(cash.normalize()),
        "positions": positions,
        "activities": sorted(evidence, key=lambda a: a["id"]),
        "observed_cash": str(decimal(snapshot["cash"]).normalize()),
        "observed_positions": {
            row["symbol"]: str(decimal(row["qty"]).normalize())
            for row in snapshot["positions"]
        },
    }
    return {**review, "reference": digest(review)}


def confirm_adjustment(store, broker, reference):
    from .paper import account_orders, event, order_write_lock, plans, reconcile
    from .staged import update_fill_check

    with order_write_lock(store):
        snapshot = reconcile(store, broker)
        batches = plans(store)
        saved = account_orders(store, snapshot["account_key"], batches=batches)
        review = proposed_review(store, snapshot, saved, batches)
        if not review or review["reference"] != reference:
            raise ResearchError(
                "The broker adjustment or account changed. Refresh and review the current activity."
            )
        account_key = snapshot["account_key"]
        recorded = reviews(store, account_key)
        for a in review["activities"]:
            recorded["activities"][a["id"]] = {"activity": a, "confirmed_at": now()}
        if identifier := review["plan_id"]:
            prior = recorded["plans"].get(identifier, {})
            positions = prior.get("positions", {})
            for symbol, qty in review["positions"].items():
                positions[symbol] = str(
                    decimal(positions.get(symbol, "0")) + decimal(qty)
                )
            recorded["plans"][identifier] = {
                "cash": str(decimal(prior.get("cash", "0")) + decimal(review["cash"])),
                "positions": positions,
                "activity_ids": sorted(
                    set(prior.get("activity_ids", ()))
                    | {a["id"] for a in review["activities"]}
                ),
                "confirmed_at": now(),
            }
        store.set_preference("paper_adjustments_" + account_key, recorded)
        snapshot = guard(store, snapshot)
        store.set_preference("paper_snapshot", snapshot)
        update_fill_check(store, snapshot, saved, batches)
        event(
            store,
            "Confirmed documented broker activity against current paper cash and positions.",
        )
    return {"confirmed": True}
