from dataclasses import replace
from decimal import Decimal as D

import httpx
import pytest
from fastapi.testclient import TestClient

from aperture.api import create_app
from aperture.domain import Policy, RankedStock, ResearchError
from aperture.exposure import summarize
from aperture.ingest import practice_dataset
from aperture.portfolio import target_weights
from aperture.sectors import URL, attach, capture, classify, normalize, parse
from aperture.store import Store, decode
from sector_fixtures import archive_csv


SOURCE = {
    "url": URL,
    "sha256": "source-digest",
    "captured_at": "2026-11-05T00:00:00+00:00",
}


def snapshot(names, **metadata):
    return dict(
        symbols=names,
        start="2016-01-04",
        end="2026-11-04",
        source="Fixture",
        metadata=metadata,
    )


def test_classification_uses_current_last_known_and_reviewed_history_without_inventing_identity():
    rows = parse(
        archive_csv(
            [
                [
                    "GGP",
                    "895648",
                    "Old GGP",
                    "financials",
                    "2007-01-01",
                    "2009-03-01",
                    "2007-03-05",
                ],
                [
                    "GGP",
                    "1496048",
                    "GGP REIT",
                    "real_estate",
                    "2013-12-10",
                    "2018-08-28",
                    "2013-12-10",
                ],
                [
                    "DD",
                    "30554",
                    "Original DuPont",
                    "materials",
                    "2000-01-01",
                    "2017-09-01",
                    "2007-03-05",
                ],
                [
                    "DD",
                    "1666700",
                    "New DuPont",
                    "industrials",
                    "2019-06-03",
                    "",
                    "2019-06-03",
                ],
                [
                    "REUSE",
                    "1",
                    "Issuer A",
                    "energy",
                    "2016-01-01",
                    "2018-01-01",
                    "2016-01-01",
                ],
                [
                    "REUSE",
                    "2",
                    "Issuer B",
                    "financials",
                    "2020-01-01",
                    "",
                    "2020-01-01",
                ],
            ]
        )
    )
    summary = snapshot(
        ["GGP", "DD", "DD.OLD", "REUSE", "MRP", "MYN", "SPY", "XRXDW", "NEW"],
        membership={
            "kind": "combined",
            "current": {
                "members": [
                    {"symbol": "DD", "sector": "Industrials", "cik": "0001666700"}
                ]
            },
        },
    )
    sectors, audit = classify(summary, {}, rows, SOURCE)
    assert sectors["GGP"] == "Real Estate" and sectors["DD.OLD"] == "Materials"
    assert sectors["DD"] == "Industrials" and sectors["MRP"] == "Real Estate"
    assert sectors["XRXDW"] == "Information Technology"
    assert audit["records"]["DD.OLD"]["cik"] == "0000030554"
    assert set(audit["unresolved_symbols"]) == {"NEW", "REUSE"}
    assert audit["not_applicable_count"] == 2
    assert audit["records"]["MRP"]["method"] == "dated_public_classification"
    assert "look-ahead" in audit["warning"]
    assert "identity" not in summary["metadata"]


def test_normalization_does_not_split_one_sector_into_several_cap_buckets():
    assert (
        normalize("Technology")
        == normalize("Information Technology")
        == normalize("information_technology")
    )
    assert normalize("Healthcare") == "Health Care"
    ranked = [
        RankedStock(
            str(i), 1.0, normalize("Technology" if i % 2 else "Information Technology")
        )
        for i in range(25)
    ]
    weights, _ = target_weights(ranked, Policy())
    assert sum(weights.values()) == D("0.25")
    ranked = [
        replace(
            s,
            sector=["Energy", "Industrials", "Health Care", "Financials", "Materials"][
                i % 5
            ],
        )
        for i, s in enumerate(ranked)
    ]
    weights, _ = target_weights(ranked, Policy())
    assert sum(weights.values()) == D("0.98")
    assert max(
        sum((w for s, w in weights.items() if ranked[int(s)].sector == sector), D(0))
        for sector in {s.sector for s in ranked}
    ) <= D(".25")


@pytest.mark.parametrize(
    "transform",
    [
        lambda text: text.replace("symbol,cik", "ticker,cik", 1),
        lambda text: text.replace("industrials", "invented_sector", 1),
        lambda text: text[:200],
    ],
)
def test_malformed_or_incomplete_archive_is_rejected(transform):
    with pytest.raises(ResearchError, match="archive"):
        parse(transform(archive_csv()))


def test_capture_caches_and_force_refreshes_public_data_without_credentials(tmp_path):
    store = Store(tmp_path / "sectors.sqlite3")
    calls = []

    def handler(request):
        calls.append(request)
        assert not any(
            "key" in k.lower() or "authorization" in k.lower() for k in request.headers
        )
        return httpx.Response(200, text=archive_csv())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    a, source = capture(store, client=client)
    b, cached = capture(store, client=client)
    assert a == b and cached["observation_id"] == source["observation_id"]
    assert len(calls) == 1
    capture(store, client=client, refresh=True)
    assert len(calls) == 2
    failed = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(ResearchError):
        capture(store, client=failed, refresh=True)
    assert store.cached("sectors", URL, 86400) is not None


def test_enrichment_shares_prices_and_filings_preserves_saved_research_and_deduplicates(
    tmp_path,
):
    store = Store(tmp_path / "sectors.sqlite3")
    ds, raw, warnings = practice_dataset()
    ds = replace(ds, kind="imported", digest="a" * 64, id="a" * 24)
    store.save_dataset(ds, raw, warnings)
    with store.connect() as db:
        original_body = bytes(
            db.execute("SELECT body FROM datasets WHERE id=?", (ds.id,)).fetchone()[0]
        )
        count = db.execute("SELECT count(*) FROM content_blobs").fetchone()[0]
    text = archive_csv(
        [
            [
                s,
                str(i + 1),
                s + " issuer",
                "health_care",
                "2000-01-01",
                "",
                "2007-03-05",
            ]
            for i, s in enumerate(ds.bars)
            if s != "SPY"
        ]
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text=text))
    )
    saved = attach(store, ds.id, client=client)
    assert saved["id"] != ds.id
    assert saved["metadata"]["sector_classification"]["unresolved_count"] == 0
    assert attach(store, ds.id, client=client)["id"] == saved["id"]
    assert attach(store, saved["id"], client=client)["id"] == saved["id"]
    assert store.dataset(ds.id) == ds
    with store.connect() as db:
        old = bytes(
            db.execute("SELECT body FROM datasets WHERE id=?", (ds.id,)).fetchone()[0]
        )
        new = decode(
            db.execute(
                "SELECT body FROM datasets WHERE id=?", (saved["id"],)
            ).fetchone()[0]
        )
        assert old == original_body
        assert new["bar_chunks"] == decode(old)["bar_chunks"]
        assert new["fundamental_chunks"] == decode(old)["fundamental_chunks"]
        assert (
            db.execute("SELECT count(*) FROM content_blobs").fetchone()[0] == count + 1
        )  # source capture only
    failed = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="broken"))
    )
    n = len(store.datasets())
    with pytest.raises(ResearchError):
        attach(store, saved["id"], client=failed, refresh=True)
    assert len(store.datasets()) == n


def test_legacy_exposure_is_derived_without_rewriting_result_body(tmp_path):
    store = Store(tmp_path / "exposure.sqlite3")
    result = {
        "curve": [
            {"equity": "100", "cash": "75", "receivable": "0"},
            {"equity": "110", "cash": "82.5", "receivable": "0"},
        ],
        "decisions": [{"targets": {"ABC": ".25"}}],
    }
    assert summarize(result)["mean_stock_weight"] == 0.25
    job = store.enqueue("backtest", {"start": "2024-01-02", "end": "2024-02-01"})
    store.finish(job, result)
    with store.connect() as db:
        before = bytes(db.execute("SELECT body FROM results").fetchone()[0])
    assert store.results("backtest")[0]["exposure"]["mean_cash_weight"] == 0.75
    with store.connect() as db:
        assert bytes(db.execute("SELECT body FROM results").fetchone()[0]) == before


def test_sector_api_requires_local_write_header_and_retains_audits(tmp_path):
    app = create_app(tmp_path / "api.sqlite3", web_path=None)
    ds, raw, warnings = practice_dataset()
    ds = replace(ds, kind="imported", digest="b" * 64, id="b" * 24)
    app.state.store.save_dataset(ds, raw, warnings)
    c = TestClient(app)
    assert c.post(f"/api/datasets/{ds.id}/sectors", json={}).status_code == 403
    response = c.post(
        f"/api/datasets/{ds.id}/sectors", json={}, headers={"x-aperture-client": "1"}
    )
    assert response.status_code == 202 and response.json()["kind"] == "sector_update"
    assert c.get(f"/api/datasets/{ds.id}/sectors").json() == {}
