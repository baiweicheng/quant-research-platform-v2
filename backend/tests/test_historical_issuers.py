import hashlib
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from aperture.domain import ResearchError
from aperture.historical_issuers import ISSUERS, VERSION, verify, mapping_evidence
from aperture.providers import ResourceMissing
from test_dated_research import vendor, payload  # noqa: F401
from test_fundamentals import dataset, FixtureProvider  # noqa: F401


@pytest.mark.parametrize("symbol", list(ISSUERS))
def test_exact_dated_filing_and_quote_vintage_are_required(symbol, monkeypatch):
    proof = ISSUERS[symbol]
    raw = b"Independent historical ticker and issuer cover fixture"
    monkeypatch.setitem(proof, "sha256", hashlib.sha256(raw).hexdigest())
    calls = []
    api = SimpleNamespace(document=lambda url: calls.append(url) or raw)
    result = verify(symbol, proof["quote_asof"], api)
    assert result == {"symbol": symbol, "version": VERSION, **proof}
    assert calls == [proof["url"]]
    assert verify(symbol, "2026-11-06", api) is None
    assert verify("UNREVIEWED", proof["quote_asof"], api) is None
    assert calls == [proof["url"]]
    api.document = lambda url: b"Changed issuer evidence"
    with pytest.raises(ResearchError, match="fingerprint changed"):
        verify(symbol, proof["quote_asof"], api)


def test_imported_or_stale_evidence_cannot_override_current_issuer():
    proof = {"symbol": "TMK", "version": VERSION, **ISSUERS["TMK"]}
    metadata = {
        "historical_issuer_evidence": {"TMK": proof},
        "identity_resolution": {"TMK": {"asof": proof["quote_asof"]}},
    }
    assert mapping_evidence(metadata, "TMK") == proof
    assert mapping_evidence({**metadata, "identity_resolution": {}}, "TMK") is None
    metadata["historical_issuer_evidence"]["TMK"] = {**proof, "cik": "0000000002"}
    assert mapping_evidence(metadata, "TMK") is None


@pytest.mark.parametrize("symbol", ["ARNC", "DWDP"])
def test_separation_issuer_mapping_requires_the_repaired_price_contract(symbol):
    proof = {"symbol": symbol, "version": VERSION, **ISSUERS[symbol]}
    metadata = {
        "historical_issuer_evidence": {symbol: proof},
        "identity_resolution": {symbol: {"asof": proof["quote_asof"]}},
        "normalizer_version": "dated-research-inputs-v7-native-date-reconciliation",
    }
    assert mapping_evidence(metadata, symbol) is None
    metadata["normalizer_version"] = proof["required_price_contract"]
    assert mapping_evidence(metadata, symbol) == proof


def test_primary_issuer_revalidation_preserves_old_quotes_and_other_blocks(
    vendor,  # noqa: F811
    monkeypatch,
):
    from aperture import membership
    from aperture.research_data import download, MISSING_DIRECTORY

    store, api, state = vendor
    audit = {
        "kind": "historical",
        "coverage_start": "2016-01-04",
        "coverage_end": "2017-02-10",
        "additional_symbols": [],
        "rosters": [
            {"effective": "2016-01-04", "symbols": ["ABC", "NEW"]},
            {"effective": "2017-02-04", "symbols": ["NEW"]},
        ],
    }
    monkeypatch.setattr(
        membership, "resolve", lambda *a: (["ABC", "NEW", "SPY"], audit, {})
    )
    get = api.get

    def directory(provider, url, params=None, ttl=300):
        if url.endswith("/assets/ABC"):
            raise ResourceMissing("No current listing")
        return [r for r in get(provider, url, params, ttl) if r["symbol"] != "ABC"]

    api.get = directory
    old = store.dataset(download(store, payload(), lambda *a: None, api)["id"])
    assert any(i["reason"] == MISSING_DIRECTORY for i in old.metadata["input_issues"])
    raw = b"ABC common listing, independently dated"
    proof = {
        **ISSUERS["TMK"],
        "cik": "0000000001",
        "quote_asof": "2017-02-03",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    monkeypatch.setitem(ISSUERS, "ABC", proof)
    api.document = lambda url: raw
    other = {
        "symbol": "ABC",
        "kind": "identity",
        "start": "2016-01-04",
        "end": "2017-02-03",
        "reason": "Separate unresolved action identity",
    }
    changed = replace(
        old,
        metadata={
            **old.metadata,
            "input_issues": [*old.metadata["input_issues"], other],
        },
    )
    state["latest"] = date(2017, 2, 10)
    new = store.dataset(
        download(store, payload("2017-02-10"), lambda *a: None, api, base=changed)["id"]
    )
    assert not any(
        i["reason"] == MISSING_DIRECTORY for i in new.metadata["input_issues"]
    )
    assert any(i["reason"] == other["reason"] for i in new.metadata["input_issues"])
    assert mapping_evidence(new.metadata, "ABC")["cik"] == "0000000001"
    assert (
        new.metadata["historical_identity_revalidation"][0]["issuer_evidence"]["url"]
        == proof["url"]
    )
    assert tuple(b for b in new.bars["ABC"] if b.session < date(2017, 1, 24)) == tuple(
        b for b in old.bars["ABC"] if b.session < date(2017, 1, 24)
    )
    assert any(
        i["reason"] == MISSING_DIRECTORY
        for i in store.dataset(old.id).metadata["input_issues"]
    )


def test_dated_issuer_loads_historical_financials_without_current_ticker_guess(
    dataset,  # noqa: F811
    tmp_path,
    monkeypatch,
):
    from aperture.store import Store
    from aperture.fundamentals import attach, as_of

    store = Store(tmp_path / "issuer.sqlite3")
    proof = {**ISSUERS["TMK"], "cik": "0000000001", "quote_asof": "2024-08-30"}
    monkeypatch.setitem(ISSUERS, "ABC", proof)
    evidence = {"symbol": "ABC", "version": VERSION, **proof}
    base = replace(
        dataset,
        fundamentals={},
        metadata={
            "historical_issuer_evidence": {"ABC": evidence},
            "identity_resolution": {"ABC": {"asof": proof["quote_asof"]}},
        },
    )
    store.save_dataset(base, b"Independent prices", [])

    class HistoricalProvider(FixtureProvider):
        def get(self, provider, url, **kwargs):
            if "tickers_exchange" in url:
                # The current ticker belongs to someone else; only the exact
                # reviewed historical quote context can select old issuer 1.
                return {"fields": ["cik", "ticker"], "data": [[2, "ABC"]]}
            assert "CIK0000000001" in url
            return super().get(provider, url, **kwargs)

    result = store.dataset(
        attach(store, base.id, lambda *a: None, HistoricalProvider())["id"]
    )
    assert result.fundamentals["ABC"] and all(
        r.cik == "0000000001" for r in result.fundamentals["ABC"]
    )
    assert as_of(result.fundamentals["ABC"], date(2023, 2, 10)) is None
    assert as_of(result.fundamentals["ABC"], date(2023, 2, 13)).eps == 4
    assert (
        result.metadata["fundamentals"]["coverage"][0]["historical_issuer_evidence"]
        == evidence
    )
