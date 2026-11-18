"""Verify explicit production costs against a complete filed expense section.

Operating income is a reconciliation check only. It never supplies an unknown
cost or substitutes for gross profit. Unclassified expense lines fail closed.
"""

import re
from decimal import Decimal

from .domain import ZERO

AMORTIZATION = {
    "CostOfGoodsAndServicesSoldAmortization",
    "CostOfGoodsSoldDepreciationDepletionAndAmortization",
    "CostOfGoodsAndServicesSoldDepreciationAndAmortization",
    "CostOfServicesDepreciationAndAmortization",
    "CostOfServicesDepreciation",
}
COST_LABEL = r"(?:total )?cost(?:s)? of (?:net )?(?:revenues?|sales|(?:goods|products)(?: and services)?(?: sold)?)(?:(?:, ?| \()(?:including|includes|notes?)\b.*)?"

PRODUCTION = {
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "CostOfGoodsSold",
    "CostOfServices",
    "CostOfGoodsAndServicesSoldAmortization",
    "CostOfGoodsSoldDepreciationDepletionAndAmortization",
    "CostOfGoodsAndServicesSoldDepreciationAndAmortization",
    "CostOfServicesDepreciationAndAmortization",
    "CostOfServicesDepreciation",
    "CostOfGoodsSoldDepreciation",
    "FinancialServicesCosts",
    "FinancingInterestExpense",
    "DirectOperatingCostRoyaltyExpense",
}
NONPRODUCTION = {
    "InterestExpense",
    "InterestIncomeExpenseNet",
    "InterestIncomeExpenseNonoperatingNet",
    "PreOpeningCosts",
    "SellingGeneralAndAdministrativeExpense",
    "SellingGeneralAndAdministrativeExpenseExcludingDepreciationAmortizationAndNetGainLossOnDispositionOfPropertyPlantEquipment",
    "SellingAndMarketingExpense",
    "SellingExpense",
    "GeneralAndAdministrativeExpense",
    "OtherSellingGeneralAndAdministrativeExpense",
    "ResearchAndDevelopmentExpense",
    "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost",
    "ResearchAndDevelopmentAssetAcquiredOtherThanThroughBusinessCombinationWrittenOff",
    "ResearchAndDevelopmentInProcess",
    "RestructuringCharges",
    "RestructuringAndRelatedCostIncurredCost",
    "RestructuringSettlementAndImpairmentProvisions",
    "GoodwillImpairmentLoss",
    "BusinessCombinationAcquisitionRelatedCosts",
    "BusinessCombinationIntegrationRelatedCosts",
}


def display_unit(row):
    return (
        Decimal(row.get("display_unit", "0"))
        if Decimal(row.get("value", "0"))
        else ZERO
    )


def rounded_equal(left, right, units):
    """Compare a displayed total within its inputs' combined rounding bound."""
    return left == right or abs(left - right) <= sum(units) / 2


def separately_allocated_target_depreciation(row, rows, cik):
    """Target explicitly includes its supply-chain depreciation in cost of sales."""
    return (
        cik == "0000027419"
        and row["concept"] == "us-gaap_DepreciationAndAmortization"
        and row["label"].lower().rstrip(":")
        == "depreciation and amortization (exclusive of depreciation included in cost of sales)"
        and any(
            item["concept"] == "us-gaap_CostOfGoodsAndServicesSold"
            and item["label"].lower().rstrip(":") == "cost of sales"
            for item in rows
        )
    )


def extract(rows, revenue, cik=None):
    """All explicit expense lines must reconcile before accepting cost coverage."""
    anchors = [
        i
        for i, r in enumerate(rows)
        if Decimal(r["value"]) == revenue
        and ("revenue" in r["label"].lower() or "sales" in r["label"].lower())
    ]
    if not anchors:
        return None
    begin = anchors[-1]
    end = next(
        (
            i
            for i in range(begin + 1, len(rows))
            if rows[i]["concept"]
            in {"us-gaap_OperatingIncomeLoss", "us-gaap_CostsAndExpenses"}
        ),
        None,
    )
    if end is None:
        if cik == "0000822416":
            return homebuilder_section(rows, revenue, begin)
        return None
    total_row = rows[end]
    total = Decimal(total_row["value"])
    if total_row["concept"] == "us-gaap_OperatingIncomeLoss":
        total = revenue - total
    elif total < ZERO:
        total = -total
    expenses = rows[begin + 1 : end]
    if not expenses:
        return None
    if not any(
        r["concept"].removeprefix("us-gaap_")
        in {
            "CostOfRevenue",
            "CostOfGoodsAndServicesSold",
            "CostOfGoodsSold",
            "CostOfServices",
        }
        for r in expenses
    ):
        return None  # Production amounts may instead be in supported dimensions.
    explicit_total = any(
        re.fullmatch(
            r"total costs? of (?:net )?(?:revenues?|sales)",
            r["label"].lower().rstrip(":"),
        )
        for r in expenses
    )
    production = PRODUCTION | (
        {"regn_Costofmanufacturing"}
        if cik == "0000872589"
        else {"abt_AmortizationOfIntangibleAssetsExcludingDiscontinuedOperations"}
        if cik == "0000001800"
        and any("excluding amortization" in r["label"].lower() for r in rows)
        else set()
    )
    if cik == "0001043277":
        production |= {"chrw_CostOfPurchasedTransportationAndRelatedServices"}
    nonproduction = NONPRODUCTION | (
        {"LaborAndRelatedExpense"} if cik == "0001043277" else set()
    )
    if cik == "0001137789":
        nonproduction |= {
            r["concept"]
            for r in expenses
            if r["concept"].lower()
            == "stx_amortizationofintangibleassetsexcludingamountincludedincostofrevenue"
        }
    if cik == "0000202058" and any(
        r["concept"] == "us-gaap_OperatingExpenses"
        and r["label"].lower() == "engineering, selling and administrative expenses"
        for r in expenses
    ):
        nonproduction.add("OperatingExpenses")
    classified = []
    for row in expenses:
        tag = row["concept"].removeprefix("us-gaap_")
        if separately_allocated_target_depreciation(row, expenses, cik):
            classified.append((tag, Decimal(row["value"])))
            continue
        if tag not in production | nonproduction:
            if Decimal(row["value"]) == ZERO:
                continue
            if tag in {
                "DepreciationAndAmortization",
                "DepreciationDepletionAndAmortization",
                "DepreciationAmortizationAndAccretionNet",
                "AmortizationOfIntangibleAssets",
            } or re.search(
                r"depreciat|amortiz", row["concept"] + " " + row["label"], re.IGNORECASE
            ):
                return {"status": "filed_cost_excludes_unallocated_expenses"}
            if explicit_total or re.search(
                r"restructur|integrat|acquisit|disposit|transform|separat|research|development",
                row["concept"] + " " + row["label"],
                re.IGNORECASE,
            ):
                return None
            if re.search(
                r"cost|manufactur", row["concept"] + " " + row["label"], re.IGNORECASE
            ):
                return {"status": "unclassified_filed_production_expense"}
            return None
        classified.append((tag, Decimal(row["value"])))
    # Preserve a reported expense-credit sign. Reverse a display convention
    # only when every expense and the total reconcile under that reversal.
    signed = sum(v for _, v in classified)
    direction = (
        Decimal(1)
        if signed == total
        else Decimal(-1)
        if signed == -total and all(v <= ZERO for _, v in classified)
        else None
    )
    if direction is None:
        tags = {tag for tag, _ in classified}
        if tags & {"CostOfRevenue", "CostOfGoodsAndServicesSold"} and tags & {
            "CostOfGoodsSold",
            "CostOfServices",
            "CostOfServicesDepreciation",
            "CostOfServicesDepreciationAndAmortization",
            "CostOfGoodsAndServicesSoldDepreciationAndAmortization",
        }:
            return None  # A displayed parent/child hierarchy needs its subtotal path.
        return {"status": "filed_expense_section_does_not_reconcile"}
    costs = [(tag, v * direction) for tag, v in classified if tag in production]
    if not costs or any(v < ZERO for _, v in costs):
        return None
    # An aggregate and its components could otherwise double-count costs even
    # if an unrelated coincidental total happened to reconcile.
    tags = {tag for tag, _ in costs}
    if tags & {"CostOfRevenue", "CostOfGoodsAndServicesSold"} and tags & {
        "CostOfGoodsSold",
        "CostOfServices",
    }:
        return None
    cost = sum(v for _, v in costs)
    return {
        "value": str(revenue - cost),
        "method": "filed_reconciled_expense_section",
        "revenue": str(revenue),
        "cost": str(cost),
        "total_expenses": str(total),
        "production_components": {tag: str(v) for tag, v in costs},
        "expense_section_reconciled": True,
        "expense_display_direction": str(direction),
    }


def homebuilder_section(rows, revenue, begin):
    """Pulte's matched homebuilding/finance costs, including signed displays.

    The primary statement separately reports both businesses and the complete
    expense section. The pretax subtotal checks display direction only; no
    missing production cost is inferred from earnings.
    """
    end = next(
        (
            i
            for i in range(begin + 1, len(rows))
            if rows[i]["concept"]
            == "us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic"
        ),
        None,
    )
    if end is None:
        return None
    values = {}
    for r in rows[:end]:
        tag = r["concept"].removeprefix("us-gaap_")
        if tag in values:
            return {"status": "filed_expense_section_does_not_reconcile"}
        values[tag] = Decimal(r["value"])
    production = {"CostOfRealEstateRevenue", "FinancialServicesCosts"}
    children = {"HomeBuildingCosts", "CostsOfRealEstateServicesAndLandSales"}
    nonproduction = {
        "SellingGeneralAndAdministrativeExpense",
        "OtherNonoperatingIncomeExpense",
    }
    expense_rows = {
        r["concept"].removeprefix("us-gaap_") for r in rows[begin + 1 : end]
    }
    if not production | nonproduction <= expense_rows or expense_rows - (
        production | children | nonproduction
    ):
        return {"status": "unclassified_filed_production_expense"}
    if not {"RealEstateRevenueNet", "FinancialServicesRevenue"} <= values.keys():
        return {"status": "incomplete_filed_product_service_partition"}
    if values["RealEstateRevenueNet"] + values["FinancialServicesRevenue"] != revenue:
        return {"status": "incomplete_filed_product_service_partition"}
    if expense_rows & children and (
        not children <= expense_rows
        or sum(values[k] for k in children) != values["CostOfRealEstateRevenue"]
    ):
        return {"status": "filed_expense_section_does_not_reconcile"}
    total = revenue - Decimal(rows[end]["value"])
    signed = sum(values[k] for k in production | nonproduction)
    directions = [
        d
        for d in (Decimal(1), Decimal(-1))
        if signed * d == total
        and all(
            values[k] * d >= ZERO
            for k in production | {"SellingGeneralAndAdministrativeExpense"}
        )
    ]
    if len(directions) != 1:
        return {"status": "filed_expense_section_does_not_reconcile"}
    costs = {k: values[k] * directions[0] for k in sorted(production)}
    cost = sum(costs.values())
    return {
        "value": str(revenue - cost),
        "method": "filed_reconciled_expense_section",
        "revenue": str(revenue),
        "cost": str(cost),
        "total_expenses": str(total),
        "production_components": {k: str(v) for k, v in costs.items()},
        "expense_section_reconciled": True,
        "expense_display_direction": str(directions[0]),
    }
