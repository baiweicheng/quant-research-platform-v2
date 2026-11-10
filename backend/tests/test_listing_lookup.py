from collections import defaultdict

import pytest

from aperture.domain import ResearchError
from aperture.providers import ResourceMissing
from aperture.security_identity import supplement_listing_directory
from test_dated_research import vendor, payload  # noqa: F401


class API:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, provider, url, ttl):
        self.calls.append((provider, url, ttl))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_missing_bulk_listing_is_recovered_without_overwriting_collision():
    asset = dict(symbol="OLD", id="old-id", name="Old issuer", exchange="NYSE")
    api = API(asset)
    candidates = defaultdict(dict, CLASH={"a": {}, "b": {}})
    audit = supplement_listing_directory(api, candidates, ["CLASH", "OLD"])
    assert candidates["CLASH"] == {"a": {}, "b": {}}
    assert candidates["OLD"] == {"old-id": asset}
    assert audit == {"OLD": {"status": "found", "listing_id": "old-id"}}
    assert len(api.calls) == 1 and api.calls[0][1].endswith("/OLD")


def test_missing_individual_listing_remains_unresolved():
    api = API(ResourceMissing("not found"))
    candidates = defaultdict(dict)
    assert supplement_listing_directory(api, candidates, ["OLD"]) == {
        "OLD": {"status": "not_found"}
    }
    assert not candidates.get("OLD")


@pytest.mark.parametrize(
    "response", [[], {}, {"symbol": "NEW", "id": "x", "name": "New"}]
)
def test_wrong_or_malformed_listing_cannot_certify_old_symbol(response):
    with pytest.raises(ResearchError, match="inconsistent listing"):
        supplement_listing_directory(API(response), defaultdict(dict), ["OLD"])


def test_permission_and_transport_errors_are_not_treated_as_absent_assets():
    with pytest.raises(ResearchError, match="unreachable"):
        supplement_listing_directory(
            API(ResearchError("unreachable")), defaultdict(dict), ["OLD"]
        )


@pytest.mark.parametrize("fund", [False, True])
def test_download_uses_individual_metadata_and_keeps_fund_gate(
    vendor,  # noqa: F811
    fund,
    monkeypatch,
):
    from aperture.research_data import download
    from aperture import historical_mergers

    store, api, _ = vendor
    get = api.get

    def directory(provider, url, params=None, ttl=300):
        rows = get(provider, url, params, ttl)
        if url.endswith("/assets/ABC"):
            asset = next(r for r in rows if r["symbol"] == "ABC")
            return {**asset, "name": "Unrelated ETF" if fund else "ABC Corporation"}
        return [r for r in rows if r["symbol"] != "ABC"]

    api.get = directory

    def merger_candidates(names, listings, *args):
        # Recovery must precede reviewed missing-merger selection; otherwise
        # omitted DISCK-like source listings never acquire their recipient path.
        assert set(listings["ABC"]) == {"ABC-v1"}
        return []

    monkeypatch.setattr(historical_mergers, "candidates", merger_candidates)
    result = download(store, payload(), lambda *a: None, api)
    ds = store.dataset(result["id"])
    issues = [i for i in ds.metadata["input_issues"] if i["kind"] == "identity"]
    assert bool(issues) is fund
    if fund:
        assert "fund" in issues[0]["reason"]
    assert ds.metadata["identity_resolution"]["ABC"]["individual_lookup"] == {
        "status": "found",
        "listing_id": "ABC-v1",
    }


@pytest.mark.parametrize("fund", [False, True])
def test_update_revalidates_only_exact_missing_directory_issue(
    vendor,  # noqa: F811
    monkeypatch,
    fund,
):
    from datetime import date
    from dataclasses import replace
    from aperture.research_data import download, MISSING_DIRECTORY

    store, api, state = vendor
    get = api.get
    available = False

    def directory(provider, url, params=None, ttl=300):
        rows = get(provider, url, params, ttl)
        if url.endswith("/assets/ABC"):
            if not available:
                raise ResourceMissing("not found")
            asset = next(r for r in rows if r["symbol"] == "ABC")
            return {**asset, "name": "Unrelated ETF" if fund else "ABC Corporation"}
        return [r for r in rows if r["symbol"] != "ABC"]

    api.get = directory
    first = download(store, payload(), lambda *a: None, api)
    old = store.dataset(first["id"])
    assert any(i["reason"] == MISSING_DIRECTORY for i in old.metadata["input_issues"])
    unrelated = {
        "symbol": "ABC",
        "start": "2016-02-01",
        "end": "2016-02-01",
        "kind": "identity",
        "reason": "Separate issuer conflict",
    }
    old = replace(
        old,
        metadata={
            **old.metadata,
            "input_issues": [*old.metadata["input_issues"], unrelated],
        },
    )
    available = True
    state["latest"] = date(2017, 2, 10)
    fresh = download(store, payload("2017-02-10"), lambda *a: None, api, base=old)
    new = store.dataset(fresh["id"])
    assert (
        any(i["reason"] == MISSING_DIRECTORY for i in new.metadata["input_issues"])
        is fund
    )
    assert unrelated in new.metadata["input_issues"]
    assert bool(new.metadata["historical_identity_revalidation"]) is (not fund)
    assert tuple(b for b in new.bars["ABC"] if b.session < date(2017, 1, 24)) == tuple(
        b for b in old.bars["ABC"] if b.session < date(2017, 1, 24)
    )
    assert any(
        i["reason"] == MISSING_DIRECTORY
        for i in store.dataset(first["id"]).metadata["input_issues"]
    )
