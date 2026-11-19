"""Comparable whole-issuer net income from captured SEC annual reports."""

from collections import defaultdict
from datetime import date, timedelta
import re

from .domain import decimal

VERSION = "annual-net-income-v1"
MISSING_INPUTS = "Add or refresh SEC financials in Data to prepare comparable annual net income for this dataset."
NET_INCOME_TAGS = ("NetIncomeLoss", "ProfitLoss")
ANNUAL_FORM = "10-K"
ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}")
# Balance-sheet and established annual flow tags establish the fiscal-end
# anchor on older reports outside submissions.recent. None supplies earnings.
ANCHORS = (
    "Assets",
    "EarningsPerShareDiluted",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "NetCashProvidedByUsedInOperatingActivities",
)


def observed_reports(submissions: dict) -> dict:
    recent = submissions.get("filings", {}).get("recent", {})
    reports = {}
    for accession, form, filed, period in zip(
        *(
            recent.get(key, [])
            for key in ("accessionNumber", "form", "filingDate", "reportDate")
        )
    ):
        if form != ANNUAL_FORM or not filed or not period:
            continue
        try:
            end, filed_on = date.fromisoformat(period), date.fromisoformat(filed)
        except (TypeError, ValueError):
            continue
        if ACCESSION.fullmatch(accession) and end <= filed_on:
            reports[accession] = (filed_on, end)
    return reports


def comparable_income(facts: dict, fiscal_end: date) -> dict:
    """Return same-concept annual income and its comparative evidence."""
    starts = sorted(
        {
            start
            for tag, start, end in facts
            if tag in NET_INCOME_TAGS
            and end == fiscal_end
            and start
            and 330 <= (end - start).days + 1 <= 400
        }
    )
    if not starts:
        return {}
    start = starts[0]
    assets = facts.get(("Assets", None, start - timedelta(days=1)), set())
    if len(assets) != 1 or (beginning_assets := next(iter(assets))) <= 0:
        return {}
    duration = (fiscal_end - start).days + 1
    for tag in NET_INCOME_TAGS:
        current = facts.get((tag, start, fiscal_end), set())
        if len(current) != 1:
            continue
        prior = [
            (prior_start, prior_end, next(iter(values)))
            for (concept, prior_start, prior_end), values in facts.items()
            if concept == tag
            and prior_start
            and len(values) == 1
            and 350 <= (fiscal_end - prior_end).days <= 380
            and 350 <= (start - prior_start).days <= 380
            and abs((prior_end - prior_start).days + 1 - duration) <= 8
        ]
        if len(prior) == 1:
            prior_start, prior_end, prior_income = prior[0]
            return {
                "start": str(start),
                "previous_start": str(prior_start),
                "previous_end": str(prior_end),
                "net_income_tag": tag,
                "net_income": str(next(iter(current))),
                "previous_net_income": str(prior_income),
                "beginning_assets": str(beginning_assets),
            }
    return {}


def normalize(cik: str, company: dict, submissions: dict) -> list[dict]:
    """Keep missing original annual reports as explicit unavailable records."""
    from .fundamentals import filing_available

    if submissions.get("entityType") not in (None, "", "operating"):
        return []
    facts_by_accession = defaultdict(lambda: defaultdict(set))
    filing_dates = defaultdict(set)
    facts = company.get("facts", {}).get("us-gaap", {})
    for tag in (*NET_INCOME_TAGS, *ANCHORS):
        unit = "USD/shares" if tag == "EarningsPerShareDiluted" else "USD"
        for row in facts.get(tag, {}).get("units", {}).get(unit, ()):
            accession = row.get("accn", "")
            if row.get("form") != ANNUAL_FORM or not ACCESSION.fullmatch(accession):
                continue
            try:
                filed = date.fromisoformat(row["filed"])
                end = date.fromisoformat(row["end"])
                start = date.fromisoformat(row["start"]) if row.get("start") else None
                value = decimal(row["val"], "Annual filing fact")
            except (KeyError, TypeError, ValueError):
                continue
            if end > filed or (start is not None and start > end):
                continue
            facts_by_accession[accession][(tag, start, end)].add(value)
            filing_dates[accession].add(filed)
    reports = observed_reports(submissions)
    output = []
    for accession in filing_dates.keys() | reports.keys():
        facts = facts_by_accession[accession]
        dates = filing_dates[accession]
        if accession in reports:
            filed, fiscal_end = reports[accession]
            if dates and dates != {filed}:
                continue
        else:
            if len(dates) != 1:
                continue
            filed = next(iter(dates))
            fiscal_end = max(end for _, _, end in facts)
        # Existing platform calendar supports historical research from 1990.
        if filed.year < 1990 or (filed - fiscal_end).days > 550:
            continue
        output.append(
            {
                "cik": cik,
                "accession": accession,
                "filed": str(filed),
                "end": str(fiscal_end),
                "available_at": filing_available(filed).isoformat(),
                **comparable_income(facts, fiscal_end),
            }
        )
    return sorted(
        output, key=lambda row: (row["end"], row["available_at"], row["accession"])
    )


def as_of(rows, decision: date, cutoff):
    day = str(decision)
    earliest = str(decision - timedelta(days=550))
    instant = cutoff.isoformat()
    return max(
        (
            r
            for r in rows
            if earliest <= r["end"] <= day
            and r["available_at"] <= instant
            and day < r.get("valid_before", "9999-12-31")
        ),
        key=lambda r: (r["end"], r["available_at"], r["accession"]),
        default=None,
    )
