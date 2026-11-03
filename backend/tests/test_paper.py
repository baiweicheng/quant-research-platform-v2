"""Independent broker contracts and execution failure paths. Never contacts Alpaca."""

from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal as D

import httpx
import pytest
from aperture import calendar
from aperture.api import create_app
from aperture.broker import Broker, ReconciliationPending
from aperture.config import PAPER_URL, Settings
from aperture.domain import Bar, Dataset, RankedStock, ResearchError
from aperture.paper import (
    approval,
    approve_strategy,
    cancel_pending,
    configuration,
    orders,
    plan,
    prepare,
    public_state,
    reconcile,
    revoke,
    save_configuration,
    schedule,
    stop,
    tick,
)
from aperture.store import Store
from fastapi.testclient import TestClient

AT = datetime(2026, 11, 3, 15, tzinfo=UTC)


class FakeBroker:
    """Explicit deterministic fixture, not a real provider or paper approval."""

    def __init__(self):
        self.cash = D(100000)
        self.held = {}
        self.book = {}
        self.submissions = []
        self.cancellations = []
        self.mode = "fill"
        self.is_open = True
        self.price_value = D(100)
        self.at = AT
        self.account_key = "fixture-paper-account"
        self.external = []
        self.spendable = None
        self.issues = []

    def close(self):
        pass

    def snapshot(self):
        positions = [
            {
                "symbol": s,
                "qty": str(q),
                "market_value": str(q * 100),
                "current_price": "100",
                "unrealized_pl": "0",
                "side": "long",
                "asset_class": "us_equity",
            }
            for s, q in self.held.items()
            if q
        ]
        return {
            "account_key": self.account_key,
            "source": "Deterministic contract fixture — not broker fills",
            "checked_at": datetime.now(UTC).isoformat(),
            "cash": str(self.cash),
            "equity": str(self.cash + sum((q * 100 for q in self.held.values()), D(0))),
            "spendable_cash": str(
                self.cash if self.spendable is None else self.spendable
            ),
            "unsettled_sales": "0",
            "positions": positions,
            "issues": self.issues,
            "clock": {"is_open": self.is_open, "timestamp": self.at.isoformat()},
            "open_orders": [
                b
                for b in self.book.values()
                if b["status"] not in ("filled", "canceled", "rejected", "expired")
            ]
            + self.external,
        }

    def market_open(self):
        return self.is_open

    def asset(self, symbol):
        return {"fractionable": True}

    def price(self, *args):
        return self.price_value

    def find_order(self, client_id):
        return deepcopy(self.book.get(client_id))

    def submit(self, payload):
        self.submissions.append(payload.copy())
        if self.mode == "timeout_before":
            return None, "unknown"
        b = {
            "id": payload["client_order_id"],
            "client_order_id": payload["client_order_id"],
            "symbol": payload["symbol"],
            "side": payload["side"],
            "qty": payload["qty"],
            "filled_qty": "0",
            "filled_avg_price": None,
            "status": "new",
            "filled_at": None,
        }
        if self.mode == "reject":
            b["status"] = "rejected"
        elif self.mode in ("fill", "timeout_after"):
            self.fill(b, D(payload["qty"]), D(payload["limit_price"]))
        elif self.mode == "partial":
            self.fill(b, D(payload["qty"]) / 2, D(payload["limit_price"]))
            b["status"] = "partially_filled"
        self.book[payload["client_order_id"]] = b
        if self.mode == "timeout_after":
            return None, "unknown"
        return deepcopy(b), "received"

    def fill(self, b, qty, price):
        old_qty = D(b["filled_qty"])
        old_price = D(b["filled_avg_price"] or 0)
        change = qty - old_qty
        average = (old_qty * old_price + change * price) / qty
        self.held[b["symbol"]] = self.held.get(b["symbol"], D(0)) + change * (
            1 if b["side"] == "buy" else -1
        )
        self.cash -= change * price * (1 if b["side"] == "buy" else -1)
        b.update(
            filled_qty=str(qty),
            filled_avg_price=str(average),
            filled_at=self.at.isoformat(),
            status="filled",
        )

    def cancel(self, identifier):
        self.cancellations.append(identifier)
        for b in self.book.values():
            if b["id"] == identifier:
                b["status"] = "canceled"

    def read(self, path, params=None):
        if "portfolio/history" in path:
            return {"timestamp": [], "equity": []}
        raise AssertionError(path)

    def activities(self, after):
        return []


@pytest.fixture
def paper(tmp_path, monkeypatch):
    store = Store(tmp_path / "paper.sqlite")
    broker = FakeBroker()
    days = calendar.sessions(date(2025, 1, 2), date(2026, 11, 2))
    ds = Dataset(
        "prices",
        "Fixture market",
        "imported",
        1,
        {
            s: tuple(
                Bar(
                    s,
                    d,
                    *([D(100)] * 4),
                    100000,
                    available_at=calendar.available_time(d),
                )
                for d in days
            )
            for s in ("AAPL", "MSFT", "SPY")
        },
        {"AAPL": "Technology", "MSFT": "Technology"},
        "Fixture provider",
        "fixture-digest",
        {"provider": "alpaca"},
    )
    summary = store.save_dataset(ds, b"fixture", [])
    monkeypatch.setattr(
        "aperture.providers.download_market", lambda *args, **kw: summary
    )
    monkeypatch.setattr(
        "aperture.paper.rank",
        lambda *args: (
            [
                RankedStock("AAPL", 1, "Technology"),
                RankedStock("MSFT", 0.5, "Technology"),
            ],
            [],
        ),
    )
    cfg = save_configuration(
        store,
        {
            "strategy_id": "momentum",
            "mode": "manual",
            "symbols": ["AAPL", "MSFT", "SPY"],
            "data_start": "2025-01-02",
            "positions": 25,
            "max_weight": ".05",
            "sector_cap": ".25",
            "cash_reserve": ".02",
            "max_drift": ".03",
        },
    )
    reconcile(store, broker)
    return store, broker, cfg


def allow(store, automatic=False):
    cfg = configuration(store)
    return approve_strategy(
        store,
        {
            "config_hash": cfg["hash"],
            "confirmation": f"APPROVE PAPER {cfg['strategy_id']} {cfg['strategy_version']}",
            "rationale": "Contract fixture authorization only; no real strategy activation.",
            "acknowledge_limits": True,
            "allow_automatic": automatic,
        },
    )


def prepared(paper):
    store, broker, cfg = paper
    output = prepare(
        store, {"payload": {"config_hash": cfg["hash"]}}, lambda *args: None, broker
    )
    return plan(store, output["plan_id"])


def test_readonly_preparation_does_not_approve_or_submit(paper):
    store, broker, _ = paper
    p = prepared(paper)
    assert p["state"] == "prepared" and len(p["changes"]) == 2
    assert not broker.submissions and approval(store) is None
    with pytest.raises(ResearchError, match="matching paper strategy"):
        schedule(store, p["id"])
    assert sum(D(t["weight"]) for t in p["targets"]) == D(".10")
    assert plan(Store(store.path), p["id"])["source_digest"] == "fixture-digest"


def test_full_manual_cycle_cash_caps_and_restart_no_duplicates(paper):
    store, broker, _cfg = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    for _ in range(4):
        tick(Store(store.path), AT, broker)
    assert plan(store, p["id"])["state"] == "complete"
    assert (
        len(broker.submissions) == 2
        and len({o["client_order_id"] for o in broker.submissions}) == 2
    )
    assert all(
        o["type"] == "limit"
        and o["time_in_force"] == "day"
        and o["extended_hours"] is False
        for o in broker.submissions
    )
    assert all(D(o["qty"]) * D(o["limit_price"]) <= D(5000) for o in broker.submissions)
    assert broker.cash >= D(2000)
    tick(store, AT, broker)
    assert len(broker.submissions) == 2


def test_closed_market_waits_without_submission(paper):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    broker.is_open = False
    tick(store, AT, broker)
    assert plan(store, p["id"])["state"] == "waiting_session" and not broker.submissions


@pytest.mark.parametrize(
    "change,message",
    [
        ("price", "price moved"),
        ("cash", "Cash changed"),
        ("positions", "Positions differ"),
        ("external", "external open order"),
        ("identity", "identity changed"),
        ("spendable", "less than $1"),
    ],
)
def test_material_execution_changes_block_without_order(paper, change, message):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    if change == "price":
        broker.price_value = D(104)
    if change == "cash":
        broker.cash += 10
    if change == "positions":
        broker.held["AAPL"] = D(1)
    if change == "external":
        broker.external = [{"client_order_id": "manual", "id": "manual"}]
    if change == "identity":
        broker.account_key = "other-account"
    if change == "spendable":
        broker.spendable = D(0)
    tick(store, AT, broker)
    assert plan(store, p["id"])["state"] == "blocked"
    assert message in plan(store, p["id"])["message"] and not broker.submissions


def test_partial_fills_wait_then_continue_without_remainder_duplicates(paper):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    broker.mode = "partial"
    tick(store, AT, broker)
    tick(store, AT, broker)
    assert (
        len(broker.submissions) == 1
        and plan(store, p["id"])["state"] == "waiting_fills"
    )
    b = next(iter(broker.book.values()))
    broker.fill(b, D(b["qty"]), D(100))
    broker.mode = "fill"
    for _ in range(3):
        tick(store, AT, broker)
    assert len(broker.submissions) == 2 and plan(store, p["id"])["state"] == "complete"


@pytest.mark.parametrize("mode", ["reject", "timeout_before", "timeout_after"])
def test_rejected_uncertain_writes_never_retry_blindly(paper, mode):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    broker.mode = mode
    for _ in range(4):
        tick(store, AT, broker)
    assert len(broker.submissions) == 1
    assert plan(store, p["id"])["state"] == "blocked"
    reconcile(store, broker)
    if mode == "timeout_before":
        with pytest.raises(ResearchError, match="Unresolved Aperture"):
            prepared(paper)
    elif mode == "timeout_after":
        assert orders(store)[0]["state"] == "filled"


def test_sells_wait_for_T_plus_one_before_buys(paper, monkeypatch):
    store, broker, _ = paper
    broker.held = {"AAPL": D(1000)}
    broker.cash = D(10000)
    monkeypatch.setattr(
        "aperture.paper.rank",
        lambda *args: ([RankedStock("MSFT", 1, "Technology")], []),
    )
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    tick(store, AT, broker)
    tick(store, AT, broker)
    assert [o["side"] for o in broker.submissions] == ["sell"]
    assert plan(store, p["id"])["state"] == "waiting_settlement"
    tomorrow = datetime(2026, 11, 4, 15, tzinfo=UTC)
    broker.at = tomorrow
    tick(store, tomorrow, broker)
    tick(store, tomorrow, broker)
    assert [o["side"] for o in broker.submissions] == ["sell", "buy"]
    assert plan(store, p["id"])["state"] == "complete" and broker.cash >= D(0)


def test_stop_revokes_future_permission_and_cancel_owned_only(paper):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    broker.mode = "partial"
    tick(store, AT, broker)
    stop(store)
    broker.external = [
        {"id": "manual", "client_order_id": "manual", "symbol": "MSFT", "side": "buy"}
    ]
    cancel_pending(store, broker)
    tick(store, AT, broker)
    assert len(broker.submissions) == 1 and broker.cancellations == [
        broker.submissions[0]["client_order_id"]
    ]
    assert plan(store, p["id"])["state"] == "stopped"
    revoke(store)
    assert approval(store) is None


def test_approval_exact_version_account_policy_and_automatic_scope(paper):
    store, broker, _cfg = paper
    with pytest.raises(ResearchError, match="Type the displayed"):
        approve_strategy(store, {"confirmation": "yes"})
    allow(store)
    assert not approval(store)["allow_automatic"]
    broker.account_key = "changed"
    reconcile(store, broker)
    assert approval(store) is None
    assert public_state(store)["snapshot"]["account_key"] == "changed"


def test_auto_only_week_end_once_and_explicit_automatic_approval(paper):
    store, broker, cfg = paper
    store.set_preference("paper_config", {**cfg, "mode": "automatic"})
    allow(store, False)
    friday = datetime(2026, 11, 6, 21, 16, tzinfo=UTC)
    tick(store, friday, broker)
    assert not store.jobs()
    allow(store, True)
    tick(store, AT, broker)
    assert not store.jobs()
    tick(store, friday, broker)
    tick(store, friday, broker)
    assert len(store.jobs()) == 1 and store.jobs()[0]["kind"] == "paper_prepare"


def test_api_header_approval_and_no_live_routes(paper):
    store, _, _ = paper
    with TestClient(create_app(store.path, None)) as c:
        assert c.post("/api/paper/actions/stop").status_code == 403
        assert (
            c.post(
                "/api/paper/plans/missing/approve",
                json={"acknowledge": False},
                headers={"X-Aperture-Client": "1"},
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/live/orders", json={}, headers={"X-Aperture-Client": "1"}
            ).status_code
            == 404
        )
        assert c.get("/api/paper").json()["approval"] is None


def test_paper_http_write_once_on_timeout_and_fixed_host():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("fixture", request=request)

    b = Broker(
        httpx.Client(transport=httpx.MockTransport(handler)),
        Settings("fixture", "fixture"),
    )
    body, state = b.submit({"symbol": "AAPL"})
    assert body is None and state == "unknown" and len(calls) == 1
    assert str(calls[0].url) == PAPER_URL + "/v2/orders"


def test_unstable_account_reads_are_retryable_not_submission(paper):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])

    def moving():
        raise ReconciliationPending("Moving fill; read again.")

    broker.snapshot = moving
    tick(store, AT, broker)
    assert (
        plan(store, p["id"])["state"] == "waiting_reconciliation"
        and not broker.submissions
    )


def test_broker_cash_ignores_margin_and_excludes_unsettled_sales():
    at = datetime(2026, 11, 3, 15, tzinfo=UTC)
    account = {
        "id": "fixture",
        "cash": "1000",
        "equity": "1000",
        "status": "ACTIVE",
        "currency": "USD",
        "short_market_value": "0",
        "long_market_value": "0",
        "buying_power": "4000",
        "non_marginable_buying_power": "1000",
    }

    def handler(req):
        path = req.url.path
        if path == "/v2/account":
            return httpx.Response(200, json=account)
        if path in ("/v2/positions", "/v2/orders"):
            return httpx.Response(200, json=[])
        if path == "/v2/clock":
            return httpx.Response(200, json={"is_open": True})
        if path == "/v2/account/activities":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "fill",
                        "activity_type": "FILL",
                        "side": "sell",
                        "qty": "2",
                        "price": "100",
                        "transaction_time": at.isoformat(),
                    }
                ],
            )
        raise AssertionError(path)

    b = Broker(
        httpx.Client(transport=httpx.MockTransport(handler)),
        Settings("fixture", "fixture"),
    )
    s = b.snapshot(at)
    assert D(s["spendable_cash"]) == 800 and D(s["unsettled_sales"]) == 200
    assert "buying_power" not in s
    assert (
        D(b.snapshot(datetime(2026, 11, 4, 15, tzinfo=UTC))["spendable_cash"]) == 1000
    )


def test_quotes_and_assets_fail_closed_on_staleness_or_eligibility():
    def handler(req):
        if "/assets/" in req.url.path:
            return httpx.Response(
                200,
                json={
                    "class": "us_equity",
                    "status": "active",
                    "tradable": True,
                    "fractionable": False,
                },
            )
        return httpx.Response(
            200, json={"quote": {"t": "2026-11-03T14:00:00Z", "bp": 100, "ap": 101}}
        )

    b = Broker(
        httpx.Client(transport=httpx.MockTransport(handler)),
        Settings("fixture", "fixture"),
    )
    with pytest.raises(ResearchError, match="fractional"):
        b.asset("AAPL")
    with pytest.raises(ResearchError, match="stale"):
        b.price("AAPL", "buy", AT)


def test_broker_pagination_repeated_token_never_publishes_partial_activity():
    batch = [{"id": str(i)} for i in range(100)]
    b = Broker(
        httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=batch))
        ),
        Settings("fixture", "fixture"),
    )
    with pytest.raises(ResearchError, match="No partial"):
        b.activities("2026-01-01")


def test_all_sells_execute_before_waiting_on_settlement(paper, monkeypatch):
    store, broker, _ = paper
    broker.held = {"AAPL": D(100), "MSFT": D(100)}
    monkeypatch.setattr("aperture.paper.rank", lambda *args: ([], []))
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    for _ in range(3):
        tick(store, AT, broker)
    assert len(broker.submissions) == 2 and all(
        o["side"] == "sell" for o in broker.submissions
    )
    assert plan(store, p["id"])["state"] == "complete"


def test_settlement_skips_bank_holidays_when_exchange_is_open():
    assert calendar.sessions(date(2026, 11, 11), date(2026, 11, 11)) == [
        date(2026, 11, 11)
    ]
    assert calendar.settlement_session(date(2026, 11, 10)) == date(2026, 11, 12)
    assert calendar.settlement_session(date(2026, 10, 9)) == date(2026, 10, 13)
    assert calendar.settlement_session(date(2026, 7, 2)) == date(2026, 7, 6)


def test_quote_newer_than_reconciliation_start_is_checked_at_receipt():
    from datetime import timedelta

    receipt = datetime.now(UTC)

    def handler(request):
        return httpx.Response(
            200, json={"quote": {"t": receipt.isoformat(), "bp": 100, "ap": 100.01}}
        )

    b = Broker(
        httpx.Client(transport=httpx.MockTransport(handler)),
        Settings("fixture", "fixture"),
    )
    assert b.price("AAPL", "buy", receipt - timedelta(seconds=5)) == D("100.01")


def test_hand_calculated_preview_and_limit_order_round_down_to_cash_bound(paper):
    store, broker, _ = paper
    p = prepared(paper)
    first = p["changes"][0]
    assert first["reference_price"] == "100" and first["quantity"] == "49.950000"
    assert first["max_notional"] == "4995.00"
    allow(store)
    schedule(store, p["id"])
    tick(store, AT, broker)
    request = broker.submissions[0]
    assert request["limit_price"] == "100.10"
    assert request["qty"] == "49.900099"
    # 49.900099 shares at $100.10 cost exactly $4,994.9999099; cash is never borrowed.
    assert broker.cash == D("95005.0000901")


def test_market_closing_during_pricing_prevents_queued_next_day_order(paper):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    broker.market_open = lambda: False
    tick(store, AT, broker)
    assert not broker.submissions
    assert plan(store, p["id"])["state"] == "waiting_reconciliation"


@pytest.mark.parametrize("cash", ["1000", "100000", "1000000"])
@pytest.mark.parametrize("quote", ["98", "100", "102"])
def test_paper_cash_and_name_limits_across_capital_and_price_changes(
    paper, cash, quote
):
    store, broker, _ = paper
    broker.cash = D(cash)
    broker.price_value = D(quote)
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    for _ in range(4):
        tick(store, AT, broker)
    assert plan(store, p["id"])["state"] == "complete"
    equity = broker.cash + sum((q * 100 for q in broker.held.values()), D(0))
    assert broker.cash >= D(cash) * D(".02")
    assert all(q * 100 / equity <= D(".05") for q in broker.held.values())
    for request in broker.submissions:
        preview = next(c for c in p["changes"] if c["symbol"] == request["symbol"])
        assert D(request["qty"]) <= D(preview["quantity"])
        assert D(request["qty"]) * D(request["limit_price"]) <= D(
            preview["max_notional"]
        )


def test_temporary_quote_failure_waits_then_continues_same_plan_without_duplicates(
    paper,
):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])

    def unavailable(*args):
        raise ReconciliationPending("AAPL: quote is temporarily unavailable.")

    original = broker.price
    broker.price = unavailable
    tick(store, AT, broker)
    assert (
        not broker.submissions
        and plan(store, p["id"])["state"] == "waiting_reconciliation"
    )
    broker.price = original
    for _ in range(4):
        tick(store, AT, broker)
    assert plan(store, p["id"])["state"] == "complete" and len(broker.submissions) == 2


def test_explicit_quote_retry_keeps_fills_but_rejects_other_block_reasons(paper):
    from aperture.paper import retry_quote, set_state

    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    tick(store, AT, broker)
    set_state(
        store,
        p["id"],
        "blocked",
        "MSFT: quote is missing, crossed or wider than the 2% spread limit.",
    )
    retry_quote(store, p["id"])
    for _ in range(3):
        tick(store, AT, broker)
    assert len(broker.submissions) == 2 and plan(store, p["id"])["state"] == "complete"
    set_state(store, p["id"], "blocked", "External manual account change.")
    with pytest.raises(ResearchError, match="Only a quote"):
        retry_quote(store, p["id"])


def test_one_unavailable_quote_does_not_block_other_approved_targets(paper):
    store, broker, _ = paper
    p = prepared(paper)
    allow(store)
    schedule(store, p["id"])
    original = broker.price

    def price(symbol, *args):
        if symbol == "AAPL":
            raise ReconciliationPending("AAPL: quote unavailable.")
        return D(100)

    broker.price = price
    tick(store, AT, broker)
    tick(store, AT, broker)
    assert [r["symbol"] for r in broker.submissions] == ["MSFT"]
    assert public_state(store)["quote_waits"]["reasons"] == ["AAPL: quote unavailable."]
    broker.price = original
    for _ in range(3):
        tick(store, AT, broker)
    assert plan(store, p["id"])["state"] == "complete"
    assert len(broker.submissions) == 2 and {
        r["symbol"] for r in broker.submissions
    } == {"AAPL", "MSFT"}
