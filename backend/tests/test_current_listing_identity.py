from collections import defaultdict
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from aperture.domain import ResearchError
from aperture.security_identity import reconcile_current_listings


def context():
    listing = {
        "symbol": "NEW",
        "name": "New Company common stock",
        "exchange": "NYSE",
        "class": "us_equity",
    }
    candidates = defaultdict(
        dict,
        NEW={
            "inactive": {**listing, "id": "inactive", "status": "inactive"},
            "active": {**listing, "id": "active", "status": "active"},
        },
    )
    members = {"NEW": {"date_added": "2020-06-01"}}
    first = {"NEW": date(2020, 6, 1)}
    api = SimpleNamespace(get=lambda *a, **kw: deepcopy(candidates["NEW"]["active"]))
    return api, candidates, members, first


def test_identical_duplicate_provider_records_require_current_admission_context():
    api, candidates, members, first = context()
    audit = reconcile_current_listings(api, candidates, members, first)
    assert list(candidates["NEW"]) == ["active"]
    assert audit["NEW"]["all_candidate_ids"] == ["active", "inactive"]
    assert audit["NEW"]["selected_id"] == "active"


@pytest.mark.parametrize(
    "mutation",
    [
        "old_member",
        "not_current",
        "different_name",
        "different_class",
        "two_active",
        "unknown_date",
    ],
)
def test_old_or_ambiguous_cohorts_are_not_resolved_by_today_lookup(mutation):
    api, candidates, members, first = context()
    if mutation == "old_member":
        first["NEW"] = date(2019, 1, 1)
    elif mutation == "not_current":
        members = {}
    elif mutation == "different_name":
        candidates["NEW"]["inactive"]["name"] = "Unrelated old issuer"
    elif mutation == "different_class":
        candidates["NEW"]["inactive"]["class"] = "fund"
    elif mutation == "two_active":
        candidates["NEW"]["inactive"]["status"] = "active"
    elif mutation == "unknown_date":
        members["NEW"]["date_added"] = None
    api.get = lambda *a, **kw: pytest.fail("No lookup is justified for this cohort")
    assert reconcile_current_listings(api, candidates, members, first) == {}
    assert len(candidates["NEW"]) == 2


@pytest.mark.parametrize("change", [{"id": "wrong"}, {"status": "inactive"}])
def test_lookup_disagreement_cannot_replace_bulk_candidates(change):
    api, candidates, members, first = context()
    api.get = lambda *a, **kw: {**candidates["NEW"]["active"], **change}
    with pytest.raises(ResearchError, match="disagree"):
        reconcile_current_listings(api, candidates, members, first)
    assert len(candidates["NEW"]) == 2


def test_current_duplicate_revalidation_is_an_immutable_ordinary_update(
    tmp_path, monkeypatch
):

    # Use an ordinary captured-price fixture with an independent directory.
    from aperture.store import Store
    from aperture.research_data import download, MULTIPLE_DIRECTORY
    from aperture import membership, security_identity, calendar
    from sector_fixtures import stub_sectors
    from test_dated_research import payload

    stub_sectors(monkeypatch)
    monkeypatch.setattr(calendar, "latest_complete", lambda *a: date(2017, 2, 10))
    store = Store(tmp_path / "duplicate.sqlite3")
    history = {
        "kind": "combined",
        "additional_symbols": [],
        "current": {
            "members": [
                {"symbol": "NEW", "date_added": "2016-01-04", "sector": "Industrials"}
            ]
        },
        "historical": {
            "rosters": [{"effective": "2016-01-04", "symbols": ["NEW"]}],
            "coverage_start": "2016-01-04",
            "coverage_end": "2017-02-10",
        },
    }
    monkeypatch.setattr(
        membership, "resolve", lambda *a: (["NEW", "SPY"], deepcopy(history), {})
    )
    base = {
        "symbol": "NEW",
        "name": "New Company",
        "exchange": "NYSE",
        "class": "us_equity",
    }

    class Vendor:
        observations = []

        def get(self, provider, url, params=None, ttl=300):
            if url.endswith("/assets/NEW"):
                return {**base, "id": "active", "status": "active"}
            status = params["status"]
            return [
                {**base, "id": status, "status": status},
                {
                    "symbol": "SPY",
                    "id": "spy",
                    "name": "SPY",
                    "exchange": "NYSE",
                    "class": "us_equity",
                    "status": status,
                },
            ]

        def pages(self, path, query, key):
            if key == "corporate_actions":
                return [{"corporate_actions": {}}]
            days = calendar.sessions(
                date.fromisoformat(query["start"][:10]),
                date.fromisoformat(query["end"][:10]),
            )
            return [
                {
                    "bars": {
                        s: [
                            {
                                "t": calendar.open_time(d).isoformat(),
                                "o": "100",
                                "h": "100",
                                "l": "100",
                                "c": "100",
                                "v": 1000,
                            }
                            for d in days
                        ]
                        for s in query["symbols"].split(",")
                    }
                }
            ]

    api = Vendor()
    reconcile = security_identity.reconcile_current_listings
    monkeypatch.setattr(security_identity, "reconcile_current_listings", lambda *a: {})
    first = download(store, payload("2017-02-03", ["NEW"]), lambda *a: None, api)
    old = store.dataset(first["id"])
    assert any(i["reason"] == MULTIPLE_DIRECTORY for i in old.metadata["input_issues"])
    monkeypatch.setattr(security_identity, "reconcile_current_listings", reconcile)
    new = store.dataset(
        download(store, payload("2017-02-10", ["NEW"]), lambda *a: None, api, base=old)[
            "id"
        ]
    )
    assert not any(
        i["reason"] == MULTIPLE_DIRECTORY for i in new.metadata["input_issues"]
    )
    assert any(
        i["reason"] == MULTIPLE_DIRECTORY
        for i in store.dataset(old.id).metadata["input_issues"]
    )
    assert new.metadata["identity_resolution"]["NEW"]["current_listing_resolution"][
        "all_candidate_ids"
    ] == ["active", "inactive"]
