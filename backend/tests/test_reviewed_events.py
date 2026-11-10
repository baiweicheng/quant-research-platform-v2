"""Reviewed terminal conversions, distributions, lifetimes and vendor rejections."""

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal as D

import pytest

from aperture import reviewed_events as reviewed
from aperture.domain import Bar, Portfolio, ResearchError
from aperture.ledger import apply_actions
from aperture.lifecycles import complete_consideration, recipients
from aperture.research_data import security_events
from test_dated_research import vendor, payload  # noqa: F401

RAW = b"Reviewed primary filing fixture"
DIGEST = hashlib.sha256(RAW).hexdigest()


class Documents:
    def __init__(self, raw=RAW):
        self.raw, self.calls = raw, []

    def document(self, url):
        self.calls.append(url)
        return self.raw


def bar(symbol, day, close, **extra):
    close = D(str(close))
    return Bar(
        symbol,
        day,
        close,
        close,
        close,
        close,
        extra.pop("volume", 1000),
        available_at=datetime(2016, 1, 1, tzinfo=timezone.utc),
        **extra,
    )


def fingerprinted(monkeypatch, record):
    monkeypatch.setitem(record, "sha256", DIGEST)
    if "terms_source" in record:
        monkeypatch.setitem(record["terms_source"], "sha256", DIGEST)


def run(
    bars,
    identities,
    events=(),
    issues=None,
    first=date(2016, 1, 4),
    last=date(2026, 11, 9),
    api=None,
):
    found = []
    issues = [] if issues is None else issues

    def issue(symbol, day, reason, kind="action", end=None):
        found.append((symbol, str(day), reason, kind))
        issues.append(
            {
                "symbol": symbol,
                "start": str(day),
                "end": str(end or day),
                "kind": kind,
                "reason": reason,
            }
        )

    income = {}
    out, remaining, receipts = reviewed.apply(
        bars,
        identities,
        list(events),
        income,
        issues,
        first,
        last,
        api or Documents(),
        issue,
    )
    return out, remaining, receipts, income, found


@pytest.mark.parametrize("symbol", sorted(reviewed.TERMINALS))
def test_reviewed_terminal_terms_require_the_captured_cohort_and_source(
    monkeypatch, symbol
):
    spec = reviewed.TERMINALS[symbol]
    fingerprinted(monkeypatch, spec)
    final = date.fromisoformat(spec["last_trading"])
    rows = {final: bar(symbol, final, spec["last_close"])}
    later = date.fromisoformat(spec["effective"])
    if spec.get("truncate"):
        rows[later] = bar(symbol, later, spec["last_close"], volume=0)
    bars = {symbol: dict(rows)}
    identities = {symbol: {"asof": spec["quote_asof"]}}
    natives = [
        {
            "id": event_id,
            "source": symbol,
            "kind": sig["kind"],
            "effective": sig["effective"],
            "cash": sig["cash"],
            "target": sig["targets"][0][0] if sig["targets"] else None,
            "ratio": sig["targets"][0][1] if sig["targets"] else "0",
        }
        for event_id, sig in spec.get("replaces", {}).items()
    ]
    api = Documents()
    events, _, _, _, found = run(bars, identities, natives, api=api)
    event = next(e for e in events if e["id"].endswith("-terminal"))
    assert event["effective"] == spec["effective"] and event["source"] == symbol
    assert complete_consideration(event)
    assert [(s, str(r)) for s, r in recipients(event)] == [
        (t["symbol"], str(D(t["ratio"]))) for t in spec["targets"]
    ]
    assert D(event["cash"]) == D(spec["cash"])
    assert max(bars[symbol]) == final  # Later marks never stay executable.
    assert all(
        e["kind"] == "rejected_native_merger"
        for e in events
        if e["id"] in spec.get("replaces", {})
    )
    assert api.calls[0] == spec["url"]
    # An incremental Update re-applies the review to records carried from the
    # earlier snapshot: same terminal record, no conflict with itself.
    again, _, _, _, repeat = run(bars, identities, events)
    assert [e for e in again if e["id"].endswith("-terminal")] == [event]
    assert [e for e in again if e["id"] in spec.get("replaces", {})] == [
        e for e in events if e["id"] in spec.get("replaces", {})
    ]
    assert not any("conflict" in f[2] for f in repeat)
    if D(spec["cash"]):
        assert (
            symbol,
            spec["effective"],
            "Merger cash payment date is unavailable.",
            "cash_payment",
        ) in found
    # A different quote vintage, final close or unreviewed vendor instruction fails closed.
    for changed in ({symbol: {"asof": "1999-01-01"}},):
        events, *_, found = run({symbol: dict(rows)}, changed)
        assert not any(e["id"].endswith("-terminal") for e in events) and found
    moved = {symbol: {final: bar(symbol, final, D(spec["last_close"]) + 1)}}
    events, *_, found = run(moved, identities)
    assert not any(e["id"].endswith("-terminal") for e in events)
    other = {
        "id": "unreviewed",
        "source": symbol,
        "kind": "cash_mergers",
        "effective": spec["effective"],
        "cash": "1",
    }
    events, *_, found = run({symbol: dict(rows)}, identities, [other, *natives])
    assert not any(e["id"].endswith("-terminal") for e in events)
    assert any("Unreviewed vendor merger" in f[2] for f in found)
    with pytest.raises(ResearchError, match="fingerprint changed"):
        run({symbol: dict(rows)}, identities, natives, api=Documents(b"changed terms"))


@pytest.mark.parametrize("index", range(len(reviewed.DISTRIBUTIONS)))
def test_reviewed_distributions_value_children_in_post_split_units(monkeypatch, index):
    spec = reviewed.DISTRIBUTIONS[index]
    fingerprinted(monkeypatch, spec)
    parent, day = spec["parent"], date.fromisoformat(spec["ex_date"])
    before = date.fromordinal(day.toordinal() - 3)
    bars = {
        parent: {
            before: bar(parent, before, spec["prev_close"]),
            day: bar(parent, day, spec["close"], split=D("0.3")),
        }
    }
    split = D(spec.get("parent_split", "1"))
    # Child price that conserves value across the ex-date in this fixture.
    ratios = sum((D(c["ratio"]) for c in spec["children"]), D(0))
    child = (
        (
            (D(spec["prev_close"]) / split - D(spec["close"])) * split
            - D(spec.get("cash", "0"))
        )
        / ratios
        if ratios
        else D(0)
    ).quantize(D("0.01"))
    for c in spec["children"]:
        when = date.fromisoformat(c.get("price_date", spec["ex_date"]))
        bars[c["symbol"]] = {when: bar(c["symbol"], when, child)}
    issues = [
        {
            "symbol": parent,
            "start": spec["ex_date"],
            "end": spec["ex_date"],
            "kind": "action",
            "reason": reviewed.SPLIT_CONFLICT,
        }
    ]
    events, remaining, receipts, income, found = run(bars, {}, issues=issues)
    expected = (
        D(spec.get("cash", "0")) + sum(D(c["ratio"]) * child for c in spec["children"])
    ) / split
    row = bars[parent][day]
    assert row.split == split and row.research_distribution == expected
    assert receipts[0]["kind"] == "reviewed_distributions"
    assert not any(i["reason"] == reviewed.SPLIT_CONFLICT for i in remaining)
    assert (
        parent,
        spec["ex_date"],
        reviewed.DISTRIBUTION_NOTE,
        "cash_payment",
    ) in found
    # Re-applying to the corrected row reproduces identical inputs.
    run(bars, {})
    assert bars[parent][day] == row
    natives = [
        {"id": event_id, "source": parent, "target": None, "ratio": "0", **sig}
        for event_id, sig in spec.get("rejects_merger", {}).items()
    ]
    if natives:
        first_events, _, first_receipts, *_ = run(bars, {}, natives)
        rejected = [e for e in first_events if e["id"] in spec["rejects_merger"]]
        assert all(e["kind"] == "rejected_native_merger" for e in rejected)
        # A repeated Update receives the carried rejection and reproduces it.
        again, _, again_receipts, *_ = run(bars, {}, first_events)
        assert [e for e in again if e["id"] in spec["rejects_merger"]] == rejected
        assert again_receipts == first_receipts
        changed = [{**natives[0], "cash": "6"}]
        with pytest.raises(ResearchError, match="no longer matches"):
            run(bars, {}, changed)
    # Changed parent quotes or an absent child price keep the stock blocked.
    shifted = {
        **bars,
        parent: {**bars[parent], day: bar(parent, day, D(spec["close"]) + 1)},
    }
    _, _, receipts, _, found = run(shifted, {})
    assert not receipts and any("no longer matches" in f[2] for f in found)
    if spec["children"]:
        orphan = {parent: dict(bars[parent])}
        orphan[parent][day] = bar(parent, day, spec["close"])
        _, _, receipts, _, found = run(orphan, {})
        assert not receipts and any("child price is unavailable" in f[2] for f in found)


@pytest.mark.parametrize("symbol", sorted(reviewed.LIFETIMES))
def test_reviewed_lifetimes_trim_only_the_matching_cohort(monkeypatch, symbol):
    spec = reviewed.LIFETIMES[symbol]
    fingerprinted(monkeypatch, spec)
    cut = date.fromisoformat(spec.get("keep_from") or spec["keep_until"])
    outside = date.fromordinal(cut.toordinal() + (-3 if "keep_from" in spec else 3))
    close = spec.get("first_close") or spec["last_close"]
    bars = {symbol: {cut: bar(symbol, cut, close), outside: bar(symbol, outside, "1")}}
    run(bars, {})
    assert list(bars[symbol]) == [cut]
    changed = {symbol: {cut: bar(symbol, cut, "1"), outside: bar(symbol, outside, "1")}}
    *_, found = run(changed, {})
    assert len(changed[symbol]) == 2 and found


def test_merger_shares_do_not_inherit_the_recipients_same_day_distribution():
    """Raytheon holders receive post-spin RTX shares, not Carrier and Otis."""
    day = date(2020, 4, 3)
    portfolio = Portfolio(D(0), {"RTN": D(10), "RTX": D(5)})
    events = [
        {
            "kind": "stock_mergers",
            "source": "RTN",
            "target": "RTX",
            "ratio": "2.3348",
            "cash": "0",
            "effective": str(day),
        }
    ]
    rtx = bar("RTX", day, "49.93", research_distribution=D("40.58"))
    fresh = security_events(portfolio, day, events, {"RTX": rtx}, "ex_date")
    assert fresh == {"RTX": D("23.348")}
    apply_actions(portfolio, day, {"RTX": rtx}, "ex_date", fresh=fresh)
    assert portfolio.positions == {"RTX": D("28.348")}
    assert portfolio.research_income == [("RTX", D(5) * D("40.58"))]


def test_multi_recipient_and_reviewed_zero_recovery_conversions():
    day = date(2019, 3, 19)
    split = {
        "kind": "stock_mergers",
        "source": "FOXA.OLD",
        "cash": "0",
        "effective": str(day),
        "targets": [
            {"symbol": "FOXA", "ratio": "0.3333333333"},
            {"symbol": "DIS", "ratio": "0.3328202389"},
        ],
    }
    portfolio = Portfolio(D(0), {"FOXA.OLD": D(300)})
    bars = {s: bar(s, day, "40") for s in ("FOXA", "DIS")}
    fresh = security_events(portfolio, day, [split], bars, "ex_date")
    assert portfolio.positions == {"FOXA": D("99.99999999"), "DIS": D("99.84607167")}
    assert fresh == portfolio.positions
    failed = {
        "kind": "cash_mergers",
        "source": "SIVB",
        "cash": "0",
        "effective": "2023-03-10",
        "reviewed_evidence": {"zero_recovery": True},
    }
    assert complete_consideration(failed)
    assert not complete_consideration({**failed, "reviewed_evidence": {}})
    portfolio = Portfolio(D(0), {"SIVB": D(10)})
    security_events(portfolio, date(2023, 3, 10), [failed], {}, "ex_date")
    assert (
        portfolio.positions == {}
        and portfolio.receivables == []
        and portfolio.cash == 0
    )


def test_reviewed_vendor_rejections_and_symbol_epochs():
    ca = {"id": "fa113393-e8dd-4aec-b909-c789caac7839"}
    assert reviewed.rejected_native(ca, "CA", date(2026, 5, 21))
    assert reviewed.rejected_native(ca, "OTHER", date(2026, 5, 21)) is None
    assert reviewed.rejected_native({"id": "x"}, "CA", date(2026, 5, 21)) is None
    assert reviewed.verified_dividend("EG", date(2023, 3, 15), D("1.65"))
    assert not reviewed.verified_dividend("EG", date(2023, 3, 15), D("1.74"))


def test_implausible_share_factor_flags_a_spin_off_recorded_as_reverse_split():
    a, b = date(2017, 5, 31), date(2017, 6, 1)
    bars = {
        "SPY": {a: bar("SPY", a, "240"), b: bar("SPY", b, "241")},
        "TGNA": {
            a: bar("TGNA", a, "23.74"),
            b: bar("TGNA", b, "15.35", split=D("0.33333")),
        },
        "AAPL": {a: bar("AAPL", a, "400"), b: bar("AAPL", b, "101", split=D(4))},
    }
    findings = reviewed.implausible_share_factors(bars, set())
    assert [(f[0], f[1]) for f in findings] == [("TGNA", b)]
    assert reviewed.implausible_share_factors(bars, {("TGNA", str(b))}) == []


def test_duplicate_dividend_under_a_second_cusip_counts_once(vendor):  # noqa: F811
    from aperture.research_data import download

    store, api, state = vendor
    record = dict(
        symbol="ABC",
        ex_date="2017-01-12",
        process_date="2017-01-20",
        payable_date="2017-01-20",
        record_date="2017-01-13",
        rate=1,
    )
    state["events"] = {
        "cash_dividends": [
            {**record, "id": "old", "cusip": "000000001"},
            {**record, "id": "new", "cusip": "000000002"},
            {**record, "id": "special", "cusip": "000000002", "rate": 0.5},
        ]
    }
    ds = store.dataset(download(store, payload(), lambda *a: None, api)["id"])
    row = next(b for b in ds.bars["ABC"] if b.session == date(2017, 1, 12))
    assert row.research_dividend == D("1.5")
    assert ds.metadata["set_aside_vendor_records"]["new"]["status"] == "duplicate"
