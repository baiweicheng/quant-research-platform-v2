"""Financial and immutable-update contracts for the combined research path."""

import copy
from datetime import date
from decimal import Decimal as D

import pytest
from aperture import calendar
from aperture.backtest import run
from aperture.domain import Bar, Policy, Portfolio, ResearchError
from aperture.ledger import apply_actions, reinvest_research_income
from aperture.research_data import download, blocked_inputs, security_events
from aperture.signals import total_return_levels
from aperture.store import Store


def bar(day, close=100, **kw):
    return Bar("ABC", day, *([D(close)] * 4), 1000, **kw)


def test_exdate_income_belongs_to_overnight_holder_and_waits_until_close():
    day = date(2024, 5, 6)
    b = bar(day, 90, research_dividend=D(10))
    p = Portfolio(D(0), {"ABC": D(10)})
    apply_actions(p, day, {"ABC": b}, "ex_date")
    assert p.cash == 0 and p.positions["ABC"] == 10
    assert p.research_income == [("ABC", D(100))]
    reinvest_research_income(p, day, {"ABC": b})
    assert p.positions["ABC"] == D("11.111111")
    assert p.value({"ABC": D(90)}) == 1000
    fresh = Portfolio(D(0))
    apply_actions(fresh, day, {"ABC": b}, "ex_date")
    fresh.positions["ABC"] = D(10)
    reinvest_research_income(fresh, day, {"ABC": b})
    assert fresh.positions["ABC"] == 10 and fresh.cash == 0
    sold = Portfolio(D(0), {"ABC": D(10)})
    apply_actions(sold, day, {"ABC": b}, "ex_date")
    sold.positions.clear()
    assert sold.cash == 0
    reinvest_research_income(sold, day, {"ABC": b})
    assert sold.cash == 100 and not sold.positions


def test_split_and_distribution_units_agree_with_independent_return():
    a, b = (
        bar(date(2024, 5, 3)),
        bar(date(2024, 5, 6), 49, split=D(2), research_dividend=D(1)),
    )
    assert total_return_levels([a, b]) == [1, 1]
    p = Portfolio(D(0), {"ABC": D(10)})
    apply_actions(p, b.session, {"ABC": b}, "ex_date")
    assert p.positions["ABC"] == 20 and p.cash == 0
    reinvest_research_income(p, b.session, {"ABC": b})
    assert p.value({"ABC": D(49)}) == 1000


def test_merger_cash_keeps_verified_payment_date_in_research():
    p = Portfolio(D(0), {"ABC": D(10)})
    day = date(2024, 5, 6)
    events = [
        dict(
            effective=str(day),
            kind="cash_mergers",
            source="ABC",
            cash="20",
            pay_date="2024-05-08",
        )
    ]
    security_events(p, day, events, {}, "ex_date")
    assert p.receivables == [(date(2024, 5, 8), D(200))] and not p.positions
    apply_actions(p, day, {}, "ex_date")
    assert p.cash == 0
    apply_actions(p, date(2024, 5, 8), {}, "ex_date")
    assert p.cash == 200
    p = Portfolio(D(0), {"ABC": D(10)})
    with pytest.raises(ResearchError, match="contingent"):
        security_events(
            p, day, [{**events[0], "unpriced_consideration": "123CVR"}], {}, "ex_date"
        )
    assert p.positions["ABC"] == 10


@pytest.fixture
def vendor(tmp_path, monkeypatch):
    from sector_fixtures import stub_sectors

    stub_sectors(monkeypatch)
    store = Store(tmp_path / "research.sqlite3")
    state = {
        "latest": date(2017, 2, 3),
        "events": {},
        "missing": None,
        "identity": "ABC-v1",
        "fail": False,
        "price": 100,
    }
    monkeypatch.setattr(calendar, "latest_complete", lambda *a: state["latest"])

    class Vendor:
        observations = []
        calls = []

        def get(self, provider, url, params=None, ttl=300):
            return [
                dict(
                    symbol=s,
                    id=state["identity"] if s == "ABC" else s,
                    name=s + " Corporation",
                    exchange="NASDAQ",
                    **{"class": "us_equity"},
                )
                for s in ["ABC", "SPY", "NEW"]
            ]

        def pages(self, path, query, key):
            self.calls.append((path, copy.deepcopy(query)))
            if state["fail"]:
                raise ResearchError("Interrupted provider")
            if key == "corporate_actions":
                return [{"corporate_actions": copy.deepcopy(state["events"])}]
            first, last = (date.fromisoformat(query[k][:10]) for k in ["start", "end"])
            rows = {}
            for symbol in query["symbols"].split(","):
                rows[symbol] = []
                for day in calendar.sessions(first, last):
                    if (symbol, str(day)) == state["missing"]:
                        continue
                    price = D(state["price"]) + D((day - date(2016, 1, 4)).days) / 100
                    rows[symbol].append(
                        dict(
                            t=calendar.open_time(day).isoformat(),
                            o=str(price),
                            h=str(price),
                            l=str(price),
                            c=str(price),
                            v=10000,
                        )
                    )
            return [{"bars": rows}]

    yield store, Vendor(), state


def payload(end="2017-02-03", symbols=None):
    return dict(
        name="Research",
        universe="custom",
        symbols=symbols or ["ABC"],
        start="2016-01-04",
        end=end,
    )


def test_missing_paydates_are_dated_and_models_stay_distinct(vendor):
    s, p, state = vendor
    state["events"] = {
        "cash_dividends": [
            dict(
                id="div",
                symbol="ABC",
                ex_date="2017-01-12",
                process_date="2017-01-12",
                rate=1,
            )
        ]
    }
    summary = download(s, payload(), lambda *a: None, p)
    ds = s.dataset(summary["id"])
    b = next(b for b in ds.bars["ABC"] if b.session == date(2017, 1, 12))
    assert b.research_dividend == 1 and b.dividend == 0 and b.pay_date is None
    assert not blocked_inputs(
        ds, {"ABC"}, date(2017, 1, 1), date(2017, 2, 3), "ex_date"
    )
    assert blocked_inputs(
        ds, {"ABC"}, date(2017, 1, 1), date(2017, 2, 3), "pay_date"
    ) == {"ABC"}
    assert not blocked_inputs(
        ds, {"ABC"}, date(2017, 1, 13), date(2017, 2, 3), "pay_date"
    )
    out = run(
        ds,
        "momentum",
        date(2017, 1, 1),
        date(2017, 2, 3),
        D(10000),
        Policy(),
        dividend_model="ex_date",
    )
    assert out["trade_count"] > 0 and out["dividend_model"] == "ex_date"
    with pytest.raises(ResearchError, match="Payment-date"):
        run(
            ds,
            "momentum",
            date(2017, 1, 1),
            date(2017, 2, 3),
            D(10000),
            Policy(),
            dividend_model="pay_date",
        )


def test_exploratory_exclusions_are_complete_visible_and_do_not_mutate_inputs(vendor):
    s, p, state = vendor
    state["missing"] = ("ABC", "2017-01-12")
    summary = download(s, payload(symbols=["ABC", "NEW"]), lambda *a: None, p)
    ds = s.dataset(summary["id"])
    out = run(
        ds,
        "momentum",
        date(2017, 1, 1),
        date(2017, 2, 3),
        D(10000),
        Policy(),
        coverage_mode="coverage_limited",
    )
    assert out["coverage"]["excluded_count"] == 1
    assert out["coverage"]["excluded"][0]["symbol"] == "ABC"
    assert "2017-01-12" in out["coverage"]["excluded"][0]["reasons"][0]
    assert "survivorship" in out["coverage"]["warning"]
    assert all(t["symbol"] != "ABC" for t in out["trades"])
    assert "research_exclusions" not in ds.metadata
    assert out == run(
        s.dataset(ds.id),
        "momentum",
        date(2017, 1, 1),
        date(2017, 2, 3),
        D(10000),
        Policy(),
        coverage_mode="coverage_limited",
    )


def test_incremental_refresh_replaces_overlap_backfills_new_and_shares_old(vendor):
    s, p, state = vendor
    old = download(s, payload(), lambda *a: None, p)
    base = s.dataset(old["id"])
    old_result = run(
        base, "momentum", date(2017, 1, 1), date(2017, 2, 3), D(10000), Policy()
    )
    p.calls.clear()
    state["latest"] = date(2017, 2, 10)
    state["missing"] = ("ABC", "2017-02-01")
    state["price"] = 101
    new = download(
        s, payload("2017-02-10", ["ABC", "NEW"]), lambda *a: None, p, base=base
    )
    ds = s.dataset(new["id"])
    queries = [q for path, q in p.calls if path.endswith("/bars")]
    assert all(q["start"] > "2016-01-04" for q in queries if "ABC" in q["symbols"])
    assert all(q["start"] == "2016-01-04" for q in queries if "NEW" in q["symbols"])
    assert not any(b.session == date(2017, 2, 1) for b in ds.bars["ABC"])
    assert ds.bars["ABC"][0] == base.bars["ABC"][0]
    assert (
        run(
            s.dataset(base.id),
            "momentum",
            date(2017, 1, 1),
            date(2017, 2, 3),
            D(10000),
            Policy(),
        )
        == old_result
    )
    from test_snapshots import chunks

    assert set(chunks(s, base.id)["bar_chunks"]) & set(chunks(s, ds.id)["bar_chunks"])
    count = len(s.datasets())
    state["identity"] = "different-equity"
    with pytest.raises(ResearchError, match="identity changed"):
        download(s, payload("2017-02-10"), lambda *a: None, p, base=base)
    assert len(s.datasets()) == count


def test_failure_publishes_no_partial_price_snapshot(vendor):
    s, p, state = vendor
    state["fail"] = True
    with pytest.raises(ResearchError, match="Interrupted"):
        download(s, payload(), lambda *a: None, p)
    assert s.datasets() == []


def test_ambiguous_historical_listing_is_quarantined_not_discarded(vendor):
    s, p, state = vendor
    get = p.get

    def listings(provider, url, params=None, ttl=300):
        if params and params.get("status") == "inactive":
            return [
                dict(
                    id="other-issuer",
                    symbol="ABC",
                    name="Unrelated company",
                    exchange="NYSE",
                    **{"class": "us_equity"},
                )
            ]
        return get(provider, url, params, ttl)

    p.get = listings
    saved = download(s, payload(), lambda *a: None, p)
    ds = s.dataset(saved["id"])
    assert ds.bars["ABC"]
    assert any(i["kind"] == "identity" for i in ds.metadata["input_issues"])
    with pytest.raises(ResearchError, match="unavailable/unverified"):
        run(ds, "momentum", date(2017, 1, 1), date(2017, 2, 3), D(10000), Policy())
    out = run(
        ds,
        "momentum",
        date(2017, 1, 1),
        date(2017, 2, 3),
        D(10000),
        Policy(),
        coverage_mode="coverage_limited",
    )
    assert out["coverage"]["excluded"][0]["symbol"] == "ABC" and out["trade_count"] == 0


def test_dividend_usd_crosscheck_does_not_assume_foreign_flag_is_usd(vendor):
    s, p, state = vendor
    state["events"] = {
        "cash_dividends": [
            dict(
                id="div",
                symbol="ABC",
                ex_date="2017-01-12",
                process_date="2017-01-12",
                rate=20,
                foreign=True,
            )
        ]
    }
    saved = download(s, payload(), lambda *a: None, p)
    assert any(
        "USD adjusted-price" in i["reason"] for i in saved["metadata"]["input_issues"]
    )
    assert any(q.get("adjustment") == "dividend" for _, q in p.calls)


def test_known_conflicting_split_stays_flagged_and_is_never_applied(vendor):
    s, p, state = vendor
    state["events"] = {
        "reverse_splits": [
            dict(
                id="78f521c7-d5ad-42fe-a534-5c5ac1497d33",
                symbol="ABC",
                ex_date="2017-01-12",
                process_date="2017-01-12",
                old_rate=1,
                new_rate=".1666",
            )
        ]
    }
    saved = download(s, payload(), lambda *a: None, p)
    ds = s.dataset(saved["id"])
    assert next(b for b in ds.bars["ABC"] if b.session == date(2017, 1, 12)).split == 1
    assert any("Ingevity" in i["reason"] for i in ds.metadata["input_issues"])


def test_normal_download_requires_both_sources_before_queueing(tmp_path, monkeypatch):
    from aperture.api import create_app
    from aperture.config import Settings
    from fastapi.testclient import TestClient

    monkeypatch.setattr("aperture.api.settings", lambda: Settings("test", "test"))
    with TestClient(create_app(tmp_path / "api.sqlite3", None)) as c:
        body = payload()
        r = c.post("/api/downloads", json=body, headers={"X-Aperture-Client": "1"})
        assert r.status_code == 422 and "SEC_USER_AGENT" in r.json()["detail"]
        monkeypatch.setattr(
            "aperture.api.settings",
            lambda: Settings("test", "test", "Test test@example.com"),
        )
        assert (
            c.post(
                "/api/downloads",
                json={**body, "include_fundamentals": False},
                headers={"X-Aperture-Client": "1"},
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/downloads", json=body, headers={"X-Aperture-Client": "1"}
            ).status_code
            == 202
        )


def test_missing_sec_facts_are_coverage_exclusion_other_errors_still_fail(
    vendor, monkeypatch
):
    from aperture.fundamentals import attach
    from aperture.providers import ResourceMissing

    s, p, state = vendor
    saved = download(s, payload(), lambda *a: None, p)

    class SEC:
        observations = []

        def get(self, provider, url, params=None, ttl=300):
            if url.endswith("company_tickers_exchange.json"):
                return dict(fields=["cik", "ticker"], data=[[1, "ABC"]])
            raise ResourceMissing("SEC resource 404")

    complete = attach(s, saved["id"], lambda *a: None, SEC(), allow_empty=True)
    assert complete["metadata"]["fundamentals"]["record_count"] == 0
    assert "HTTP 404" in complete["metadata"]["fundamentals"]["coverage"][0]["reason"]

    class Broken(SEC):
        def get(self, *a, **kw):
            raise ResearchError("SEC temporarily unavailable")

    count = len(s.datasets())
    with pytest.raises(ResearchError, match="temporarily unavailable"):
        attach(s, saved["id"], lambda *a: None, Broken(), allow_empty=True)
    assert len(s.datasets()) == count


def test_opening_nav_counts_known_income_without_spending_it():
    from aperture.ledger import buy

    day = date(2024, 5, 6)
    b = bar(day, 90, research_dividend=D(10))
    p = Portfolio(D(0), {"ABC": D(10)})
    apply_actions(p, day, {"ABC": b}, "ex_date")
    assert p.value({"ABC": D(90)}) == 1000 and p.cash == 0
    assert buy(p, "ABC", b.open, D(100), Policy(), day) is None
    reinvest_research_income(p, day, {"ABC": b})
    assert p.research_income_value == 0 and p.value({"ABC": D(90)}) == 1000


def test_future_spinoff_close_cannot_change_same_day_opening_trades():
    from aperture.ledger import rebalance

    day = date(2024, 5, 6)
    records = []
    values = []
    for closing_distribution in [10, 20]:
        b = bar(day, 90, research_distribution=D(closing_distribution))
        p = Portfolio(D(100), {"ABC": D(10)})
        apply_actions(p, day, {"ABC": b}, "ex_date", {"ABC": D(5)})
        assert p.value({"ABC": D(90)}) == 1050 and p.cash == 100
        records.append(rebalance(p, {"ABC": D(".5")}, {"ABC": b}, Policy(), day))
        reinvest_research_income(p, day, {"ABC": b})
        values.append(p.value({"ABC": D(90)}))
    assert records[0] == records[1] and values[1] - values[0] == 100


def test_initial_combined_download_worker_finishes_with_price_coverage_list(
    vendor, monkeypatch
):
    from aperture.config import Settings
    from aperture.worker import process_one
    from test_fundamentals import source

    s, p, state = vendor
    original = p.get
    p.cfg = Settings("test", "test", "QA qa@example.com")
    p.close = lambda: None

    def get(provider, url, params=None, ttl=300):
        if provider == "sec":
            if url.endswith("company_tickers_exchange.json"):
                return dict(fields=["cik", "ticker"], data=[[1, "ABC"]])
            if "/submissions/" in url:
                return dict(cik=1, tickers=["ABC"], entityType="operating")
            if "/companyfacts/" in url:
                return source()
            raise AssertionError(url)
        return original(provider, url, params, ttl)

    p.get = get
    monkeypatch.setattr("aperture.bundles.Provider", lambda store: p)
    s.enqueue("download", {**payload(), "include_fundamentals": True})
    assert process_one(s)
    assert s.jobs()[0]["state"] == "complete", s.jobs()[0]["message"]
    assert len(s.datasets()) == 3
    complete = s.datasets()[0]
    assert complete["metadata"]["sector_classification"]["classified_count"] == 1
    assert complete["metadata"]["bundle_role"] == "complete"
    assert complete["metadata"]["fundamentals"]["record_count"] > 0
    result = s.result(s.jobs()[0]["result_id"])
    assert isinstance(result["coverage"], list)
    assert result["dataset_id"] == complete["id"]


def test_unfinished_sec_stage_cannot_be_used_as_normal_research(vendor, monkeypatch):
    from dataclasses import replace
    from aperture.api import create_app
    from fastapi.testclient import TestClient

    s, p, state = vendor
    saved = download(s, payload(), lambda *a: None, p)
    with TestClient(create_app(s.path, None)) as c:
        r = c.post(
            "/api/tasks/backtest",
            json=dict(
                dataset_id=saved["id"],
                strategy_id="momentum",
                start="2017-01-01",
                end="2017-02-03",
            ),
            headers={"X-Aperture-Client": "1"},
        )
        assert r.status_code == 422 and "SEC stage" in r.json()["detail"]
    ds = s.dataset(saved["id"])
    complete = replace(
        ds,
        id="empty-sec",
        digest="empty-sec-digest",
        metadata={
            **ds.metadata,
            "bundle_role": "complete",
            "price_dataset_id": ds.id,
            "fundamentals": {"record_count": 0},
        },
    )
    s.save_dataset(complete, b"empty-sec", [])
    with TestClient(create_app(s.path, None)) as c:
        request = dict(
            dataset_id=complete.id,
            strategy_id="momentum",
            start="2017-01-01",
            end="2017-02-03",
        )
        assert (
            c.post(
                "/api/tasks/backtest", json=request, headers={"X-Aperture-Client": "1"}
            ).status_code
            == 202
        )
        assert (
            c.post(
                "/api/tasks/backtest",
                json={**request, "strategy_id": "quality"},
                headers={"X-Aperture-Client": "1"},
            ).status_code
            == 422
        )


def test_update_request_for_old_version_uses_latest_complete_family(
    vendor, monkeypatch
):
    from dataclasses import replace
    from aperture.api import create_app
    from aperture.config import Settings
    from fastapi.testclient import TestClient

    s, p, state = vendor
    old = download(s, payload(), lambda *a: None, p)
    base = s.dataset(old["id"])
    state["latest"] = date(2017, 2, 10)
    newest = download(s, payload("2017-02-10"), lambda *a: None, p, base=base)
    new = s.dataset(newest["id"])
    complete = replace(
        new,
        id="complete-latest",
        digest="complete-latest-digest",
        metadata={
            **new.metadata,
            "price_dataset_id": new.id,
            "bundle_role": "complete",
            "fundamentals": {"record_count": 1},
        },
    )
    s.save_dataset(complete, b"complete", [])
    monkeypatch.setattr(
        "aperture.api.settings", lambda: Settings("test", "test", "QA qa@example.com")
    )
    with TestClient(create_app(s.path, None)) as c:
        assert (
            c.post(
                "/api/datasets/" + base.id + "/update",
                json={},
                headers={"X-Aperture-Client": "1"},
            ).status_code
            == 202
        )
    assert s.claim()["payload"]["dataset_id"] == complete.id


def test_spinoff_opening_marks_survive_incremental_update_without_changing_universe(
    vendor,
):
    from aperture.membership import eligible

    s, p, state = vendor
    state["events"] = {
        "spin_offs": [
            dict(
                id="spin",
                source_symbol="ABC",
                new_symbol="NEW",
                source_rate=2,
                new_rate=1,
                ex_date="2017-01-12",
                process_date="2017-01-12",
                payable_date="2017-01-12",
            )
        ]
    }
    first = download(s, payload(), lambda *a: None, p)
    base = s.dataset(first["id"])
    child = next(b for b in base.bars["NEW"] if b.session == date(2017, 1, 12))
    assert (
        D(base.metadata["research_open_income"]["2017-01-12"]["ABC"]) == child.open / 2
    )
    assert "NEW" not in eligible(base, date(2017, 1, 13))
    state["latest"] = date(2017, 2, 10)
    new = download(s, payload("2017-02-10"), lambda *a: None, p, base=base)
    assert (
        new["metadata"]["research_open_income"]["2017-01-12"]
        == base.metadata["research_open_income"]["2017-01-12"]
    )
    assert "NEW" not in eligible(s.dataset(new["id"]), date(2017, 2, 10))


def test_quote_alias_does_not_certify_missing_original_corporate_actions(vendor):
    from dataclasses import replace
    from aperture.coverage import plan

    s, p, state = vendor
    saved = download(s, payload(), lambda *a: None, p)
    ds = s.dataset(saved["id"])
    ds = replace(
        ds,
        metadata={
            **ds.metadata,
            "identity_resolution": {
                "ABC": {
                    "reviewed_alias": {
                        "until": "2017-01-12",
                        "source": "https://example.com/verified-ticker-change",
                    }
                }
            },
        },
    )
    assert blocked_inputs(ds, {"ABC"}, date(2017, 1, 3), date(2017, 1, 20)) == {"ABC"}
    audit = plan(
        ds,
        date(2017, 1, 3),
        date(2017, 2, 3),
        "momentum",
        "ex_date",
        "coverage_limited",
    )
    assert (
        audit["excluded"][0]["symbol"] == "ABC"
        and "corporate actions" in audit["excluded"][0]["reasons"][0]
    )
    assert not blocked_inputs(ds, {"ABC"}, date(2017, 1, 17), date(2017, 2, 3))


@pytest.mark.parametrize(
    "kind,target,ratio,cash",
    [
        ("cash_mergers", None, "0", "0"),
        ("stock_mergers", "NEW", "0", "0"),
        ("stock_mergers", None, "1", "0"),
    ],
)
def test_incomplete_merger_terms_cannot_erase_a_held_position(
    kind, target, ratio, cash
):
    day = date(2024, 5, 6)
    p = Portfolio(D(0), {"ABC": D(10)})
    event = dict(
        effective=str(day),
        kind=kind,
        source="ABC",
        target=target,
        ratio=ratio,
        cash=cash,
    )
    with pytest.raises(ResearchError, match="zero recovery"):
        security_events(p, day, [event], {}, "ex_date")
    assert p.positions["ABC"] == 10


def test_incomplete_mergers_are_excluded_before_exploratory_simulation(vendor):
    from dataclasses import replace

    s, p, state = vendor
    saved = download(s, payload(), lambda *a: None, p)
    ds = s.dataset(saved["id"])
    ds = replace(
        ds,
        metadata={
            **ds.metadata,
            "corporate_actions": [
                dict(
                    kind="stock_mergers",
                    source="ABC",
                    effective="2017-01-12",
                    target=None,
                    ratio="1",
                    cash="0",
                )
            ],
        },
    )
    out = run(
        ds,
        "momentum",
        date(2017, 1, 1),
        date(2017, 2, 3),
        D(10000),
        Policy(),
        coverage_mode="coverage_limited",
    )
    assert out["coverage"]["excluded"][0]["symbol"] == "ABC"
    assert "zero recovery" in out["coverage"]["excluded"][0]["reasons"][0]
    assert out["trade_count"] == 0


def test_refresh_preserves_spanning_identity_issues_and_new_symbol_old_events(vendor):
    from aperture.research_data import blocked_inputs

    s, p, state = vendor
    original = p.get
    state["ambiguous"] = True

    def listings(provider, url, params=None, ttl=300):
        rows = original(provider, url, params, ttl)
        if params and params.get("status") == "inactive" and state["ambiguous"]:
            rows += [
                dict(
                    id="unrelated-issuer",
                    symbol="ABC",
                    name="Another Corporation",
                    exchange="NYSE",
                    **{"class": "us_equity"},
                )
            ]
        return rows

    p.get = listings
    old = download(s, payload(), lambda *a: None, p)
    base = s.dataset(old["id"])
    original_issues = copy.deepcopy(base.metadata["input_issues"])
    state["latest"] = date(2017, 2, 10)
    state["events"] = {
        "cash_mergers": [
            dict(
                id="new-stock-old-merger",
                acquiree_symbol="NEW",
                process_date="2016-05-02",
                rate="25",
                payable_date="2016-05-04",
            )
        ]
    }
    new = download(
        s, payload("2017-02-10", ["ABC", "NEW"]), lambda *a: None, p, base=base
    )
    ds = s.dataset(new["id"])
    assert blocked_inputs(ds, {"ABC"}, date(2016, 1, 4), date(2017, 2, 10)) == {"ABC"}
    assert blocked_inputs(ds, {"ABC"}, date(2017, 2, 10), date(2017, 2, 10)) == {"ABC"}
    assert any(
        e["source"] == "NEW" and e["effective"] == "2016-05-02"
        for e in ds.metadata["corporate_actions"]
    )
    assert base.metadata["input_issues"] == original_issues
    assert s.dataset(base.id).metadata["input_issues"] == original_issues
    # Resolving today's directory cannot certify frozen historical identities.
    state["ambiguous"] = False
    again = download(
        s, payload("2017-02-10", ["ABC", "NEW"]), lambda *a: None, p, base=ds
    )
    updated = s.dataset(again["id"])
    assert blocked_inputs(updated, {"ABC"}, date(2016, 1, 4), date(2016, 1, 4)) == {
        "ABC"
    }
    assert not blocked_inputs(updated, {"ABC"}, date(2017, 2, 10), date(2017, 2, 10))
