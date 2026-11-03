"""Version-approved, durable, cash-constrained weekly PAPER execution only."""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import ROUND_DOWN
from uuid import uuid4

from . import __version__, calendar
from .broker import NY, TERMINAL, Broker, ReconciliationPending
from .domain import CENT, ONE, SHARE, ZERO, Policy, ResearchError, decimal, strategy
from .portfolio import target_weights
from .signals import rank
from .store import decode, encode, now

FINAL = {"complete", "blocked", "stopped", "expired", "superseded"}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def initialize(store):
    with store.connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS paper_approvals (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, config_hash TEXT NOT NULL,
            account_key TEXT NOT NULL, body TEXT NOT NULL, revoked_at TEXT);
        CREATE TABLE IF NOT EXISTS paper_plans (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            state TEXT NOT NULL, message TEXT NOT NULL, body BLOB NOT NULL);
        CREATE TABLE IF NOT EXISTS paper_orders (
            client_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, symbol TEXT NOT NULL,
            side TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT OR IGNORE INTO schema_version VALUES (3);
        CREATE TABLE IF NOT EXISTS paper_events (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, message TEXT NOT NULL);
        """)


def event(store, message):
    with store.connect() as db:
        db.execute(
            "INSERT INTO paper_events(created_at,message) VALUES (?,?)",
            (now(), message),
        )


def policy_from(data):
    return Policy(
        positions=int(data["positions"]),
        max_weight=decimal(data["max_weight"]),
        sector_cap=decimal(data["sector_cap"]),
        cash_reserve=decimal(data["cash_reserve"]),
    )


def configuration(store):
    return store.preference("paper_config")


def save_configuration(store, data):
    recipe = strategy(data["strategy_id"])
    policy = policy_from(data)
    if not decimal(".01") <= policy.cash_reserve <= decimal(".5"):
        raise ResearchError(
            "For paper execution keep a cash reserve between 1% and 50%."
        )
    if not decimal(".001") <= decimal(data["max_drift"]) <= decimal(".05"):
        raise ResearchError("Choose a maximum price change between 0.1% and 5%.")
    from .providers import validate_symbols

    symbols = validate_symbols(data["symbols"])
    if not any(s != "SPY" for s in symbols):
        raise ResearchError("Choose at least one US stock for the paper universe.")
    symbols = sorted(set(symbols) | {"SPY"})
    start = date.fromisoformat(data["data_start"])
    if start < date(2016, 1, 4) or start >= calendar.latest_complete():
        raise ResearchError(
            "Choose a data start from 2016 before the latest completed session."
        )
    if any(p["state"] not in FINAL for p in plans(store)):
        raise ResearchError(
            "Stop the current plan and reconcile outstanding orders before changing its settings."
        )
    if any(o["state"] not in TERMINAL | {"planned"} for o in orders(store)):
        raise ResearchError(
            "Reconcile or cancel pending orders before changing paper settings."
        )
    body = {
        "strategy_id": recipe["id"],
        "strategy_version": recipe["version"],
        "policy": {k: str(v) for k, v in vars(policy).items()},
        "max_drift": str(decimal(data["max_drift"])),
        "symbols": symbols,
        "data_start": str(start),
        "execution_version": "paper-limits-v1",
        "environment": "paper",
    }
    body["hash"] = digest(body)
    body.update(mode=data["mode"], paused=False, updated_at=now())
    store.set_preference("paper_config", body)
    event(
        store,
        "Paper settings saved. Matching strategy, account and policy approval is required before submission.",
    )
    return body


def approval(store, cfg=None, snapshot=None):
    cfg = cfg or configuration(store)
    snapshot = snapshot or store.preference("paper_snapshot", {})
    if not cfg or not snapshot:
        return None
    with store.connect() as db:
        row = db.execute(
            "SELECT * FROM paper_approvals WHERE config_hash=? AND account_key=? AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1",
            (cfg["hash"], snapshot.get("account_key")),
        ).fetchone()
    return (
        {**json.loads(row["body"]), "id": row["id"], "created_at": row["created_at"]}
        if row
        else None
    )


def approve_strategy(store, data):
    cfg = configuration(store)
    snap = store.preference("paper_snapshot", {})
    if not cfg or not snap:
        raise ResearchError(
            "Save paper settings and refresh the paper account before approval."
        )
    expected = f"APPROVE PAPER {cfg['strategy_id']} {cfg['strategy_version']}"
    if data.get("confirmation") != expected or not data.get("acknowledge_limits"):
        raise ResearchError(
            "Type the displayed approval phrase and acknowledge the data, risk and dedicated-account limits."
        )
    if data.get("config_hash") != cfg["hash"]:
        raise ResearchError(
            "Paper settings changed. Review the new settings before approval."
        )
    if snap["issues"]:
        raise ResearchError(
            "Resolve the account issues before approval: " + " ".join(snap["issues"])
        )
    if (
        datetime.now(UTC) - datetime.fromisoformat(snap["checked_at"])
    ).total_seconds() > 300:
        raise ResearchError(
            "Refresh the paper account before approval; the saved account check is over five minutes old."
        )
    if len(data.get("rationale", "").strip()) < 10:
        raise ResearchError(
            "Record why you approve this paper experiment and what you reviewed."
        )
    body = {
        "config_hash": cfg["hash"],
        "account_key": snap["account_key"],
        "environment": "paper",
        "strategy_id": cfg["strategy_id"],
        "strategy_version": cfg["strategy_version"],
        "policy": cfg["policy"],
        "symbols": cfg["symbols"],
        "rationale": data["rationale"].strip(),
        "allow_automatic": bool(data.get("allow_automatic")),
        "execution_version": cfg["execution_version"],
    }
    with store.connect() as db:
        db.execute(
            "INSERT INTO paper_approvals VALUES (?,?,?,?,?,NULL)",
            (str(uuid4()), now(), cfg["hash"], snap["account_key"], json.dumps(body)),
        )
    event(
        store,
        "Explicit paper strategy/version/policy approval recorded. Live trading remains unavailable.",
    )
    return approval(store)


def revoke(store):
    with store.connect() as db:
        db.execute(
            "UPDATE paper_approvals SET revoked_at=? WHERE revoked_at IS NULL", (now(),)
        )
    stop(store)
    event(
        store,
        "Paper strategy approval revoked. Existing broker orders must still be reconciled or canceled.",
    )


def plans(store):
    with store.connect() as db:
        rows = db.execute(
            "SELECT * FROM paper_plans ORDER BY created_at DESC"
        ).fetchall()
    return [
        {
            **decode(r["body"]),
            **{k: r[k] for k in ("id", "created_at", "updated_at", "state", "message")},
        }
        for r in rows
    ]


def plan(store, identifier):
    p = next((p for p in plans(store) if p["id"] == identifier), None)
    if not p:
        raise ResearchError("That paper plan was not found.")
    return p


def set_state(store, identifier, state, message):
    with store.connect() as db:
        current = db.execute(
            "SELECT state,message FROM paper_plans WHERE id=?", (identifier,)
        ).fetchone()
        if current and current["state"] == state and current["message"] == message:
            return
        db.execute(
            "UPDATE paper_plans SET state=?,message=?,updated_at=? WHERE id=?",
            (state, message, now(), identifier),
        )
    event(store, message)


def orders(store, identifier=None):
    with store.connect() as db:
        rows = db.execute(
            "SELECT * FROM paper_orders ORDER BY updated_at,client_id"
        ).fetchall()
    return [
        {
            **json.loads(r["body"]),
            **{
                k: r[k]
                for k in (
                    "client_id",
                    "plan_id",
                    "symbol",
                    "side",
                    "state",
                    "updated_at",
                )
            },
        }
        for r in rows
        if identifier is None or r["plan_id"] == identifier
    ]


def public_state(store):
    cfg = configuration(store)
    snap = store.preference("paper_snapshot")
    with store.connect() as db:
        events = [
            dict(r)
            for r in db.execute("SELECT * FROM paper_events ORDER BY id DESC LIMIT 100")
        ]
    return {
        "config": cfg,
        "snapshot": snap,
        "approval": approval(store),
        "plans": plans(store),
        "orders": orders(store),
        "events": events,
        "quote_waits": store.preference("paper_quote_waits"),
        "performance": store.preference("paper_performance"),
        "last_error": store.preference("paper_error"),
        "worker_seen": store.preference("worker_seen"),
        "automatic_status": store.preference(
            "paper_auto_status", "Manual mode. Prepare a weekly review when ready."
        ),
    }


def signature(snap):
    return digest(
        {
            "account": snap["account_key"],
            "cash": snap["cash"],
            "positions": sorted(
                (p["symbol"], str(decimal(p["qty"]))) for p in snap["positions"]
            ),
        }
    )


def reconcile(store, broker, performance=False, dataset=None):
    snap = broker.snapshot()
    store.set_preference("paper_snapshot", snap)
    store.set_preference("paper_error", None)
    # Track every known broker order by immutable client identifier, including after restart.
    for o in orders(store):
        if o["state"] == "planned":
            continue
        b = broker.find_order(o["client_id"])
        if b:
            if b.get("symbol") != o["symbol"] or b.get("side") != o["side"]:
                raise ResearchError(
                    "Broker order identity does not match the saved plan. Submission stopped."
                )
            with store.connect() as db:
                db.execute(
                    "UPDATE paper_orders SET state=?,body=?,updated_at=? WHERE client_id=?",
                    (
                        b.get("status", "unknown"),
                        json.dumps({**o, "broker": b}),
                        now(),
                        o["client_id"],
                    ),
                )
        elif o["state"] not in TERMINAL:
            with store.connect() as db:
                db.execute(
                    "UPDATE paper_orders SET state='unknown',updated_at=? WHERE client_id=?",
                    (now(), o["client_id"]),
                )
    if performance:
        from .account_performance import refresh

        if dataset is None:
            summaries = store.datasets()
            usable = next(
                (
                    d
                    for d in summaries
                    if d.get("metadata", {}).get("provider") == "alpaca"
                ),
                None,
            )
            dataset = store.dataset(usable["id"]) if usable else None
        try:
            store.set_preference("paper_performance", refresh(store, broker, dataset))
        except ResearchError as e:
            store.set_preference(
                "paper_performance",
                {"available": False, "curve": [], "windows": {}, "notes": [str(e)]},
            )
    return snap


def ensure_account(snap, cfg):
    if snap["issues"]:
        raise ResearchError(" ".join(snap["issues"]))
    outside = [
        p["symbol"]
        for p in snap["positions"]
        if p["symbol"] not in cfg["symbols"] or p["symbol"] == "SPY"
    ]
    if outside:
        raise ResearchError(
            "Use a dedicated paper stock account. Holdings outside the approved universe must be resolved first: "
            + ", ".join(outside)
        )
    if snap["open_orders"]:
        raise ResearchError(
            "Open broker orders exist. Reconcile/cancel them before preparing a new plan."
        )


def prepare(store, job, progress, broker):
    cfg = configuration(store)
    if not cfg:
        raise ResearchError(
            "Choose the paper strategy, universe and risk policy first."
        )
    if strategy(cfg["strategy_id"])["version"] != cfg["strategy_version"]:
        raise ResearchError(
            "The strategy implementation version changed. Save new settings and obtain fresh approval."
        )
    if cfg["hash"] != job["payload"].get("config_hash"):
        raise ResearchError("Paper settings changed after this preparation was queued.")
    if any(p["state"] not in FINAL for p in plans(store)):
        raise ResearchError(
            "Review or stop the current paper plan before preparing another."
        )
    snap = reconcile(store, broker)
    if any(o["state"] not in TERMINAL for o in orders(store)):
        raise ResearchError(
            "Unresolved Aperture orders remain. Reconcile their client IDs or cancel pending orders before preparing another plan."
        )
    ensure_account(snap, cfg)
    progress(10, "Paper account reconciled; updating completed-session market data")
    from .providers import download_market

    latest = calendar.latest_complete()
    saved = download_market(
        store,
        {
            "name": "Paper universe",
            "symbols": cfg["symbols"],
            "start": cfg["data_start"],
            "end": str(latest),
        },
        lambda n, t: progress(10 + round(n * 0.5), t),
    )
    from .fundamentals import FUNDAMENTAL_STRATEGIES, attach

    if cfg["strategy_id"] in FUNDAMENTAL_STRATEGIES:
        saved = attach(
            store, saved["id"], lambda n, t: progress(60 + round(n * 0.25), t)
        )
    ds = store.dataset(saved["id"])
    if ds.kind == "synthetic" or ds.metadata.get("provider") != "alpaca":
        raise ResearchError("Paper preparation requires captured actual Alpaca prices.")
    if max(b.session for rows in ds.bars.values() for b in rows) != latest:
        raise ResearchError("Data is not current through the latest completed session.")
    ranked, excluded = rank(ds, cfg["strategy_id"], latest)
    policy = policy_from(
        {**cfg["policy"], "positions": int(cfg["policy"]["positions"])}
    )
    targets, notes = target_weights(ranked, policy)
    for symbol in targets:
        broker.asset(symbol)
    snap = reconcile(store, broker, performance=True, dataset=ds)
    ensure_account(snap, cfg)
    equity = decimal(snap["equity"])
    held = {p["symbol"]: decimal(p["qty"]) for p in snap["positions"]}
    prices = {
        s: next((b.close for b in reversed(rows) if b.session == latest), None)
        for s, rows in ds.bars.items()
    }
    changes = []
    for symbol in sorted(set(held) | set(targets)):
        price = prices.get(symbol)
        if price is None:
            raise ResearchError(
                f"{symbol}: the latest held-stock close is unavailable."
            )
        weight = targets.get(symbol, ZERO)
        # A small sizing cushion protects target caps and cash against fees.
        target_qty = (equity * weight * decimal(".999") / price).quantize(
            SHARE, rounding=ROUND_DOWN
        )
        current = held.get(symbol, ZERO)
        delta = target_qty - current
        if abs(delta) * price < ONE:
            continue
        side = "buy" if delta > ZERO else "sell"
        changes.append(
            {
                "symbol": symbol,
                "side": side,
                "quantity": str(abs(delta)),
                "reference_price": str(price),
                "max_notional": str((abs(delta) * price).quantize(CENT)),
                "before_weight": str(current * price / equity),
                "target_weight": str(weight),
                "sector": ds.sectors.get(symbol, "Unknown"),
                "reason": "Move toward the approved target; excluded names reduce toward zero.",
            }
        )
    # Broker eligibility also applies to reductions and holdings.
    for symbol in held:
        broker.asset(symbol)
    identifier = str(uuid4())
    body = {
        "id": identifier,
        "config_hash": cfg["hash"],
        "config": cfg,
        "engine_version": __version__,
        "account_key": snap["account_key"],
        "account_signature": signature(snap),
        "account": snap,
        "dataset_id": ds.id,
        "dataset_name": ds.name,
        "source_digest": ds.digest,
        "strategy": strategy(cfg["strategy_id"]),
        "decision_session": str(latest),
        "execute_session": str(calendar.next_session(latest)),
        "last_execution_session": str(
            calendar.next_session(calendar.next_session(latest))
        ),
        "targets": [
            {"symbol": s, "weight": str(w), "sector": ds.sectors.get(s, "Unknown")}
            for s, w in targets.items()
        ],
        "changes": changes,
        "cash_weight": str(ONE - sum(targets.values(), ZERO)),
        "signals": [
            {"symbol": s.symbol, "score": s.score, "components": s.components}
            for s in ranked
        ],
        "excluded": excluded,
        "notes": notes
        + [
            "Regular-hours DAY limit orders only; IEX quotes are one venue, not a consolidated NBBO.",
            "Sells are processed first. Their proceeds cannot fund buys until the following exchange session.",
            "Prices, positions, cash, approval and caps are rechecked before every submission; a changed plan requires a fresh review.",
        ],
    }
    if cfg != configuration(store):
        raise ResearchError(
            "Paper settings changed during preparation. No plan was published."
        )
    stamp = now()
    with store.connect() as db:
        db.execute(
            "INSERT INTO paper_plans VALUES (?,?,?,?,?,?)",
            (
                identifier,
                stamp,
                stamp,
                "prepared",
                "Read-only review prepared. Approval does not follow from research.",
                encode(body),
            ),
        )
    progress(98, "Immutable paper review saved; no orders submitted")
    return {
        "plan_id": identifier,
        "completion_message": "Paper review prepared. Inspect targets, cash and exclusions in Portfolio; no orders submitted.",
    }


def schedule(store, identifier):
    p = plan(store, identifier)
    cfg = configuration(store)
    a = approval(store)
    if p["state"] != "prepared":
        raise ResearchError(
            "Only a freshly prepared plan can be approved. Reopen its current status."
        )
    if not cfg or cfg["paused"] or p["config_hash"] != cfg["hash"] or not a:
        raise ResearchError(
            "Approve the matching paper strategy/version/policy and resume it before approving a plan."
        )
    if a["account_key"] != p["account_key"]:
        raise ResearchError("The paper account changed. Prepare a new review.")
    if datetime.now(UTC) >= calendar.close_time(
        date.fromisoformat(p["execute_session"])
    ):
        raise ResearchError(
            "The intended execution session has closed. Prepare a new review with current data."
        )
    set_state(
        store,
        identifier,
        "scheduled",
        "Rebalance approved for the following regular session; worker must remain running.",
    )
    return plan(store, identifier)


def retry_quote(store, identifier):
    p = plan(store, identifier)
    cfg = configuration(store)
    if p["state"] != "blocked" or "quote" not in p["message"].lower():
        raise ResearchError(
            "Only a quote-validation stop can retry this frozen plan. Other changes need a new review."
        )
    if (
        not cfg
        or cfg["paused"]
        or cfg["hash"] != p["config_hash"]
        or not approval(store)
    ):
        raise ResearchError(
            "The matching paper approval and policy must still be active."
        )
    if datetime.now(UTC) >= calendar.close_time(
        date.fromisoformat(p["execute_session"])
    ):
        raise ResearchError(
            "The intended execution session has closed. Prepare a current review instead."
        )
    if any(o["state"] != "filled" for o in orders(store, identifier)):
        raise ResearchError(
            "Resolve the existing orders first. Uncertain/rejected orders are never retried this way."
        )
    set_state(
        store,
        identifier,
        "waiting_reconciliation",
        "Rechecking quotes for this same approved plan; confirmed fills will not be submitted again.",
    )
    return plan(store, identifier)


def stop(store):
    cfg = configuration(store)
    if cfg:
        store.set_preference("paper_config", {**cfg, "paused": True})
    for p in plans(store):
        if p["state"] not in FINAL:
            set_state(
                store,
                p["id"],
                "stopped",
                "Stopped future submissions. Existing broker orders may still fill; reconcile or cancel them.",
            )


def resume(store):
    cfg = configuration(store)
    if not cfg:
        raise ResearchError("Save paper settings first.")
    store.set_preference("paper_config", {**cfg, "paused": False})
    return configuration(store)


def cancel_pending(store, broker):
    snap = reconcile(store, broker)
    own = {o["client_id"] for o in orders(store)}
    for b in snap["open_orders"]:
        if b.get("client_order_id") in own:
            broker.cancel(b["id"])
    reconcile(store, broker)
    event(
        store,
        "Cancellation requested for Aperture-owned paper orders only. Reconcile until terminal; cancellation is not a fill reversal.",
    )


def expected_positions(p, local_orders):
    qty = {r["symbol"]: decimal(r["qty"]) for r in p["account"]["positions"]}
    for o in local_orders:
        filled = decimal(o.get("broker", {}).get("filled_qty", "0"))
        qty[o["symbol"]] = qty.get(o["symbol"], ZERO) + filled * (
            ONE if o["side"] == "buy" else -ONE
        )
    return {s: q for s, q in qty.items() if q != ZERO}


def execute_plan(store, p, broker, at=None):
    at = at or datetime.now(UTC)
    cfg = configuration(store)
    a = approval(store)
    if not cfg or cfg.get("paused") or cfg["hash"] != p["config_hash"] or not a:
        raise ResearchError(
            "Paper approval/settings changed or execution is paused. Stop and prepare a new review."
        )
    if strategy(cfg["strategy_id"])["version"] != cfg["strategy_version"]:
        raise ResearchError(
            "The approved strategy version changed. New paper approval is required."
        )
    if cfg["mode"] == "automatic" and not a["allow_automatic"]:
        raise ResearchError(
            "Automatic paper execution has not been explicitly approved."
        )
    snap = reconcile(store, broker)
    if snap["account_key"] != p["account_key"] or a["account_key"] != p["account_key"]:
        raise ResearchError("Paper account identity changed. Prepare a new review.")
    if snap["issues"]:
        raise ResearchError(" ".join(snap["issues"]))
    own = orders(store, p["id"])
    known = {o["client_id"] for o in own}
    if any(b.get("client_order_id") not in known for b in snap["open_orders"]):
        raise ResearchError(
            "An external open order changed the account. Cancel/reconcile it and prepare a new review."
        )
    if any(o["state"] == "unknown" or o["state"] == "submitting" for o in own):
        raise ResearchError(
            "An order submission has an uncertain outcome. Reconcile by client ID; it will never be blindly resubmitted."
        )
    if any(o["state"] in TERMINAL - {"filled"} for o in own):
        raise ResearchError(
            "A broker order was rejected, canceled, expired or replaced. Reconcile actual partial fills and prepare a fresh review; no remainder is resubmitted."
        )
    if any(o["state"] not in TERMINAL for o in own):
        if p["state"] != "waiting_fills":
            set_state(
                store,
                p["id"],
                "waiting_fills",
                "Waiting for actual broker fills; acceptance and partial fills are not completion.",
            )
        return
    expected = expected_positions(p, own)
    actual = {
        r["symbol"]: decimal(r["qty"])
        for r in snap["positions"]
        if decimal(r["qty"]) != ZERO
    }
    if expected != actual:
        raise ResearchError(
            "Positions differ from this plan and its confirmed fills. Reconcile manual trades/corporate actions and prepare a new review."
        )
    expected_cash = decimal(p["account"]["cash"])
    for o in own:
        b = o.get("broker", {})
        if decimal(b.get("filled_qty", "0")):
            if b.get("filled_avg_price") is None:
                raise ResearchError(
                    "Filled order is missing its broker average price. Reconcile before continuing."
                )
            expected_cash += (
                decimal(b["filled_qty"])
                * decimal(b["filled_avg_price"])
                * (ONE if o["side"] == "sell" else -ONE)
            )
    if abs(decimal(snap["cash"]) - expected_cash) > ONE:
        raise ResearchError(
            "Cash changed beyond the confirmed fills and $1 fee tolerance. Review transfers/dividends/fees and prepare a fresh plan."
        )
    day = at.astimezone(NY).date()
    first = date.fromisoformat(p["execute_session"])
    last = date.fromisoformat(p["last_execution_session"])
    if at >= calendar.close_time(last):
        set_state(
            store,
            p["id"],
            "expired",
            "Execution window expired. Reconcile any existing orders, then prepare a current review.",
        )
        return
    if day < first or not snap["clock"].get("is_open"):
        if p["state"] != "waiting_session":
            set_state(
                store,
                p["id"],
                "waiting_session",
                "Waiting for the following regular market session. Keep the worker running.",
            )
        return
    sells = [c for c in p["changes"] if c["side"] == "sell"]
    sell_orders = [o for o in own if o["side"] == "sell"]
    remaining = [
        c
        for c in p["changes"]
        if (c["symbol"], c["side"]) not in {(o["symbol"], o["side"]) for o in own}
    ]
    if sells and len(sell_orders) < len(sells):
        remaining = [c for c in remaining if c["side"] == "sell"]
    if not remaining:
        set_state(
            store,
            p["id"],
            "complete",
            "All planned paper orders filled and positions reconciled. Targets may drift with prices; inspect actual holdings.",
        )
        return
    if sell_orders and len(sell_orders) == len(sells):
        settle = max(
            calendar.settlement_session(
                datetime.fromisoformat(o["broker"]["filled_at"]).astimezone(NY).date()
            )
            for o in sell_orders
        )
        if day < settle:
            if p["state"] != "waiting_settlement":
                set_state(
                    store,
                    p["id"],
                    "waiting_settlement",
                    f"Sell proceeds are reserved until {settle}; no anticipated sale cash funds buys.",
                )
            return
    if day > first and not sell_orders:
        raise ResearchError(
            "The original execution session was missed. Prepare a fresh review rather than trading stale signals."
        )
    quote_waits = []
    c = None
    for candidate in remaining:
        broker.asset(candidate["symbol"])
        try:
            price = broker.price(candidate["symbol"], candidate["side"], at)
        except ReconciliationPending as error:
            quote_waits.append(str(error))
            continue
        c = candidate
        break
    store.set_preference(
        "paper_quote_waits", {"plan_id": p["id"], "reasons": quote_waits}
    )
    if c is None:
        raise ReconciliationPending(
            "Waiting for valid quotes: " + "; ".join(quote_waits)
        )
    symbol = c["symbol"]
    side = c["side"]
    ref = decimal(c["reference_price"])
    if abs(price / ref - ONE) > decimal(cfg["max_drift"]):
        raise ResearchError(
            f"{symbol}: price moved beyond the approved {decimal(cfg['max_drift']):.1%} band. Prepare a new review."
        )
    limit = (price * (decimal("1.001") if side == "buy" else decimal(".999"))).quantize(
        CENT if price >= ONE else decimal("0.0001"), rounding=ROUND_DOWN
    )
    if limit <= ZERO:
        raise ResearchError(
            f"{symbol}: the quote is below the supported price increment."
        )
    qty = decimal(c["quantity"])
    policy = policy_from(
        {**cfg["policy"], "positions": int(cfg["policy"]["positions"])}
    )
    if side == "buy":
        held = actual.get(symbol, ZERO)
        equity = decimal(snap["equity"])
        weight = decimal(c["target_weight"])
        capacity = max(ZERO, equity * min(weight, policy.max_weight) - held * limit)
        sector = c["sector"]
        sector_value = ZERO
        sectors = {t["symbol"]: t["sector"] for t in p["targets"]}
        sectors.update({t["symbol"]: t["sector"] for t in p["changes"]})
        for r in snap["positions"]:
            if sectors.get(r["symbol"], "Unknown") == sector:
                sector_value += decimal(r["market_value"])
        capacity = min(capacity, max(ZERO, equity * policy.sector_cap - sector_value))
        reserve = equity * policy.cash_reserve
        cash = max(ZERO, decimal(snap["spendable_cash"]) - reserve - ONE)
        qty = min(
            qty, decimal(c["max_notional"]) / limit, capacity / limit, cash / limit
        ).quantize(SHARE, rounding=ROUND_DOWN)
    else:
        qty = min(qty, actual.get(symbol, ZERO))
    if qty <= ZERO or qty * limit < ONE:
        raise ResearchError(
            f"{symbol}: less than $1 remains after cash/target/sector checks. Prepare a new review; limits were not relaxed."
        )
    # Recheck immediate stop/revocation immediately before committing one side effect.
    current = configuration(store)
    if (
        not current
        or current["paused"]
        or current["hash"] != cfg["hash"]
        or not approval(store)
    ):
        raise ResearchError(
            "Submission stopped because paper approval or settings changed."
        )
    if not broker.market_open():
        raise ReconciliationPending(
            "The regular session closed while the order was priced. No order was submitted; the worker will recheck or expire the plan."
        )
    client_id = "ap-" + digest([p["id"], symbol, side])[:40]
    payload = {
        "symbol": symbol,
        "side": side,
        "qty": str(qty),
        "type": "limit",
        "time_in_force": "day",
        "limit_price": str(limit),
        "extended_hours": False,
        "client_order_id": client_id,
    }
    with store.connect() as db:
        db.execute(
            "INSERT INTO paper_orders VALUES (?,?,?,?,?,?,?)",
            (
                client_id,
                p["id"],
                symbol,
                side,
                "submitting",
                json.dumps({"request": payload, "broker": None}),
                now(),
            ),
        )
    response, status = broker.submit(payload)
    with store.connect() as db:
        db.execute(
            "UPDATE paper_orders SET state=?,body=?,updated_at=? WHERE client_id=?",
            (
                (response or {}).get("status", "unknown"),
                json.dumps({"request": payload, "broker": response}),
                now(),
                client_id,
            ),
        )
    if status == "unknown":
        raise ResearchError(
            "Broker submission outcome is uncertain. Reconcile the saved client ID; no automatic retry will place a duplicate."
        )
    set_state(
        store,
        p["id"],
        "waiting_fills",
        f"{symbol} {side} submitted to PAPER. Awaiting broker fill and reconciliation.",
    )


def tick(store, at=None, broker=None):
    at = at or datetime.now(UTC)
    cfg = configuration(store)
    if not cfg:
        return
    active = next(
        (
            p
            for p in plans(store)
            if p["state"] not in FINAL and p["state"] != "prepared"
        ),
        None,
    )
    if active:
        b = broker or Broker()
        try:
            execute_plan(store, active, b, at)
        except ReconciliationPending as e:
            set_state(store, active["id"], "waiting_reconciliation", str(e))
        except ResearchError as e:
            store.set_preference("paper_error", str(e))
            set_state(store, active["id"], "blocked", str(e))
        finally:
            if broker is None:
                b.close()
        return
    if any(o["state"] not in TERMINAL for o in orders(store)):
        b = broker or Broker()
        try:
            reconcile(store, b)
        except ResearchError as e:
            store.set_preference("paper_error", str(e))
        finally:
            if broker is None:
                b.close()
        return
    if cfg["mode"] != "automatic" or cfg["paused"]:
        return
    a = approval(store)
    if not a or not a["allow_automatic"]:
        store.set_preference(
            "paper_auto_status",
            "Automatic mode needs matching explicit paper approval, including automatic execution.",
        )
        return
    latest = calendar.latest_complete(at)
    following = calendar.next_session(latest)
    if latest.isocalendar()[:2] == following.isocalendar()[:2]:
        return
    if at >= calendar.close_time(following):
        store.set_preference(
            "paper_auto_status",
            "The weekly execution session was missed. Prepare a manual current review; no stale catch-up order will be submitted.",
        )
        return
    key = "paper_auto_" + cfg["hash"] + "_" + str(latest)
    if store.preference(key):
        return
    if any(p["state"] not in FINAL for p in plans(store)):
        return
    store.set_preference(key, now())
    store.enqueue("paper_prepare", {"config_hash": cfg["hash"], "automatic": True})
    store.set_preference(
        "paper_auto_status",
        f"Weekly preparation queued after {latest}. Worker must remain running for next-session execution.",
    )
