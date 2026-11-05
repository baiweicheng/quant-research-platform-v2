"""Weekly roster/backfill changes must never widen a trading approval silently."""

import pytest

from aperture import membership
from aperture.paper import (
    save_configuration,
    configuration,
    prepare,
    apply_membership_update,
    approval,
    plans,
)
from aperture.domain import ResearchError
from aperture.signals import rank
from test_paper import paper, allow  # noqa: F401
from test_membership import refresh_fixture, html, history_csv


@pytest.fixture
def indexed(paper):  # noqa: F811 - imported pytest fixture
    store, broker, old = paper
    names = [f"S{i:03}" for i in range(501)] + ["AAPL", "MSFT"]
    refresh_fixture(store, "current", html(names))
    cfg = save_configuration(
        store,
        {
            "strategy_id": old["strategy_id"],
            "mode": "manual",
            "execution": "broker_market",
            "universe": "sp500",
            "symbols": ["EXTRA"],
            "data_start": old["data_start"],
            "max_drift": old["max_drift"],
            **old["policy"],
        },
    )
    return store, broker, cfg, names


def test_weekly_preparation_refreshes_and_backfills_then_requires_new_approval(
    indexed, monkeypatch
):
    store, broker, cfg, names = indexed
    allow(store)
    new_names = names[1:] + ["NEW"]
    current = refresh_fixture(store, "current", html(new_names))
    historical = refresh_fixture(store, "historical", history_csv())
    refresh_calls = []

    def refresh_all(s):
        refresh_calls.append(s.path)
        return {"current": current, "historical": historical}

    monkeypatch.setattr(membership, "refresh_all", refresh_all)
    calls = []
    saved = store.datasets()[0]

    def download(s, payload, progress):
        calls.append(payload)
        return saved

    monkeypatch.setattr("aperture.bundles.download", download)
    result = prepare(
        store, {"payload": {"config_hash": cfg["hash"]}}, lambda *a: None, broker
    )
    assert len(refresh_calls) == 1
    assert "plan_id" not in result and plans(store) == []
    assert calls[0]["symbols"] == ["NEW"]
    assert calls[0]["start"] == cfg["data_start"]
    pending = store.preference("paper_membership_update")
    assert pending["added"] == ["NEW"] and pending["removed"] == ["S000"]
    assert pending["backfill_dataset_id"] == saved["id"]
    assert configuration(store)["symbols"] == cfg["symbols"]
    assert approval(store) is not None  # Original concrete list remains approved.
    assert broker.submissions == []
    updated = apply_membership_update(store)
    assert "NEW" in updated["symbols"] and "S000" not in updated["symbols"]
    assert "EXTRA" in updated["symbols"]
    assert updated["hash"] != cfg["hash"] and approval(store) is None
    assert broker.submissions == []


def test_unchanged_roster_automatically_updates_approved_prices_without_separate_download(
    indexed, monkeypatch
):
    store, broker, cfg, _ = indexed
    current = store.membership("current")
    monkeypatch.setattr(
        membership, "refresh_all", lambda s: {"current": current, "historical": {}}
    )
    calls = []
    saved = store.datasets()[0]
    monkeypatch.setattr(
        "aperture.bundles.download",
        lambda s, payload, progress: calls.append(payload) or saved,
    )
    result = prepare(
        store, {"payload": {"config_hash": cfg["hash"]}}, lambda *a: None, broker
    )
    assert result["plan_id"]
    assert calls[0]["universe"] == "sp500_current"
    assert calls[0]["symbols"] == ["EXTRA"]
    assert calls[0]["start"] == cfg["data_start"] and calls[0]["end"] == "2026-11-02"
    assert store.preference("paper_membership_update") is None
    assert broker.submissions == []


def test_backfill_failure_leaves_approved_universe_and_pending_change_visible(
    indexed, monkeypatch
):
    store, broker, cfg, names = indexed
    current = refresh_fixture(store, "current", html(names[1:] + ["NEW"]))
    monkeypatch.setattr(
        membership, "refresh_all", lambda s: {"current": current, "historical": {}}
    )

    def fail(*args):
        raise ResearchError("new member data unavailable")

    monkeypatch.setattr("aperture.bundles.download", fail)
    with pytest.raises(ResearchError, match="unavailable"):
        prepare(
            store, {"payload": {"config_hash": cfg["hash"]}}, lambda *a: None, broker
        )
    assert configuration(store)["hash"] == cfg["hash"]
    assert store.preference("paper_membership_update")["added"] == ["NEW"]
    assert store.preference("paper_membership_update")["backfill_dataset_id"] is None
    assert plans(store) == [] and broker.submissions == []


def test_held_departure_is_retained_only_for_exit_and_reentry_needs_review(
    indexed, monkeypatch
):
    store, broker, cfg, names = indexed
    from decimal import Decimal

    broker.held = {"S000": Decimal("10")}
    current = refresh_fixture(store, "current", html(names[1:]))
    monkeypatch.setattr(
        membership, "refresh_all", lambda s: {"current": current, "historical": {}}
    )
    prepare(store, {"payload": {"config_hash": cfg["hash"]}}, lambda *a: None, broker)
    assert store.preference("paper_membership_update")["exit_symbols"] == ["S000"]
    updated = apply_membership_update(store)
    assert updated["exit_symbols"] == ["S000"]
    assert "S000" in updated["symbols"]
    assert updated["exit_sectors"]["S000"] != "Unknown"
    assert updated["hash"] != cfg["hash"]
    assert approval(store) is None and broker.submissions == []

    current = refresh_fixture(store, "current", html(names))
    prepare(
        store, {"payload": {"config_hash": updated["hash"]}}, lambda *a: None, broker
    )
    assert store.preference("paper_membership_update")["added"] == ["S000"]
    assert configuration(store)["exit_symbols"] == ["S000"]


def test_exit_only_holding_cannot_enter_ranks_even_with_valid_price_history(indexed):
    store, _, _, _ = indexed
    dataset = store.dataset("prices")
    from datetime import date

    ranked, excluded = rank(dataset, "momentum", date(2026, 11, 2), {"AAPL"})
    assert all(r.symbol != "AAPL" for r in ranked)
    assert any(r["symbol"] == "AAPL" for r in excluded)
