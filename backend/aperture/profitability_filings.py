"""Bounded annual profitability recovery from SEC-rendered filing statements.

Read compact statement tables, never estimate gross profit from operating profit.
Every recovery stays in its own accession, USD scale and annual date column.
Immutable captures and parsed evidence are reused by ordinary acquisition.
"""

import hashlib
import re
from datetime import datetime
from decimal import Decimal

from lxml import html

from .domain import ZERO
from .filing_classes import xml
from .profitability_expenses import AMORTIZATION, COST_LABEL
from .providers import EvidenceLimit, ResourceMissing

VERSION = "filed-profitability-v28"
REVENUES = {
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
}
COSTS = {"CostOfRevenue", "CostOfGoodsAndServicesSold"}
STRUCTURED_COST_CANDIDATES = {
    "aggregate_cost",
    "reconciled_components",
    "ambiguous_aggregate_cost",
    "ambiguous_total_revenue",
    "partial_cost",
    "conflicting_facts",
}
# Pulte has a reviewed historical expense layout that does not persist through
# its earliest and latest candidate filings. Preserve that verified window.
REVIEWED_HISTORICAL_LAYOUT = {"0000822416"}
MISSING_REASONS = {
    "bounded_filing_search": "Structured annual facts lack a supported cost or revenue lead. The issuer's sampled filings did not establish a recovery route, so this accession was not inspected under the bounded filing policy.",
    "filing_outside_verified_decisions": "This annual record was retained for provenance but was outside the periods selected for filing verification. A structured cost candidate alone cannot supply gross profit.",
    "unverified_financing_cost_scope": "Financial-services revenue is present, but the filing does not establish the associated financing production costs. Interest expense is not automatically treated as corporate overhead for this presentation.",
    "unclassified_filed_operating_expense": "A separate operating expense could not be classified as included production cost or supported nonproduction expense. A CostOfRevenue tag alone cannot establish complete company costs.",
    "unsupported_filed_expense_scope": "The complete company expense section could not be verified in the supported filing layout; a convenient cost subtotal is not substituted.",
    "unclassified_filed_production_expense": "The filing reports additional production or manufacturing costs that could not be included in a verified complete numerator.",
    "filed_expense_section_does_not_reconcile": "The classified expense lines do not reconcile to the filing subtotal; an apparent cost line is not substituted for the inconsistent section.",
    "unsupported_annual_header": "The filing's report was captured, but its annual period, currency or column layout is unsupported. No amount is guessed from another period.",
    "filed_expenses_by_nature": "The inspected statement reports expenses by nature. A comparable split between production costs and other operating expenses could not be verified; operating profit is not substituted for gross profit.",
    "no_distinct_supported_gross_profit_or_complete_cost_subtotal": "A complete gross-profit or cost-of-revenue subtotal could not be verified in the supported filing tables. Expenses may use custom concepts or a different presentation.",
    "no_unambiguous_filed_total_revenue": "A unique company-wide annual revenue subtotal could not be verified in the filing table.",
    "no_supported_statement_report": "This filing has no income statement report supported by the bounded reader.",
    "no_matching_annual_column": "The filing table's annual dates do not match this financial period. Values from a different year or date are not substituted.",
    "filed_cost_excludes_unallocated_expenses": "The reported costs exclude depreciation or amortization without a supported allocation to production costs.",
    "conflicting_filed_subtotals": "The filing tables contain conflicting gross-profit subtotals.",
    "conflicting_filed_cost_subtotals": "The filing table contains conflicting or unsupported signed cost subtotals.",
    "filed_aggregate_smaller_than_component": "The apparent total cost is smaller than a separately reported cost component; complete expenses are unverified.",
    "incomplete_filed_product_service_partition": "Product and service revenues do not reconcile to the company's total revenue.",
    "ambiguous_filed_cost_depreciation_allocation": "The production depreciation/amortization allocation is ambiguous.",
    "filed_revenue_does_not_match_structured_period": "The filing table's revenue does not match the captured financial period or currency scale.",
    "filing_report_unavailable_or_unsupported": "The required filing report is unavailable or its format is unsupported. No substitute gross profit is used.",
}


def text(node):
    return " ".join(node.text_content().split())


def date_header(value):
    value = value.replace(".", "").replace("Sept ", "Sep ")
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def amount(value):
    value = (
        re.sub(r"\[[^]]*\]", "", value)
        .strip()
        .replace("$", "")
        .replace(",", "")
        .replace(" ", "")
    )
    if value in {"—", "–", "-"}:
        return ZERO
    if not re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", value):
        return None
    return Decimal(value.strip("()")) * (-1 if value.startswith("(") else 1)


def parse_report(raw):
    """Return annual-column rows with explicit concept/scope and USD scale.

    Reject unusual headers instead of interpreting quarters as annual values.
    Rendered report tables retain dimension headers (unlike companyfacts).
    """
    root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    tables = root.xpath(
        '//table[contains(concat(" ",normalize-space(@class)," ")," report ")]'
    )
    if len(tables) != 1:
        return {}
    rows = tables[0].xpath("./tr|./tbody/tr")
    if len(rows) < 3:
        return {}
    heading = text(rows[0])
    if "USD ($)" not in heading:
        return {}
    scale_match = re.search(
        r"(?:\$|USD \(\$\)) in (Millions|Thousands|Billions)", heading, re.IGNORECASE
    )
    scale = (
        Decimal(
            {"millions": 1000000, "thousands": 1000, "billions": 1000000000}.get(
                scale_match[1].lower(), 1
            )
        )
        if scale_match
        else Decimal(1)
    )
    # Each duration header covers exactly its own date columns, including
    # quarterly notes with both three- and twelve-month columns.
    durations = []
    for cell in rows[0].xpath("./th")[1:]:
        durations += [
            bool(
                re.fullmatch(
                    r"(?:12 Months|Years?|Fiscal Years?) Ended",
                    text(cell),
                    re.IGNORECASE,
                )
            )
        ] * int(cell.get("colspan", "1"))
    dates = []
    for cell in rows[1].xpath("./th"):
        width = int(cell.get("colspan", "1"))
        dates.extend([date_header(text(cell)), *([None] * (width - 1))])
    prefix_width = int(rows[0].xpath("./th")[0].get("colspan", "1"))
    if not dates or len(dates) != len(durations):
        return {}
    columns = {i: d for i, d in enumerate(dates) if d and durations[i]}
    if len(set(columns.values())) != len(columns):
        return {}
    result = {d: [] for d in columns.values()}
    scope = None
    for row in rows[2:]:
        cells = row.xpath("./td")
        if not cells:
            continue
        link = " ".join(cells[0].xpath(".//a/@onclick"))
        concept = re.search(r"defref_([^'\"]+)", link)
        concept = concept[1] if concept else ""
        if row.get("class") == "rh":
            scope = concept  # Never lose a dimension just because a row is blank.
        physical = []
        for cell in cells:
            physical.extend([cell, *([None] * (int(cell.get("colspan", "1")) - 1))])
        if len(physical) != len(dates) + prefix_width:
            continue
        label = text(cells[0])
        for i, d in columns.items():
            cell = physical[i + prefix_width]
            val = amount(text(cell)) if cell is not None else None
            if val is not None:
                result[d].append(
                    {
                        "concept": concept,
                        "label": label,
                        "scope": scope,
                        "value": str(val * scale),
                        "display_unit": str(scale.scaleb(val.as_tuple().exponent)),
                    }
                )
    return result


def extract_period(rows, cik=None):
    from .profitability_scope import collapse_administrative_subtotal, verify

    rows = collapse_administrative_subtotal(rows)
    result = _extract_period(rows, cik)
    if result.get("method") in {
        "filed_reconciled_expense_section",
        "filed_total_revenue_minus_total_cost",
        "filed_reconciled_entity_components",
        "filed_reconciled_product_service_costs",
    }:
        return verify(rows, result, cik)
    return result


def _extract_period(rows, cik=None):
    """Use only explicit entity subtotals or a reconciled product/service split."""
    entity = [r for r in rows if r["scope"] is None]

    def values(predicate, pool=entity):
        return {Decimal(r["value"]) for r in pool if predicate(r)}

    gross = values(
        lambda r: (
            r["concept"] == "us-gaap_GrossProfit"
            or r["label"].lower().rstrip(":") in {"gross profit", "gross profit (loss)"}
        )
    )
    if len(gross) == 1:
        return {"value": str(next(iter(gross))), "method": "reported_gross_profit"}
    if gross:
        return {"status": "conflicting_filed_subtotals"}
    explicit_totals = values(
        lambda r: (
            r["label"].lower().rstrip(":")
            in {
                "total revenues",
                "total revenue",
                "total net revenues",
                "total net revenue",
                "total sales and revenues",
                "total net sales and revenue",
                "total operating revenues",
                "total operating revenue",
            }
        )
    )
    # Whole-company standard totals take precedence over their goods/service
    # children in the same primary statement (e.g. LYB related-party sales).
    standard_totals = values(
        lambda r: r["concept"] in {"us-gaap_Revenues", "us-gaap_SalesRevenueNet"}
    )
    revenue = (
        explicit_totals
        or standard_totals
        or values(
            lambda r: (
                r["concept"].removeprefix("us-gaap_") in REVENUES
                or r["label"].lower().rstrip(":")
                in {
                    "total revenues",
                    "total revenue",
                    "total net revenues",
                    "total net revenue",
                    "net revenues",
                    "net revenue",
                    "net sales",
                    "sales",
                    "total sales",
                    "revenues",
                    "revenue",
                }
            )
        )
    )
    if len(revenue) != 1:
        return {"status": "no_unambiguous_filed_total_revenue"}
    revenue = next(iter(revenue))
    from .profitability_expenses import extract as expense_section

    verified_section = expense_section(entity, revenue, cik)
    if verified_section is not None and (
        "value" in verified_section
        or not any(
            r["concept"]
            in {"us-gaap_CostOfRevenue", "us-gaap_CostOfGoodsAndServicesSold"}
            and r["label"].lower().rstrip(":")
            in {"total cost of revenues", "total cost of revenue"}
            for r in entity
        )
    ):
        return verified_section
    generic_allocation_tags = {
        "us-gaap_DepreciationAndAmortization",
        "us-gaap_DepreciationDepletionAndAmortization",
        "us-gaap_DepreciationAmortizationAndAccretionNet",
        "us-gaap_Depreciation",
        "us-gaap_AmortizationOfIntangibleAssets",
    }
    for i, row in enumerate(entity):
        if (
            row["concept"] not in generic_allocation_tags
            or Decimal(row["value"]) == ZERO
        ):
            continue
        administrative = (
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
        )
        other_intangibles = (
            row["concept"] == "us-gaap_AmortizationOfIntangibleAssets"
            and "other acquired" in row["label"].lower()
            and any(
                r["concept"].removeprefix("us-gaap_") in AMORTIZATION for r in entity
            )
        )
        if not administrative and not other_intangibles:
            return {"status": "filed_cost_excludes_unallocated_expenses"}
    cost_rows = [
        r
        for r in entity
        # Some filers use the aggregate tag for one business stream, such as
        # purchased commodities or property operations. Require an explicit
        # company cost subtotal; otherwise the complete expense section or
        # reconciled revenue/cost partition must establish its coverage.
        if re.fullmatch(
            COST_LABEL,
            r["label"].lower().rstrip(":"),
        )
    ]
    if any(
        re.search(
            r"exclud|exclusiv|before|without",
            r["label"] + " " + r["concept"],
            re.IGNORECASE,
        )
        for r in cost_rows
    ):
        cost_rows = []  # Complete matched components may still be recoverable.
    if any(
        r["concept"] in {"us-gaap_CostOfGoodsSold", "us-gaap_CostOfServices"}
        or "products" in r["label"].lower()
        or "goods" in r["label"].lower()
        for r in cost_rows
    ) and any(
        r["concept"]
        in {
            "us-gaap_CostOfGoodsSold",
            "us-gaap_CostOfServices",
            "us-gaap_FinancialServicesCosts",
            "us-gaap_FinancingInterestExpense",
            "us-gaap_DirectOperatingCostRoyaltyExpense",
            "us-gaap_PolicyholderBenefitsAndClaimsIncurredNet",
            "us-gaap_PolicyholderBenefitsAndClaimsIncurredHealthCare",
            "us-gaap_PolicyholderBenefitsAndClaimsIncurredOther",
            "us-gaap_BenefitsLossesAndExpenses",
        }
        and r not in cost_rows
        and Decimal(r["value"]) != ZERO
        for r in entity
    ):
        cost_rows = []
    if cost_rows:
        subtotal_end = max(entity.index(r) for r in cost_rows)
        if any(
            r["concept"]
            in {"us-gaap_FinancialServicesCosts", "us-gaap_FinancingInterestExpense"}
            and Decimal(r["value"]) != ZERO
            for r in entity[subtotal_end + 1 :]
        ):
            cost_rows = []  # Separate financing must join a complete revenue partition.
    costs = {Decimal(r["value"]) for r in cost_rows}
    if len(costs) == 1:
        cost = next(iter(costs))
        component_costs = values(
            lambda r: (
                r["concept"] in {"us-gaap_CostOfGoodsSold", "us-gaap_CostOfServices"}
            )
        )
        if any(c > cost for c in component_costs):
            return {"status": "filed_aggregate_smaller_than_component"}
        if cost >= ZERO:
            return {
                "value": str(revenue - cost),
                "method": "filed_total_revenue_minus_total_cost",
                "revenue": str(revenue),
                "cost": str(cost),
            }
    if costs:
        return {"status": "conflicting_filed_cost_subtotals"}
    # Explicit entity-level product, service and financing line items. The
    # entire revenue partition must reconcile; associated finance costs cannot
    # disappear merely because only goods/services were supported previously.
    pairs = [
        ("us-gaap_RealEstateRevenueNet", "us-gaap_CostOfRealEstateRevenue"),
        ("us-gaap_FinancialServicesRevenue", "us-gaap_FinancialServicesCosts"),
        ("us-gaap_SalesRevenueGoodsNet", "us-gaap_CostOfGoodsSold"),
        ("us-gaap_SalesRevenueServicesNet", "us-gaap_CostOfServices"),
        (
            "us-gaap_CapitalLeasesIncomeStatementLeaseRevenue",
            "us-gaap_FinancialServicesCosts",
        ),
        ("us-gaap_InterestIncomeOperating", "us-gaap_FinancingInterestExpense"),
    ]
    if cik == "0001043277":
        # C.H. Robinson's primary income statement separately identifies its
        # purchased transportation and sourced-product revenue/cost streams.
        # Both streams must reconcile to total revenue. Exact reviewed labels:
        # SEC 0001043277-16-000020/R4.htm; no arbitrary custom-tag inference.
        pairs.append(
            (
                "chrw_TransportationServicesRevenue",
                "chrw_CostOfPurchasedTransportationAndRelatedServices",
            )
        )
    alternatives = {}
    for revenue_concept, cost_concept in pairs:
        alternatives.setdefault(cost_concept, []).append(revenue_concept)
    components = {}
    for cost_concept, revenue_concepts in alternatives.items():
        revenues = values(lambda r, concepts=revenue_concepts: r["concept"] in concepts)
        costs = values(lambda r, concept=cost_concept: r["concept"] == concept)
        if not revenues and not costs:
            continue
        if (
            len(revenues) != 1
            or len(costs) != 1
            or any(v < ZERO for v in revenues | costs)
        ):
            components = {}
            break
        revenue_concept = next(
            concept
            for concept in revenue_concepts
            if any(r["concept"] == concept for r in entity)
        )
        components[revenue_concept] = (next(iter(revenues)), next(iter(costs)))
    if components and sum(v[0] for v in components.values()) == revenue:
        extras = [
            r for r in entity if r["concept"].removeprefix("us-gaap_") in AMORTIZATION
        ]
        if len(extras) <= 1:
            extra = Decimal(extras[0]["value"]) if extras else ZERO
            if extra >= ZERO:
                cost = sum(v[1] for v in components.values()) + extra
                return {
                    "value": str(revenue - cost),
                    "method": "filed_reconciled_entity_components",
                    "revenue": str(revenue),
                    "cost": str(cost),
                    "components": {
                        k: [str(n) for n in v] for k, v in components.items()
                    },
                    "additional_production_amortization": str(extra),
                }

    # These are disjoint product/service partitions on the face statement.
    # Custom members require a reviewed issuer restriction. Geographies and
    # general business segments cannot supply these inputs.
    members = {
        "0001043277": (
            "us-gaap_ProductMember|chrw_SourcingMember",
            "us-gaap_ServiceMember|chrw_TransportationCustomersFreightMember",
        ),
        "0000896878": (
            "us-gaap_ProductMember|intu_ProductAndOtherMember",
            "us-gaap_ServiceMember",
        ),
    }.get(cik, ("us-gaap_ProductMember", "us-gaap_ServiceMember"))
    components = {}
    component_rows = []
    for member, member_pattern in zip(
        ("ProductMember", "ServiceMember"), members, strict=True
    ):
        pool = [
            r
            for r in rows
            if re.fullmatch(
                rf"(?:srt|us-gaap)_ProductOrServiceAxis=(?:{member_pattern})",
                r["scope"] or "",
            )
        ]
        revenue_rows = [
            r for r in pool if r["concept"].removeprefix("us-gaap_") in REVENUES
        ]
        cost_rows = [r for r in pool if r["concept"].removeprefix("us-gaap_") in COSTS]
        if (
            len(revenue_rows) != 1
            or len(cost_rows) != 1
            or any(Decimal(r["value"]) < ZERO for r in revenue_rows + cost_rows)
        ):
            excluded = [
                r
                for r in entity
                if "ExcludingDepreciationDepletionAndAmortization" in r["concept"]
            ]
            if excluded:
                return {"status": "filed_cost_excludes_unallocated_expenses"}
            nature_tags = {
                "LaborAndRelatedExpense",
                "FuelCosts",
                "AircraftFuel",
                "RepairsAndMaintenance",
                "DepreciationAndAmortization",
                "DepreciationDepletionAndAmortization",
                "SalariesAndWages",
                "SalariesWagesAndOfficersCompensation",
            }
            if (
                len(
                    {r["concept"].removeprefix("us-gaap_") for r in entity}
                    & nature_tags
                )
                >= 2
            ):
                return {"status": "filed_expenses_by_nature"}
            return {
                "status": "no_distinct_supported_gross_profit_or_complete_cost_subtotal"
            }
        component_rows.append((revenue_rows[0], cost_rows[0]))
        components[member] = tuple(
            Decimal(r["value"]) for r in (revenue_rows[0], cost_rows[0])
        )
    from .profitability_expenses import display_unit, rounded_equal

    total_row = next(
        (
            r
            for r in entity
            if Decimal(r["value"]) == revenue
            and re.fullmatch(
                r"(?:total )?(?:net )?(?:operating )?(?:revenues?|sales)",
                r["label"].lower().rstrip(":"),
            )
        ),
        {},
    )
    if not rounded_equal(
        sum(v[0] for v in components.values()),
        revenue,
        [display_unit(total_row), *(display_unit(r) for r, _ in component_rows)],
    ):
        return {"status": "incomplete_filed_product_service_partition"}
    extras = [
        r for r in entity if r["concept"].removeprefix("us-gaap_") in AMORTIZATION
    ]
    if len(extras) > 1:
        return {"status": "ambiguous_filed_cost_depreciation_allocation"}
    extra = Decimal(extras[0]["value"]) if extras else ZERO
    if extra < ZERO:
        return {"status": "ambiguous_filed_cost_depreciation_allocation"}
    cost = sum(v[1] for v in components.values()) + extra
    return {
        "value": str(revenue - cost),
        "method": "filed_reconciled_product_service_costs",
        "revenue": str(revenue),
        "cost": str(cost),
        "components": {k: [str(n) for n in v] for k, v in components.items()},
        "component_scopes": {
            member: revenue_row["scope"]
            for member, (revenue_row, _) in zip(components, component_rows, strict=True)
        },
        "additional_production_amortization": str(extra),
        "production_display_units": [
            str(display_unit(r)) for r in [*(r for _, r in component_rows), *extras]
        ],
    }


def _statement_priority(name, category):
    if any(s in name for s in ("parenthetical", "parent company")):
        return None
    # Some filing vintages categorize the face income statement as
    # Uncategorized, while the separate OCI statement is under Statements.
    # Require a face-statement title for that exception, not keyword matches
    # in segment, detail, or disclosure reports.
    face = re.fullmatch(
        r"(?:consolidated |combined |condensed )*statements? of "
        r"(?:operations|income|earnings)(?: \((?:loss|income)\))?"
        r"(?: and (?:total )?comprehensive (?:income|loss)(?: \((?:loss|income)\))?)?",
        name,
    )
    if category in {"Statements", "Uncategorized"} and face:
        return 0
    if category == "Statements" and any(
        s in name for s in ("income", "operations", "earnings")
    ):
        return 2 if "comprehensive" in name else 1
    return None


def read(api, cik, accession):
    """At most one primary statement and one quarterly table per accession."""
    key = f"{VERSION}:{cik}:{accession}"
    store = getattr(api, "store", None)
    cached = store.filing_evidence(key) if store else None
    if cached:
        api.observations.extend(s["id"] for s in cached["sources"])
        return cached["proof"]
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    start = len(api.observations)
    try:
        summary = xml(api.document(folder + "FilingSummary.xml"))
        candidates = []
        for node in summary.findall(".//Report"):
            fields = {e.tag: (e.text or "").strip() for e in node}
            name = " ".join(fields.get("ShortName", "").lower().split())
            priority = _statement_priority(name, fields.get("MenuCategory"))
            primary = priority is not None
            quarterly = "quarterly" in name and not any(
                s in name for s in ("detail", "parenthetical")
            )
            filename = fields.get("HtmlFileName", "")
            if (primary or quarterly) and re.fullmatch(r"R\d+\.htm", filename):
                candidates.append(
                    (
                        not primary,
                        priority if primary else 0,
                        int(fields.get("Position") or 999999),
                        filename,
                    )
                )
        proof = {
            "periods": {},
            "status": "no_supported_statement_report",
            "reports": [],
        }
        seen = set()
        for quarterly, _, _, filename in sorted(candidates):
            if quarterly in seen:
                continue
            seen.add(quarterly)
            raw = api.document(folder + filename)
            periods = parse_report(raw)
            proof["reports"].append(
                {"url": folder + filename, "sha256": hashlib.sha256(raw).hexdigest()}
            )
            for end, rows in periods.items():
                result = extract_period(rows, cik)
                prior = proof["periods"].get(end)
                if prior and "value" not in prior and "value" not in result:
                    continue
                if prior and "value" in prior:
                    if "value" in result and result["value"] != prior["value"]:
                        proof["periods"][end] = {
                            "status": "conflicting_filed_subtotals"
                        }
                    continue
                proof["periods"][end] = {
                    **result,
                    "url": folder + filename,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            proof["status"] = (
                "inspected_bounded_filing_reports"
                if proof["periods"]
                else "unsupported_annual_header"
            )
            if (
                not quarterly
                and proof["periods"]
                and all("value" in r for r in proof["periods"].values())
            ):
                break
        from . import profitability_supplement

        if cik in profitability_supplement.ISSUERS and (
            not proof["periods"]
            or any("value" not in r for r in proof["periods"].values())
        ):
            url = profitability_supplement.primary_url(api, folder, accession)
            if url:
                raw = api.document(url)
                digest = hashlib.sha256(raw).hexdigest()
                proof["reports"].append({"url": url, "sha256": digest})
                for end, evidence in profitability_supplement.extract(raw, cik).items():
                    prior = proof["periods"].get(end, {})
                    if "value" in prior:
                        if prior["value"] != evidence["value"]:
                            proof["periods"][end] = {
                                "status": "conflicting_filed_subtotals"
                            }
                        continue
                    proof["periods"][end] = {**evidence, "url": url, "sha256": digest}
    except (ResourceMissing, EvidenceLimit, ValueError, SyntaxError) as error:
        proof = {
            "periods": {},
            "status": "filing_report_unavailable_or_unsupported",
            "reason": str(error),
        }
    if store:
        store.save_filing_evidence(key, proof, api.observations[start:])
    return proof


def enrich(statements, api, first, last, progress=None):
    """Recover only accessions that can inform this dataset's decision window.

    The existing as-of selector preserves filing availability and stale/ambiguous
    gates. Each accession is read once, including negative cache outcomes.
    """
    from dataclasses import replace

    from .fundamentals import as_of

    if not statements:
        return statements
    if not hasattr(api, "document"):
        # A provider without filed evidence cannot certify a derived candidate.
        return tuple(
            replace(
                r,
                gross_profit=None,
                sources={
                    **r.sources,
                    "profitability_status": "unsupported_filing",
                    "profitability_filing_status": "filing_report_unavailable_or_unsupported",
                    "profitability_filing_reason": "The provider cannot supply the filed evidence required to validate derived gross profit.",
                },
            )
            if r.sources.get("profitability_status") != "reported"
            else r
            for r in statements
        )
    days = {first}
    days.update(
        r.available_at.date()
        for r in statements
        if first <= r.available_at.date() <= last
    )
    days.update(
        datetime.strptime(r.sources["valid_before"], "%Y-%m-%d").date()
        for r in statements
        if r.sources.get("valid_before")
        and str(first) <= r.sources["valid_before"] <= str(last)
    )
    selected = {}
    # As-of selection changes only at filing availability or validity boundaries;
    # staleness removes a candidate, it never exposes an older fiscal period.
    for day in sorted(days):
        row = as_of(statements, day)
        if row and row.sources.get("profitability_status") not in {
            "reported",
            "unsupported_structured_presentation",
        }:
            selected.setdefault(row.accession, row)
    proofs = {}
    from .profitability_supplement import ISSUERS

    # Verify every promising accession. Where structured facts offer no lead,
    # inspect the earliest and latest relevant statement for a custom layout
    # before adding its remaining historical reports to a cold acquisition.
    direct = {
        r.accession
        for r in statements
        if r.accession in selected
        and (
            r.sources.get("profitability_status") in STRUCTURED_COST_CANDIDATES
            or r.cik in REVIEWED_HISTORICAL_LAYOUT
            or r.cik in ISSUERS
        )
    }
    weak = {}
    for accession, row in sorted(
        selected.items(), key=lambda pair: (pair[1].filed, pair[0])
    ):
        if accession not in direct:
            weak.setdefault(row.cik, []).append(accession)
    probes = {key for group in weak.values() for key in (group[0], group[-1])}

    def inspect(accession):
        row = selected[accession]
        child = api.fork() if hasattr(api, "fork") else api
        try:
            proof = read(child, row.cik, accession)
            return (
                accession,
                proof,
                list(child.observations) if child is not api else [],
            )
        finally:
            if child is not api:
                child.close()

    def collect(results, total):
        for accession, proof, observations in results:
            proofs[accession] = proof
            api.observations.extend(observations)
            if progress:
                progress(len(proofs), total)

    def verify_plan(mapper):
        initial = sorted(direct | probes)
        collect(mapper(inspect, initial), len(initial))
        expanded = sorted(
            accession
            for group in weak.values()
            if any(
                "value" in period
                for key in {group[0], group[-1]}
                for period in proofs[key].get("periods", {}).values()
            )
            for accession in group
            if accession not in probes
        )
        collect(mapper(inspect, expanded), len(initial) + len(expanded))

    if len(selected) > 1 and hasattr(api, "fork"):
        from concurrent.futures import ThreadPoolExecutor

        # All issuer readers still share Provider's eight-starts/sec gate.
        with ThreadPoolExecutor(max_workers=2) as pool:
            verify_plan(pool.map)
    else:
        verify_plan(map)
    output = []
    for row in statements:
        proof = proofs.get(row.accession)
        if row.sources.get("profitability_status") in {
            "reported",
            "unsupported_structured_presentation",
        }:
            output.append(row)
            continue
        if proof is None:
            if row.accession not in selected and row.gross_profit is None:
                output.append(row)
                continue
            status = (
                "bounded_filing_search"
                if row.accession in selected
                else "filing_outside_verified_decisions"
            )
            sources = {
                **row.sources,
                "profitability_status": "unsupported_filing",
                "profitability_filing_status": status,
                "profitability_filing_reason": MISSING_REASONS[status],
            }
            sources.pop("gross_profit", None)
            output.append(replace(row, gross_profit=None, sources=sources))
            continue
        evidence = proof.get("periods", {}).get(str(row.end), {})
        if (
            evidence.get("revenue")
            and row.sources.get("profitability_revenue")
            and Decimal(evidence["revenue"])
            != Decimal(row.sources["profitability_revenue"])
        ):
            evidence = {
                **evidence,
                "status": "filed_revenue_does_not_match_structured_period",
            }
            evidence.pop("value", None)
        if "value" in evidence:
            sources = {
                **row.sources,
                "gross_profit": evidence["method"],
                "profitability_status": "filed_statement",
                "profitability_evidence": evidence["url"],
                "profitability_evidence_sha256": evidence["sha256"],
                "profitability_parser": VERSION,
            }
            if "cost" in evidence:
                sources["cost"] = evidence["cost"]
            if evidence.get("definition"):
                sources["profitability_definition"] = evidence["definition"]
            issues = tuple(
                i
                for i in row.issues
                if not any(
                    t in i
                    for t in (
                        "Profitability: ",
                        "Partial-cost",
                        "Matched annual gross profit/assets",
                        "Total annual revenue",
                        "Complete annual cost",
                    )
                )
            )
            output.append(
                replace(
                    row,
                    gross_profit=Decimal(evidence["value"]),
                    sources=sources,
                    issues=issues,
                )
            )
        else:
            # A reconciled structured component candidate still needs the
            # primary statement to rule out additional production costs.
            status = evidence.get("status") or (
                "no_matching_annual_column"
                if proof.get("periods")
                else proof.get("status", "filing_not_resolved")
            )
            message = "Gross profit unavailable: " + MISSING_REASONS.get(
                status,
                "A comparable complete gross-profit/cost subtotal was not verified by the bounded filing reader.",
            )
            sources = {
                **row.sources,
                "profitability_status": "unsupported_filing",
                "profitability_filing_status": status,
                "profitability_filing_reason": message,
                "profitability_parser": VERSION,
            }
            if evidence.get("url"):
                sources["profitability_evidence"] = evidence["url"]
                sources["profitability_evidence_sha256"] = evidence["sha256"]
            output.append(
                replace(
                    row,
                    gross_profit=None,
                    sources=sources,
                    issues=(*row.issues, message),
                )
            )
    return tuple(output)
