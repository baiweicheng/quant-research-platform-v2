"""Lightweight, explicitly approximate per-share research inputs.

No report-body acquisition. Ordinary common-share comparability is an accepted
research assumption, not a claim of independently verified historical classes.
Dates, currency, periods, conflicting facts and splits are validated separately.
"""

import re

VERSION = "structured-eps-v1"
WARNING = (
    "Lightweight EPS research: reported SEC per-share values are assumed to match "
    "ordinary listed shares. Share-class differences may remain; historical "
    "classes are not exhaustively verified. Known unequal-share cases are excluded."
)
UNEQUAL_ISSUERS = {
    "0001067983": {
        "name": "Berkshire Hathaway",
        "url": "https://www.berkshirehathaway.com/2025ar/202510-k.pdf",
        "reason": "Berkshire Class A and B have materially different per-share units; lightweight research does not infer a class conversion.",
    }
}


def assess(symbol, cik, company, start, end):
    """Record the lightweight assumption per accession; never label it verified."""
    wanted = {}
    facts = (
        company.get("facts", {})
        .get("us-gaap", {})
        .get("EarningsPerShareDiluted", {})
        .get("units", {})
        .get("USD/shares", [])
    )
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
