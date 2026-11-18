"""Source-backed regressions for B-039's omitted-expense ranking errors."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest
from aperture.fundamentals import normalize
from aperture.profitability import extract

FIXTURES = Path(__file__).parent / "fixtures" / "profitability"


@pytest.mark.parametrize("symbol", ["CNC", "ORCL", "AMT"])
def test_incomplete_service_costs_do_not_admit_the_reviewed_issuers(symbol):
    capture = json.loads((FIXTURES / f"{symbol}.json").read_text())
    company = capture["company"]
    rows, _ = normalize(
        symbol, str(company["cik"]).zfill(10), company, {"entityType": "operating"}
    )
    row = next(r for r in rows if r.accession == capture["accession"])
    assert row.gross_profit is None
    assert row.sources["profitability_status"] == "partial_cost"
    assert any("does not reconcile" in issue for issue in row.issues)


def test_reviewed_tmo_service_cost_correction_survives():
    capture = json.loads((FIXTURES / "TMO.json").read_text())
    rows, _ = normalize(
        "TMO", "0000097745", capture["company"], {"entityType": "operating"}
    )
    row = next(r for r in rows if r.accession == capture["accession"])
    assert row.gross_profit == D(8369100000)
    assert row.sources["profitability_status"] == "reconciled_components"


def test_apparent_aggregate_cannot_be_smaller_than_reported_component():
    gross, sources, _ = extract(
        {
            "Revenues": {D(10855810000)},
            "CostOfRevenue": {D(40439000)},
            "CostOfServices": {D(7082932000)},
        }
    )
    assert gross is None
    assert sources["profitability_status"] == "partial_cost"


def test_goods_revenue_without_company_total_is_not_synthesized():
    gross, sources, _ = extract(
        {"SalesRevenueGoodsNet": {D(100)}, "CostOfGoodsSold": {D(40)}}
    )
    assert gross is None
    assert sources["profitability_status"] == "unverified_total_revenue"


def test_missing_opposite_tag_does_not_prove_pure_service_business():
    gross, sources, _ = extract({"Revenues": {D(6000)}, "CostOfServices": {D(2500)}})
    assert gross is None
    assert sources["profitability_status"] == "partial_cost"


def test_explicit_zero_goods_revenue_allows_complete_service_partition():
    gross, _, _ = extract(
        {
            "Revenues": {D(6000)},
            "SalesRevenueGoodsNet": {D(0)},
            "SalesRevenueServicesNet": {D(6000)},
            "CostOfServices": {D(2500)},
        }
    )
    assert gross == 3500


def test_ambiguous_component_does_not_fall_back_to_smaller_expenses():
    gross, sources, _ = extract(
        {
            "Revenues": {D(100)},
            "SalesRevenueGoodsNet": {D(60)},
            "SalesRevenueServicesNet": {D(40)},
            "CostOfGoodsSold": {D(25)},
            "CostOfServices": {D(10), D(30)},
        }
    )
    assert gross is None
    assert sources["profitability_status"] == "conflicting_facts"


def test_newer_missing_annual_inputs_do_not_reuse_an_older_complete_year():
    from datetime import date

    from aperture.fundamentals import as_of

    capture = json.loads((FIXTURES / "TMO.json").read_text())
    company = capture["company"]
    # Earlier complete period is present, but the new filing provides assets
    # and incomplete service costs with no compatible EPS. Retain that missing
    # period so as_of cannot silently carry the old favorable numerator ahead.
    facts = company["facts"]["us-gaap"]
    for tag, body in list(facts.items()):
        if tag not in {"Assets", "Revenues", "CostOfServices"}:
            continue
        prior = body["units"]["USD"][0]
        new = {
            **prior,
            "accn": "0000097745-18-000001",
            "filed": "2018-02-01",
            "end": "2017-12-31",
        }
        if tag != "Assets":
            new["start"] = "2017-01-01"
        body["units"]["USD"].append(new)
    rows, _ = normalize("TMO", "0000097745", company, {"entityType": "operating"})
    latest = as_of(rows, date(2018, 3, 1))
    assert latest.end == date(2017, 12, 31)
    assert latest.gross_profit is None


def test_financial_presentation_is_identified_by_matched_facts_not_sector():
    gross, sources, issues = extract(
        {
            "Revenues": {D(100)},
            "InterestIncomeExpenseNet": {D(40)},
            "NoninterestExpense": {D(30)},
        }
    )
    assert gross is None
    assert sources["profitability_presentation"] == "interest_and_noninterest"
    assert sources["profitability_status"] == "unsupported_structured_presentation"
    assert "not applicable" not in " ".join(issues)
    # A bank can still supply explicit gross profit; the presentation marker
    # does not override an economically supported reported numerator.
    gross, sources, _ = extract(
        {
            "GrossProfit": {D(50)},
            "InterestIncomeExpenseNet": {D(40)},
            "NoninterestExpense": {D(30)},
        }
    )
    assert gross == 50
    assert sources["profitability_status"] == "reported"


def test_different_revenue_measures_require_company_total_from_filing():
    gross, sources, _ = extract(
        {
            "Revenues": {D(100)},
            "RevenueFromContractWithCustomerExcludingAssessedTax": {D(80)},
            "CostOfRevenue": {D(60)},
        }
    )
    assert gross is None
    assert sources["profitability_status"] == "ambiguous_total_revenue"


def test_two_different_aggregate_cost_tags_do_not_choose_the_smaller_one():
    gross, sources, _ = extract(
        {
            "Revenues": {D(100)},
            "CostOfRevenue": {D(40)},
            "CostOfGoodsAndServicesSold": {D(60)},
        }
    )
    assert gross is None
    assert sources["profitability_status"] == "ambiguous_aggregate_cost"


def test_aggregate_cost_cannot_omit_part_of_the_combined_components():
    gross, sources, _ = extract(
        {
            "Revenues": {D(100)},
            "CostOfRevenue": {D(60)},
            "CostOfGoodsSold": {D(40)},
            "CostOfServices": {D(30)},
        }
    )
    assert gross is None
    assert sources["profitability_status"] == "partial_cost"


def test_revenue_only_new_annual_filing_does_not_expose_an_older_factor():
    from datetime import date

    from aperture.fundamentals import as_of

    capture = json.loads((FIXTURES / "TMO.json").read_text())
    company = capture["company"]
    prior = company["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    company["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(
        {
            **prior,
            "accn": "0000097745-18-000001",
            "filed": "2018-02-01",
            "start": "2017-01-01",
            "end": "2017-12-31",
        }
    )
    rows, _ = normalize("TMO", "0000097745", company, {"entityType": "operating"})
    latest = as_of(rows, date(2018, 3, 1))
    assert latest.end == date(2017, 12, 31)
    assert latest.gross_profit is None and latest.assets is None and latest.eps is None
