"""Actual SEC statements plus adverse-layout cases for bounded recovery."""

import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from aperture.fundamentals import normalize
from aperture.profitability_filings import enrich, extract_period, parse_report

FIXTURES = Path(__file__).parent / "fixtures" / "profitability"


def report(symbol):
    return (FIXTURES / f"{symbol}-income.htm").read_bytes()


@pytest.mark.parametrize(
    "symbol,end,expected",
    [
        ("TMO", "2016-12-31", 8369100000),
        ("HAL", "2018-12-31", 2986000000),
        ("NOC", "2018-12-31", 6791000000),
        ("INTU", "2018-07-31", 4987000000),
    ],
)
def test_primary_filing_recovers_complete_costs(symbol, end, expected):
    value = extract_period(parse_report(report(symbol))[end])
    assert D(value["value"]) == expected
    if symbol == "INTU":
        assert D(value["additional_production_amortization"]) == 15000000


def test_cnc_medical_costs_cannot_be_replaced_by_small_service_costs():
    value = extract_period(parse_report(report("CNC"))["2015-12-31"])
    assert "value" not in value


def test_quarterly_column_and_non_usd_are_not_treated_as_annual_usd():
    assert not parse_report(
        report("TMO").replace(b"12 Months Ended", b"3 Months Ended")
    )
    assert not parse_report(report("TMO").replace(b"USD ($)", b"CAD ($)"))


def test_product_service_partition_must_reconcile_before_adding_costs():
    raw = report("INTU").replace(b"$ 1,462", b"$ 1,400")
    value = extract_period(parse_report(raw)["2018-07-31"])
    assert "value" not in value
    assert value["status"] == "incomplete_filed_product_service_partition"


def test_arbitrary_segment_axis_cannot_masquerade_as_a_complete_cost_split():
    raw = report("INTU").replace(
        b"srt_ProductOrServiceAxis", b"us-gaap_StatementBusinessSegmentsAxis"
    )
    assert "value" not in extract_period(parse_report(raw)["2018-07-31"])


def test_tmo_rounded_filed_costs_keep_both_revenue_streams():
    rows = parse_report(report("TMO-2025"))["2025-12-31"]
    result = extract_period(rows, "0000097745")
    assert D(result["value"]) == 18238000000
    assert D(result["expense_reconciliation_difference"]) == -1000000

    service_cost = next(
        r
        for r in rows
        if (r["scope"] or "").endswith("ServiceMember")
        and r["label"] == "Cost of revenues"
    )
    service_cost["value"] = "12903000000"
    assert extract_period(rows, "0000097745")["status"] == (
        "filed_expense_section_does_not_reconcile"
    )


@pytest.mark.parametrize(
    "symbol, cik, end, gross",
    [
        ("CHRW", "0001043277", "2016-12-31", 2277528000),
        ("INTU", "0000896878", "2025-07-31", 14983000000),
    ],
)
def test_reviewed_product_service_dimensions_keep_the_full_revenue_partition(
    symbol, cik, end, gross
):
    rows = parse_report(report(f"{symbol}-partition"))[end]
    proof = extract_period(rows, cik)
    assert D(proof["value"]) == gross
    assert "value" not in extract_period(rows, "0000000000")
    scope = proof["component_scopes"]["ProductMember"]
    assert "value" not in extract_period([r for r in rows if r["scope"] != scope], cik)


def test_explicit_administrative_subtotal_keeps_production_depreciation_distinct():
    rows = parse_report(report("PAYC-partition"))["2018-12-31"]
    proof = extract_period(rows, "0001590955")
    assert D(proof["value"]) == 475573000
    assert D(proof["cost"]) == 90763000
    administrative_da = next(
        r for r in rows if r["concept"] == "us-gaap_DepreciationAndAmortization"
    )
    administrative_da["value"] = "15124000"
    assert "value" not in extract_period(rows, "0001590955")


def test_target_recovers_sales_costs_only_with_explicit_depreciation_scope():
    rows = parse_report(report("TGT"))["2017-01-28"]
    proof = extract_period(rows, "0000027419")
    assert D(proof["value"]) == 21126000000
    assert D(proof["cost"]) == 49145000000
    assert "value" not in extract_period(rows, "0000000000")

    depreciation = next(
        r for r in rows if r["concept"] == "us-gaap_DepreciationAndAmortization"
    )
    depreciation["label"] = (
        "Depreciation and amortization (excluded from cost of sales)"
    )
    assert "value" not in extract_period(rows, "0000027419")


@pytest.mark.parametrize("sample_recovers", [False, True])
def test_bounded_filing_search_expands_after_a_supported_sample(
    monkeypatch, sample_recovers
):
    from types import SimpleNamespace

    from aperture import profitability_filings
    from aperture.domain import AnnualStatement
    from aperture.fundamentals import filing_available

    periods = []
    for year in range(2016, 2020):
        filed = date(year + 1, 2, 15)
        periods.append(
            AnnualStatement(
                "TEST",
                "0000000001",
                date(year, 1, 1),
                date(year, 12, 31),
                filed,
                filing_available(filed),
                f"0000000001-{year % 100:02}-000001",
                "10-K",
                D(100),
                None,
                None,
                False,
                {"profitability_status": "unsupported_cost_presentation"},
                (),
            )
        )
    calls = []
    dates = {r.accession: str(r.end) for r in periods}

    def read(api, cik, accession):
        calls.append(accession)
        return {
            "periods": {
                dates[accession]: {
                    "value": "25",
                    "method": "reported_gross_profit",
                    "url": "https://www.sec.gov/test.htm",
                    "sha256": "test-hash",
                }
            }
            if sample_recovers and accession == periods[-1].accession
            else {}
        }

    monkeypatch.setattr(profitability_filings, "read", read)
    api = SimpleNamespace(document=lambda url: None, observations=[])
    result = enrich(tuple(periods), api, date(2017, 1, 3), date(2020, 3, 1))
    assert calls[:2] == [periods[0].accession, periods[-1].accession]
    if sample_recovers:
        assert set(calls) == set(dates)
        assert result[-1].gross_profit == D(25)
    else:
        assert len(calls) == 2
        assert (
            result[1].sources["profitability_filing_status"] == "bounded_filing_search"
        )
        assert result[1].gross_profit is None


def test_recovery_never_uses_a_different_accession_or_comparative_year():
    capture = json.loads((FIXTURES / "TMO.json").read_text())
    rows, _ = normalize(
        "TMO", "0000097745", capture["company"], {"entityType": "operating"}
    )

    class UnsupportedClient:
        def __init__(self):
            self.observations = []

        def document(self, url):
            if url.endswith("FilingSummary.xml"):
                return b"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Operations</ShortName><HtmlFileName>R2.htm</HtmlFileName></Report></MyReports></FilingSummary>"
            return report("CNC")  # unrelated years must never fill 2016 inputs

    row = next(r for r in rows if r.end == date(2016, 12, 31))
    result = enrich((row,), UnsupportedClient(), date(2017, 3, 1), date(2017, 3, 10))
    assert result[0].gross_profit is None


@pytest.mark.parametrize(
    "symbol,cik,end,expected",
    [
        ("PHM", "0000822416", "2016-12-31", "1939814000"),
        ("STX", "0001137789", "2016-07-01", "2615000000"),
        ("LHX", "0000202058", "2018-06-29", "2251000000"),
    ],
)
def test_source_reviewed_expense_displays_preserve_complete_costs(
    symbol, cik, end, expected
):
    raw = (FIXTURES / f"{symbol}-display-income.htm").read_bytes()
    rows = parse_report(raw)[end]
    result = extract_period(rows, cik)
    assert result["value"] == expected
    assert result["expense_section_reconciled"]
    assert "value" not in extract_period(rows, "0000000001")
    if symbol == "PHM":
        assert result["production_components"]["FinancialServicesCosts"] == "108573000"
        for tag in ("us-gaap_HomeBuildingCosts", "us-gaap_FinancialServicesCosts"):
            changed = [
                {**r, "value": str(D(r["value"]) + 1000)} if r["concept"] == tag else r
                for r in rows
            ]
            assert "value" not in extract_period(changed, cik)
    elif symbol == "STX":
        changed = [
            {
                **r,
                "concept": r["concept"].replace(
                    "excludingamountincludedincostofrevenue", "unallocated"
                ),
            }
            for r in rows
        ]
        assert "value" not in extract_period(changed, cik)
    else:
        changed = [
            {**r, "label": "Unallocated operating expenses"}
            if r["concept"] == "us-gaap_OperatingExpenses"
            else r
            for r in rows
        ]
        assert "value" not in extract_period(changed, cik)


def test_retained_primary_source_fingerprints_match_regression_inputs():
    import hashlib

    for source in json.loads((FIXTURES / "reports.json").read_text()):
        assert (
            hashlib.sha256((FIXTURES / source["file"]).read_bytes()).hexdigest()
            == source["sha256"]
        )


@pytest.mark.parametrize(
    "symbol,end,expected",
    [("TMO", date(2016, 12, 31), D(8369100000)), ("CNC", date(2015, 12, 31), None)],
)
def test_normal_download_enrichment_preserves_complete_cost_correction(
    symbol, end, expected
):
    capture = json.loads((FIXTURES / f"{symbol}.json").read_text())
    cik = str(capture["company"]["cik"]).zfill(10)
    rows, _ = normalize(symbol, cik, capture["company"], {"entityType": "operating"})

    class CapturedClient:
        def __init__(self):
            self.observations = []

        def document(self, url):
            if url.endswith("FilingSummary.xml"):
                return b"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Operations</ShortName><HtmlFileName>R2.htm</HtmlFileName></Report></MyReports></FilingSummary>"
            return report(symbol)

    selected = next(r for r in rows if r.end == end)
    decision = date(2017, 3, 1) if symbol == "TMO" else date(2016, 3, 1)
    enriched = enrich((selected,), CapturedClient(), decision, decision)
    assert enriched[0].gross_profit == expected
    assert enriched[0].accession == selected.accession
    assert enriched[0].available_at == selected.available_at
    if expected is not None:
        assert enriched[0].sources["profitability_status"] == "filed_statement"
        assert not any("Partial-cost" in i for i in enriched[0].issues)


@pytest.mark.parametrize(
    "symbol,end,expected",
    [
        ("PG", "2016-06-30", 32390000000),
        ("ABBV", "2015-12-31", 18359000000),
        ("ADP", "2016-06-30", 4827500000),
        ("CHRW", "2015-12-31", 2268480000),
    ],
)
def test_complete_expense_sections_and_footnote_columns(symbol, end, expected):
    cik = "0001043277" if symbol == "CHRW" else None
    result = extract_period(parse_report(report(symbol))[end], cik)
    assert D(result["value"]) == expected
    if symbol == "ADP":
        # The disclosed total already includes production depreciation; do not
        # subtract the separately displayed child component a second time.
        assert D(result["cost"]) == 6840300000


def test_custom_transportation_recipe_is_issuer_scoped():
    rows = parse_report(report("CHRW"))["2015-12-31"]
    assert "value" not in extract_period(rows, "0000000001")


def test_unknown_nonzero_expense_cannot_be_ignored_to_force_reconciliation():
    raw = report("PG").replace(b"13,441", b"13,440")
    # A changed operating total no longer reconciles to the known components.
    assert "value" not in extract_period(parse_report(raw)["2016-06-30"])


@pytest.mark.parametrize(
    "symbol,cik,end,expected",
    [
        ("ROST", "0000745732", "2016-01-30", 3363126000),
        ("SLB", "0000087347", "2016-12-31", 3700000000),
        ("REGN", "0000872589", "2015-12-31", 3711019000),
        ("VRTX", "0000875320", "2015-12-31", 907824000),
        ("COST", "0000909832", "2016-08-28", 15818000000),
        ("ABT", "0000001800", "2015-12-31", 11057000000),
    ],
)
def test_newly_audited_complete_cost_and_revenue_components(symbol, cik, end, expected):
    result = extract_period(parse_report(report(symbol))[end], cik)
    assert D(result["value"]) == expected


def test_explicit_production_amortization_is_not_ignored_as_general_overhead():
    rows = parse_report(report("ABT"))["2015-12-31"]
    value = extract_period(rows, "0000001800")
    assert (
        D(
            value["production_components"][
                "abt_AmortizationOfIntangibleAssetsExcludingDiscontinuedOperations"
            ]
        )
        == 601000000
    )
    # Independent primary MDA reports 54.2%; the older omitted-cost value was 57.1%.
    assert round(D(value["value"]) / D(value["revenue"]) * 100, 1) == D("54.2")


def test_contract_manufacturing_cost_cannot_disappear_from_regeneron():
    rows = parse_report(report("REGN"))["2015-12-31"]
    value = extract_period(rows, "0000872589")
    assert D(value["production_components"]["regn_Costofmanufacturing"]) == 151007000
    assert "value" not in extract_period(rows, "0000000001")


@pytest.mark.parametrize(
    "title",
    [
        "Consolidated Statements of Income and Comprehensive Income",
        "Consolidated Statements of Income and Total Comprehensive Income",
        "Consolidated Statements of Comprehensive Income",
    ],
)
def test_filing_cache_reuses_captures_and_invalidates_changed_source(tmp_path, title):
    import base64

    import httpx
    from aperture.config import Settings
    from aperture.profitability_filings import read
    from aperture.providers import Provider
    from aperture.store import Store

    calls = []
    summary = f"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>{title}</ShortName><Position>2</Position><HtmlFileName>R2.htm</HtmlFileName></Report></MyReports></FilingSummary>".encode()

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            content=summary
            if str(request.url).endswith("FilingSummary.xml")
            else report("TMO"),
        )

    store = Store(tmp_path / "source.sqlite3")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = Provider(
            store, client, Settings(sec_agent="B039 tests contact@example.com")
        )
        first = read(api, "0000097745", "0000097745-17-000007")
        assert D(first["periods"]["2016-12-31"]["value"]) == 8369100000
        assert len(calls) == 2
        assert read(api, "0000097745", "0000097745-17-000007") == first
        assert len(calls) == 2
        url = first["reports"][0]["url"]
        raw = report("TMO").replace(b"18,274.1", b"18,274.2")
        assert raw != report("TMO")
        store.observe(
            "sec",
            url + "#filed-document-v1",
            json.dumps({"base64": base64.b64encode(raw).decode()}).encode(),
        )
        changed = read(api, "0000097745", "0000097745-17-000007")
        assert "value" not in changed["periods"]["2016-12-31"]
        assert (
            len(calls) == 2
        )  # Reparse the new capture; do not rerequest prices/reports.


@pytest.mark.parametrize("category", ["Statements", "Uncategorized"])
def test_separate_income_statement_precedes_earlier_oci_report(category):
    from aperture.profitability_filings import read

    class Captured:
        def __init__(self):
            self.observations = []

        def document(self, url):
            if url.endswith("FilingSummary.xml"):
                return f"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Comprehensive Income</ShortName><Position>2</Position><HtmlFileName>R2.htm</HtmlFileName></Report><Report><MenuCategory>{category}</MenuCategory><ShortName>Consolidated Statements of Operations</ShortName><Position>3</Position><HtmlFileName>R3.htm</HtmlFileName></Report></MyReports></FilingSummary>".encode()
            assert url.endswith("R3.htm")
            return report("TMO")

    result = read(Captured(), "0000097745", "0000097745-17-000007")
    assert D(result["periods"]["2016-12-31"]["value"]) == 8369100000


def test_old_comparative_value_does_not_skip_current_year_quarterly_evidence():
    from types import SimpleNamespace

    from aperture.profitability_filings import read

    primary = b"""<table class="report"><tr><th>Income, USD ($)</th><th colspan="2">12 Months Ended</th></tr><tr><th>Dec. 31, 2023</th><th>Dec. 31, 2022</th></tr><tr><td><a onclick="defref_us-gaap_Revenues">Total revenues</a></td><td>100</td><td>100</td></tr><tr><td><a onclick="defref_us-gaap_GrossProfit">Gross profit</a></td><td></td><td>30</td></tr><tr><td><a onclick="defref_us-gaap_CostOfRevenue">Cost of revenue</a></td><td>60</td><td>70</td></tr><tr><td><a onclick="defref_custom_Fulfillment">Fulfillment</a></td><td>20</td><td>0</td></tr><tr><td><a onclick="defref_us-gaap_OperatingIncomeLoss">Operating income</a></td><td>20</td><td>30</td></tr></table>"""
    quarterly = b"""<table class="report"><tr><th>Quarterly information, USD ($)</th><th>12 Months Ended</th></tr><tr><th>Dec. 31, 2023</th></tr><tr><td><a onclick="defref_us-gaap_GrossProfit">Gross profit</a></td><td>40</td></tr></table>"""
    summary = b"""<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Income</ShortName><HtmlFileName>R2.htm</HtmlFileName></Report><Report><MenuCategory>Notes</MenuCategory><ShortName>Quarterly Information</ShortName><HtmlFileName>R3.htm</HtmlFileName></Report></MyReports></FilingSummary>"""
    calls = []

    def document(url):
        calls.append(url)
        return (
            summary
            if url.endswith("FilingSummary.xml")
            else primary
            if url.endswith("R2.htm")
            else quarterly
        )

    result = read(
        SimpleNamespace(document=document, observations=[]),
        "0000000001",
        "0000000001-24-000001",
    )
    assert result["periods"]["2022-12-31"]["value"] == "30"
    assert result["periods"]["2023-12-31"]["value"] == "40"
    assert calls[-1].endswith("R3.htm")


def test_property_operating_cost_tag_does_not_cover_separate_depreciation():
    rows = parse_report(report("WELL"))["2023-12-31"]
    result = extract_period(rows, "0000766704")
    assert result == {"status": "filed_cost_excludes_unallocated_expenses"}
    # The old candidate subtracted $3.947776bn property costs from $6.637995bn
    # revenue, omitting $1.401101bn D&A with no production allocation.
    assert any(r["concept"] == "us-gaap_DepreciationAndAmortization" for r in rows)


def test_derived_aggregate_candidate_still_requires_filed_complete_costs():
    from aperture.domain import AnnualStatement
    from aperture.fundamentals import filing_available

    row = AnnualStatement(
        symbol="TEST",
        cik="0000097745",
        start=date(2016, 1, 1),
        end=date(2016, 12, 31),
        filed=date(2017, 2, 28),
        available_at=filing_available(date(2017, 2, 28)),
        accession="0000097745-17-000007",
        form="10-K",
        assets=D(45907500000),
        gross_profit=D(10060200000),
        eps=D(5),
        eps_compatible=True,
        sources={"profitability_status": "aggregate_cost"},
    )

    class Captured:
        def __init__(self):
            self.observations = []

        def document(self, url):
            if url.endswith("FilingSummary.xml"):
                return b"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Income</ShortName><HtmlFileName>R2.htm</HtmlFileName></Report></MyReports></FilingSummary>"
            return report("TMO")

    fixed = enrich((row,), Captured(), date(2017, 3, 1), date(2017, 3, 1))[0]
    assert fixed.gross_profit == D(8369100000)
    assert (
        enrich((row,), object(), date(2017, 3, 1), date(2017, 3, 1))[0].gross_profit
        is None
    )


def test_standard_cost_tag_for_one_business_stream_is_not_a_total():
    rows = [
        {
            "concept": "us-gaap_Revenues",
            "label": "Total revenues",
            "scope": None,
            "value": "1000",
        },
        {
            "concept": "us-gaap_CostOfGoodsAndServicesSold",
            "label": "Purchased commodities",
            "scope": None,
            "value": "100",
        },
        {
            "concept": "custom_OtherProductionCosts",
            "label": "Production and operating expenses",
            "scope": None,
            "value": "500",
        },
    ]
    assert "value" not in extract_period(rows)


def test_hpe_financing_and_unallocated_amortization_are_not_dropped():
    rows = parse_report(report("HPE"))["2016-10-31"]
    assert any(
        r["concept"] == "us-gaap_FinancialServicesCosts" and D(r["value"]) == 249000000
        for r in rows
    )
    result = extract_period(rows, "0001645590")
    assert "value" not in result
    assert result["status"] == "filed_cost_excludes_unallocated_expenses"


@pytest.mark.parametrize(
    "symbol,end,expected",
    [
        ("ECL", "2015-12-31", 6321600000),
        ("ETN", "2015-12-31", 6563000000),
        ("NUE", "2015-12-31", 1581262000),
        ("LYB", "2015-12-31", 7052000000),
    ],
)
def test_complete_whole_company_cost_labels_preserve_manufacturing_inputs(
    symbol, end, expected
):
    assert D(extract_period(parse_report(report(symbol))[end])["value"]) == expected


def test_pharmacy_products_do_not_cover_insurance_benefits():
    assert "value" not in extract_period(parse_report(report("ELV"))["2019-12-31"])


def test_unallocated_xerox_intangibles_are_not_assigned_to_production_or_ignored():
    rows = parse_report(report("XRX"))["2015-12-31"]
    result = extract_period(rows, "0000108772")
    assert result["status"] == "filed_cost_excludes_unallocated_expenses"


def test_scoped_administrative_depreciation_does_not_reduce_production_twice():
    rows = parse_report(report("VLO"))["2018-12-31"]
    # The actual source additionally has $45m of unspecified other operating
    # expenses. Its administrative allocation alone does not certify full GP.
    assert (
        extract_period(rows, "0001035002")["status"]
        == "unclassified_filed_operating_expense"
    )
    # Isolate the explicit administrative allocation by removing that unrelated
    # expense and adjusting the filed operating total by the same amount.
    rows = [
        {**r, "value": "0"}
        if r["concept"] == "us-gaap_OtherCostAndExpenseOperating"
        else {**r, "value": str(D(r["value"]) + 45000000)}
        if r["concept"] == "us-gaap_OperatingIncomeLoss"
        else r
        for r in rows
    ]
    result = extract_period(rows, "0001035002")
    assert D(result["value"]) == 5594000000
    assert D(result["cost"]) == 111439000000


@pytest.mark.parametrize(
    "symbol,cik,status",
    [
        ("AMZN", "0001018724", "unclassified_filed_operating_expense"),
        ("PFE", "0000078003", "filed_cost_excludes_unallocated_expenses"),
        ("ZTS", "0001555280", "filed_cost_excludes_unallocated_expenses"),
        ("ITW", "0000049826", "filed_cost_excludes_unallocated_expenses"),
    ],
)
def test_aggregate_tag_and_company_cost_label_do_not_hide_residual_expenses(
    symbol, cik, status
):
    raw = (FIXTURES / f"{symbol}-residual-income.htm").read_bytes()
    rows = parse_report(raw)["2016-12-31"]
    assert extract_period(rows, cik)["status"] == status
    if symbol == "AMZN":
        # An explicit-looking "total" label cannot erase the source's separately
        # presented fulfillment and technology/content expense functions.
        changed = [
            {**r, "label": "Total cost of revenues"}
            if r["concept"] == "us-gaap_CostOfGoodsAndServicesSold"
            else r
            for r in rows
        ]
        assert "value" not in extract_period(changed, cik)


def test_nonrecurring_keyword_does_not_classify_explicit_production_as_overhead():
    from aperture.profitability_scope import nonproduction

    row = {
        "concept": "custom_AcquisitionRelatedProductionCosts",
        "label": "Acquisition-related production costs",
        "value": "20",
        "scope": None,
    }
    assert not nonproduction(row, [row], None)


def test_parallel_accessions_keep_independent_evidence_and_reuse_the_cache(tmp_path):
    import threading
    from dataclasses import replace

    import httpx
    from aperture.config import Settings
    from aperture.fundamentals import filing_available
    from aperture.providers import Provider
    from aperture.store import Store

    capture = json.loads((FIXTURES / "TMO.json").read_text())
    rows, _ = normalize(
        "TMO", "0000097745", capture["company"], {"entityType": "operating"}
    )
    first = next(r for r in rows if str(r.end) == "2016-12-31")
    second = replace(
        first,
        accession="0000097745-17-000008",
        filed=date(2017, 3, 1),
        available_at=filing_available(date(2017, 3, 1)),
    )
    barrier = threading.Barrier(2)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if str(request.url).endswith("FilingSummary.xml"):
            barrier.wait(timeout=5)
            return httpx.Response(
                200,
                content=b"<FilingSummary><MyReports><Report><MenuCategory>Statements</MenuCategory><ShortName>Consolidated Statements of Income</ShortName><HtmlFileName>R2.htm</HtmlFileName></Report></MyReports></FilingSummary>",
            )
        return httpx.Response(200, content=report("TMO"))

    store = Store(tmp_path / "parallel.sqlite3")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        api = Provider(
            store, client, Settings(sec_agent="Source tests contact@example.com")
        )
        result = enrich((first, second), api, date(2017, 3, 1), date(2017, 3, 3))
        assert [r.gross_profit for r in result] == [D(8369100000)] * 2
        assert len(calls) == 4
        from aperture.profitability_filings import VERSION

        for row in (first, second):
            saved = store.filing_evidence(f"{VERSION}:{row.cik}:{row.accession}")
            assert len(saved["sources"]) == 2
            assert all(
                row.accession.replace("-", "") in s["resource"]
                for s in saved["sources"]
            )
        again = enrich((first, second), api, date(2017, 3, 1), date(2017, 3, 3))
        assert result == again and len(calls) == 4


def test_homebuilding_total_cost_does_not_omit_separate_financial_services():
    rows = parse_report(report("PHM"))["2015-12-31"]
    value = extract_period(rows, "0000822416")
    assert D(value["value"]) == 1423166000
    assert D(value["cost"]) == D(4476751000) + D(82047000)
    assert D(value["revenue"]) == 5981964000


def test_body_colspan_keeps_annual_amounts_aligned_with_footnote_columns():
    periods = parse_report(report("TGT"))
    expected = {
        "2019-02-02": 75356000000,
        "2018-02-03": 72714000000,
        "2017-01-28": 70271000000,
    }
    for end, revenue in expected.items():
        row = next(r for r in periods[end] if r["label"] == "Total revenue")
        assert D(row["value"]) == revenue and row["scope"] is None
