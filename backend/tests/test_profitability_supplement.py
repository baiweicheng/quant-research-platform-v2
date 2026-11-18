from pathlib import Path
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from types import SimpleNamespace

from aperture.profitability_supplement import extract, primary_url

FIXTURE = Path(__file__).parent / "fixtures" / "profitability" / "XOM-quarterly.htm"


def test_xom_uses_explicit_year_total_and_keeps_issuer_definition():
    result = extract(FIXTURE.read_bytes())
    assert result["2016-12-31"]["value"] == "60202000000"
    assert result["2015-12-31"]["value"] == "75850000000"
    assert "estimated costs" in result["2016-12-31"]["definition"]


def test_xom_quarterly_sum_does_not_replace_a_missing_year_total():
    assert "2016-12-31" not in extract(
        FIXTURE.read_bytes().replace(b"60,202", b"60,000")
    )


def test_xom_rejects_a_table_without_year_units_or_definition():
    raw = FIXTURE.read_bytes()
    for old, new in [
        (b"millions of dollars", b"thousands of dollars"),
        (b"Year", b"Quarter"),
        (b"Gross profit equals", b"Other disclosure equals"),
    ]:
        assert not extract(raw.replace(old, new))


def test_primary_index_unwraps_only_one_official_same_accession_document():
    folder = "https://www.sec.gov/Archives/edgar/data/1645590/000164559025000130/"

    def locate(href):
        raw = f'<table><tr><td>1</td><td>10-K</td><td><a href="{href}">Primary</a></td><td>10-K</td></tr></table>'.encode()
        return primary_url(
            SimpleNamespace(document=lambda url: raw), folder, "0001645590-25-000130"
        )

    assert (
        locate(
            "/ix?doc=/Archives/edgar/data/1645590/000164559025000130/hpe-20251031.htm"
        )
        == folder + "hpe-20251031.htm"
    )
    for href in [
        "/ix?doc=https://example.com/annual.htm",
        "/ix?doc=/Archives/edgar/data/1/000000000100000001/annual.htm",
        "/ix?doc=/Archives/edgar/data/1645590/000164559025000130/../annual.htm",
        "/ix?doc=/Archives/edgar/data/1645590/000164559025000130/a.htm&amp;doc=b.htm",
    ]:
        assert locate(href) is None


def test_hpe_reported_annual_subtotal_is_bound_to_monetary_year_columns():
    root = FIXTURE.parent
    old = extract((root / "HPE-annual-mda.htm").read_bytes(), "0001645590")
    new = extract((root / "HPE-annual-mda-2025.htm").read_bytes(), "0001645590")
    assert old["2016-10-31"]["value"] == "14616000000"
    assert old["2016-10-31"]["cost"] == "35507000000"
    assert new["2025-10-31"]["value"] == "10377000000"
    assert new["2025-10-31"]["revenue"] == "34296000000"
    assert (
        "before separately presented intangible amortization"
        in new["2025-10-31"]["definition"]
    )
    # Percent columns are never mistaken for dollar amounts. Unsupported dates,
    # units, company scope and inconsistent reported subtotals fail closed.
    raw = (root / "HPE-annual-mda.htm").read_bytes()
    for before, after in [
        (b"October", b"September"),
        (b"Dollars in millions", b"Dollars in thousands"),
        (b"14,616", b"14,600"),
        (b"Research and development", b"Segment expenses"),
    ]:
        assert "2016-10-31" not in extract(raw.replace(before, after), "0001645590")
    assert not extract(raw, "0000000001")


def test_reported_quarters_without_annual_total_do_not_supply_an_annual_value():
    raw = (FIXTURE.parent / "MDT-quarterly-2019.htm").read_bytes()
    assert not extract(raw, "0001613103")


def test_ordinary_enrichment_uses_hpe_reported_gp_with_same_period_revenue():
    from aperture.domain import AnnualStatement
    from aperture.profitability_filings import enrich
    from filing_fixtures import INCOME_SUMMARY

    row = AnnualStatement(
        symbol="HPE",
        cik="0001645590",
        start=date(2015, 11, 1),
        end=date(2016, 10, 31),
        filed=date(2016, 12, 15),
        available_at=datetime(2016, 12, 16, tzinfo=timezone.utc),
        accession="0001628280-16-022051",
        form="10-K",
        assets=Decimal(79679000000),
        gross_profit=None,
        eps=None,
        eps_compatible=False,
        sources={
            "profitability_status": "derived",
            "profitability_revenue": "50123000000",
        },
    )
    calls = []

    def document(url):
        calls.append(url)
        if url.endswith("FilingSummary.xml"):
            return INCOME_SUMMARY
        if url.endswith("R2.htm"):
            return (FIXTURE.parent / "HPE-income.htm").read_bytes()
        if url.endswith("-index.htm"):
            return b'<table><tr><td>1</td><td>10-K</td><td><a href="annual.htm">Annual</a></td><td>10-K</td></tr></table>'
        assert url.endswith("annual.htm")
        return (FIXTURE.parent / "HPE-annual-mda.htm").read_bytes()

    api = SimpleNamespace(document=document, observations=[])
    day = date(2017, 1, 3)
    result = enrich((row,), api, day, day)[0]
    assert result.gross_profit == Decimal(14616000000)
    assert result.accession == row.accession and result.available_at == row.available_at
    assert (
        "before separately presented intangible amortization"
        in result.sources["profitability_definition"]
    )
    changed = replace(
        row, sources={**row.sources, "profitability_revenue": "50000000000"}
    )
    rejected = enrich((changed,), api, day, day)[0]
    assert rejected.gross_profit is None
    assert (
        rejected.sources["profitability_filing_status"]
        == "filed_revenue_does_not_match_structured_period"
    )
