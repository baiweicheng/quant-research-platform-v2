from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx

from aperture.annual_refresh import companyfacts
from aperture.config import Settings
from aperture.providers import Provider
from aperture.store import Store


def test_annual_changes_force_and_periodic_revalidation_while_quarters_reuse(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("aperture.providers.time.sleep", lambda _: None)
    calls = []

    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"cik": 1, "capture": len(calls)})

    store = Store(tmp_path / "annual.sqlite3")
    api = Provider(
        store,
        httpx.Client(transport=httpx.MockTransport(handle)),
        Settings(sec_agent="Fixture test@example.com"),
    )
    submissions = {
        "cik": 1,
        "entityType": "operating",
        "filings": {
            "recent": {
                "form": ["10-K"],
                "accessionNumber": ["0000000001-23-000001"],
                "filingDate": ["2023-02-10"],
                "reportDate": ["2022-12-31"],
                "primaryDocument": ["annual.htm"],
            }
        },
    }
    first = companyfacts(api, "0000000001", submissions)
    assert companyfacts(api, "0000000001", submissions) == first and len(calls) == 1
    quarterly = deepcopy(submissions)
    values = {
        "form": "10-Q",
        "accessionNumber": "0000000001-23-000002",
        "filingDate": "2023-05-10",
        "reportDate": "2023-03-31",
        "primaryDocument": "quarter.htm",
    }
    for key, value in values.items():
        quarterly["filings"]["recent"][key].insert(0, value)
    assert companyfacts(api, "0000000001", quarterly) == first and len(calls) == 1
    amended = deepcopy(submissions)
    amended["filings"]["recent"]["form"][0] = "10-K/A"
    amended["filings"]["recent"]["accessionNumber"][0] = "0000000001-23-000003"
    assert companyfacts(api, "0000000001", amended)["capture"] == 2
    assert companyfacts(api, "0000000001", amended, force=True)["capture"] == 3
    with store.connect() as db:
        db.execute(
            "update observations set fetched_at=?",
            ((datetime.now(timezone.utc) - timedelta(days=31)).isoformat(),),
        )
    assert companyfacts(api, "0000000001", amended)["capture"] == 4
    assert companyfacts(api, "0000000001", {"cik": 1})["capture"] == 5
    assert companyfacts(api, "0000000001", {"cik": 1})["capture"] == 6
    incomplete = deepcopy(submissions)
    incomplete["filings"]["recent"]["primaryDocument"] = []
    assert companyfacts(api, "0000000001", incomplete)["capture"] == 7
    assert companyfacts(api, "0000000001", incomplete)["capture"] == 8
    incomplete["filings"]["recent"]["primaryDocument"] = None
    assert companyfacts(api, "0000000001", incomplete)["capture"] == 9
    assert companyfacts(api, "0000000001", incomplete)["capture"] == 10
    assert api.annual_cache_stats == {"reused": 2, "downloaded": 10}


def test_unexpected_capture_replacement_cannot_reuse_stale_validation(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("aperture.providers.time.sleep", lambda _: None)
    calls = []

    def handle(request):
        calls.append(1)
        return httpx.Response(200, json={"cik": 1})

    store = Store(tmp_path / "changed.sqlite3")
    api = Provider(
        store,
        httpx.Client(transport=httpx.MockTransport(handle)),
        Settings(sec_agent="Fixture test@example.com"),
    )
    subs = {"cik": 1, "filings": {"recent": {"form": [], "accessionNumber": []}}}
    companyfacts(api, "0000000001", subs)
    store.observe(
        "sec",
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json?{}",
        b'{"cik": 99}',
    )
    assert companyfacts(api, "0000000001", subs) == {"cik": 1}
    assert len(calls) == 2


def test_wrong_issuer_response_is_not_authorized_for_future_cache_reuse(
    tmp_path, monkeypatch
):
    import pytest
    from aperture.domain import ResearchError

    monkeypatch.setattr("aperture.providers.time.sleep", lambda _: None)
    calls = []

    def handle(request):
        calls.append(1)
        return httpx.Response(200, json={"cik": 2 if len(calls) == 1 else 1})

    store = Store(tmp_path / "identity.sqlite3")
    api = Provider(
        store,
        httpx.Client(transport=httpx.MockTransport(handle)),
        Settings(sec_agent="Fixture test@example.com"),
    )
    subs = {"cik": 1, "filings": {"recent": {"form": [], "accessionNumber": []}}}
    with pytest.raises(ResearchError, match="identity mismatch"):
        companyfacts(api, "0000000001", subs)
    assert store.preference("annual-facts-v1:0000000001") is None
    assert companyfacts(api, "0000000001", subs) == {"cik": 1}
    assert len(calls) == 2
