from dataclasses import replace
from datetime import date

import pytest

from aperture.security_identity import known_gaps, freeze_historical_quotes
from aperture.coverage import plan
from test_lifecycles import dataset
from test_dated_research import vendor, payload  # noqa: F401


def test_bank_fund_ticker_collision_rejects_only_the_funds_records():
    """BNY meant a municipal fund before the bank adopted the ticker.

    The fund's monthly income and merger are rejected by raw-symbol epoch;
    the bank's own BK-era and later BNY dividends remain. No blanket identity
    gap excludes the bank any longer.
    """
    from aperture.reviewed_events import rejected_native

    assert known_gaps(["BNY"], date(2016, 1, 4), date(2026, 11, 6)) == []
    fund_income = {"id": "fund", "cusip": "", "kind": "cash_dividends"}
    assert rejected_native(fund_income, "BNY", date(2016, 1, 13))
    fund_merger = {"id": "m", "acquiree_cusip": "09248L106"}
    assert rejected_native(fund_merger, "BNY", date(2026, 2, 9))
    late_fund = {"id": "late", "cusip": "09248L106"}
    assert rejected_native(late_fund, "BNY", date(2026, 6, 1))
    bank = {"id": "bank", "cusip": "064058100"}
    assert rejected_native(bank, "BNY", date(2026, 7, 27)) is None
    assert rejected_native(bank, "BK", date(2016, 1, 29)) is None


def test_current_or_still_overlapping_security_is_not_frozen():
    ds = dataset()
    assert not freeze_historical_quotes(ds, "ABC", date(2024, 5, 8), date(2024, 5, 6))
    assert not freeze_historical_quotes(ds, "SAFE", date(2024, 5, 1), date(2024, 5, 20))
    # An old indexed vintage is not revived merely because its ticker is now
    # listed again. Preserve the original history rather than add current bars.
    assert freeze_historical_quotes(ds, "ABC", date(2024, 5, 8), date(2024, 5, 20))


@pytest.mark.parametrize("directory_status", ["active", "inactive"])
@pytest.mark.parametrize("quote_end", ["2016-08-01", "2015-12-31"])
def test_old_cohort_cannot_gain_spurious_current_quotes_on_update(
    vendor,  # noqa: F811
    monkeypatch,
    directory_status,
    quote_end,
):
    from aperture import membership
    from aperture.research_data import download

    store, api, state = vendor
    audit = {
        "kind": "historical",
        "coverage_start": "2016-01-04",
        "coverage_end": "2017-02-10",
        "additional_symbols": [],
        "rosters": [
            {"effective": "2016-01-04", "symbols": ["ABC", "NEW"]},
            {"effective": "2016-06-01", "symbols": ["NEW"]},
        ],
    }
    monkeypatch.setattr(
        membership, "resolve", lambda *a: (["ABC", "NEW", "SPY"], audit, {})
    )
    get, pages = api.get, api.pages

    def directory(provider, url, params=None, ttl=300):
        rows = get(provider, url, params, ttl)
        return [
            r
            for r in rows
            if (r["symbol"] == "ABC") == (params.get("status") == directory_status)
        ]

    def quotes(path, query, key):
        result = pages(path, query, key)
        if (
            key == "bars"
            and "ABC" in query["symbols"].split(",")
            and not state.get("leak")
        ):
            for page in result:
                page["bars"]["ABC"] = [
                    r for r in page["bars"].get("ABC", []) if r["t"][:10] <= quote_end
                ]
        return result

    api.get, api.pages = directory, quotes
    first = download(store, payload("2017-02-03"), lambda *a: None, api)
    before = store.dataset(first["id"])
    state["latest"] = date(2017, 2, 10)
    state["leak"] = True
    api.calls.clear()
    second = download(store, payload("2017-02-10"), lambda *a: None, api, base=before)
    after = store.dataset(second["id"])
    assert after.bars["ABC"] == before.bars["ABC"]
    assert not after.bars["ABC"] or str(after.bars["ABC"][-1].session) == quote_end
    for issue in before.metadata["input_issues"]:
        if issue["symbol"] == "ABC":
            assert issue in after.metadata["input_issues"]
    assert all(
        "ABC" not in q["symbols"].split(",")
        for p, q in api.calls
        if p == "/v2/stocks/bars"
    )
    assert after.bars["NEW"][-1].session == date(2017, 2, 10)


def test_empty_current_member_gets_full_backfill_on_update(vendor):  # noqa: F811
    from aperture.research_data import download

    store, api, state = vendor
    first = download(store, payload("2017-02-03"), lambda *a: None, api)
    ds = store.dataset(first["id"])
    base = replace(ds, bars={**ds.bars, "ABC": []})
    state["latest"] = date(2017, 2, 10)
    api.calls.clear()
    saved = download(store, payload("2017-02-10"), lambda *a: None, api, base=base)
    after = store.dataset(saved["id"])
    assert after.bars["ABC"][0].session == date(2016, 1, 4)
    assert after.bars["ABC"][-1].session == date(2017, 2, 10)
    assert any(
        q["start"][:10] == "2016-01-04" and "ABC" in q["symbols"].split(",")
        for p, q in api.calls
        if p == "/v2/stocks/bars"
    )


def test_dow_pre_separation_quotes_are_outside_the_reviewed_listing_lifetime():
    """Dow Inc. history starts April 2, 2019 instead of excluding the stock."""
    from aperture.reviewed_events import LIFETIMES

    assert known_gaps(["DOW"], date(2016, 1, 4), date(2026, 11, 6)) == []
    assert LIFETIMES["DOW"]["keep_from"] == "2019-04-02"


def test_separate_cash_and_stock_merger_rows_require_reconciliation():
    from aperture.research_data import input_issues, blocked_inputs

    ds = dataset()
    cash = dict(
        kind="cash_mergers",
        source="ABC",
        effective="2024-05-09",
        cash="15",
        ratio="0",
        target=None,
        pay_date=None,
    )
    stock = dict(
        kind="stock_mergers",
        source="ABC",
        effective="2024-05-09",
        cash="0",
        ratio="1",
        target="SAFE",
        pay_date="2024-05-09",
    )
    ds = replace(ds, metadata={"input_issues": [], "corporate_actions": [cash, stock]})
    assert any("Multiple merger instructions" in i["reason"] for i in input_issues(ds))
    assert blocked_inputs(ds, ["ABC"], date(2024, 5, 9), date(2024, 5, 9)) == {"ABC"}
    audit = plan(
        ds,
        date(2024, 5, 6),
        date(2024, 5, 24),
        "momentum",
        "ex_date",
        "coverage_limited",
    )
    assert any(
        x["symbol"] == "ABC"
        and any("Multiple merger instructions" in r for r in x["reasons"])
        for x in audit["excluded"]
    )


def test_exact_duplicate_or_single_combined_merger_does_not_trigger_conflict_gate():
    from aperture.research_data import input_issues

    ds = dataset()
    cash = dict(
        kind="cash_mergers",
        source="ABC",
        effective="2024-05-09",
        cash="15",
        ratio="0",
        target=None,
        pay_date=None,
    )
    combined = {
        **cash,
        "kind": "stock_and_cash_mergers",
        "cash": "5",
        "ratio": "0.25",
        "target": "SAFE",
    }
    for events in [[cash, dict(cash)], [combined]]:
        ds = replace(ds, metadata={"input_issues": [], "corporate_actions": events})
        assert not input_issues(ds)
