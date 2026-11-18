"""Lightweight, explicitly approximate per-share research inputs.

No report-body acquisition. Ordinary common-share comparability is an accepted
research assumption, not a claim of independently verified historical classes.
Dates, currency, periods, conflicting facts and splits are validated separately.
"""

import re
from decimal import Decimal

VERSION = "structured-eps-v2"
# Whole-entity annual diluted EPS elements, in precedence order. Many filers
# without discontinued operations tag their bottom-line diluted EPS with the
# continuing-operations element only; it is used only when no net element is
# reported for that accession and period. Earnings before discontinued
# operations is also the conventional earnings measure for value research.
EPS_TAGS = (
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "IncomeLossFromContinuingOperationsPerDilutedShare",
    "IncomeLossFromContinuingOperationsPerBasicAndDilutedShare",
)
WARNING = (
    "Lightweight EPS research: reported SEC per-share values are assumed to match "
    "ordinary listed shares. Share-class differences may remain; historical "
    "classes are not exhaustively verified. Reviewed unequal-share cases require "
    "a verified class-specific amount."
)
UNEQUAL_ISSUERS = {
    "0001067983": {
        "name": "Berkshire Hathaway",
        "url": "https://www.berkshirehathaway.com/2025ar/202510-k.pdf",
        "reason": "Berkshire Class A and B have materially different per-share units; lightweight research does not infer a class conversion.",
    }
}

# Each accession reports both the issuer's current and comparative fiscal
# years. Match the exact raw fact so the repair never rescales a later SEC fix.
_HAL_FILINGS = {
    "0000045012-23-000011": (2022, {2021: "1.63", 2022: "1.73"}),
    "0000045012-24-000007": (2023, {2022: "1.73", 2023: "2.92"}),
    "0000045012-25-000010": (2024, {2023: "2.92", 2024: "2.83"}),
}
SCALE_REVIEW_THRESHOLD = Decimal("10000")
SCALE_UNVERIFIED = (
    "The filing reports an unusually large amount per share whose scale has "
    "not been corroborated. EPS valuation is unavailable."
)
CORROBORATION_TAGS = (
    "NetIncomeLossAvailableToCommonStockholdersDiluted",
    "NetIncomeLoss",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
)


def fact_unit(tag):
    if tag in EPS_TAGS:
        return "USD/shares"
    if tag == "WeightedAverageNumberOfDilutedSharesOutstanding":
        return "shares"
    return "USD"


def checked_amount(cik, accession, start, end, eps, sources, facts=None):
    """Resolve a raw per-share value independently of the stock's price."""
    if eps is None:
        return None, {}, None
    if (
        cik == "0000045012"
        and accession in _HAL_FILINGS
        and sources.get("eps") == "IncomeLossFromContinuingOperationsPerDilutedShare"
        and str(start) == f"{end.year}-01-01"
        and str(end) == f"{end.year}-12-31"
    ):
        filing_year, amounts = _HAL_FILINGS[accession]
        amount = amounts.get(end.year)
        if amount and eps == Decimal(amount) * 1_000_000:
            return (
                Decimal(amount),
                {
                    "eps_reported_fact": str(eps),
                    "eps_scale_source": (
                        "https://www.sec.gov/Archives/edgar/data/45012/"
                        f"{accession.replace('-', '')}/hal-{filing_year}1231.htm"
                    ),
                },
                None,
            )
    if abs(eps) < SCALE_REVIEW_THRESHOLD or sources.get("eps_scale_reconciled"):
        return eps, {}, None
    # Trigger corroboration in both directions for extreme dollar-per-share
    # values. Compare only like-period, same-accession facts. The result is
    # evidence of scale, not a substitute for the filed EPS or class mapping.
    facts = facts or {}
    diluted, net, shares = (facts.get(tag, set()) for tag in CORROBORATION_TAGS)
    earnings = diluted or net
    if len(earnings) == len(shares) == 1:
        numerator, denominator = next(iter(earnings)), next(iter(shares))
        if denominator > 0 and abs(numerator / denominator - eps) <= abs(eps) / 100:
            return (
                eps,
                {"eps_scale_reconciled": CORROBORATION_TAGS[0 if diluted else 1]},
                None,
            )
    return None, {}, SCALE_UNVERIFIED


def assess(symbol, cik, company, start, end):
    """Record the lightweight assumption per accession; never label it verified."""
    wanted = {}
    facts = [
        fact
        for tag in EPS_TAGS
        for fact in company.get("facts", {})
        .get("us-gaap", {})
        .get(tag, {})
        .get("units", {})
        .get("USD/shares", [])
    ]
    for fact in facts:
        if (
            fact.get("form") in {"10-K", "10-K/A"}
            and start <= fact.get("filed", "") <= end
            and re.fullmatch(r"\d{10}-\d{2}-\d{6}", fact.get("accn", ""))
        ):
            wanted[fact["accn"]] = fact["filed"]
    excluded = UNEQUAL_ISSUERS.get(str(cik).zfill(10))
    return {
        accession: {
            "version": VERSION,
            "method": "structured-sec-ordinary-share-assumption",
            "symbol": symbol,
            "cik": cik,
            "accession": accession,
            "filed": filed,
            "compatible": not bool(excluded),
            "class_verified": False,
            "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
            "reason": excluded["reason"] if excluded else WARNING,
            **({"exception_source": excluded["url"]} if excluded else {}),
        }
        for accession, filed in sorted(wanted.items())
    }
