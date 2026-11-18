"""Complete expense scope and source-role regressions, separate from ranking."""

from aperture.profitability_scope import verify
from aperture.profitability_filings import extract_period, parse_report
from filing_fixtures import income_report


def line(concept, label, value):
    return {"concept": concept, "label": label, "value": str(value), "scope": None}


def financing_statement():
    # Independently specified company accounting: revenue 100, production 45,
    # administrative expense 10, operating income 45 and gross profit 55.
    rows = [
        line("us-gaap_Revenues", "Total revenue", 100),
        line("us-gaap_CostOfGoodsSold", "Product cost", 40),
        line("us-gaap_FinancingInterestExpense", "Financing interest cost", 5),
        line(
            "us-gaap_SellingGeneralAndAdministrativeExpense",
            "Administrative expenses",
            10,
        ),
        line("us-gaap_OperatingIncomeLoss", "Operating income", 45),
    ]
    evidence = {
        "method": "filed_reconciled_entity_components",
        "value": "55",
        "revenue": "100",
        "cost": "45",
        "components": {
            "us-gaap_SalesRevenueGoodsNet": ["80", "40"],
            "us-gaap_InterestIncomeOperating": ["20", "5"],
        },
    }
    return rows, evidence


def test_matched_financing_production_cost_is_not_classified_as_overhead():
    rows, evidence = financing_statement()
    result = verify(rows, evidence, None)
    assert result["value"] == "55"
    assert result["total_expenses"] == "55"
    assert [r["concept"] for r in result["nonproduction_terms"]] == [
        "us-gaap_SellingGeneralAndAdministrativeExpense"
    ]
    # A changed mapped financing cost cannot become a generic interest expense.
    rows[2]["value"] = "6"
    rows[-1]["value"] = "39"
    assert "value" not in verify(rows, evidence, None)


def test_expense_subtotal_cannot_hide_a_later_production_expense():
    rows, evidence = financing_statement()
    rows[-1:-1] = [
        line("us-gaap_CostsAndExpenses", "Total costs and expenses", 55),
        line("custom_Fulfillment", "Fulfillment", 20),
    ]
    rows[-1]["value"] = "25"
    assert (
        verify(rows, evidence, None)["status"] == "unclassified_filed_operating_expense"
    )
    # The same boundary must cover the otherwise reconciled expense-section
    # route, not only the component/aggregate fallback paths.
    ordinary = [
        line("us-gaap_Revenues", "Total revenue", 100),
        line("us-gaap_CostOfRevenue", "Cost of revenue", 45),
        *rows[3:],
    ]
    assert extract_period(ordinary)["status"] == "unclassified_filed_operating_expense"


def test_isolated_revenue_and_cost_table_does_not_certify_complete_scope():
    rows = parse_report(income_report())["2022-12-31"]
    assert extract_period(rows)["value"] == "40"
    assert "value" not in extract_period(rows[:-1])


def test_financial_revenue_does_not_make_generic_interest_an_overhead_cost():
    rows = [
        line("us-gaap_SalesRevenueGoodsNet", "Product revenue", 80),
        line("us-gaap_FinancialServicesRevenue", "Financial services revenue", 20),
        line("us-gaap_Revenues", "Total revenue", 100),
        line("us-gaap_CostOfGoodsSold", "Cost of goods sold", 40),
        line("us-gaap_InterestExpense", "Interest expense", 5),
        line(
            "us-gaap_SellingGeneralAndAdministrativeExpense",
            "Administrative expenses",
            10,
        ),
        line("us-gaap_OperatingIncomeLoss", "Operating income", 45),
    ]
    assert extract_period(rows)["status"] == "unverified_financing_cost_scope"
    # A source-specific production element is positive allocation evidence.
    rows[4]["concept"] = "us-gaap_FinancingInterestExpense"
    assert extract_period(rows)["value"] == "55"
