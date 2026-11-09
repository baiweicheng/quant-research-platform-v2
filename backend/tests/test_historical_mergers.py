import hashlib
from datetime import date
from types import SimpleNamespace

import pytest

from test_dated_research import vendor  # noqa: F401
from aperture.domain import ResearchError
from aperture.historical_mergers import MERGERS, candidates, apply_missing


@pytest.mark.parametrize("symbol", list(MERGERS))
def test_missing_completed_terms_require_exact_listing_and_primary_source(
    monkeypatch, symbol
):
    proof = MERGERS[symbol]
    raw = b"Independent completed-merger source fixture"
    monkeypatch.setitem(proof, "sha256", hashlib.sha256(raw).hexdigest())
    calls = []
    api = SimpleNamespace(document=lambda url: calls.append(url) or raw)
    listings = {symbol: {proof["listing_id"]: {}}}
    params = ([symbol], listings, [], date(2016, 1, 4), date(2026, 11, 6), api)
    event = candidates(*params)[0]
    assert event["cash"] == proof["cash"] and event["ratio"] == proof["ratio"]
    assert event["target"] == proof["target"] and event["source_record"] is None
    assert event["reviewed_evidence"]["url"] == proof["url"]
    assert calls == [proof["url"]]
    issues = []
    append = lambda *v: issues.append(v)
    bars = {symbol: {date.fromisoformat(proof["last_quote"]): None}}
    assert apply_missing([], [event], bars, append) == [event]
    assert apply_missing([event], [event], bars, append) == [event]
    # A current/reused listing or a new native event cannot inherit this exception.
    assert (
        candidates([symbol], {symbol: {"other": {}}}, [], params[3], params[4], api)
        == []
    )
    assert (
        candidates(
            [symbol],
            listings,
            [
                {
                    "kind": "stock_mergers",
                    "acquiree_symbol": symbol,
                    "unpriced_consideration": "CVR",
                }
            ],
            params[3],
            params[4],
            api,
        )
        == []
    )
    assert candidates([symbol], listings, [], date(2026, 1, 1), params[4], api) == []
    assert calls == [proof["url"]]
    bad = SimpleNamespace(document=lambda url: b"Changed economic terms")
    with pytest.raises(ResearchError, match="fingerprint changed"):
        candidates(*params[:-1], bad)
    # Contradictory quote lifetimes cannot be hidden by the source annotation.
    issues.clear()
    bars[symbol][date(2026, 11, 6)] = None
    assert apply_missing([event], [event], bars, append) == []
    assert "conflicts" in issues[0][2]


def test_normal_update_keeps_reviewed_historical_merger_outside_overlap(
    vendor,  # noqa: F811
    monkeypatch,
):
    from aperture.research_data import download
    from test_dated_research import payload

    store, api, state = vendor
    symbol, proof = "EVHC", MERGERS["EVHC"]
    raw = b"Completed cash acquisition fixture"
    monkeypatch.setitem(proof, "sha256", hashlib.sha256(raw).hexdigest())
    state["latest"] = date(2018, 10, 25)
    original_get, original_pages = api.get, api.pages

    def get(*a, **kw):
        return original_get(*a, **kw) + [
            dict(
                symbol=symbol,
                id=proof["listing_id"],
                name="Envision Healthcare",
                exchange="NYSE",
                **{"class": "us_equity"},
            )
        ]

    def pages(*a, **kw):
        result = original_pages(*a, **kw)
        for page in result:
            if "bars" in page and symbol in page["bars"]:
                page["bars"][symbol] = [
                    r
                    for r in page["bars"][symbol]
                    if r["t"][:10] <= proof["last_quote"]
                ]
        return result

    api.get, api.pages = get, pages
    api.document = lambda url: raw
    first = download(store, payload("2018-10-25", [symbol]), lambda *a: None, api)
    old = store.dataset(first["id"])
    event = next(e for e in old.metadata["corporate_actions"] if e["source"] == symbol)
    assert event["cash"] == "46" and event["effective"] == "2018-10-11"
    state["latest"] = date(2018, 11, 2)
    new = download(
        store, payload("2018-11-02", [symbol]), lambda *a: None, api, base=old
    )
    after = store.dataset(new["id"])
    assert [
        e for e in after.metadata["corporate_actions"] if e["source"] == symbol
    ] == [event]
    assert after.bars[symbol] == old.bars[symbol]
    assert (
        store.dataset(old.id).metadata["corporate_actions"]
        == old.metadata["corporate_actions"]
    )
