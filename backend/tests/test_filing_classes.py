from copy import deepcopy

import base64
import json
import httpx
import pytest

from aperture.filing_classes import inspect_cover, inspect_instance, acquire
from aperture.fundamentals import normalize
from filing_fixtures import cover, evidence
from test_fundamentals import source, ACC, CIK
from aperture.config import Settings
from aperture.providers import Provider, ResearchError
from aperture.store import Store


@pytest.fixture
def captured(tmp_path, monkeypatch):
    monkeypatch.setattr("aperture.providers.time.sleep", lambda _: None)
    store = Store(tmp_path / "evidence.sqlite3")
    calls = []
    raw = {"body": cover(), "status": 200}

    def respond(request):
        calls.append(str(request.url))
        if raw.get("fail_suffix") and str(request.url).endswith(raw["fail_suffix"]):
            return httpx.Response(503)
        return httpx.Response(raw["status"], content=raw["body"])

    def api():
        return Provider(
            store,
            httpx.Client(transport=httpx.MockTransport(respond)),
            Settings(sec_agent="Acceptance test test@example.com"),
        )

    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": [ACC],
                "primaryDocument": ["annual.htm"],
                "filingDate": ["2023-02-10"],
            }
        }
    }
    return store, api, submissions, calls, raw


def get_proof(api, submissions, **kwargs):
    return acquire(
        api,
        kwargs.get("symbol", "ABC"),
        kwargs.get("cik", CIK),
        source(),
        submissions,
        "2022-01-01",
        "2024-12-31",
    )


def test_persistent_parsed_evidence_reuses_proof_and_original_sources(
    captured, monkeypatch
):
    store, api, submissions, calls, _ = captured
    first = api()
    expected = get_proof(first, submissions)
    assert len(calls) == 1 and first.filing_cache_stats == {"parsed": 1, "reused": 0}
    monkeypatch.setattr(
        "aperture.filing_classes.inspect_cover",
        lambda *a, **k: pytest.fail("Historical evidence was reparsed"),
    )
    second = api()
    assert get_proof(second, submissions) == expected
    assert second.observations == first.observations
    assert second.filing_cache_stats == {"parsed": 0, "reused": 1}
    assert len(calls) == 1
    assert Store(store.path).filing_evidence("unknown") is None


@pytest.mark.parametrize(
    "change", ["parser", "symbol", "cik", "source", "missing", "damage"]
)
def test_parser_identity_source_or_cache_change_reverifies(
    captured, monkeypatch, change
):
    store, api, submissions, calls, _ = captured
    first = api()
    get_proof(first, submissions)
    options = {}
    if change == "parser":
        monkeypatch.setattr("aperture.filing_classes.CACHE_VERSION", "next-parser")
    elif change in {"symbol", "cik"}:
        options[change] = "OTHER" if change == "symbol" else "0000000002"
    elif change == "source":
        with store.connect() as db:
            resource = db.execute("SELECT resource FROM observations").fetchone()[0]
        store.observe(
            "sec",
            resource,
            json.dumps(
                {"base64": base64.b64encode(cover(symbol="OTHER")).decode()}
            ).encode(),
        )
    else:
        with store.connect() as db:
            db.execute(
                "DELETE FROM observations"
                if change == "missing"
                else "UPDATE parsed_filings SET body=x'00'"
            )
    second = api()
    result = get_proof(second, submissions, **options)
    assert second.filing_cache_stats == {"parsed": 1, "reused": 0}
    if change in {"symbol", "cik", "source"}:
        assert not result[ACC]["compatible"]


def test_new_amended_accession_is_verified_without_reparsing_old(captured, monkeypatch):
    _, api, submissions, calls, _ = captured
    get_proof(api(), submissions)
    amended = "0000000001-23-000002"
    company = source()
    row = company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][
        0
    ]
    company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"][
        "USD/shares"
    ].append({**row, "form": "10-K/A", "accn": amended, "filed": "2023-03-10"})
    recent = submissions["filings"]["recent"]
    for key, value in [
        ("accessionNumber", amended),
        ("filingDate", "2023-03-10"),
        ("primaryDocument", "amended.htm"),
    ]:
        recent[key].append(value)
    second = api()
    result = acquire(
        second, "ABC", CIK, company, submissions, "2022-01-01", "2024-12-31"
    )
    assert set(result) == {ACC, amended}
    assert second.filing_cache_stats == {"parsed": 1, "reused": 1}
    assert len(calls) == 2


def test_failed_source_is_retryable_and_completed_accession_survives_interruption(
    captured,
):
    _, api, submissions, calls, raw = captured
    raw["status"] = 503
    with pytest.raises(ResearchError):
        get_proof(api(), submissions)
    raw["status"] = 200
    expected = get_proof(api(), submissions)
    retry = api()
    assert get_proof(retry, submissions) == expected
    assert retry.filing_cache_stats["reused"] == 1


def test_html_parser_limit_does_not_accept_truncated_class_evidence():
    raw = cover() + b"<div>" * 400 + b"Class B common stock"
    assert not inspect(raw)["compatible"]


def test_valid_xhtml_fast_path_preserves_classes_and_namespace_checks():
    def xhtml(raw):
        return raw.replace(
            b"<html ",
            b'<html xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" ',
        )

    for raw in [
        cover(),
        cover(preferred=True),
        cover(symbol="OTHER"),
        cover(
            classes=[
                ("A", "ABC", "Common stock"),
                ("B", "ABC.B", "Class B common stock"),
            ]
        ),
    ]:
        a, b = inspect(raw), inspect(xhtml(raw))
        a.pop("sha256")
        b.pop("sha256")
        assert a == b
    assert not inspect(
        xhtml(cover()).replace(
            b"http://xbrl.sec.gov/dei/2023", b"https://untrusted.invalid/dei/2023"
        )
    )["compatible"]
    malicious = b'<!DOCTYPE html [<!ENTITY title "Preferred common stock">]>' + xhtml(
        cover()
    ).replace(b">Common stock<", b">&title;<")
    assert not inspect(malicious)["compatible"]


def inspect(raw, **extra):
    return inspect_cover(
        raw,
        symbol="ABC",
        cik=CIK,
        accession=ACC,
        filed="2023-02-10",
        url="https://www.sec.gov/fixture.htm",
        **extra,
    )


def test_dated_single_common_class_is_not_rejected_for_preferred_listings_today():
    company = source()
    proof = evidence(company)
    a = normalize("ABC", CIK, company, {"tickers": ["ABC"]}, proof)[0]
    b = normalize("ABC", CIK, company, {"tickers": ["ABC", "ABC-P", "FUTURE"]}, proof)[
        0
    ]
    assert a == b and a[0].eps == 4
    assert inspect(cover(preferred=True))["compatible"]


def test_each_accession_uses_its_own_classes_never_a_later_filing():
    company = source()
    future = "0000000001-24-000001"
    for concept in company["facts"]["us-gaap"].values():
        items = next(iter(concept["units"].values()))
        items.append({**items[0], "accn": future, "filed": "2024-02-10"})
    proofs = evidence(company)
    proofs[future] = inspect_cover(
        cover(
            classes=[
                ("A", "ABC", "Class A common stock"),
                ("B", "ABC.B", "Class B common stock"),
            ]
        ),
        symbol="ABC",
        cik=CIK,
        accession=future,
        filed="2024-02-10",
        url="https://www.sec.gov/future.htm",
    )
    rows = normalize("ABC", CIK, company, {"tickers": ["ABC", "ABC.B"]}, proofs)[0]
    by_accession = {r.accession: r for r in rows}
    assert by_accession[ACC].eps == 4
    assert by_accession[future].eps is None
    assert by_accession[future].gross_profit == 40


def test_unproven_or_wrong_identity_date_alias_and_multi_class_fail_closed():
    assert not inspect(cover(cik="0000000002"))["compatible"]
    assert not inspect(cover(symbol="OTHER"))["compatible"]
    assert not inspect(b"<html>Annual report, common stock ABC</html>")["compatible"]
    company = source()
    assert normalize("ABC", CIK, company, {"tickers": ["ABC"]})[0][0].eps is None
    for key, value in [
        ("filed", "2024-01-01"),
        ("cik", "0000000002"),
        ("symbol", "OTHER"),
        ("accession", "wrong"),
    ]:
        proofs = deepcopy(evidence(company))
        proofs[ACC][key] = value
        assert normalize("ABC", CIK, company, {}, proofs)[0][0].eps is None


def test_unlisted_second_common_class_prevents_entity_eps_mapping():
    raw = (
        cover()
        + b'<xbrli:context id="other"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">company:UnlistedClass</xbrldi:explicitMember></xbrli:segment></xbrli:entity></xbrli:context><ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="other">12</ix:nonFraction><ix:nonFraction name="dei:EntityCommonStockSharesOutstanding" contextRef="c0">10</ix:nonFraction>'
    )
    assert not inspect(raw)["compatible"]


def test_archive_pagination_is_dated_and_documents_captured_once_per_accession():
    class API:
        def __init__(self):
            self.requests = []

        def get(self, provider, url, **kwargs):
            self.requests.append(url)
            return {
                "accessionNumber": [ACC],
                "primaryDocument": ["annual.htm"],
                "filingDate": ["2023-02-10"],
            }

        def document(self, url):
            self.requests.append(url)
            return cover()

    api = API()
    submissions = {
        "filings": {
            "files": [
                {
                    "name": "CIK0000000001-submissions-001.json",
                    "filingFrom": "2020-01-01",
                    "filingTo": "2023-12-31",
                }
            ]
        }
    }
    proofs = acquire(api, "ABC", CIK, source(), submissions, "2022-01-01", "2023-12-31")
    assert proofs[ACC]["compatible"] and len(api.requests) == 2
    assert not acquire(
        api, "ABC", CIK, source(), submissions, "2024-01-01", "2024-12-31"
    )


def legacy(extra="", namespace="http://fasb.org/us-gaap/2016"):
    return f'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:dei="http://xbrl.sec.gov/dei/2016" xmlns:us-gaap="{namespace}" xmlns:xbrldi="http://xbrl.org/2006/xbrldi">
    <xbrli:context id="c"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier></xbrli:entity></xbrli:context>
    <dei:EntityCommonStockSharesOutstanding contextRef="c">100</dei:EntityCommonStockSharesOutstanding><us-gaap:EarningsPerShareDiluted contextRef="c">4</us-gaap:EarningsPerShareDiluted>{extra}</xbrli:xbrl>'''.encode()


def test_legacy_filing_uses_its_own_xbrl_basis_not_current_tickers():
    kwargs = dict(
        symbol="ABC",
        cik=CIK,
        accession=ACC,
        filed="2023-02-10",
        url="https://www.sec.gov/instance.xml",
    )
    proof = inspect_instance(legacy(), b"Single common stock", **kwargs)
    assert proof["compatible"]
    assert not inspect_instance(
        legacy(), b"Class A common stock and Class B common stock", **kwargs
    )["compatible"]
    assert not inspect_instance(
        legacy(namespace="https://untrusted/custom"), b"Common stock", **kwargs
    )["compatible"]
    assert not inspect_instance(
        b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x/>',
        b"Common stock",
        **kwargs,
    )["compatible"]
    other = '<xbrli:context id="b"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">1</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">ClassB</xbrldi:explicitMember></xbrli:segment></xbrli:entity></xbrli:context><us-gaap:EarningsPerShareDiluted contextRef="b">2</us-gaap:EarningsPerShareDiluted>'
    assert not inspect_instance(legacy(other), b"Common stock", **kwargs)["compatible"]


def test_inline_custom_namespace_cannot_masquerade_as_dei():
    raw = cover().replace(
        b"http://xbrl.sec.gov/dei/2023", b"https://custom.invalid/dei/2023"
    )
    assert not inspect(raw)["compatible"]


def test_legacy_manifest_uses_declared_instance_not_filename_guess():
    class API:
        def document(self, url):
            if url.endswith("annual.htm"):
                return b"<html>Common stock</html>"
            if url.endswith("FilingSummary.xml"):
                return b"<FilingSummary><InputFiles><File>actual-instance.xml</File><File>actual-instance_cal.xml</File></InputFiles></FilingSummary>"
            assert url.endswith("actual-instance.xml")
            return legacy()

    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": [ACC],
                "filingDate": ["2023-02-10"],
                "primaryDocument": ["annual.htm"],
            }
        }
    }
    proofs = acquire(
        API(), "ABC", CIK, source(), submissions, "2022-01-01", "2023-12-31"
    )
    assert proofs[ACC]["compatible"] and proofs[ACC]["url"].endswith(
        "actual-instance.xml"
    )
