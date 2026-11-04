"""Broker-held order contracts. Uses a deterministic broker, never Alpaca writes."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from aperture.domain import RankedStock
from aperture.paper import (
    save_configuration,
    configuration,
    plan,
    orders,
    schedule,
    tick,
    stop,
    revoke,
)
from aperture.staged import VERSION, fill_check
from aperture.store import Store
from aperture.worker import reconcile_on_startup
from aperture.api import create_app
from aperture.config import Settings
from fastapi.testclient import TestClient
from test_paper import FakeBroker, paper, allow, prepared  # noqa: F401


class QueuedBroker(FakeBroker):
    def snapshot(self):
        return {
            **super().snapshot(),
            "buying_power": str(getattr(self, "buying_power", self.cash)),
        }

    def price(self, *args):
        raise AssertionError("Broker staging must not require a regular-hours quote")

    def market_open(self):
        raise AssertionError("Off-hours orders must be sent before the regular open")

    def submit(self, request):
        assert request["type"] == "market" and request["time_in_force"] == "day"
        assert request["extended_hours"] is False
        assert ("notional" in request) != ("qty" in request)
        self.submissions.append(request.copy())
        if self.mode == "timeout_before":
            return None, "unknown"
        body = {
            **request,
            "id": "broker-" + request["client_order_id"],
            "status": "rejected" if self.mode == "reject" else "accepted",
            "qty": request.get("qty"),
            "filled_qty": "0",
            "filled_avg_price": None,
        }
        self.book[request["client_order_id"]] = body
        return (None, "unknown") if self.mode == "timeout_after" else (body, "received")

    def fill_all(self, price=D(125)):
        for order in self.book.values():
            if order["status"] != "accepted":
                continue
            qty = (
                D(order["notional"]) / price
                if order.get("notional")
                else D(order["qty"])
            )
            symbol = order["symbol"]
            self.held[symbol] = self.held.get(symbol, D(0)) + qty * (
                1 if order["side"] == "buy" else -1
            )
            self.cash += qty * price * (-1 if order["side"] == "buy" else 1)
            order.update(
                status="filled",
                filled_qty=str(qty),
                filled_avg_price=str(price),
                filled_at=self.at.isoformat(),
            )


@pytest.fixture
def staged(paper, monkeypatch):  # noqa: F811 - imported pytest fixture
    store, broker, cfg = paper
    broker.__class__ = QueuedBroker
    broker.mode = "queue"
    broker.at = datetime(2026, 11, 1, 23, tzinfo=UTC)  # Sunday evening.
    source = store.dataset("prices")
    ds = replace(
        source,
        id="staged-prices",
        digest="staged-fixture",
        bars={
            s: tuple(b for b in bars if b.session <= date(2026, 10, 30))
            for s, bars in source.bars.items()
        },
    )
    saved = store.save_dataset(ds, b"staged fixture", [])
    monkeypatch.setattr("aperture.providers.download_market", lambda *a, **kw: saved)
    cfg = save_configuration(
        store,
        {
            "strategy_id": cfg["strategy_id"],
            "mode": "manual",
            "execution": "broker_market",
            "universe": "custom",
            "symbols": cfg["symbols"],
            "data_start": cfg["data_start"],
            "max_drift": cfg["max_drift"],
            **cfg["policy"],
        },
    )
    return store, broker, cfg


def approve_and_stage(staged):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    for _ in range(4):
        tick(store, broker.at, broker)
    return plan(store, p["id"])


def test_weekend_batch_is_accepted_without_waiting_for_fills_or_quotes(staged):
    store, broker, cfg = staged
    p = approve_and_stage(staged)
    assert cfg["execution_version"] == VERSION
    assert p["execute_session"] == "2026-11-02"
    assert p["state"] == "broker_staged"
    assert len(broker.submissions) == 2
    assert len({r["client_order_id"] for r in broker.submissions}) == 2
    assert all(D(r["notional"]) <= D(4995) for r in broker.submissions)
    assert broker.held == {}
    assert all(o["state"] == "accepted" for o in orders(store))
    assert "may close Aperture" in p["message"]


def test_manual_approval_returns_only_after_broker_acceptance_without_worker(
    staged, monkeypatch
):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    monkeypatch.setattr("aperture.paper.Broker", lambda: broker)
    monkeypatch.setattr("aperture.api.settings", lambda: Settings("fixture", "fixture"))
    with TestClient(create_app(store.path)) as client:
        response = client.post(
            f"/api/paper/plans/{p['id']}/approve",
            json={"acknowledge": True},
            headers={"X-Aperture-Client": "1"},
        )
    assert response.status_code == 200
    assert response.json()["state"] == "broker_staged"
    assert len(broker.submissions) == 2 and broker.held == {}


def test_overlapping_api_and_worker_attempts_preserve_one_post_per_instruction(staged):
    from concurrent.futures import ThreadPoolExecutor
    from aperture.staged import execute

    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            pool.submit(execute, Store(store.path), p, broker, broker.at)
            for _ in range(2)
        ]
        for result in results:
            result.result()
    tick(store, broker.at, broker)
    assert plan(store, p["id"])["state"] == "broker_staged"
    assert (
        len(broker.submissions)
        == len({r["client_order_id"] for r in broker.submissions})
        == 2
    )


def test_incomplete_manual_approval_stops_and_preserves_uncertain_client_id(
    staged, monkeypatch
):
    from aperture.staged import approve_and_stage
    from aperture.domain import ResearchError

    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    broker.mode = "timeout_before"
    with pytest.raises(ResearchError, match="uncertain"):
        approve_and_stage(store, p["id"], broker)
    assert plan(store, p["id"])["state"] == "blocked"
    assert len(broker.submissions) == 1
    tick(store, broker.at, broker)
    assert len(broker.submissions) == 1


def test_next_launch_reconciles_gap_fills_without_any_resubmission_even_revoked(staged):
    store, broker, _ = staged
    p = approve_and_stage(staged)
    stop(store)
    revoke(store)
    broker.at = datetime(2026, 11, 2, 16, tzinfo=UTC)
    broker.fill_all(D(125))  # 25% gap: no hidden legacy 3% limit.
    restarted = Store(store.path)
    assert reconcile_on_startup(restarted, broker)
    assert plan(restarted, p["id"])["state"] == "complete"
    assert restarted.preference("paper_fill_check")["counts"] == {"filled": 2}
    assert all(D(o["broker"]["filled_avg_price"]) == D(125) for o in orders(restarted))
    tick(restarted, broker.at, broker)
    assert len(broker.submissions) == 2
    assert broker.cash == D(90010)
    assert configuration(restarted)["paused"] is True


def test_resolved_prior_expiry_does_not_leave_a_later_completed_batch_in_attention(
    staged,
):
    store, broker, _ = staged
    old = approve_and_stage(staged)
    for order in broker.book.values():
        order["status"] = "expired"
    fill_check(store, broker)
    assert plan(store, old["id"])["state"] == "blocked"
    latest = prepared(staged)
    schedule(store, latest["id"])
    for _ in range(4):
        tick(store, broker.at, broker)
    broker.fill_all()
    fill_check(store, broker)
    assert plan(store, latest["id"])["state"] == "complete"
    assert store.preference("paper_fill_check")["counts"] == {"filled": 2}
    assert store.preference("paper_fill_check")["status"] == "checked"


def test_sales_do_not_fund_simultaneous_buys_or_assumed_sector_capacity(
    staged, monkeypatch
):
    store, broker, _ = staged
    broker.cash, broker.held = D(5000), {"AAPL": D(950)}
    monkeypatch.setattr(
        "aperture.paper.rank", lambda *a: ([RankedStock("MSFT", 1, "Technology")], [])
    )
    p = approve_and_stage(staged)
    assert p["state"] == "broker_staged"
    assert len(broker.submissions) == 1
    assert broker.submissions[0]["side"] == "sell"
    assert p["deferred_buys"][0]["symbol"] == "MSFT"
    assert all(r["side"] != "buy" for r in broker.submissions)


def test_paper_margin_stages_sales_and_buys_without_waiting_and_reconciles_debit(
    staged, monkeypatch
):
    from aperture.staged import approve_and_stage as stage_now
    from aperture.paper import public_state

    store, broker, cfg = staged
    broker.cash, broker.held, broker.buying_power = D(1000), {"AAPL": D(990)}, D(200000)
    cfg = save_configuration(
        store,
        {
            "strategy_id": cfg["strategy_id"],
            "mode": "manual",
            "execution": "broker_market",
            "funding_policy": "paper_margin",
            "universe": "custom",
            "symbols": cfg["symbols"],
            "data_start": cfg["data_start"],
            "max_drift": cfg["max_drift"],
            **cfg["policy"],
            "cash_reserve": ".05",
        },
    )
    monkeypatch.setattr(
        "aperture.paper.rank", lambda *a: ([RankedStock("MSFT", 1, "Technology")], [])
    )
    p = prepared((store, broker, cfg))
    allow(store)
    p = stage_now(store, p["id"], broker)
    assert p["state"] == "broker_staged" and len(broker.submissions) == 2
    assert {o["side"] for o in broker.submissions} == {"buy", "sell"}
    assert not p["deferred_buys"]
    assert D(p["funding"]["reference_cash_after"]) >= D(5000)
    assert D(p["funding"]["debit_if_buys_fill_first"]) > 0
    # Buy fills while the sell fails: an overnight debit is possible and visible.
    for o in broker.book.values():
        if o["side"] == "sell":
            o["status"] = "expired"
    broker.fill_all(D(125))
    assert broker.cash < 0
    fill_check(store, broker)
    assert store.preference("paper_fill_check")["status"] == "attention"
    assert "margin debit" in " ".join(store.preference("paper_fill_check")["issues"])
    assert public_state(store)["snapshot"]["cash"] == str(broker.cash)
    tick(store, broker.at, broker)
    assert len(broker.submissions) == 2


@pytest.mark.parametrize("kind", ["timeout_before", "timeout_after", "reject"])
def test_uncertain_or_rejected_submission_is_never_resent(staged, kind):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    broker.mode = kind
    tick(store, broker.at, broker)
    assert plan(store, p["id"])["state"] == "blocked"
    for _ in range(3):
        tick(Store(store.path), broker.at, broker)
    assert len(broker.submissions) == 1
    if kind == "timeout_after":
        assert orders(store)[0]["state"] == "accepted"


@pytest.mark.parametrize(
    "status", ["partially_filled", "canceled", "expired", "rejected"]
)
def test_fill_check_preserves_partial_and_failed_broker_outcomes(staged, status):
    store, broker, _ = staged
    p = approve_and_stage(staged)
    first = next(iter(broker.book.values()))
    first.update(status=status, filled_qty="1", filled_avg_price="101")
    fill_check(Store(store.path), broker, performance=False)
    assert (
        next(o for o in orders(store) if o["client_id"] == first["client_order_id"])[
            "broker"
        ]["filled_qty"]
        == "1"
    )
    assert plan(store, p["id"])["state"] == (
        "broker_staged" if status == "partially_filled" else "blocked"
    )
    assert len(broker.submissions) == 2


def test_unsubmitted_instructions_expire_at_open_instead_of_catching_up(staged):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    tick(store, datetime(2026, 11, 2, 15, tzinfo=UTC), broker)
    assert plan(store, p["id"])["state"] == "expired"
    assert broker.submissions == []


def test_pending_broker_buying_power_reservations_are_counted_once(staged, monkeypatch):
    store, broker, cfg = staged
    cfg = save_configuration(
        store,
        {
            "strategy_id": cfg["strategy_id"],
            "mode": "manual",
            "execution": "broker_market",
            "universe": "custom",
            "symbols": cfg["symbols"],
            "data_start": cfg["data_start"],
            "max_drift": cfg["max_drift"],
            **cfg["policy"],
            "positions": 2,
            "max_weight": ".5",
            "sector_cap": "1",
        },
    )
    original = broker.snapshot

    def snapshot():
        snap = original()
        held_for_orders = sum(
            (
                D(o.get("notional", "0"))
                for o in broker.book.values()
                if o["status"] == "accepted"
            ),
            D(0),
        )
        snap["spendable_cash"] = str(max(D(0), broker.cash - held_for_orders))
        return snap

    monkeypatch.setattr(broker, "snapshot", snapshot)
    p = approve_and_stage((store, broker, cfg))
    assert p["state"] == "broker_staged"
    assert sum(D(r["notional"]) for r in broker.submissions) <= D(98000)
    assert len(broker.submissions) == 2


@pytest.mark.parametrize("problem", ["cash", "positions", "missing_price"])
def test_fill_check_does_not_claim_completion_until_cash_positions_and_fill_details_agree(
    staged, problem
):
    store, broker, _ = staged
    p = approve_and_stage(staged)
    broker.fill_all()
    if problem == "cash":
        broker.cash += D(100)
    elif problem == "positions":
        broker.held["AAPL"] += D(1)
    else:
        next(iter(broker.book.values()))["filled_avg_price"] = None
    fill_check(store, broker, performance=False)
    assert plan(store, p["id"])["state"] == "waiting_reconciliation"
    assert store.preference("paper_fill_check")["status"] == "attention"
    assert len(broker.submissions) == 2


def test_switching_to_automatic_does_not_inherit_manual_permission(staged):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    cfg = configuration(store)
    cfg["mode"] = "automatic"
    store.set_preference("paper_config", cfg)
    tick(store, broker.at, broker)
    assert plan(store, p["id"])["state"] == "blocked"
    assert broker.submissions == []


def test_failed_startup_fill_check_stays_visible_and_never_sends_an_order(
    staged, monkeypatch
):
    store, broker, _ = staged
    approve_and_stage(staged)

    def fail():
        raise RuntimeError("fixture connection unavailable")

    monkeypatch.setattr(broker, "snapshot", fail)
    assert not reconcile_on_startup(Store(store.path), broker)
    assert store.preference("paper_fill_check")["status"] == "attention"
    assert len(broker.submissions) == 2
