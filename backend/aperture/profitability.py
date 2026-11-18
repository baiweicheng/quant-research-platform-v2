"""Matched annual gross profit; missing tags never prove complete expenses.

Companyfacts omits custom concepts and dimensional facts. Component sums are
usable only when their revenue partition reconciles to reported total revenue.
No sector, operating-income proxy, or absent tag establishes comparability.
"""

from .domain import ZERO

REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
COST_TAGS = ("CostOfRevenue", "CostOfGoodsAndServicesSold")
COMPONENT_TAGS = (
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "CostOfGoodsSold",
    "CostOfServices",
)
PRESENTATION_TAGS = (
    "InterestIncomeExpenseNet",
    "NoninterestExpense",
    "BenefitsLossesAndExpenses",
    "ElectricUtilityRevenue",
    "UtilitiesOperatingExpenseMaintenanceOperationsAndOtherCostsAndExpenses",
)
TAGS = ("GrossProfit",) + REVENUE_TAGS + COST_TAGS + COMPONENT_TAGS + PRESENTATION_TAGS


def extract(values):
    """Return value, provenance and diagnostics for ONE accession/duration/unit.

    The caller groups validated annual USD facts; no dates or facts are joined
    here. Keep an explicit reason even when no supported numerator survives.
    """
    sources, issues, conflicts = {}, [], set()

    def one(tag):
        candidates = values.get(tag, set())
        if len(candidates) > 1:
            conflicts.add(tag)
            return None
        return next(iter(candidates)) if candidates else None

    def finish(gross, status, expression=None, reason=None):
        sources["profitability_status"] = status
        if expression:
            sources["gross_profit"] = expression
        if reason:
            issues.append(reason)
        return gross, sources, issues

    gross = one("GrossProfit")
    if "GrossProfit" in conflicts:
        return finish(
            None,
            "conflicting_facts",
            reason="Conflicting GrossProfit facts in the same filing/period; not selected.",
        )
    if gross is not None:
        return finish(gross, "reported", "GrossProfit")

    revenue_measures = {tag: one(tag) for tag in REVENUE_TAGS}
    if (
        any(tag in conflicts for tag in REVENUE_TAGS)
        or len({v for v in revenue_measures.values() if v is not None}) > 1
    ):
        return finish(
            None,
            "ambiguous_total_revenue",
            reason="Reported revenue measures differ or conflict. The filing must establish complete company-wide revenue and matching costs; a convenient revenue tag is not selected.",
        )
    aggregate_measures = {tag: one(tag) for tag in COST_TAGS}
    if (
        any(tag in conflicts for tag in COST_TAGS)
        or len({v for v in aggregate_measures.values() if v is not None}) > 1
    ):
        return finish(
            None,
            "ambiguous_aggregate_cost",
            reason="Reported aggregate cost measures differ or conflict. Complete company-wide cost coverage requires filing verification.",
        )

    revenue, revenue_tag = None, None
    for tag in REVENUE_TAGS:
        revenue = one(tag)
        if tag in conflicts:
            return finish(
                None,
                "conflicting_facts",
                reason=f"Conflicting {tag} values in the same filing/period; not selected.",
            )
        if revenue is not None:
            revenue_tag = tag
            sources["revenue"] = tag
            sources["profitability_revenue"] = str(revenue)
            break
    if revenue is None:
        if (
            one("InterestIncomeExpenseNet") is not None
            and one("NoninterestExpense") is not None
        ):
            sources["profitability_presentation"] = "interest_and_noninterest"
            return finish(
                None,
                "unsupported_structured_presentation",
                reason="Structured annual facts report net interest and noninterest expenses without supported company-wide revenue/gross profit. No sector-wide non-applicability claim or bank-profit proxy is applied; bulk filing reconstruction is omitted for this presentation.",
            )
        return finish(
            None,
            "unverified_total_revenue",
            reason="Total annual revenue is unavailable in supported whole-entity facts; isolated goods/services revenue is not assumed complete.",
        )

    goods_revenue, services_revenue, goods_cost, services_cost = (
        one(tag) for tag in COMPONENT_TAGS
    )
    if conflicts:
        return finish(
            None,
            "conflicting_facts",
            reason="Conflicting component revenue/cost values in the same filing/period; not selected.",
        )
    for tag in COST_TAGS:
        cost = one(tag)
        if tag in conflicts:
            return finish(
                None,
                "conflicting_facts",
                reason=f"Conflicting {tag} values in the same filing/period; not selected.",
            )
        if cost is None:
            continue
        # An apparent total smaller than a reported component is demonstrably
        # incomplete (e.g. a separate property line alongside service costs).
        if sum(c for c in (goods_cost, services_cost) if c is not None) > cost:
            return finish(
                None,
                "partial_cost",
                reason="Partial-cost fallback rejected: reported aggregate cost is smaller than a separately reported component; complete company costs are unverified.",
            )
        if cost < ZERO:
            return finish(
                None,
                "invalid_cost",
                reason="Negative annual cost of revenue is not normalized without source verification.",
            )
        sources["cost"] = tag
        return finish(revenue - cost, "aggregate_cost", f"{revenue_tag} - {tag}")

    if goods_cost is None and services_cost is None:
        presentation = (
            "interest_and_noninterest"
            if one("InterestIncomeExpenseNet") is not None
            and one("NoninterestExpense") is not None
            else "insurance_benefits_and_losses"
            if one("BenefitsLossesAndExpenses") is not None
            else "utility_expenses_by_nature"
            if one("ElectricUtilityRevenue") is not None
            and one(
                "UtilitiesOperatingExpenseMaintenanceOperationsAndOtherCostsAndExpenses"
            )
            is not None
            else None
        )
        if presentation:
            sources["profitability_presentation"] = presentation
            return finish(
                None,
                "unsupported_structured_presentation",
                reason="The annual facts report "
                + {
                    "interest_and_noninterest": "net interest and noninterest expenses",
                    "insurance_benefits_and_losses": "insurance benefits, losses and expenses",
                    "utility_expenses_by_nature": "utility revenue and expenses by nature",
                }[presentation]
                + ". A comparable gross-profit/cost-of-revenue subtotal is unavailable in the supported facts. These expense presentations are disclosed research limits; they do not establish sector-wide non-applicability.",
            )
        return finish(
            None,
            "unsupported_cost_presentation",
            reason="Complete annual cost of revenue/gross profit is unavailable in supported whole-entity facts. Custom, dimensional or expense-by-nature presentation may require filing evidence; economic non-applicability is not established.",
        )

    # A complete revenue partition is positive evidence about the coverage of
    # component costs. Absence of the opposite cost/revenue tag is not evidence.
    if (
        goods_revenue is None
        and services_revenue is None
        or sum(v or ZERO for v in (goods_revenue, services_revenue)) != revenue
        or any(v is not None and v < ZERO for v in (goods_revenue, services_revenue))
        or goods_revenue is not None
        and goods_revenue > ZERO
        and goods_cost is None
        or services_revenue is not None
        and services_revenue > ZERO
        and services_cost is None
        or goods_cost is not None
        and goods_revenue is None
        or services_cost is not None
        and services_revenue is None
    ):
        return finish(
            None,
            "partial_cost",
            reason="Partial-cost fallback rejected: goods/services revenue does not reconcile to total revenue with corresponding costs. Missing tags do not prove a pure goods or service business.",
        )
    costs = [
        tag
        for tag, value in (
            ("CostOfGoodsSold", goods_cost),
            ("CostOfServices", services_cost),
        )
        if value is not None
    ]
    cost = sum(one(tag) for tag in costs)
    if any(one(tag) < ZERO for tag in costs):
        return finish(
            None,
            "invalid_cost",
            reason="Negative component costs require source verification.",
        )
    sources["cost"] = " + ".join(costs)
    sources["revenue_partition"] = " + ".join(
        tag for tag in COMPONENT_TAGS[:2] if one(tag) is not None
    )
    return finish(
        revenue - cost, "reconciled_components", f"{revenue_tag} - ({sources['cost']})"
    )
