"""Manual paper workflows exercised against an isolated deterministic account."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from aperture import calendar, membership
from aperture.api import create_app
from aperture.broker import AssetIneligible, ReconciliationPending, SubmissionNotSent
from aperture.domain import ResearchError
from aperture.paper import orders, plan, public_state, save_configuration, tick
from aperture.staged import approve_and_stage, fill_check
from aperture.store import Store
from aperture.worker import process_one
from fastapi.testclient import TestClient
from test_paper import allow, paper, prepared  # noqa: F401
from test_staged import staged as staged_fixture

staged = staged_fixture

HEADERS = {"X-Aperture-Client": "1"}


def weekly(staged, monkeypatch, *, universe="custom", funding="cash_only"):
    store, broker, old = staged
    cfg = save_configuration(
        store,
        {
            **old["policy"],
            "strategy_id": "liquidity_breadth",
            "mode": "manual",
            "execution": "broker_market",
            "funding_policy": funding,
            "universe": universe,
            "symbols": [] if universe == "sp500" else old["symbols"],
            "data_start": old["data_start"],
            "max_drift": old["max_drift"],
        },
    )

    def weekly_model(dataset, recipe):
        targets = {
            s: D(".05")
            for s in ("AAPL", "MSFT")
            if s not in dataset.metadata.get("research_exclusions", [])
        }
        return SimpleNamespace(decision=lambda *_: ([], [], targets, [], {}))

    monkeypatch.setattr("aperture.paper.weekly_model", weekly_model)
    return store, broker, cfg


@pytest.mark.parametrize("stage", ["read", "clock", "pace"])
def test_manual_staging_retries_only_definitely_unsent_orders(
    staged, monkeypatch, stage
):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    method = {"read": "staging_snapshot", "clock": "clock", "pace": "submit"}[stage]
    original = getattr(broker, method)

    def fail_once(*args, **kwargs):
        if len(broker.submissions) == 1:
            monkeypatch.setattr(broker, method, original)
            error = ReconciliationPending("Temporary fixture outage")
            if stage == "pace":
                raise SubmissionNotSent(str(error)) from error
            raise error
        return original(*args, **kwargs)

    monkeypatch.setattr(broker, method, fail_once)
    result = approve_and_stage(store, p["id"], broker)
    assert result["state"] == "waiting_reconciliation"
    assert [o["state"] for o in orders(store, p["id"])] == ["accepted"]

    store = Store(store.path)
    tick(store, broker.at, broker)
    tick(store, broker.at, broker)
    assert plan(store, p["id"])["state"] == "broker_staged"
    assert (
        len({o["client_order_id"] for o in broker.submissions})
        == len(broker.submissions)
        == 2
    )


def test_transient_staging_wait_expires_without_additional_broker_reads(
    staged, monkeypatch
):
    store, broker, _ = staged
    p = prepared(staged)
    allow(store)
    calls = []

    def unavailable():
        calls.append(True)
        raise ReconciliationPending("Fixture unavailable")

    monkeypatch.setattr(broker, "snapshot", unavailable)
    assert (
        approve_and_stage(store, p["id"], broker)["state"] == "waiting_reconciliation"
    )
    assert len(calls) == 1
    broker.at = calendar.open_time(date.fromisoformat(p["execute_session"]))
    tick(store, broker.at, broker)
    assert plan(store, p["id"])["state"] == "expired"
    assert len(calls) == 1 and broker.submissions == []


def test_weekly_recovery_queues_a_new_approval_for_only_the_unfilled_side(
    staged, monkeypatch
):
    session = weekly(staged, monkeypatch)
    store, broker, cfg = session
    original = prepared(session)
    allow(store)
    assert approve_and_stage(store, original["id"], broker)["state"] == "broker_staged"
    failed = broker.book[broker.submissions[1]["client_order_id"]]
    failed.update(status="canceled", filled_qty="10", filled_avg_price="100")
    broker.cash -= D(1000)
    broker.held["MSFT"] = D(10)
    broker.at = datetime(2026, 11, 2, 22, tzinfo=UTC)
    broker.fill_all(D(100))
    fill_check(store, broker, performance=False)

    # The job uses the newer Monday dataset. Ordinary weekly preparation is closed.
    monday = store.datasets()
    market = next(row for row in monday if row["id"] == "prices")
    monkeypatch.setattr("aperture.bundles.download", lambda *_: market)
    monkeypatch.setattr("aperture.paper.Broker", lambda: broker)
    monkeypatch.setattr("aperture.api.settings", lambda: SimpleNamespace(headers=dict))
    with TestClient(create_app(store.path, None)) as client:
        assert (
            client.post(
                "/api/paper/actions/prepare", json={}, headers=HEADERS
            ).status_code
            == 422
        )
        recovery = public_state(store)["weekly_recovery"]
        assert recovery == {"plan_id": original["id"], "execute_session": "2026-11-03"}
        queued = client.post(
            f"/api/paper/plans/{original['id']}/recover",
            json={"acknowledge": True},
            headers=HEADERS,
        )
        assert queued.status_code == 202
        assert process_one(store)
        new = public_state(store)["plans"][0]
        assert new["state"] == "prepared"
        assert new["recovery_of"] == original["id"]
        assert new["decision_session"] == original["decision_session"]
        assert new["reference_session"] == "2026-11-02"
        assert new["targets"] == original["targets"]
        assert [(r["symbol"], r["side"]) for r in new["staged_orders"]] == [
            ("MSFT", "buy")
        ]
        assert D(new["staged_orders"][0]["notional"]) < D(failed["notional"])
        assert len(broker.submissions) == 2
        denied = client.post(
            f"/api/paper/plans/{new['id']}/approve", json={}, headers=HEADERS
        )
        assert denied.status_code == 422
        assert public_state(store)["weekly_recovery"] is None
        done = client.post(
            f"/api/paper/plans/{new['id']}/approve",
            json={"acknowledge": True},
            headers=HEADERS,
        )
        assert done.status_code == 200 and done.json()["state"] == "broker_staged"
    assert len(broker.submissions) == 3
    assert len({r["client_order_id"] for r in broker.submissions}) == 3


@pytest.mark.parametrize("deferred", [False, True])
def test_empty_rebalance_has_a_truthful_terminal_state(staged, monkeypatch, deferred):
    if deferred:
        staged = weekly(staged, monkeypatch)
        staged[1].spendable = D(0)
    else:
        monkeypatch.setattr("aperture.paper.rank", lambda *a, **k: ([], []))
    p = prepared(staged)
    assert p["staged_orders"] == []
    assert not staged[1].submissions
    if deferred:
        assert p["state"] == "blocked" and "deferred" in p["message"]
        assert {b["symbol"] for b in p["deferred_buys"]} == {"AAPL", "MSFT"}
    else:
        assert p["state"] == "complete" and "No trades needed" in p["message"]


@pytest.mark.parametrize("problem", ["missing", "fractionable", "benchmark", "held"])
def test_weekly_preparation_uses_current_roster_and_reports_symbol_problems(
    staged, monkeypatch, problem
):
    roster = {
        "id": "current-fixture",
        "members": [{"symbol": s, "sector": "Technology"} for s in ("AAPL", "MSFT")],
    }
    observed_rosters = []

    def fresh(_store, kind, **_kwargs):
        observed_rosters.append(kind)
        assert kind == "current"
        return roster

    monkeypatch.setattr(membership, "fresh", fresh)
    session = weekly(staged, monkeypatch, universe="sp500")
    store, broker, _ = session
    source = store.dataset("staged-prices")
    blocked = "SPY" if problem == "benchmark" else "MSFT"
    bars = dict(source.bars)
    if problem != "fractionable":
        del bars[blocked]
    if problem == "held":
        broker.held["MSFT"] = D(5)
    fixture = store.save_dataset(
        replace(
            source,
            id="symbol-case",
            digest="symbol-case",
            bars=bars,
            metadata={
                **source.metadata,
                "membership": {**roster, "kind": "current", "additional_symbols": []},
            },
        ),
        b"fixture",
        [],
    )

    def download(_store, payload, _progress):
        assert payload["universe"] == "sp500_current" and payload["capture_available"]
        return fixture

    monkeypatch.setattr("aperture.bundles.download", download)
    asset = broker.asset

    def check(symbol):
        if problem == "fractionable" and symbol == "MSFT":
            raise AssetIneligible("MSFT is not fractionable")
        return asset(symbol)

    monkeypatch.setattr(broker, "asset", check)
    if problem in ("held", "benchmark"):
        with pytest.raises(
            ResearchError, match=rf"held stocks before preparing: {blocked}"
        ):
            prepared(session)
    else:
        p = prepared(session)
        assert [o["symbol"] for o in p["staged_orders"]] == ["AAPL"]
        assert any(e["symbol"] == "MSFT" for e in p["excluded"])
    assert observed_rosters == ["current", "current"]


def test_broker_adjustment_requires_documentation_and_a_fresh_account_read(
    staged, monkeypatch
):
    store, broker, _ = staged
    original = prepared(staged)
    allow(store)
    approve_and_stage(store, original["id"], broker)
    broker.at = datetime(2026, 11, 2, 22, tzinfo=UTC)
    broker.fill_all(D(100))
    broker.cash -= D(8)
    broker.held["MSFT"] *= 2
    assert fill_check(store, broker, performance=False)["issues"] == []
    assert plan(store, original["id"])["state"] == "waiting_reconciliation"
    assert "adjustment_review" not in public_state(store)["fill_check"]
    activity = [
        {
            "activity_type": "FEE",
            "id": "fixture-fee",
            "date": "2026-11-02",
            "net_amount": "-8",
        },
        {
            "activity_type": "SSP",
            "id": "fixture-split",
            "date": "2026-11-02",
            "symbol": "MSFT",
        },
    ]
    snapshot = broker.snapshot
    monkeypatch.setattr(
        broker, "snapshot", lambda: {**snapshot(), "broker_activities": activity}
    )
    fill_check(store, broker, performance=False)
    review = public_state(store)["fill_check"]["adjustment_review"]
    assert D(review["cash"]) == D(-8) and set(review["positions"]) == {"MSFT"}
    body = {"acknowledge": True, "reference": review["reference"]}
    monkeypatch.setattr("aperture.broker.Broker", lambda: broker)
    with TestClient(create_app(store.path, None)) as client:
        broker.cash -= D(10)
        path = "/api/paper/adjustments/confirm"
        assert client.post(path, json=body, headers=HEADERS).status_code == 422
        broker.cash += D(10)
        assert client.post(path, json=body, headers=HEADERS).status_code == 200
        assert client.post(path, json=body, headers=HEADERS).status_code == 422
    snap = fill_check(Store(store.path), broker, performance=False)
    assert snap["issues"] == []
    assert plan(store, original["id"])["state"] == "complete"
    assert len(broker.submissions) == 2
