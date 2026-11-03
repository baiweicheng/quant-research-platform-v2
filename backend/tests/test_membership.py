"""Independent universe/date acceptance cases; no network or broker writes."""

import copy
import csv
import io
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal as D

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st

from aperture import calendar, membership
from aperture.api import create_app
from aperture.backtest import run
from aperture.config import Settings
from aperture.domain import Bar, Dataset, Policy, ResearchError
from aperture.providers import Provider, download_market
from aperture.signals import rank
from aperture.store import Store
from aperture.worker import process_one


def html(names=None):
    names = names or [f"S{i:03}" for i in range(503)]
    head = '<table id="constituents"><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>Industry</th><th>Location</th><th>Date added</th><th>CIK</th><th>Founded</th></tr>'
    return (
        head
        + "".join(
            f"<tr><td>{s}</td><td>Company {s}</td><td>Industrials</td><td>Industry</td><td>City</td><td>2020-01-01</td><td>{i + 1}</td><td>1900</td></tr>"
            for i, s in enumerate(names)
        )
        + "</table>"
    )


def history_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "tickers"])
    writer.writerow(["2024-01-02", ",".join(f"S{i:03}" for i in range(503))])
    writer.writerow(
        ["2024-05-08", ",".join([f"S{i:03}" for i in range(1, 503)] + ["NEW"])]
    )
    writer.writerow(
        ["2024-05-10", ",".join([f"S{i:03}" for i in range(1, 503)] + ["NEW"])]
    )
    return output.getvalue()


def refresh_fixture(store, kind, text):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=text))
    ) as client:
        return membership.refresh(store, kind, client)


@pytest.fixture
def timeline():
    days = calendar.sessions(date(2023, 1, 3), date(2025, 1, 10))
    bars = {
        s: tuple(
            Bar(
                s,
                d,
                *([D(100) + D(i) / 10] * 4),
                10000,
                available_at=calendar.available_time(d),
            )
            for i, d in enumerate(days)
        )
        for s in ("OLD", "NEW", "EXTRA", "SPY")
    }
    audit = {
        "kind": "historical",
        "coverage_start": "2023-01-03",
        "coverage_end": "2025-01-10",
        "additional_symbols": ["EXTRA"],
        "rosters": [
            {"effective": "2023-01-03", "symbols": ["OLD"]},
            {"effective": "2024-07-08", "symbols": ["NEW"]},
            {"effective": "2024-08-01", "symbols": ["OLD"]},
        ],
    }
    return Dataset(
        "test",
        "Timeline",
        "imported",
        1,
        bars,
        {s: "Industry" for s in bars},
        "fixture",
        "digest",
        {"membership": audit},
    )


def test_current_table_validates_share_classes_count_duplicates_and_cik():
    names = [f"S{i:03}" for i in range(501)] + ["BRK.B", "BRK.A"]
    result = membership.parse_current(html(names))
    assert len(result) == 503
    assert {"BRK.A", "BRK.B"} <= {r["symbol"] for r in result}
    assert result[0]["cik"].isdigit()
    for broken in [
        html(names[:-20]),
        html(names[:-1] + [names[0]]),
        html().replace("GICS Sector", "Changed"),
        html().replace("<td>1</td>", "<td></td>", 1),
    ]:
        with pytest.raises(ResearchError):
            membership.parse_current(broken)


def test_refresh_snapshots_are_immutable_with_observation_times_and_diffs(tmp_path):
    store = Store(tmp_path / "a.sqlite")
    first = refresh_fixture(store, "current", html())
    newer = refresh_fixture(
        store, "current", html([f"S{i:03}" for i in range(1, 503)] + ["NEW"])
    )
    assert newer["added"] == ["NEW"] and newer["removed"] == ["S000"]
    assert first["id"] != newer["id"]
    assert Store(store.path).membership("current", first["id"]) == first
    assert store.membership("current")["id"] == newer["id"]
    assert datetime.fromisoformat(first["captured_at"]).tzinfo is not None
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(503))
    ) as client:
        with pytest.raises(ResearchError, match="unchanged"):
            membership.refresh(store, "current", client)
    assert store.membership("current") == newer
    store.set_preference("watchlist", {"symbols": ["EXTRA"]})
    frozen = {"symbols": ["MANUAL", "SPY"], "hash": "approved-frozen-universe"}
    store.set_preference("paper_config", frozen)
    with TestClient(create_app(store.path)) as api:
        defaults = api.get("/api/providers").json()["paper_default_symbols"]
        assert len(defaults) == 505 and {"EXTRA", "SPY", "NEW"} <= set(defaults)
    assert store.preference("paper_config") == frozen


def test_history_has_explicit_bounds_and_no_extension_from_current(tmp_path):
    store = Store(tmp_path / "a.sqlite")
    saved = refresh_fixture(store, "historical", history_csv())
    refresh_fixture(store, "current", html())
    assert "S000" in membership.historical_names(saved, date(2024, 5, 7))
    assert "S000" not in membership.historical_names(saved, date(2024, 5, 8))
    assert "NEW" in membership.historical_names(saved, date(2024, 5, 8))
    assert saved["knowledge_basis"] == "retrospective_effective_dates"
    for day in (date(2024, 1, 1), date(2024, 5, 11)):
        with pytest.raises(ResearchError, match="never extrapolated"):
            membership.historical_names(saved, day)
    for bad in [
        history_csv().replace("2024-05-08", "2024-01-02"),
        history_csv().replace("S001,", "S000,", 1),
        history_csv().replace("date,tickers", "date,symbols"),
    ]:
        with pytest.raises(ResearchError):
            membership.parse_history(bad)


def test_union_includes_departures_and_supplements_without_replacing_core(tmp_path):
    store = Store(tmp_path / "a.sqlite")
    refresh_fixture(store, "historical", history_csv())
    names, audit, _ = membership.resolve(
        store,
        {"universe": "sp500_historical", "symbols": ["extra", "NEW", "extra"]},
        date(2024, 5, 6),
        date(2024, 5, 10),
    )
    assert len(names) == 506  # 503 core + departed + supplement + benchmark
    assert {"S000", "NEW", "EXTRA", "SPY"} <= set(names)
    assert audit["additional_symbols"] == ["EXTRA", "NEW"]
    with pytest.raises(ResearchError, match="covers"):
        membership.resolve(
            store,
            {"universe": "sp500_historical", "symbols": []},
            date(2024, 5, 6),
            date(2024, 5, 13),
        )


def test_effective_day_reentry_and_no_future_roster_leakage(timeline):
    before, exclusions = rank(timeline, "momentum", date(2024, 7, 5))
    assert {s.symbol for s in before} == {"OLD", "EXTRA"}
    assert next(e for e in exclusions if e["symbol"] == "NEW")["reason"].startswith(
        "Not an S&P"
    )
    assert {s.symbol for s in rank(timeline, "momentum", date(2024, 7, 8))[0]} == {
        "NEW",
        "EXTRA",
    }
    assert {s.symbol for s in rank(timeline, "momentum", date(2024, 8, 1))[0]} == {
        "OLD",
        "EXTRA",
    }
    changed = copy.deepcopy(timeline.metadata)
    changed["membership"]["rosters"][2]["symbols"] = ["UNSEEN"]
    assert rank(replace(timeline, metadata=changed), "momentum", date(2024, 7, 5)) == (
        before,
        exclusions,
    )


@given(st.integers(min_value=0, max_value=19))
def test_future_membership_changes_never_change_prior_eligibility(offset):
    audit = {
        "coverage_start": "2024-01-02",
        "coverage_end": "2024-12-31",
        "rosters": [
            {"effective": "2024-01-02", "symbols": ["OLD"]},
            {
                "effective": str(date(2024, 8, 1) + timedelta(days=offset)),
                "symbols": ["NEW"],
            },
        ],
    }
    assert membership.historical_names(audit, date(2024, 7, 31)) == {"OLD"}


def test_missing_departed_member_is_a_hard_failure_before_simulation(timeline):
    gap = replace(
        timeline,
        bars={
            s: tuple(
                b for b in bars if not (s == "OLD" and b.session == date(2024, 7, 5))
            )
            for s, bars in timeline.bars.items()
        },
    )
    with pytest.raises(
        ResearchError, match="Departed or missing members cannot be dropped"
    ):
        run(gap, "momentum", date(2024, 7, 1), date(2024, 7, 12), D(100000), Policy())
    absent = replace(
        timeline, bars={s: b for s, b in timeline.bars.items() if s != "OLD"}
    )
    with pytest.raises(ResearchError, match="no price history"):
        rank(absent, "momentum", date(2024, 7, 5))


def test_backtest_uses_old_and_new_members_with_next_session_fills(timeline):
    result = run(
        timeline,
        "momentum",
        date(2024, 7, 1),
        date(2024, 8, 8),
        D(100000),
        Policy(positions=2, max_weight=D(".5"), sector_cap=D(1)),
        frequency="daily",
    )
    before = next(d for d in result["decisions"] if d["session"] == "2024-07-05")
    after = next(d for d in result["decisions"] if d["session"] == "2024-07-08")
    assert set(before["targets"]) == {"OLD", "EXTRA"}
    assert set(after["targets"]) == {"NEW", "EXTRA"}
    assert after["execute_session"] == "2024-07-09"
    assert any(t["symbol"] == "OLD" and t["side"] == "Sell" for t in result["trades"])
    assert any("Not survivorship-safe" in n for n in result["notes"])
    assert result["input_audit"]["membership"] == timeline.metadata["membership"]


def test_current_roster_cannot_be_used_in_historical_tests(timeline):
    audit = {
        "kind": "current",
        "coverage_start": "2024-07-05",
        "captured_at": "2024-07-05T22:00:00+00:00",
        "members": [{"symbol": "OLD"}],
        "additional_symbols": [],
    }
    ds = replace(timeline, metadata={"membership": audit})
    assert {s.symbol for s in rank(ds, "momentum", date(2024, 7, 5))[0]} == {"OLD"}
    with pytest.raises(ResearchError, match="cannot be backdated"):
        run(ds, "momentum", date(2024, 7, 5), date(2024, 7, 12), D(100000), Policy())
    with pytest.raises(ResearchError, match="not historical membership"):
        rank(ds, "momentum", date(2024, 7, 3))
    with pytest.raises(ResearchError, match="seven days"):
        rank(ds, "momentum", date(2024, 7, 15))


def test_default_api_is_full_index_and_navigation_does_not_refresh(
    tmp_path, monkeypatch
):
    app = create_app(tmp_path / "a.sqlite")
    monkeypatch.setattr("aperture.api.settings", lambda: Settings("key", "secret"))
    monkeypatch.setattr(
        membership,
        "refresh",
        lambda *args: (_ for _ in ()).throw(AssertionError("GET must not download")),
    )
    with TestClient(app) as client:
        info = client.get("/api/providers").json()
        assert info["watchlist"]["universe"] == "sp500_current"
        assert info["watchlist"]["symbols"] == []
        job = client.post(
            "/api/downloads",
            json={"start": "2024-05-06", "end": "2024-05-10"},
            headers={"X-Aperture-Client": "1"},
        )
        assert job.status_code == 202
        assert app.state.store.claim()["payload"]["universe"] == "sp500_current"
        assert (
            client.post("/api/membership/current/refresh", json={}).status_code == 403
        )
        job = client.post(
            "/api/membership/current/refresh",
            json={},
            headers={"X-Aperture-Client": "1"},
        )
        assert job.status_code == 202


@pytest.mark.parametrize(
    "historical,scenario",
    [
        (False, "normal"),
        (True, "normal"),
        (False, "large"),
        (False, "reuse"),
        (True, "reuse"),
        (False, "omitted"),
        (True, "missing_member"),
    ],
)
def test_full_index_download_batches_and_keeps_all_members(
    tmp_path, historical, scenario
):
    store = Store(tmp_path / "a.sqlite")
    snapshot = refresh_fixture(
        store,
        "historical" if historical else "current",
        history_csv() if historical else html(),
    )
    core = {f"S{i:03}" for i in range(503)} | ({"NEW"} if historical else set())
    names = core | {"EXTRA", "SPY"}
    calls = []
    start, end = (
        (date(2024, 1, 2), date(2024, 11, 1))
        if scenario == "large"
        else (date(2024, 5, 6), date(2024, 5, 10))
    )
    days = calendar.sessions(start, end)

    def handler(request):
        calls.append(request)
        if "/assets/" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "id": "S000-id",
                    "symbol": "S000",
                    "class": "us_equity",
                    "exchange": "NASDAQ",
                    "status": "inactive",
                    "name": "Archived Common Stock",
                },
            )
        if request.url.path.endswith("/assets"):
            inactive = request.url.params["status"] == "inactive"
            assets = [
                {
                    "id": s + "-id",
                    "symbol": s,
                    "class": "us_equity",
                    "exchange": "NASDAQ",
                    "status": "inactive" if inactive else "active",
                    "name": s + " Common Stock",
                }
                for s in sorted(names)
                if (s == "S000") == inactive
                and not (scenario == "omitted" and s == "S000")
            ]
            if inactive and scenario == "reuse":
                assets.append({**assets[0], "symbol": "S001", "id": "old-reused-id"})
            return httpx.Response(200, json=assets)
        requested = request.url.params["symbols"].split(",")
        assert len(requested) <= 100
        if request.url.path.endswith("corporate-actions"):
            return httpx.Response(200, json={"corporate_actions": {}})
        return httpx.Response(
            200,
            json={
                "bars": {
                    s: [
                        {
                            "t": f"{day}T12:00:00Z",
                            "o": 100,
                            "h": 100,
                            "l": 100,
                            "c": 100,
                            "v": 10000,
                        }
                        for day in days
                        if not (
                            scenario == "missing_member"
                            and s == "S000"
                            and day == date(2024, 5, 7)
                        )
                    ]
                    for s in requested
                }
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = Provider(store, client, Settings("key", "secret"))
        payload = {
            "universe": "sp500_historical" if historical else "sp500_current",
            "symbols": ["EXTRA"],
            "start": str(start),
            "end": str(end),
        }
        if historical and scenario in ("reuse", "missing_member"):
            with pytest.raises(
                ResearchError,
                match="Ambiguous historical identity"
                if scenario == "reuse"
                else "coverage is incomplete",
            ):
                download_market(store, payload, lambda *a: None, provider)
            assert store.datasets() == []
            return
        result = download_market(store, payload, lambda *a: None, provider)
    assert set(result["symbols"]) == names
    assert result["row_count"] == len(names) * len(days)
    if scenario == "large":
        assert result["row_count"] > 80000
    ds = Store(store.path).dataset(result["id"])
    assert ds.metadata["membership"]["id"] == snapshot["id"]
    assert "EXTRA" in ds.bars and "SPY" in ds.bars
    assert any(
        a["symbol"] == "S000" and a["status"] == "inactive"
        for a in ds.metadata["securities"]
    )
    assert len([r for r in calls if r.url.path.endswith("/assets")]) == 2
    assert len([r for r in calls if r.url.path.endswith("/bars")]) == 12


def test_membership_worker_failure_does_not_publish_partial_state(
    tmp_path, monkeypatch
):
    store = Store(tmp_path / "a.sqlite")
    monkeypatch.setattr(
        membership,
        "refresh",
        lambda *a: (_ for _ in ()).throw(ResearchError("source unavailable")),
    )
    store.enqueue("membership", {"kind": "historical"})
    process_one(store)
    assert store.jobs()[0]["state"] == "failed"
    assert store.membership("historical") is None


def test_stale_refresh_is_required_and_never_falls_back_to_an_old_roster(
    tmp_path, monkeypatch
):
    store = Store(tmp_path / "a.sqlite")
    first = refresh_fixture(store, "current", html())
    assert membership.fresh(store, "current")["id"] == first["id"]
    old = {
        **first,
        "id": "stale",
        "captured_at": (datetime.now().astimezone() - timedelta(days=2)).isoformat(),
    }
    # Use a separate store so the genuinely newer first observation does not
    # mask the deliberately stale fixture.
    stale = Store(tmp_path / "stale.sqlite")
    stale.save_membership(old, b"original stale source")
    called = []

    def fail(*args):
        called.append(True)
        raise ResearchError("refresh failed")

    monkeypatch.setattr(membership, "refresh", fail)
    with pytest.raises(ResearchError, match="refresh failed"):
        membership.fresh(stale, "current")
    assert called == [True]
    assert stale.membership("current")["id"] == "stale"
