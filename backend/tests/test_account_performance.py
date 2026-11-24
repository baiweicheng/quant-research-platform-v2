from datetime import date, datetime
from decimal import Decimal as D

import pytest
from aperture.account_performance import build
from aperture.domain import Bar, Dataset, ResearchError
from aperture.paper import public_state, reconcile
from aperture.store import Store
from test_paper import FakeBroker


def raw(values, days=None):
    days = days or ["2026-10-26", "2026-10-27", "2026-10-28"]
    return {
        "timestamp": [
            int(datetime.fromisoformat(d + "T20:00:00+00:00").timestamp()) for d in days
        ],
        "equity": values,
    }


def test_deposit_and_withdrawal_do_not_become_investment_profit():
    result = build(
        raw([100, 200, 210]),
        [{"activity_type": "CSD", "date": "2026-10-27", "net_amount": "100"}],
        latest=date(2026, 10, 28),
    )
    assert float(result["curve"][1]["equity"]) == 100
    assert result["windows"]["All"]["metrics"]["return"] == pytest.approx(0.05)
    result = build(
        raw([100, 50, 55]),
        [{"activity_type": "CSW", "date": "2026-10-27", "net_amount": "-50"}],
        latest=date(2026, 10, 28),
    )
    assert result["windows"]["All"]["metrics"]["return"] == pytest.approx(0.10)


def test_spy_split_dividend_receivable_and_payment_not_double_counted():
    days = [date(2026, 10, 26), date(2026, 10, 27), date(2026, 10, 28)]
    rows = (
        Bar("SPY", days[0], *([D(100)] * 4), 100),
        Bar("SPY", days[1], *([D(49)] * 4), 100, D(2), D(1), days[2]),
        Bar("SPY", days[2], *([D(49)] * 4), 100),
    )
    ds = Dataset("d", "Spy", "imported", 1, {"SPY": rows}, {}, "independent", "s")
    result = build(raw([100, 100, 100]), [], ds, days[-1])
    assert [D(r["benchmark"]) for r in result["curve"]] == [D(100), D(100), D(100)]
    assert result["windows"]["All"]["metrics"]["difference"] == 0


def test_missing_benchmark_does_not_manufacture_comparison():
    r = build(raw([100, 110, 105]), [], latest=date(2026, 10, 28))
    assert r["windows"]["All"]["metrics"]["benchmark_return"] is None
    assert r["windows"]["All"]["metrics"]["drawdown"] == pytest.approx(105 / 110 - 1)
    assert set(r["windows"]) == {"1W", "1M", "3M", "6M", "YTD", "1Y", "All"}


def test_unsupported_transfer_bad_flow_and_empty_history():
    assert not build(
        raw([100, 110, 105]), [{"activity_type": "JNLT"}], latest=date(2026, 10, 28)
    )["available"]
    with pytest.raises(ResearchError, match="sign"):
        build(
            raw([100, 110, 105]),
            [{"activity_type": "CSW", "date": "2026-10-27", "net_amount": "50"}],
        )
    assert not build({"timestamp": [], "equity": []}, [])["available"]
    with pytest.raises(ResearchError, match="different lengths"):
        build({"timestamp": [1], "equity": []}, [])


def test_current_uncompleted_session_is_excluded():
    r = build(raw([100, 110, 999]), [], latest=date(2026, 10, 27))
    assert r["end"] == "2026-10-27" and len(r["curve"]) == 2


def test_tracking_baseline_excludes_seeded_history_and_initial_funding():
    r = build(
        raw([100000, 100000, 100000]),
        [{"activity_type": "JNLC", "date": "2026-10-27", "net_amount": "100000"}],
        latest=date(2026, 10, 28),
        start=date(2026, 10, 27),
    )
    assert r["start"] == "2026-10-27" and r["windows"]["All"]["metrics"]["return"] == 0


def test_unknown_activity_and_account_reset_cannot_manufacture_returns():
    assert not build(
        raw([100, 110, 120]),
        [{"activity_type": "NEW_TRANSFER_TYPE"}],
        latest=date(2026, 10, 28),
    )["available"]
    with pytest.raises(ResearchError, match="returned to zero"):
        build(raw([100, 0, 100]), [], latest=date(2026, 10, 28))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (raw([100, 110]), "different lengths"),
        (raw([110, None, 125]), "no completed valuation for 2026-10-27"),
        (
            raw([100, 110, 125], ["2026-10-26", "2026-10-27", "2026-10-27"]),
            "conflicting values",
        ),
        ({"timestamp": ["bad"], "equity": [100]}, "invalid timestamp"),
        ({"timestamp": [], "equity": None}, "timestamp and equity arrays"),
        ({"timestamp": [], "equity": []}, "empty for a previously funded account"),
        (raw([100, "NaN", 125]), "finite number"),
    ],
)
def test_rejected_history_keeps_saved_report_and_archive(
    tmp_path, monkeypatch, payload, message
):
    store = Store(tmp_path / "returns.sqlite3")
    broker = FakeBroker()
    key = broker.account_key
    monkeypatch.setattr(
        "aperture.calendar.latest_complete", lambda *_: date(2026, 10, 28)
    )
    store.set_preference("paper_tracking_" + key, "2026-10-26")
    monkeypatch.setattr(broker, "read", lambda *_: raw([100, 110, 120]))
    reconcile(store, broker, performance=True)
    prior = public_state(store)["performance"]
    assert prior["end"] == "2026-10-28" and prior["available"]
    archive = store.preference("paper_equity_archive_" + key)
    with store.connect() as db:
        count = db.execute("SELECT count(*) FROM observations").fetchone()[0]

    monkeypatch.setattr(broker, "read", lambda *_: payload)
    reconcile(store, broker, performance=True)
    stale = public_state(store)["performance"]
    assert message in stale.pop("refresh_issue")
    assert stale == prior
    assert store.preference("paper_equity_archive_" + key) == archive
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM observations").fetchone()[0] == count

    monkeypatch.setattr(broker, "read", lambda *_: raw([100, 115, 125]))
    reconcile(store, broker, performance=True)
    recovered = public_state(store)["performance"]
    assert "refresh_issue" not in recovered
    assert [row["account_equity"] for row in recovered["curve"]] == [
        "100",
        "115",
        "125",
    ]


def test_history_distinguishes_funding_lag_and_another_account(tmp_path, monkeypatch):
    store = Store(tmp_path / "returns.sqlite3")
    broker = FakeBroker()
    key = broker.account_key
    monkeypatch.setattr(
        "aperture.calendar.latest_complete", lambda *_: date(2026, 10, 28)
    )
    store.set_preference("paper_tracking_" + key, "2026-10-23")
    days = ["2026-10-23", "2026-10-26", "2026-10-27", "2026-10-29"]
    monkeypatch.setattr(broker, "read", lambda *_: raw([None, 100, 120, None], days))
    reconcile(store, broker, performance=True)
    history = public_state(store)["performance"]
    assert history["available"]
    assert history["start"] == "2026-10-26" and history["end"] == "2026-10-27"
    assert "2026-10-28 is still missing" in history["refresh_issue"]
    assert store.preference("paper_equity_archive_" + key)["rows"].keys() == {
        "2026-10-26",
        "2026-10-27",
    }
    broker.account_key = "other-paper-account"
    monkeypatch.setattr(broker, "read", lambda *_: raw([100, 110]))
    reconcile(store, broker, performance=True)
    result = public_state(store)["performance"]
    assert not result["available"] and not result["curve"]
    assert "different lengths" in result["refresh_issue"]
