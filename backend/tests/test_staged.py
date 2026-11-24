"""Broker-held order contracts. Uses a deterministic broker, never Alpaca writes."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from threading import Event

import httpx
import pytest
from aperture import calendar
from aperture.api import create_app
from aperture.broker import NY, Broker
from aperture.config import Settings
from aperture.domain import RankedStock, ResearchError
from aperture.paper import (
    configuration,
    orders,
    plan,
    public_state,
    revoke,
    save_configuration,
    schedule,
    stop,
    tick,
)
from aperture.staged import VERSION, execute, fill_check
from aperture.store import Store, encode
from aperture.worker import process_one, reconcile_on_startup
from fastapi.testclient import TestClient
from test_paper import FakeBroker, allow, paper, prepared  # noqa: F401


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

    def clock(self):
        day = self.at.astimezone(NY).date()
        opening = next(
            opening
            for session in calendar.sessions(day, day + timedelta(days=7))
            if (opening := calendar.open_time(session)) > self.at
        )
        return {
            "next_open": opening.isoformat(),
            "timestamp": self.at.isoformat(),
            "is_open": False,
        }

    def submit(self, request, *, before_send=None):
        if before_send:
            before_send()
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
    monkeypatch.setattr("aperture.bundles.download", lambda *a, **kw: saved)
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


def test_archived_broker_market_plan_cannot_stage_orders(staged, monkeypatch):
    store, broker, cfg = staged
    with monkeypatch.context() as legacy:
        legacy.setattr("aperture.domain.ARCHIVED_STRATEGIES", frozenset())
        cfg = save_configuration(
            store,
            {
                "strategy_id": "quality_value",
                "mode": "manual",
                "execution": "broker_market",
                "universe": "custom",
                "symbols": cfg["symbols"],
                "data_start": cfg["data_start"],
                "max_drift": cfg["max_drift"],
                **cfg["policy"],
            },
        )
        p = prepared((store, broker, cfg))
        allow(store)
        schedule(store, p["id"])
    with pytest.raises(ResearchError, match="Quality Value is archived"):
        execute(store, p, broker, broker.at)
    tick(store, broker.at, broker)
    assert plan(store, p["id"])["state"] == "blocked"
    assert not orders(store, p["id"]) and not broker.submissions


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
    from aperture.domain import ResearchError
    from aperture.staged import approve_and_stage

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
    from aperture.paper import public_state
    from aperture.staged import approve_and_stage as stage_now

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


@pytest.mark.parametrize("cross_at", ["lock", "reconciliation", "intent", "send"])
def test_no_post_after_boundary_and_prior_acceptance_survives(
    staged, monkeypatch, cross_at
):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    execute(store, p, broker, broker.at)
    opening = calendar.open_time(date.fromisoformat(p["execute_session"]))
    stale = opening - timedelta(minutes=1)
    broker.at = stale
    after = opening + timedelta(seconds=1)
    if cross_at == "lock":
        old_plan = plan

        def after_lock(*args):
            broker.at = after
            return old_plan(*args)

        monkeypatch.setattr("aperture.paper.plan", after_lock)
    elif cross_at == "reconciliation":
        old_snapshot = broker.staging_snapshot

        def slow_reconciliation():
            result = old_snapshot()
            broker.at = after
            return result

        monkeypatch.setattr(broker, "staging_snapshot", slow_reconciliation)
    elif cross_at == "intent":
        old_clock = broker.clock

        def clock_after_commit():
            assert any(o["state"] == "submitting" for o in orders(store))
            return {**old_clock(), "timestamp": after.isoformat(), "is_open": True}

        monkeypatch.setattr(broker, "clock", clock_after_commit)
    else:
        old_submit = broker.submit

        def paced_submit(*args, **kwargs):
            broker.at = after
            return old_submit(*args, **kwargs)

        monkeypatch.setattr(broker, "submit", paced_submit)
    execute(store, p, broker, stale)
    assert plan(store, p["id"])["state"] == "expired"
    assert len(broker.submissions) == 1
    assert orders(store)[0]["state"] == "accepted"
    assert {o["state"] for o in orders(store)} == (
        {"accepted", "not_sent"} if cross_at in {"intent", "send"} else {"accepted"}
    )


@pytest.mark.parametrize("mode", ["timeout_before", "timeout_after"])
def test_uncertain_order_review_is_account_bound_and_survives_restart(staged, mode):
    from aperture.paper import close_uncertain_order

    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    schedule(store, p["id"])
    broker.mode = mode
    tick(store, broker.at, broker)
    reference = orders(store)[0]["client_id"]
    assert orders(store)[0]["state"] == "unknown"
    store = Store(store.path)
    account_key = broker.account_key
    broker.account_key = "different-account"
    with pytest.raises(ResearchError, match="same paper account"):
        close_uncertain_order(store, broker, reference)
    assert orders(store)[0]["state"] == "unknown"
    broker.account_key = account_key
    if mode == "timeout_after":
        broker.at = datetime(2026, 11, 2, 16, tzinfo=UTC)
        broker.fill_all(D(100))
        assert close_uncertain_order(store, broker, reference)["state"] == "filled"
    else:
        with pytest.raises(ResearchError, match="DAY execution window closes"):
            close_uncertain_order(store, broker, reference)
        broker.at = datetime(2026, 11, 2, 21, 6, tzinfo=UTC)
        broker.cash += D(10)
        with pytest.raises(ResearchError, match="differ from confirmed fills"):
            close_uncertain_order(store, broker, reference)
        broker.cash -= D(10)
        result = close_uncertain_order(store, broker, reference)
        assert (
            result["state"] == "closed_unconfirmed"
            and result["resolution"]["first_absent_at"]
        )
        broker.at = datetime(2026, 11, 1, 23, tzinfo=UTC)
        fresh = prepared((store, broker, configuration(store)))
        assert reference not in {o["client_order_id"] for o in fresh["staged_orders"]}
    assert len(broker.submissions) == 1


@pytest.mark.parametrize("broker_outcome", ["cancel", "fill_race", "outage"])
def test_cancellation_serviced_while_research_is_running(
    staged, monkeypatch, broker_outcome
):
    store, broker, _ = staged
    approve_and_stage(staged)
    monkeypatch.setattr("aperture.paper.Broker", lambda: broker)
    from aperture import worker

    real_execute = worker.execute
    research_started, research_release = Event(), Event()

    def run_job(store, job):
        if job["kind"] == "download":
            research_started.set()
            assert research_release.wait(5)
            store.finish(job, {})
        else:
            real_execute(store, job)

    monkeypatch.setattr(worker, "execute", run_job)
    if broker_outcome == "fill_race":
        old_cancel = broker.cancel

        def fill_during_cancel(identifier):
            broker.fill_all(D(100))
            # A DELETE completing after fill does not reverse the fill.
            if any(
                o["id"] == identifier and o["status"] != "filled"
                for o in broker.book.values()
            ):
                old_cancel(identifier)

        monkeypatch.setattr(broker, "cancel", fill_during_cancel)
    if broker_outcome == "outage":

        def offline():
            raise ResearchError("Broker unavailable")

        monkeypatch.setattr(broker, "cancellation_view", offline)

    store.enqueue("download", {})
    with ThreadPoolExecutor() as pool, TestClient(create_app(store.path)) as client:
        research = pool.submit(process_one, store)
        try:
            assert research_started.wait(2)
            response = client.post(
                "/api/paper/actions/cancel", headers={"X-Aperture-Client": "1"}
            )
            assert response.status_code == 202
            assert public_state(store)["cancellation"]["status"] == "pending"
            assert pool.submit(
                process_one, Store(store.path), cancellation=True
            ).result(timeout=3)
            assert not research.done() and configuration(store)["paused"]
            result = public_state(store)["cancellation"]["status"]
            if broker_outcome == "outage":
                assert result == "attention" and not broker.cancellations
            else:
                assert result == "confirmed"
                expected = "filled" if broker_outcome == "fill_race" else "canceled"
                assert {o["state"] for o in orders(store)} == {expected}
        finally:
            research_release.set()


def test_first_25_and_multileg_with_history_use_a_bounded_number_of_http_requests(
    staged, monkeypatch
):
    from aperture.staged import approve_and_stage

    store, fixture, _ = staged
    fixture.mode = "queue"
    requests = []

    def transport(request):
        method, path = request.method, request.url.path.removeprefix("/v2")
        requests.append((method, path))
        snap = fixture.snapshot()
        if method == "POST":
            import json

            receipt, _ = fixture.submit(json.loads(request.content))
            return httpx.Response(200, json=receipt)
        if path == "/account":
            return httpx.Response(
                200,
                json={
                    "id": "bound-account",
                    "status": "ACTIVE",
                    "currency": "USD",
                    "cash": snap["cash"],
                    "equity": snap["equity"],
                    "buying_power": snap["buying_power"],
                },
            )
        if path == "/positions":
            return httpx.Response(200, json=snap["positions"])
        if path == "/orders":
            rows = (
                snap["open_orders"]
                if request.url.params["status"] == "open"
                else list(fixture.book.values())
            )
            return httpx.Response(200, json=rows)
        if path == "/clock":
            return httpx.Response(200, json=fixture.clock())
        if path == "/account/activities":
            return httpx.Response(200, json=[])
        if path.startswith("/assets/"):
            return httpx.Response(
                200,
                json={
                    "class": "us_equity",
                    "status": "active",
                    "tradable": True,
                    "fractionable": True,
                },
            )
        raise AssertionError((method, path))

    fixture.account_key = Broker.account_key({"id": "bound-account"})
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        broker = Broker(client, Settings("fixture", "fixture"))
        monkeypatch.setattr(broker.pace, "acquire", lambda: None)
        symbols = [f"T{i:02d}" for i in range(25)]
        original = store.dataset("staged-prices")
        extended = replace(
            original,
            id="basket-prices",
            digest="basket-prices",
            bars={
                **original.bars,
                **{
                    s: tuple(replace(bar, symbol=s) for bar in original.bars["AAPL"])
                    for s in symbols
                },
            },
        )
        saved = store.save_dataset(extended, b"Basket fixture", [])
        monkeypatch.setattr("aperture.bundles.download", lambda *_a, **_kw: saved)
        cfg = configuration(store)
        save_configuration(
            store,
            {
                **cfg["policy"],
                "strategy_id": cfg["strategy_id"],
                "mode": "manual",
                "execution": "broker_market",
                "universe": "custom",
                "funding_policy": "cash_only",
                "symbols": [*symbols, "AAPL", "MSFT"],
                "data_start": cfg["data_start"],
                "max_drift": cfg["max_drift"],
            },
        )

        def replace_batch(sells, buys):
            p = prepared((store, fixture, configuration(store)))
            p["staged_orders"] = [
                {
                    "client_order_id": f"{p['id']}-{i}",
                    "type": "market",
                    "time_in_force": "day",
                    "side": side,
                    "symbol": symbol,
                    "extended_hours": False,
                    **amount,
                }
                for i, (side, symbol, amount) in enumerate(
                    [("sell", s, {"qty": str(fixture.held[s])}) for s in sells]
                    + [("buy", s, {"notional": "10"}) for s in buys]
                )
            ]
            with store.connect() as db:
                db.execute(
                    "UPDATE paper_plans SET body=? WHERE id=?", (encode(p), p["id"])
                )
            return p["id"]

        first = replace_batch([], symbols)
        allow(store)
        requests.clear()
        assert approve_and_stage(store, first, broker)["state"] == "broker_staged"
        assert len(requests) == 161 and requests.count(("POST", "/orders")) == 25
        fixture.fill_all(D(100))
        requests.clear()
        fill_check(Store(store.path), broker, performance=False)
        assert plan(store, first)["state"] == "complete"
        assert len(requests) == 8  # Seven snapshot requests and one batch receipt read.
        # Retain terminal history but use the original two names for preparation
        # of the next plan, then freeze a buy/sell rebalance to test broker I/O.
        second = replace_batch(symbols[:15], ["AAPL", "MSFT"])
        requests.clear()
        assert approve_and_stage(store, second, broker)["state"] == "broker_staged"
        assert requests.count(("POST", "/orders")) == 17
        assert len(requests) == 113 and not any(
            "by_client" in path for _, path in requests
        )


def test_rate_limit_backoff_is_bounded_and_a_throttled_write_is_never_retried(
    monkeypatch,
):
    from aperture import broker as adapter

    attempts, delays, throttles = [], [], []

    def transport(request):
        attempts.append(request.method)
        if request.method == "POST":
            return httpx.Response(429, headers={"Retry-After": "55"})
        if len(attempts) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        if len(attempts) == 2:
            return httpx.Response(503)
        if request.url.path == "/v2/positions":
            return httpx.Response(429, headers={"Retry-After": "55"})
        return httpx.Response(200, json={"id": "test"})

    monkeypatch.setattr(adapter.time, "sleep", delays.append)
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        broker = Broker(client, Settings("fixture", "fixture"))
        monkeypatch.setattr(broker.pace, "acquire", lambda: None)
        monkeypatch.setattr(broker.pace, "defer", throttles.append)
        assert broker.read("/v2/account") == {"id": "test"}
        assert delays == [2, 1]
        with pytest.raises(ResearchError, match="HTTP 429"):
            broker.read("/v2/positions")
        assert broker.submit({"symbol": "AAPL"}) == (None, "unknown")
        assert attempts == ["GET", "GET", "GET", "GET", "POST"]
        assert throttles == [2, 55, 55]


def test_broker_order_listing_uses_a_bounded_id_cursor(monkeypatch):
    pages = []

    def transport(request):
        pages.append(dict(request.url.params))
        rows = (
            [{"id": str(n)} for n in range(500)]
            if len(pages) == 1
            else [{"id": "older"}]
        )
        return httpx.Response(200, json=rows)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        broker = Broker(client, Settings("fixture", "fixture"))
        monkeypatch.setattr(broker.pace, "acquire", lambda: None)
        assert len(broker.order_list("all", after="2026-11-01")) == 501
    assert pages[0]["after"] == "2026-11-01"
    assert pages[1]["before_order_id"] == "499" and "after" not in pages[1]
