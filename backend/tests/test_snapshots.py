"""Snapshot isolation/storage and real ingestion updates with controlled vendors."""

import copy
import gzip
import hashlib
import json
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st

from aperture import calendar, membership, membership_sources
from aperture.api import create_app
from aperture.backtest import run
from aperture.config import Settings
from aperture.dataset_updates import update
from aperture.domain import Policy, ResearchError
from aperture.fundamentals import attach, as_of
from aperture.providers import Provider, download_market
from aperture.store import Store, decode, encode
from aperture.storage_maintenance import compact
from aperture.worker import process_one
from test_fundamentals import source, ACC
from test_membership import html


def chunks(store, identifier):
    with store.connect() as db:
        body = decode(
            db.execute(
                "SELECT body FROM datasets WHERE id=?", (identifier,)
            ).fetchone()[0]
        )
    return body


def sizes(store):
    with store.connect() as db:
        return db.execute(
            "SELECT count(*), coalesce(sum(length(body)),0) FROM content_blobs"
        ).fetchone()


@pytest.fixture
def vendor(tmp_path, monkeypatch):
    store = Store(tmp_path / "snapshots.sqlite3")
    state = {
        "latest": date(2024, 5, 6),
        "amended": False,
        "failed": False,
        "missing": None,
        "identity": "ABC-id",
        "corrected": False,
    }
    calls = []
    monkeypatch.setattr(calendar, "latest_complete", lambda *a: state["latest"])
    monkeypatch.setattr("aperture.providers.time.sleep", lambda *a: None)

    def handler(request):
        calls.append(request)
        if state["failed"]:
            return httpx.Response(503)
        path = request.url.path
        if "/assets/" in path:
            symbol = path.rsplit("/", 1)[1]
            return httpx.Response(
                200,
                json={
                    "id": state["identity"] if symbol == "ABC" else symbol + "-id",
                    "symbol": symbol,
                    "class": "us_equity",
                    "exchange": "NASDAQ",
                    "status": "active",
                    "name": symbol + " Common Stock",
                },
            )
        if path.endswith("corporate-actions"):
            events = {}
            if state["corrected"]:
                events = {
                    "cash_dividends": [
                        {
                            "id": "cash",
                            "symbol": "ABC",
                            "ex_date": "2024-05-10",
                            "payable_date": "2024-05-20",
                            "rate": "0.5",
                        }
                    ],
                    "forward_splits": [
                        {
                            "id": "split",
                            "symbol": "ABC",
                            "ex_date": "2024-05-09",
                            "old_rate": 1,
                            "new_rate": 2,
                        }
                    ],
                }
            return httpx.Response(200, json={"corporate_actions": events})
        if path.endswith("/bars"):
            first = date.fromisoformat(request.url.params["start"][:10])
            last = date.fromisoformat(request.url.params["end"][:10])
            body = {}
            for symbol in request.url.params["symbols"].split(","):
                rows = []
                for day in calendar.sessions(first, last):
                    if (symbol, str(day)) == state["missing"]:
                        continue
                    price = D(100)
                    if symbol == "ABC" and state["corrected"]:
                        if day == date(2024, 4, 30):
                            price = D(102)
                        if day >= date(2024, 5, 9):
                            price /= 2
                        elif request.url.params["adjustment"] == "split":
                            price /= 2
                    rows.append(
                        {
                            "t": calendar.open_time(day).isoformat(),
                            **dict.fromkeys(("o", "h", "l", "c"), str(price)),
                            "v": 10000,
                        }
                    )
                body[symbol] = rows
            return httpx.Response(200, json={"bars": body})
        if path.endswith("company_tickers_exchange.json"):
            return httpx.Response(
                200, json={"fields": ["cik", "ticker"], "data": [[1, "ABC"]]}
            )
        if "/submissions/" in path:
            return httpx.Response(
                200, json={"cik": 1, "tickers": ["ABC"], "entityType": "operating"}
            )
        if "/companyfacts/" in path:
            company = source()
            if state["amended"]:
                for facts in company["facts"]["us-gaap"].values():
                    for items in facts["units"].values():
                        items.append(
                            {
                                **items[0],
                                "val": items[0]["val"] * 2,
                                "accn": "0000000001-24-000002",
                                "filed": "2024-05-10",
                                "form": "10-K/A",
                            }
                        )
            return httpx.Response(200, json=company)
        raise AssertionError(path)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = Provider(store, client, Settings("test", "test", "QA qa@example.com"))
    initial = download_market(
        store,
        {
            "name": "Research",
            "symbols": ["ABC"],
            "start": "2024-01-02",
            "end": "2024-05-06",
        },
        lambda *a: None,
        provider,
    )
    yield store, provider, state, calls, initial
    client.close()


def test_incremental_prices_actions_restart_and_unchanged_parent(vendor):
    store, api, state, calls, initial = vendor
    before = store.dataset(initial["id"])
    count, byte_count = sizes(store)
    old_chunks = set(chunks(store, before.id)["bar_chunks"])
    state.update(latest=date(2024, 5, 13), corrected=True)
    calls.clear()
    saved = update(store, before.id, lambda *a: None, api)
    after = Store(store.path).dataset(saved["id"])
    assert Store(store.path).dataset(before.id) == before
    assert after.id != before.id and after.revision == before.revision + 1
    assert after.metadata["update"]["parent_digest"] == before.digest
    assert after.metadata["unavailable_symbols"] == {}
    a = {b.session: b for b in after.bars["ABC"]}
    assert a[date(2024, 4, 30)].close == 102
    assert a[date(2024, 5, 9)].split == 2
    assert a[date(2024, 5, 10)].dividend == D("0.5")
    assert a[date(2024, 5, 10)].pay_date == date(2024, 5, 20)
    assert all(
        b.close == 100 and b.split == 1 and b.dividend == 0 for b in before.bars["ABC"]
    )
    assert len(a) == len(calendar.sessions(date(2024, 1, 2), state["latest"]))
    assert all(
        r.url.params["start"] == "2024-04-26"
        for r in calls
        if r.url.path.endswith("/bars")
    )
    new_chunks = set(chunks(store, after.id)["bar_chunks"])
    assert len(old_chunks & new_chunks) >= 6  # Jan–Mar unchanged, both symbols.
    assert sizes(store)[0] - count < count
    assert sizes(store)[1] - byte_count < byte_count
    # A correction/action removal in the overlap replaces, rather than adds to,
    # prior actions, and cannot mutate either of the preceding vintages.
    state["corrected"] = False
    with store.connect() as db:
        db.execute("DELETE FROM observations")
    newest = update(store, after.id, lambda *a: None, api)
    assert all(
        b.dividend == 0 and b.split == 1
        for b in store.dataset(newest["id"]).bars["ABC"]
    )
    assert store.dataset(after.id) == after


@pytest.mark.parametrize("failure", ["identity", "failed"])
def test_failed_update_does_not_publish_or_mutate_snapshots(vendor, failure):
    store, api, state, calls, initial = vendor
    original = store.dataset(initial["id"])
    old_count = len(store.datasets())
    state["latest"] = date(2024, 5, 13)
    state[failure] = "different-issuer" if failure == "identity" else True
    with store.connect() as db:
        db.execute("DELETE FROM observations")
    with pytest.raises(ResearchError):
        update(store, original.id, lambda *a: None, api)
    assert len(store.datasets()) == old_count
    assert Store(store.path).dataset(original.id) == original


def test_missing_revised_bar_is_not_filled_with_stale_data(vendor):
    store, api, state, calls, initial = vendor
    original = store.dataset(initial["id"])
    state.update(latest=date(2024, 5, 13), missing=("ABC", "2024-05-03"))
    saved = update(store, original.id, lambda *a: None, api)
    assert date(2024, 5, 3) not in {
        b.session for b in store.dataset(saved["id"]).bars["ABC"]
    }
    assert date(2024, 5, 3) in {
        b.session for b in store.dataset(original.id).bars["ABC"]
    }
    assert (
        next(r for r in saved["metadata"]["coverage"] if r["symbol"] == "ABC")[
            "missing_count"
        ]
        == 1
    )


def test_sec_amendment_gets_new_price_parent_and_preserves_prior_filings(vendor):
    store, api, state, calls, initial = vendor
    first = attach(store, initial["id"], lambda *a: None, api)
    original = store.dataset(first["id"])
    original_chunks = chunks(store, original.id)
    assert original_chunks["bar_chunks"] == chunks(store, initial["id"])["bar_chunks"]
    state.update(latest=date(2024, 5, 13), amended=True)
    new = update(store, original.id, lambda *a: None, api)
    updated = Store(store.path).dataset(new["id"])
    assert updated.metadata["price_dataset_id"] != initial["id"]
    assert updated.metadata["membership"] == original.metadata["membership"]
    assert len(updated.fundamentals["ABC"]) == 2
    assert as_of(updated.fundamentals["ABC"], date(2024, 5, 9)).accession == ACC
    assert as_of(updated.fundamentals["ABC"], date(2024, 5, 14)).accession.endswith(
        "24-000002"
    )
    assert Store(store.path).dataset(original.id) == original
    assert (
        chunks(store, new["id"])["bar_chunks"]
        == chunks(store, updated.metadata["price_dataset_id"])["bar_chunks"]
    )


def test_legacy_inline_conversion_and_zero_bar_names_preserve_exact_data(vendor):
    store, api, state, calls, initial = vendor
    original = replace(
        store.dataset(initial["id"]),
        id="legacy",
        digest="legacy",
        bars={**store.dataset(initial["id"]).bars, "EMPTY": ()},
    )
    store.save_dataset(original, b"original", [])
    with store.connect() as db:
        body = chunks(store, original.id)
        body["bars"] = [
            bar
            for key in body.pop("bar_chunks")
            for bar in json.loads(store._read_blob(db, key))
        ]
        body["fundamentals"] = {}
        body.pop("fundamental_chunks")
        db.execute("UPDATE datasets SET body=? WHERE id=?", (encode(body), original.id))
    assert store.dataset(original.id) == original
    store.share_dataset_storage(original.id)
    assert Store(store.path).dataset(original.id) == original
    assert "EMPTY" in store.dataset(original.id).bars
    assert not store.dataset(original.id).bars["EMPTY"]


def test_observations_share_payload_but_keep_capture_identity_and_time(vendor):
    store, api, state, calls, initial = vendor
    raw = b'{"public_fact": 1}'
    first = store.observe("sec", "one", raw)
    second = store.observe("sec", "two", raw)
    assert first != second
    digest = hashlib.sha256(raw).hexdigest()
    with store.connect() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM content_blobs WHERE digest=?", (digest,)
            ).fetchone()[0]
            == 1
        )
        assert (
            len(
                {
                    r[0]
                    for r in db.execute(
                        "SELECT body FROM observations WHERE digest=?", (digest,)
                    )
                }
            )
            == 1
        )
    assert Store(store.path).cached("sec", "two", 100)[0] == {"public_fact": 1}


def test_update_api_headers_dedup_and_worker_completion(vendor, monkeypatch):
    store, api, state, calls, initial = vendor
    monkeypatch.setattr(
        "aperture.api.settings", lambda: Settings("test", "test", "qa@example.com")
    )
    monkeypatch.setattr("aperture.dataset_updates.Provider", lambda *a: api)
    state["latest"] = date(2024, 5, 13)
    app = create_app(store.path)
    monkeypatch.setattr(
        app.state.store,
        "dataset",
        lambda *a: (_ for _ in ()).throw(
            AssertionError("Queueing must not load full price history")
        ),
    )
    with TestClient(app) as client:
        path = f"/api/datasets/{initial['id']}/update"
        assert client.post(path, json={}).status_code == 403
        one = client.post(path, json={}, headers={"X-Aperture-Client": "1"})
        two = client.post(path, json={}, headers={"X-Aperture-Client": "1"})
        assert one.status_code == two.status_code == 202
        assert one.json()["id"] == two.json()["id"]
    assert process_one(store)
    assert store.jobs()[0]["state"] == "complete"
    assert "new snapshot" in store.jobs()[0]["message"]


def test_primary_timeline_effective_dates_transient_members_and_verified_tail(
    monkeypatch,
):
    monkeypatch.setattr(membership_sources, "SYMBOL_CHANGES", [])
    monkeypatch.setattr(calendar, "latest_complete", lambda *a: date(2024, 5, 13))
    names = [f"S{i:03}" for i in range(503)]
    rosters = [
        {"effective": "2024-01-02", "symbols": names},
        {"effective": "2024-05-01", "symbols": names},
    ]

    def table(day, added, removed):
        return (
            "<table>"
            + "".join(
                f"<tr><td>{day}</td><td>S&amp;P 500</td><td>{action}</td><td>Company</td><td>{symbol}</td><td>Sector</td><td></td></tr>"
                for action, symbol in [("Addition", added), ("Deletion", removed)]
            )
            + "</table>"
        )

    url = "https://press.spglobal.com/2024-05-03-Changes-S-P-500"
    bodies = {
        membership.CURRENT_URL: html(names),
        membership_sources.PRESS_URL
        + "&o=0": f'<a href="{url}">Release</a><a href="https://press.spglobal.com/2024-03-01-Earlier">Older</a>',
        url: table("May 8, 2024", "NEW", "S000")
        + table("May 9, 2024", "S000", "NEW")
        + table("May 20, 2024", "FUTURE", "S000"),
    }

    def fetch(url):
        return httpx.Response(200, text=bodies[url])

    rows, meta, raw = membership_sources.extend(
        rosters, "2024-05-13T22:00:00+00:00", fetch
    )
    audit = {**meta, "rosters": rows, "coverage_start": "2024-01-02"}
    assert "NEW" in membership.historical_names(audit, date(2024, 5, 8))
    assert "NEW" not in membership.historical_names(audit, date(2024, 5, 9))
    assert not any("FUTURE" in r["symbols"] for r in rows)
    assert (
        meta["last_change"] == "2024-05-09" and meta["verified_through"] == "2024-05-13"
    )
    assert len(meta["events"]) == 4
    assert "S000" in membership.historical_names(audit, date(2024, 5, 13))
    bodies[membership.CURRENT_URL] = html(names[1:] + ["UNKNOWN"])
    with pytest.raises(ResearchError, match="do not reconcile"):
        membership_sources.extend(rosters, "2024-05-13T22:00:00+00:00", fetch)
    bodies[membership_sources.PRESS_URL + "&o=0"] = (
        '<a href="https://press.spglobal.com/2024-05-03-Changes-S-P-500">Recent only</a>'
    )
    with pytest.raises(ResearchError, match="500 releases"):
        membership_sources.extend(
            rosters,
            "2024-05-13T22:00:00+00:00",
            lambda u: (
                httpx.Response(200, text=bodies[membership_sources.PRESS_URL + "&o=0"])
                if u.startswith(membership_sources.PRESS_URL)
                else fetch(u)
            ),
        )


@given(st.integers(min_value=1, max_value=12))
def test_primary_dates_distinguish_effective_month_from_publication(month):
    assert (
        membership_sources.effective_day(date(2024, month, 4).strftime("%B %d, %Y"))
        == f"2024-{month:02}-04"
    )


def test_many_snapshots_share_unchanged_blocks_and_detect_missing_storage(vendor):
    store, api, state, calls, initial = vendor
    base = store.dataset(initial["id"])
    old_count, old_bytes = sizes(store)
    for i in range(20):
        stock = list(base.bars["ABC"])
        stock[-1] = replace(stock[-1], close=D(100) + D(i) / 10, high=D(105))
        snapshot = replace(
            base, id=f"v{i}", digest=f"v{i}", bars={**base.bars, "ABC": tuple(stock)}
        )
        store.save_dataset(snapshot, b"small lineage record", [])
        assert Store(store.path).dataset(snapshot.id) == snapshot
        assert store.dataset(base.id) == base
    count, byte_count = sizes(store)
    assert count - old_count == 20  # One changed symbol/month per vintage.
    assert (
        byte_count - old_bytes < old_bytes * 4
    )  # Twenty logical copies, far below twenty baselines.
    with store.connect() as db:
        db.execute(
            "DELETE FROM content_blobs WHERE digest=?",
            (chunks(store, "v19")["bar_chunks"][0],),
        )
    with pytest.raises(ResearchError, match="shared snapshot block is missing"):
        store.dataset("v19")


def test_compaction_preserves_legacy_observations_every_dataset_and_is_idempotent(
    vendor,
):
    store, api, state, calls, initial = vendor
    first = store.dataset(initial["id"])
    second = replace(first, id="duplicate", digest="different-source")
    store.save_dataset(second, b"second source", [])
    raw = b'{"legacy":true}'
    digest = hashlib.sha256(raw).hexdigest()
    with store.connect() as db:
        for i in range(3):
            db.execute(
                "INSERT INTO observations VALUES (?,?,?,?,?,?)",
                (
                    f"legacy-{i}",
                    "sec",
                    f"legacy-{i}",
                    "2024-01-01T00:00:00+00:00",
                    digest,
                    gzip.compress(raw),
                ),
            )
    result = compact(store)
    assert result["datasets"] == 2
    assert Store(store.path).dataset(first.id) == first
    assert Store(store.path).dataset(second.id) == second
    before = tuple(sizes(store))
    compact(Store(store.path))
    assert tuple(sizes(store)) == before
    with store.connect() as db:
        assert (
            db.execute(
                "SELECT count(distinct body) FROM observations WHERE digest=?",
                (digest,),
            ).fetchone()[0]
            == 1
        )
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    import fcntl

    with store.path.with_suffix(".worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ResearchError, match="worker is still running"):
            compact(store)
    store.enqueue("practice", {})
    with pytest.raises(ResearchError, match="Finish background"):
        compact(store)


def test_snapshot_failure_rolls_back_new_blocks(vendor):
    import sqlite3

    store, api, state, calls, initial = vendor
    original = store.dataset(initial["id"])
    before = tuple(sizes(store))
    with pytest.raises(sqlite3.IntegrityError):
        store.save_dataset(
            replace(
                original,
                digest="conflicting-id",
                bars={
                    "NEW": tuple(replace(b, symbol="NEW") for b in original.bars["ABC"])
                },
            ),
            b"input",
            [],
        )
    assert tuple(sizes(store)) == before
    assert store.dataset(original.id) == original


def test_membership_update_full_backfills_newcomer_and_preserves_approvals(
    vendor, monkeypatch
):
    store, api, state, calls, initial = vendor
    old = store.dataset(initial["id"])
    audit = {
        "kind": "combined",
        "mode": "sp500",
        "additional_symbols": [],
        "current": {
            "members": [{"symbol": "ABC", "date_added": "2024-01-02"}],
            "coverage_start": "2024-05-06",
        },
        "historical": {
            "coverage_start": "2024-01-02",
            "coverage_end": "2024-05-06",
            "rosters": [{"effective": "2024-01-02", "symbols": ["ABC"]}],
        },
    }
    indexed = replace(
        old,
        id="indexed",
        digest="indexed",
        metadata={
            **old.metadata,
            "membership": audit,
            "unavailable_symbols": {"ABC": "Earlier identity issue"},
        },
    )
    store.save_dataset(indexed, b"indexed", [])
    newer = copy.deepcopy(audit)
    newer["current"]["members"].append({"symbol": "NEW", "date_added": "2024-05-09"})
    newer["historical"]["coverage_end"] = "2024-05-13"
    newer["historical"]["rosters"].append(
        {"effective": "2024-05-09", "symbols": ["NEW"]}
    )
    monkeypatch.setattr(membership, "refresh_all", lambda *a: None)
    monkeypatch.setattr(
        membership, "resolve", lambda *a: (["ABC", "NEW", "SPY"], newer, {})
    )
    store.set_preference("paper_config", {"hash": "frozen", "symbols": ["ABC"]})
    state["latest"] = date(2024, 5, 13)
    calls.clear()
    saved = update(store, indexed.id, lambda *a: None, api)
    updated = store.dataset(saved["id"])
    assert min(b.session for b in updated.bars["NEW"]) == date(2024, 1, 2)
    assert any(
        r.url.params.get("symbols") == "NEW"
        and r.url.params.get("start") == "2024-01-02"
        for r in calls
        if r.url.path.endswith("/bars")
    )
    assert membership.eligible(updated, date(2024, 5, 8)) == {"ABC"}
    assert membership.eligible(updated, date(2024, 5, 9)) == {"NEW"}
    assert updated.metadata["unavailable_symbols"]["ABC"] == "Earlier identity issue"
    assert store.preference("paper_config") == {"hash": "frozen", "symbols": ["ABC"]}
    assert store.dataset(indexed.id) == indexed
    assert updated.metadata["validation_issues"]


def test_no_new_session_update_reuses_every_bar_block_and_deduplicates(vendor):
    store, api, state, calls, initial = vendor
    old = store.dataset(initial["id"])
    saved = update(store, old.id, lambda *a: None, api)
    again = update(store, old.id, lambda *a: None, api)
    assert again["id"] == saved["id"] and again["already_imported"]
    assert (
        chunks(store, old.id)["bar_chunks"] == chunks(store, saved["id"])["bar_chunks"]
    )
    assert store.dataset(old.id) == old


def test_sec_failure_keeps_recoverable_updated_prices_and_old_sec_snapshot(
    vendor, monkeypatch
):
    store, api, state, calls, initial = vendor
    old = attach(store, initial["id"], lambda *a: None, api)
    original = store.dataset(old["id"])
    state["latest"] = date(2024, 5, 13)
    monkeypatch.setattr(
        "aperture.fundamentals.attach",
        lambda *a, **k: (_ for _ in ()).throw(ResearchError("SEC unavailable")),
    )
    with pytest.raises(
        ResearchError, match="Updated prices were saved.*SEC refresh failed"
    ):
        update(store, original.id, lambda *a: None, api)
    assert store.datasets()[0]["end"] == "2024-05-13"
    assert not store.datasets()[0]["metadata"].get("fundamentals")
    assert Store(store.path).dataset(original.id) == original


def test_interrupted_update_can_be_retried_after_restart(vendor, monkeypatch):
    store, api, state, calls, initial = vendor
    original = store.dataset(initial["id"])
    state["latest"] = date(2024, 5, 13)
    job = store.enqueue("dataset_update", {"dataset_id": original.id})
    assert store.claim()["id"] == job["id"]
    restarted = Store(store.path)
    restarted.recover()
    assert restarted.jobs()[0]["state"] == "failed"
    assert restarted.dataset(original.id) == original
    monkeypatch.setattr("aperture.dataset_updates.Provider", lambda *a: api)
    retry = restarted.enqueue("dataset_update", {"dataset_id": original.id})
    assert retry["id"] != job["id"]
    assert process_one(restarted)
    assert restarted.jobs()[0]["state"] == "complete"
    assert restarted.dataset(original.id) == original


def test_content_hash_verification_detects_modified_shared_payload(vendor):
    store, api, state, calls, initial = vendor
    with store.connect() as db:
        digest = chunks(store, initial["id"])["bar_chunks"][0]
        db.execute(
            "UPDATE content_blobs SET body=? WHERE digest=?",
            (gzip.compress(b"[]"), digest),
        )
    with pytest.raises(ResearchError, match="content hash check"):
        Store(store.path).dataset(initial["id"])


def test_old_backtest_is_exactly_reproducible_after_update_and_compaction(vendor):
    store, api, state, calls, initial = vendor
    saved = attach(store, initial["id"], lambda *a: None, api)
    old = store.dataset(saved["id"])
    arguments = ("quality", date(2024, 4, 1), date(2024, 5, 6), D(100000), Policy())
    expected = run(old, *arguments)
    assert expected["trades"]
    state.update(latest=date(2024, 5, 13), corrected=True, amended=True)
    update(store, old.id, lambda *a: None, api)
    compact(store)
    actual = run(Store(store.path).dataset(old.id), *arguments)
    assert actual == expected  # Curves, fills, filings, ranks, metrics and provenance.


@pytest.mark.parametrize("kind", ["current", "historical"])
def test_new_session_requires_membership_verification_even_under_24_hours(
    tmp_path, monkeypatch, kind
):
    from aperture.store import now

    store = Store(tmp_path / "fresh.sqlite")
    saved = {
        "id": "yesterday",
        "kind": kind,
        "captured_at": now(),
        "coverage_end": "2024-05-13",
        "verified_through": "2024-05-13",
        "history_version": membership_sources.VERSION,
        "members": [{"symbol": "ABC", "date_added": "2024-01-02"}],
    }
    store.save_membership(saved, b"public source")
    monkeypatch.setattr(calendar, "latest_complete", lambda *a: date(2024, 5, 14))
    calls = []
    monkeypatch.setattr(
        membership,
        "refresh",
        lambda store, kind: (
            calls.append(kind) or {**saved, "coverage_end": "2024-05-14"}
        ),
    )
    assert membership.fresh(store, kind)["coverage_end"] == "2024-05-14"
    assert calls == [kind]
