"""Require complete expense scope before a cost-line fallback can supply GP.

A company-labelled CostOfRevenue line can omit a service business, fulfillment
or unallocated intangibles. Neither its tag nor arithmetic alone proves scope.
Every remaining expense needs a supported role and the complete section must
reconcile without inferring a missing production amount from profit.
"""

import re
from decimal import Decimal
from itertools import product

from .profitability_expenses import (
    AMORTIZATION,
    COST_LABEL,
    NONPRODUCTION,
    display_unit,
    rounded_equal,
    separately_allocated_target_depreciation,
)

PAIRS = {
    "us-gaap_SalesRevenueGoodsNet": "us-gaap_CostOfGoodsSold",
    "us-gaap_SalesRevenueServicesNet": "us-gaap_CostOfServices",
    "us-gaap_RealEstateRevenueNet": "us-gaap_CostOfRealEstateRevenue",
    "us-gaap_FinancialServicesRevenue": "us-gaap_FinancialServicesCosts",
    "us-gaap_CapitalLeasesIncomeStatementLeaseRevenue": "us-gaap_FinancialServicesCosts",
    "us-gaap_InterestIncomeOperating": "us-gaap_FinancingInterestExpense",
    "chrw_TransportationServicesRevenue": "chrw_CostOfPurchasedTransportationAndRelatedServices",
}


def collapse_administrative_subtotal(rows):
    """Use an explicit administrative subtotal when all its children reconcile."""
    for end, row in enumerate(rows):
        if (
            row["scope"] is not None
            or row["concept"] != "us-gaap_SellingGeneralAndAdministrativeExpense"
            or row["label"].lower().rstrip(":") != "total administrative expenses"
        ):
            continue
        begin = next(
            (
                i + 1
                for i in range(end - 1, -1, -1)
                if rows[i]["scope"] is None
                and rows[i]["concept"] == "us-gaap_CostOfRevenue"
                and rows[i]["label"].lower().rstrip(":")
                in {"total cost of revenue", "total cost of revenues"}
            ),
            end,
        )
        details = rows[begin:end]
        tags = NONPRODUCTION | {
            "MarketingExpense",
            "DepreciationAndAmortization",
        }
        if (
            details
            and all(
                item["scope"] is None
                and item["concept"].removeprefix("us-gaap_") in tags
                for item in details
            )
            and sum(Decimal(item["value"]) for item in details) == Decimal(row["value"])
        ):
            return rows[:begin] + rows[end:]
    return rows


def boundary(row):
    tag = row["concept"].removeprefix("us-gaap_")
    label = re.sub(r"[,():]", "", row["label"].lower()).strip()
    if tag == "OperatingIncomeLoss":
        return "income"
    if tag == "CostsAndExpenses" or re.fullmatch(
        r"(?:total )?(?:operating )?costs?(?: and)? expenses(?: and other(?: net)?)?(?: total)?",
        label,
    ):
        return "expenses"
    if tag.endswith("CostOfSalesOperatingExpensesAndOtherNet"):
        return "expenses"
    if "BeforeIncomeTax" in tag or re.fullmatch(
        r"(?:total )?(?:income|earnings|loss|income loss) before (?:income )?taxes",
        label,
    ):
        return "income"
    return None


def nonproduction(row, entity, cik):
    tag = row["concept"].removeprefix("us-gaap_")
    label = row["label"].lower()
    if separately_allocated_target_depreciation(row, entity, cik):
        return True
    if tag in NONPRODUCTION | {
        "MarketingExpense",
        "OtherNonrecurringIncomeExpense",
        "OtherRestructuringCosts",
        "IncomeLossFromEquityMethodInvestments",
        "InterestRevenueExpenseNet",
        "InterestAndDebtExpense",
        "InterestAndOtherIncome",
        "OtherIncome",
        "OtherOperatingIncome",
        "NetPeriodicDefinedBenefitsExpenseReversalOfExpenseExcludingServiceCostComponent",
        "BusinessCombinationContingentConsiderationArrangementsChangeInAmountOfContingentConsiderationLiability1",
        "GainLossOnSaleOfProperties",
        "GainLossOnDispositionOfAssets1",
    }:
        return True
    if cik == "0001043277" and tag == "LaborAndRelatedExpense":
        return True
    if cik == "0001137789" and tag.lower() == (
        "stx_amortizationofintangibleassetsexcludingamountincludedincostofrevenue"
    ):
        return True
    if (
        cik == "0000202058"
        and tag == "OperatingExpenses"
        and label == ("engineering, selling and administrative expenses")
    ):
        return True
    if tag == "AmortizationOfIntangibleAssets" and "other acquired" in label:
        return any(
            r["concept"].removeprefix("us-gaap_") in AMORTIZATION for r in entity
        )
    if tag in {
        "DepreciationAndAmortization",
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
        "AmortizationOfIntangibleAssets",
    }:
        matches = [
            i
            for i, original in enumerate(entity)
            if original["concept"] == row["concept"]
            and original["label"] == row["label"]
            and Decimal(original["value"])
            == Decimal(row.get("source_value", row["value"]))
        ]
        i = matches[0] if len(matches) == 1 else -1
        if (
            i > 0
            and entity[i - 1]["concept"]
            in {
                "us-gaap_SellingGeneralAndAdministrativeExpense",
                "us-gaap_GeneralAndAdministrativeExpense",
            }
            and re.search(
                r"exclud[^)]*(?:depreciation|amortization)",
                entity[i - 1]["label"],
                re.IGNORECASE,
            )
        ):
            return True
    # These are separately presented nonrecurring expenses or R&D/overhead,
    # consistent with the existing derived metric. Ordinary D&A/intangibles
    # never inherit an acquisition/impairment keyword exception.
    terms = tag + " " + label
    if re.search(
        r"gain.*(?:sale|dispos).*(?:facility|business|subsidiar|property.*equipment)",
        terms,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"production|manufactur|fulfill|medical|pharmacy|royalt|costof(?:sales|revenue|goods|services)|cost of (?:sales|revenue|goods|services)",
        terms,
        re.IGNORECASE,
    ):
        return False
    if re.search(r"Nonoperating|InterestExpense|InterestIncome|InvestmentIncome", tag):
        return True
    if re.search(r"\bfines\b", label) or tag.lower().endswith("_acquirediprd"):
        return True
    return not re.search(r"amortiz|depreciat", terms, re.IGNORECASE) and bool(
        re.search(
            r"restructur|impairment|acquisition|integration|research.{0,20}development",
            terms,
            re.IGNORECASE,
        )
    )


def amounts(row):
    """Source-typed nonproduction credits can use either display convention.

    This never changes the production numerator. The complete source subtotals
    must reconcile using one consistent selection of these displayed credits.
    """
    value = Decimal(row["value"])
    if re.search(r"Income|Interest|GainLoss|RevenueExpenseNet", row["concept"]):
        return (value, -value) if value else (value,)
    return (value,)


def verify(rows, evidence, cik):
    """Verify a fallback's residual scope; do not create or change its cost."""
    entity = [r for r in rows if r["scope"] is None]
    revenue, cost = Decimal(evidence["revenue"]), Decimal(evidence["cost"])
    anchors = [
        i
        for i, r in enumerate(entity)
        if Decimal(r["value"]) == revenue
        and re.search(r"revenue|sales", r["label"], re.IGNORECASE)
    ]
    if not anchors:
        return {"status": "unsupported_filed_expense_scope"}
    begin = anchors[-1]
    financial_revenue = any(
        r["concept"].removeprefix("us-gaap_")
        in {
            "FinancialServicesRevenue",
            "InterestIncomeOperating",
            "CapitalLeasesIncomeStatementLeaseRevenue",
        }
        and Decimal(r["value"]) != 0
        for r in entity[: begin + 1]
    )
    end = next(
        (i for i in range(begin + 1, len(entity)) if boundary(entity[i]) == "income"),
        None,
    )
    if end is None:
        return {"status": "unsupported_filed_expense_scope"}
    total = Decimal(entity[end]["value"])
    total = revenue - total
    body = entity[begin + 1 : end]
    known_costs = {
        (tag if "_" in tag else "us-gaap_" + tag): Decimal(value)
        for tag, value in evidence.get("production_components", {}).items()
    }
    for revenue_tag, values in evidence.get("components", {}).items():
        if revenue_tag in PAIRS:
            known_costs[PAIRS[revenue_tag]] = Decimal(values[1])
    if evidence.get("additional_production_amortization"):
        for row in body:
            if row["concept"].removeprefix("us-gaap_") in AMORTIZATION:
                known_costs[row["concept"]] = Decimal(row["value"])
    direction = Decimal(1)
    if evidence["method"] == "filed_reconciled_expense_section":
        direction = Decimal(evidence.get("expense_display_direction", "1"))
        if direction not in {Decimal(1), Decimal(-1)} or not all(
            Decimal(r["value"]) * direction == known_costs[r["concept"]]
            for r in body
            if r["concept"] in known_costs
        ):
            return {"status": "unsupported_filed_expense_scope"}
    body = [
        {**r, "source_value": r["value"], "value": str(Decimal(r["value"]) * direction)}
        for r in body
    ]
    # An entity subtotal equal to the already reconciled component cost is a
    # parent, not an additional cost. A total-cost fallback needs its exact row.
    parent_values = {cost}
    if evidence.get("components"):
        parent_values.add(sum(Decimal(v[1]) for v in evidence["components"].values()))
    parent_rows = [
        i
        for i, r in enumerate(body)
        if Decimal(r["value"]) in parent_values
        and (
            r["concept"]
            in {
                "us-gaap_CostOfRevenue",
                "us-gaap_CostOfGoodsAndServicesSold",
                "us-gaap_CostOfGoodsSold",
                "us-gaap_CostOfServices",
            }
            or re.fullmatch(COST_LABEL, r["label"].lower().rstrip(":"))
        )
    ]
    parent = parent_rows[-1] if parent_rows else None
    prefix = set()
    if (
        parent is not None
        and re.match(r"total costs?(?: of)?\b", body[parent]["label"], re.IGNORECASE)
        and all(Decimal(r["value"]) >= 0 for r in body[:parent])
        and sum(Decimal(r["value"]) for r in body[:parent])
        == Decimal(body[parent]["value"])
    ):
        prefix = set(range(parent))
    real_estate_children = {
        "us-gaap_HomeBuildingCosts",
        "us-gaap_CostsOfRealEstateServicesAndLandSales",
    }
    property_cost = known_costs.get("us-gaap_CostOfRealEstateRevenue")
    children_rows = [r for r in body if r["concept"] in real_estate_children]
    property_partition = (
        property_cost is not None
        and {r["concept"] for r in children_rows} == real_estate_children
        and sum(Decimal(r["value"]) for r in children_rows) == property_cost
    )
    other = []
    other_rows = []
    checkpoints = []
    production_seen = parent is not None
    for i, row in enumerate(body):
        value = Decimal(row["value"])
        if value == 0:
            continue
        tag = row["concept"]
        if boundary(row) == "expenses":
            checkpoints.append((len(other), value, display_unit(row)))
            continue
        if i in prefix:
            production_seen = True
            continue
        if property_partition and tag in real_estate_children:
            production_seen = True
            continue
        if tag in known_costs and value != known_costs[tag]:
            return {"status": "filed_expense_section_does_not_reconcile"}
        if i == parent or tag in known_costs:
            production_seen = True
            continue
        if (
            financial_revenue
            and re.search(r"Interest.*Expense", tag)
            and not {
                "us-gaap_FinancialServicesCosts",
                "us-gaap_FinancingInterestExpense",
            }
            & known_costs.keys()
        ):
            return {"status": "unverified_financing_cost_scope"}
        if nonproduction(row, entity, cik):
            other.append(amounts(row))
            other_rows.append(row)
            continue
        # Parent/child commodity/service costs can be displayed together. The
        # source must put children before an explicit total, and their complete
        # known partition must reconcile; an unrelated lower cost is not enough.
        children = [
            r
            for r in body[:parent]
            if r["concept"] in {"us-gaap_CostOfGoodsSold", "us-gaap_CostOfServices"}
        ]
        if (
            parent is not None
            and i < parent
            and row in children
            and body[parent]["label"].lower().startswith("total ")
            and sum(Decimal(r["value"]) for r in children) == cost
        ):
            production_seen = True
            continue
        if re.search(r"depreciat|amortiz", tag + " " + row["label"], re.IGNORECASE):
            return {"status": "filed_cost_excludes_unallocated_expenses"}
        return {"status": "unclassified_filed_operating_expense"}
    if evidence["method"] == "filed_reconciled_product_service_costs":
        production_seen = True  # Explicit supported dimensions supply it.
    if not production_seen:
        return {"status": "unsupported_filed_expense_scope"}
    # Reject excessive ambiguity rather than searching unbounded sign choices.
    if sum(len(v) > 1 for v in other) > 8:
        return {"status": "unsupported_filed_expense_scope"}
    cost_units = [
        Decimal(unit) for unit in evidence.get("production_display_units", ())
    ]
    # Only the supported rounded product/service partition carries a precision
    # budget. All other routes continue to require exact displayed totals.
    term_units = [display_unit(row) for row in other_rows] if cost_units else []
    total_units = (
        [display_unit(entity[begin]), display_unit(entity[end])] if cost_units else []
    )
    chosen = next(
        (
            chosen
            for chosen in product(*other)
            if rounded_equal(
                cost + sum(chosen), total, cost_units + term_units + total_units
            )
            and all(
                rounded_equal(
                    cost + sum(chosen[:n]),
                    subtotal,
                    cost_units + term_units[:n] + ([unit] if cost_units else []),
                )
                for n, subtotal, unit in checkpoints
            )
        ),
        None,
    )
    if chosen is None:
        return {"status": "filed_expense_section_does_not_reconcile"}
    return {
        **evidence,
        "residual_expense_scope_verified": True,
        "total_expenses": str(total),
        "expense_reconciliation_difference": str(cost + sum(chosen) - total),
        "expense_display_direction": str(direction),
        "scope_end": {k: entity[end][k] for k in ("concept", "label", "value")},
        "nonproduction_terms": [
            {
                "concept": row["concept"],
                "label": row["label"],
                "source_value": row["source_value"],
                "reconciliation_value": str(value),
            }
            for row, value in zip(other_rows, chosen, strict=True)
        ],
    }
