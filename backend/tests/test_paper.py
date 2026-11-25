"""Independent broker contracts and execution failure paths. Never contacts Alpaca."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal as D

import httpx
import pytest
from aperture import calendar
from aperture.api import create_app
from aperture.backtest import weekly_model
from aperture.broker import Broker, ReconciliationPending
from aperture.config import PAPER_URL, Settings
from aperture.domain import Bar, Dataset, Policy, RankedStock, ResearchError, strategy
from aperture.paper import (
    approval,
    approve_strategy,
    cancel_pending,
    configuration,
    month_end_catch_up,
    month_end_used,
    orders,
    plan,
    prepare,
    public_state,
    reconcile,
    revoke,
    save_configuration,
    schedule,
    set_state,
    stop,
    tick,
)
from aperture.periodic_income import load_reports
from aperture.store import Store
from aperture.worker import process_one
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
            "checked_at": self.at.isoformat(),
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

    def staging_snapshot(self):
        return self.snapshot()

    def order_list(self, status, *, after=None):
        assert status == "all"
        return deepcopy(list(self.book.values()))

    def cancellation_view(self):
        return self.account_key, self.snapshot()["open_orders"]

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

    # These contracts model Nov 3 during trading, using Nov 2 closing prices.
    # Keep preparation/approval clocks on that fixture rather than wall time.
    class FixtureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return broker.at.astimezone(tz) if tz else broker.at.replace(tzinfo=None)

    monkeypatch.setattr("aperture.paper.datetime", FixtureClock)
    latest_complete = calendar.latest_complete
    monkeypatch.setattr(
        calendar, "latest_complete", lambda at=None: latest_complete(at or broker.at)
    )
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
    monkeypatch.setattr("aperture.bundles.download", lambda *args, **kw: summary)
    monkeypatch.setattr(
        "aperture.paper.rank",
        lambda *args, **kwargs: (
            [
                RankedStock("AAPL", 1, "Technology", {"median_dollar_volume": "100"}),
                RankedStock("MSFT", 0.5, "Technology", {"median_dollar_volume": "100"}),
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


@pytest.mark.parametrize(
    "identifier,market_state",
    [
        ("profitable_liquidity_leaders", None),
        ("session_strength_liquidity", None),
        ("earnings_market_regime", "strong"),
        ("earnings_market_regime", "weak"),
    ],
)
def test_new_paper_recipes_preserve_strategy_weights_and_approval(
    paper, monkeypatch, identifier, market_state
):
    store, broker, old = paper
    broker.at = datetime(2026, 11, 2, 13, tzinfo=UTC)
    decision = date(2026, 10, 30)
    original = store.dataset(store.datasets()[0]["id"])
    summary = store.save_dataset(
        replace(
            original,
            id="october-close-fixture",
            digest="october-close-fixture",
            bars={
                symbol: tuple(bar for bar in bars if bar.session <= decision)
                for symbol, bars in original.bars.items()
            },
        ),
        b"October close",
        [],
    )
    monkeypatch.setattr("aperture.bundles.download", lambda *a, **kw: summary)

    def ranked(dataset, strategy_id, session, *, factor_audit=None):
        assert (strategy_id, session) == (identifier, decision)
        assert factor_audit is not None
        return [
            RankedStock(
                symbol,
                score,
                "Technology",
                {"median_dollar_volume": volume, "market_state": market_state},
            )
            for symbol, score, volume in (("AAPL", 1, "900"), ("MSFT", 0.5, "100"))
        ], []

    monkeypatch.setattr("aperture.paper.rank", ranked)
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": identifier,
            "symbols": old["symbols"],
            "data_start": old["data_start"],
            "max_drift": old["max_drift"],
            "mode": "manual",
            "execution": "broker_market",
            "max_weight": ".6",
            "sector_cap": ".4",
        },
    )
    draft = prepared((store, broker, cfg))
    assert draft["execute_session"] == "2026-11-02"
    assert draft["state"] == "prepared" and not broker.submissions
    assert public_state(store)["frequency"] == "monthly"
    expected = {"AAPL": D(".3"), "MSFT": D(".1")}
    if market_state == "weak":
        expected = {"AAPL": D(".2"), "MSFT": D(".2")}
    assert {t["symbol"]: D(t["weight"]) for t in draft["targets"]} == expected
    with pytest.raises(ResearchError, match="matching paper strategy"):
        schedule(store, draft["id"])
    assert allow(store)["strategy_id"] == identifier
    broker.at = calendar.open_time(date(2026, 11, 2))
    with pytest.raises(ResearchError, match="expired at the next regular open"):
        schedule(store, draft["id"])
    tick(store, broker.at, broker)
    assert plan(store, draft["id"])["state"] == "expired"
    assert not broker.submissions


@pytest.mark.parametrize(
    "identifier",
    [
        "earnings_reaction_tracker",
        "earnings_market_capture",
        "liquidity_breadth",
        "earnings_pullback_rotation",
        "liquidity_volatility_rotation",
    ],
)
def test_weekly_paper_review_uses_model_weights_and_pinned_filings(
    paper, monkeypatch, identifier
):
    store, broker, old = paper
    decision = date(2026, 10, 30)
    broker.at = datetime(2026, 11, 1, 23, tzinfo=UTC)
    broker.held = {"AAPL": D(1), "ORCL": D(2)}
    source = store.dataset("prices")
    stock_bars = source.bars["AAPL"]
    bars = {
        symbol: tuple(
            replace(bar, symbol=symbol, volume=bar.volume * (index + 1))
            for bar in stock_bars
            if bar.session <= decision
        )
        for index, symbol in enumerate(("AAPL", "MSFT", "ORCL", "META", "SPY"))
    }
    observations, annual = [], {}
    recipe = strategy(identifier)
    if recipe.get("requires_periodic_income"):
        for index, symbol in enumerate(("AAPL", "MSFT", "ORCL", "META"), 1):
            cik = f"{index:010d}"
            accession = f"{cik}-26-000001"
            annual[symbol] = [
                {
                    "accession": "annual",
                    "cik": cik,
                    "available_at": "2026-02-01",
                    "end": "2025-12-31",
                }
            ]
            pair = [
                {
                    "accn": accession,
                    "form": "10-Q",
                    "filed": "2026-10-08",
                    "start": f"{year}-07-01",
                    "end": f"{year}-09-30",
                    "val": value,
                }
                for year, value in ((2025, 100), (2026, 100 + index))
            ]
            for root, data in (
                (
                    "api/xbrl/companyfacts",
                    {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": pair}}}}},
                ),
                ("submissions", {}),
            ):
                observations.append(
                    store.observe(
                        "sec",
                        f"https://data.sec.gov/{root}/CIK{cik}.json?{{}}",
                        json.dumps({"cik": cik, **data}).encode(),
                    )
                )
    ds = replace(
        source,
        id="weekly-paper",
        digest="weekly-paper",
        bars=bars,
        annual_income=annual,
        metadata={
            **source.metadata,
            "fundamentals": {"observation_ids": observations},
        },
    )
    saved = store.save_dataset(ds, b"weekly paper inputs", [])
    monkeypatch.setattr("aperture.bundles.download", lambda *a, **kw: saved)
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": identifier,
            "execution": "broker_market",
            "mode": "manual",
            "symbols": ["AAPL", "MSFT", "ORCL"],
            "data_start": old["data_start"],
            "max_drift": old["max_drift"],
            "max_weight": ".65",
            "sector_cap": ".8",
        },
    )
    # Preserve an approved departure's prices for the sell without allowing it
    # back into the selection. META was captured but never approved.
    cfg = {**cfg, "exit_symbols": ["ORCL"]}
    store.set_preference("paper_config", cfg)
    monkeypatch.setattr(
        "aperture.paper.rank", lambda *a, **kw: pytest.fail("Used legacy ranking")
    )
    draft = prepared((store, broker, cfg))
    inputs = replace(
        ds,
        bars={s: bars[s] for s in ("AAPL", "MSFT", "SPY")},
        periodic_income=load_reports(store, ds) if observations else {},
    )
    _, _, expected, _, audit = weekly_model(inputs, recipe).decision(
        decision, Policy(max_weight=D(".65"), sector_cap=D(".8")), {"AAPL"}
    )
    assert len(expected) == 2
    assert {t["symbol"]: D(t["weight"]) for t in draft["targets"]} == expected
    assert draft.get("factor_coverage", {}) == audit
    if observations:
        assert audit["factors"]["periodic_net_income"]["positive"] == 2
        assert all(s["components"]["filed"] == "2026-10-08" for s in draft["signals"])
    assert draft["execute_session"] == "2026-11-02"
    assert any(t["symbol"] == "ORCL" and t["side"] == "sell" for t in draft["changes"])
    assert approval(store) is None
    with pytest.raises(ResearchError, match="matching paper strategy"):
        schedule(store, draft["id"])
    assert allow(store)["strategy_id"] == identifier
    assert schedule(store, draft["id"])["state"] == "scheduled"
    assert not broker.submissions


def test_monthly_schedule_and_queued_review_enforce_month_end(paper, monkeypatch):
    store, broker, old = paper
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": "earnings_market_regime",
            "symbols": old["symbols"],
            "data_start": old["data_start"],
            "max_drift": old["max_drift"],
            "mode": "automatic",
            "execution": "broker_market",
        },
    )
    allow(store, True)
    with TestClient(
        create_app(store.path, None), headers={"X-Aperture-Client": "1"}
    ) as client:
        midmonth_friday = datetime(2026, 11, 6, 21, 20, tzinfo=UTC)
        tick(store, midmonth_friday, broker)
        response = client.post("/api/paper/actions/prepare")
        assert response.status_code == 422 and "month-end" in response.text
        assert not store.jobs()

    # Nov 30 is a Monday. A month-end order goes out on Tuesday morning.
    month_end = date(2026, 11, 30)
    decisive_close = calendar.available_time(month_end)
    tick(store, decisive_close, broker)
    tick(store, decisive_close, broker)
    (queued,) = store.jobs()
    assert queued["kind"] == "paper_prepare"
    with store.connect() as db:
        payload = json.loads(
            db.execute(
                "SELECT payload FROM jobs WHERE id=?", (queued["id"],)
            ).fetchone()[0]
        )
    assert payload["decision_session"] == str(month_end)
    assert payload["config_hash"] == cfg["hash"]

    def no_broker():
        pytest.fail("Expired preparation must not connect to the broker")

    monkeypatch.setattr("aperture.paper.Broker", no_broker)
    broker.at = calendar.open_time(date(2026, 12, 1))
    assert process_one(store)
    (failed,) = store.jobs()
    assert failed["state"] == "failed" and "month-end" in failed["message"]
    assert not broker.submissions and not public_state(store)["plans"]


@pytest.mark.parametrize(
    "identifier",
    [
        "profitable_liquidity_leaders",
        "session_strength_liquidity",
        "earnings_market_regime",
    ],
)
def test_weekly_versions_bind_distinct_approval_and_holiday_session(
    paper, monkeypatch, identifier
):
    # Exercise the retained recipes as they would run after re-enabling them.
    from aperture.domain import ARCHIVED_STRATEGIES, HIDDEN_STRATEGIES

    for module in ("domain", "paper"):
        monkeypatch.setattr(
            f"aperture.{module}.ARCHIVED_STRATEGIES",
            ARCHIVED_STRATEGIES - HIDDEN_STRATEGIES,
        )
    store, broker, original = paper
    broker.at = calendar.available_time(date(2026, 4, 1))
    reconcile(store, broker)
    data = {
        **original["policy"],
        "symbols": original["symbols"],
        "data_start": original["data_start"],
        "max_drift": original["max_drift"],
        "mode": "automatic",
        "execution": "broker_market",
    }
    monthly = save_configuration(store, {**data, "strategy_id": identifier})
    assert allow(store, True)["strategy_id"] == identifier
    weekly_id = f"{identifier}_weekly"
    weekly = save_configuration(store, {**data, "strategy_id": weekly_id})
    assert monthly["hash"] != weekly["hash"]
    assert approval(store) is None
    assert allow(store, True)["strategy_id"] == weekly_id
    monkeypatch.setattr("aperture.api.settings", lambda: Settings("test", "test"))

    with TestClient(
        create_app(store.path, None), headers={"X-Aperture-Client": "1"}
    ) as client:
        tick(store, broker.at, broker)
        midweek = client.post("/api/paper/actions/prepare")
        assert midweek.status_code == 422 and "week-end" in midweek.text
        assert not store.jobs()

        # Good Friday closes the exchange. Thursday's data unlocks this week's
        # decision, which is staged before Monday's regular open.
        final_session = date(2026, 4, 2)
        assert calendar.next_session(final_session) == date(2026, 4, 6)
        broker.at = calendar.available_time(final_session)
        tick(store, broker.at, broker)
        tick(store, broker.at, broker)
        (automatic,) = store.jobs()
        assert automatic["kind"] == "paper_prepare"
        manual = client.post("/api/paper/actions/prepare")
        assert manual.status_code == 202
        assert json.loads(manual.json()["payload"]) == {
            "config_hash": weekly["hash"],
            "decision_session": str(final_session),
        }

        broker.at = calendar.open_time(date(2026, 4, 6))
        late = client.post("/api/paper/actions/prepare")
        assert late.status_code == 422 and "week-end" in late.text
        assert not broker.submissions


def test_month_end_catch_up_includes_seventh_day_and_respects_exchange_calendar():
    october = date(2026, 10, 30)
    original = date(2026, 11, 2)
    assert month_end_catch_up(calendar.available_time(october)) is None
    assert month_end_catch_up(calendar.open_time(original)) is None
    first = month_end_catch_up(calendar.available_time(original))
    assert (first.decision, first.reference, first.execution) == (
        october,
        original,
        date(2026, 11, 3),
    )
    last = month_end_catch_up(calendar.available_time(date(2026, 11, 6)))
    assert last.original_execution == original and last.execution == date(2026, 11, 9)
    assert month_end_catch_up(calendar.open_time(last.execution)) is None
    assert month_end_catch_up(calendar.available_time(last.execution)) is None
    january = month_end_catch_up(calendar.available_time(date(2027, 1, 4)))
    assert (january.decision, january.original_execution, january.execution) == (
        date(2026, 12, 31),
        date(2027, 1, 4),
        date(2027, 1, 5),
    )


def test_month_end_catch_up_distinguishes_canceled_order_from_partial_fill():
    review = {
        "id": "month-end",
        "account_key": "one",
        "state": "blocked",
        "strategy": {"frequency": "monthly"},
        "decision_session": "2026-10-30",
    }
    canceled = {
        "plan_id": "month-end",
        "state": "canceled",
        "broker": {"filled_qty": "0"},
    }
    assert not month_end_used([review], [canceled], "one", "2026-10-30")
    partially_filled = {**canceled, "broker": {"filled_qty": "0.25"}}
    assert month_end_used([review], [partially_filled], "one", "2026-10-30")
    assert not month_end_used(
        [review], [partially_filled], "different account", "2026-10-30"
    )


def test_paper_worker_rejects_catch_up_if_reference_session_advanced(
    paper, monkeypatch
):
    store, broker, old = paper
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": "profitable_liquidity_leaders",
            "mode": "manual",
            "execution": "broker_market",
            "symbols": old["symbols"],
            "max_drift": old["max_drift"],
            "data_start": old["data_start"],
        },
    )
    store.enqueue(
        "paper_prepare",
        {
            "config_hash": cfg["hash"],
            "catch_up": True,
            "decision_session": "2026-10-30",
            "reference_session": "2026-11-02",
        },
    )
    broker.at = calendar.available_time(date(2026, 11, 3))
    monkeypatch.setattr(
        "aperture.paper.Broker", lambda: pytest.fail("Stale job contacted broker")
    )
    assert process_one(store)
    (job,) = store.jobs()
    assert job["state"] == "failed" and "catch-up session changed" in job["message"]


@pytest.mark.parametrize("reuse_saved", [False, True])
def test_manual_catch_up_keeps_month_end_signal_and_rebuilds_orders(
    paper, monkeypatch, reuse_saved
):
    store, broker, old = paper
    decision = date(2026, 10, 30)
    reference = date(2026, 11, 2)
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": "earnings_market_regime",
            "mode": "automatic",
            "execution": "broker_market",
            "max_drift": old["max_drift"],
            "symbols": old["symbols"],
            "data_start": old["data_start"],
        },
    )
    source = store.dataset("prices")
    first = store.save_dataset(
        replace(
            source,
            id="first",
            digest="month-end",
            bars={
                s: tuple(b for b in bars if b.session <= decision)
                for s, bars in source.bars.items()
            },
        ),
        b"month end",
        [],
    )
    second = store.save_dataset(
        replace(
            source,
            id="second",
            digest="later",
            bars={
                **source.bars,
                "AAPL": (
                    *source.bars["AAPL"][:-1],
                    replace(
                        source.bars["AAPL"][-1],
                        open=D(125),
                        high=D(125),
                        low=D(125),
                        close=D(125),
                    ),
                ),
            },
        ),
        b"later close",
        [],
    )
    signal_calls = []

    def month_end_rank(ds, identifier, as_of, *, factor_audit):
        assert as_of == decision
        signal_calls.append(ds.id)
        factor_audit["market_regime"] = {"state": "weak"}
        return [RankedStock("AAPL", 1, "Technology", {"market_state": "weak"})], []

    monkeypatch.setattr("aperture.paper.rank", month_end_rank)
    if reuse_saved:
        broker.at = calendar.available_time(decision)
        monkeypatch.setattr("aperture.bundles.download", lambda *a, **kw: first)
        earlier = prepared((store, broker, cfg))
    else:
        earlier = None
    broker.at = calendar.available_time(reference)
    broker.held["AAPL"] = D(7)
    reconcile(store, broker)
    allow(store, True)
    tick(store, broker.at, broker)
    assert not store.jobs(), "Automatic execution must never queue a catch-up"
    assert public_state(store)["catch_up"] == {
        "decision_session": "2026-10-30",
        "execute_session": "2026-11-03",
    }
    monkeypatch.setattr("aperture.bundles.download", lambda *a, **kw: second)
    monkeypatch.setattr("aperture.api.settings", lambda: Settings("test", "test"))
    monkeypatch.setattr("aperture.paper.Broker", lambda: broker)
    with TestClient(
        create_app(store.path, None), headers={"X-Aperture-Client": "1"}
    ) as client:
        assert client.post("/api/paper/actions/prepare").status_code == 422
        response = client.post("/api/paper/actions/catch-up")
        assert response.status_code == 202
        assert json.loads(response.json()["payload"]) == {
            "catch_up": True,
            "config_hash": cfg["hash"],
            "decision_session": "2026-10-30",
            "reference_session": "2026-11-02",
        }
    assert process_one(store)
    catch = public_state(store)["plans"][0]
    assert catch["state"] == "prepared" and not broker.submissions
    assert catch["dataset_id"] == second["id"]
    assert catch["catch_up"] == {
        "original_execution_session": "2026-11-02",
        "reference_session": "2026-11-02",
        "signal_dataset_id": (first if reuse_saved else second)["id"],
    }
    assert catch["execute_session"] == catch["last_execution_session"] == "2026-11-03"
    assert catch["factor_coverage"]["market_regime"]["state"] == "weak"
    assert signal_calls == [first["id"] if reuse_saved else second["id"]]
    assert catch["changes"][0]["reference_price"] == "125"
    assert catch["account"]["positions"][0]["qty"] == "7"
    if earlier:
        assert plan(store, earlier["id"])["state"] == "expired"
        assert catch["targets"] == earlier["targets"]
    set_state(store, catch["id"], "complete", "Fixture execution complete")
    assert public_state(store)["catch_up"] is None
    with pytest.raises(ResearchError, match="already rebalanced"):
        prepare(
            store,
            {"payload": {"config_hash": cfg["hash"], "catch_up": True}},
            lambda *a: None,
            broker,
        )


def test_catch_up_ranks_historical_sp500_and_rechecks_current_eligibility(
    paper, monkeypatch
):
    from aperture import membership

    store, broker, old = paper
    broker.at = calendar.available_time(date(2026, 11, 2))
    current = {
        "id": "nov-roster",
        "members": [{"symbol": "AAPL", "sector": "Technology"}],
    }
    history = {
        "coverage_start": "2026-10-30",
        "coverage_end": "2026-11-02",
        "rosters": [
            {"effective": "2026-10-30", "symbols": ["AAPL", "MSFT"]},
            {"effective": "2026-11-02", "symbols": ["AAPL"]},
        ],
    }
    monkeypatch.setattr(membership, "fresh", lambda *a, **kw: current)
    monkeypatch.setattr(
        membership,
        "refresh_all",
        lambda *_: {"current": current, "historical": history},
    )
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": "profitable_liquidity_leaders",
            "mode": "manual",
            "execution": "broker_market",
            "universe": "sp500",
            "symbols": [],
            "max_drift": old["max_drift"],
            "data_start": old["data_start"],
        },
    )
    summary = store.save_dataset(
        replace(
            store.dataset("prices"),
            id="combined-catch-up",
            digest="combined",
            metadata={
                "provider": "alpaca",
                "membership": {
                    "kind": "combined",
                    "current": current,
                    "historical": history,
                    "additional_symbols": [],
                },
            },
        ),
        b"combined",
        [],
    )

    def prices(_store, payload, _progress):
        assert payload["universe"] == "sp500"
        assert payload["end"] == "2026-11-02"
        return summary

    def rank_at_month_end(ds, _recipe, decision, *, factor_audit):
        assert membership.eligible(ds, decision) == {"AAPL", "MSFT"}
        return [
            RankedStock(s, 1, "Technology", {"median_dollar_volume": "100"})
            for s in ("AAPL", "MSFT")
        ], []

    monkeypatch.setattr("aperture.bundles.download", prices)
    monkeypatch.setattr("aperture.paper.rank", rank_at_month_end)
    outcome = prepare(
        store,
        {"payload": {"config_hash": cfg["hash"], "catch_up": True}},
        lambda *a: None,
        broker,
    )
    view = plan(store, outcome["plan_id"])
    assert [(t["symbol"], D(t["weight"])) for t in view["targets"]] == [
        ("AAPL", D(".05"))
    ]
    assert D(view["cash_weight"]) == D(".95")
    assert view["excluded"][0]["symbol"] == "MSFT"


@pytest.mark.parametrize(
    "strategy_id", ["quality", "low_volatility", "liquidity_weighted_momentum"]
)
def test_archived_paper_config_blocks_new_work_and_reconciles_accepted_order(
    paper, monkeypatch, strategy_id
):
    store, broker, cfg = paper
    data = {
        "strategy_id": strategy_id,
        "mode": "automatic",
        "execution": "local_limit",
        "universe": "custom",
        "symbols": cfg["symbols"],
        "data_start": cfg["data_start"],
        "max_drift": cfg["max_drift"],
        **cfg["policy"],
    }
    with monkeypatch.context() as legacy:
        legacy.setattr("aperture.domain.ARCHIVED_STRATEGIES", frozenset())
        cfg = save_configuration(store, data)
        recorded_approval = allow(store, True)
        p = prepared((store, broker, cfg))
        schedule(store, p["id"])
        broker.mode = "pending"
        tick(store, AT, broker)
    assert len(broker.submissions) == 1
    accepted = next(iter(broker.book.values()))

    def unexpected_broker():
        pytest.fail("Archived preparation initialized the broker")

    monkeypatch.setattr("aperture.paper.Broker", unexpected_broker)
    with TestClient(
        create_app(store.path, None), headers={"X-Aperture-Client": "1"}
    ) as client:
        state = client.get("/api/paper").json()
        assert state["approval"] == recorded_approval
        if strategy_id != "quality":
            assert state["archived_strategy"] == "The previously selected strategy"
            assert state["plans"][0]["hidden_strategy"] is True
        for path, body in (
            ("/api/paper/config", data),
            ("/api/paper/actions/prepare", {}),
            ("/api/paper/actions/resume", {}),
            (
                "/api/paper/approval",
                {
                    "config_hash": cfg["hash"],
                    "confirmation": "",
                    "rationale": "Existing approval remains in the audit.",
                    "acknowledge_limits": True,
                },
            ),
            (f"/api/paper/plans/{p['id']}/approve", {"acknowledge": True}),
            (f"/api/paper/plans/{p['id']}/retry-quote", {"acknowledge": True}),
        ):
            r = client.post(path, json=body)
            assert r.status_code == 422 and "is archived" in r.json()["detail"]
    assert not store.jobs()
    store.enqueue("paper_prepare", {"config_hash": cfg["hash"], "automatic": True})
    assert process_one(store)
    assert store.jobs()[0]["state"] == "failed"
    assert "is archived" in store.jobs()[0]["message"]
    tick(store, AT, broker)
    assert plan(store, p["id"])["state"] == "blocked"

    broker.fill(accepted, D(accepted["qty"]), D(100))
    tick(store, AT, broker)
    assert orders(store, p["id"])[0]["state"] == "filled"
    tick(store, datetime(2026, 11, 6, 21, 16, tzinfo=UTC), broker)
    assert configuration(store) == cfg
    assert len(store.jobs()) == len(broker.submissions) == 1


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
    assert s["buying_power"] == "4000"
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
