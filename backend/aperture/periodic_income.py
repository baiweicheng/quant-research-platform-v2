"""Original 10-Q/10-K income pairs from a snapshot's immutable EDGAR captures."""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from functools import lru_cache
from hashlib import sha256
import gzip
import json
from math import isfinite
import re

from . import reviewed_periodic_income
from .annual_income import ACCESSION, NET_INCOME_TAGS
from .domain import ResearchError

PERIODIC_INCOME_TAGS = (
    *NET_INCOME_TAGS,
    "NetIncomeLossAvailableToCommonStockholdersBasic",
)
MISSING = "Choose a completed market and SEC snapshot with saved companyfacts and dated issuer evidence. Refresh SEC data if these captures are unavailable."
RESOURCE = re.compile(
    r"https://data\.sec\.gov/api/xbrl/companyfacts/CIK(\d{10})\.json\?\{\}"
)


@dataclass(frozen=True)
class IncomeReport:
    filed: date
    accession: str
    form: str
    end: date
    start: date | None = None
    prior_start: date | None = None
    prior_end: date | None = None
    concept: str | None = None
    income: float | None = None
    previous: float | None = None
    source_url: str | None = None

    @property
    def scale(self):
        return self.income * 365 / ((self.end - self.start).days + 1)

    @property
    def growth(self):
        return (self.income - self.previous) / max(
            abs(self.previous), abs(self.income), 1
        )


@lru_cache(maxsize=32768)
def _date(value):
    return date.fromisoformat(value)


def _duration(form, start, end):
    days = (end - start).days + 1
    intervals = [(330, 400)] if form == "10-K" else [(75, 105), (160, 205), (245, 300)]
    return any(lo <= days <= hi for lo, hi in intervals)


# Citigroup's pinned companyfacts stops at its FY2025 report. The subsequent
# original 10-Q cash-flow statements print both YTD amounts in USD millions.
_CITI_10Q = {
    ("0000831001-26-000019", "2026-05-07", "2026-03-31"): (5785, 4064),
    ("0000831001-26-000045", "2026-08-06", "2026-06-30"): (11616, 8083),
    ("0000831001-26-000056", "2026-11-05", "2026-09-30"): (16861, 11835),
}


def _original_statement(cik, report):
    key = report.accession, str(report.filed), str(report.end)
    if cik != "0000831001" or report.form != "10-Q" or key not in _CITI_10Q:
        return report
    current, previous = _CITI_10Q[key]
    source = f"https://www.sec.gov/Archives/edgar/data/831001/{report.accession.replace('-', '')}/c-{report.end:%Y%m%d}.htm"
    return replace(
        report,
        start=date(2026, 1, 1),
        prior_start=date(2025, 1, 1),
        prior_end=report.end.replace(year=2025),
        concept="Citigroup’s net income",
        income=current * 1_000_000,
        previous=previous * 1_000_000,
        source_url=source,
    )


def normalize(company, submissions=None, *, reviewed_statements=False):
    # Recent submissions supply a fiscal-end anchor even when an original
    # filing has no comparable fact. Older filings use same-accession anchors.
    filings = {}
    recent = (submissions or {}).get("filings", {}).get("recent", {})
    for acc, form, filed, end in zip(
        *(
            recent.get(k, ())
            for k in ("accessionNumber", "form", "filingDate", "reportDate")
        )
    ):
        if form in ("10-Q", "10-K") and ACCESSION.fullmatch(acc) and end and filed:
            filings[(filed, acc)] = (form, end)
    anchors = {}
    values = defaultdict(lambda: defaultdict(set))
    facts = company.get("facts", {}).get("us-gaap", {})
    for tag in ("Assets", *PERIODIC_INCOME_TAGS, "Revenues", "EarningsPerShareDiluted"):
        unit = "USD/shares" if tag == "EarningsPerShareDiluted" else "USD"
        for row in facts.get(tag, {}).get("units", {}).get(unit, ()):
            form, filed, end, acc = (
                row.get(k, "") for k in ("form", "filed", "end", "accn")
            )
            if (
                form not in ("10-K", "10-Q")
                or not filed
                or not end
                or end > filed
                or not ACCESSION.fullmatch(acc)
            ):
                continue
            key = filed, acc
            if key not in anchors or end > anchors[key][1]:
                anchors[key] = form, end
            if (
                tag in PERIODIC_INCOME_TAGS
                and row.get("start")
                and isinstance(row.get("val"), (int, float))
                and isfinite(row["val"])
            ):
                values[key][tag, _date(row["start"]), _date(end)].add(row["val"])
    reports = []
    for (filed, acc), (form, end) in sorted((anchors | filings).items()):
        filed, end = _date(filed), _date(end)
        if not 0 <= (filed - end).days <= 160 or (reports and end < reports[-1].end):
            continue
        report = IncomeReport(filed, acc, form, end)
        facts = values.get((filed.isoformat(), acc), {})
        for tag in PERIODIC_INCOME_TAGS:
            starts = [
                a
                for (t, a, b), vs in facts.items()
                if t == tag and b == end and len(vs) == 1 and _duration(form, a, b)
            ]
            if not starts:
                continue
            start = min(starts)
            previous = [
                (a, b, next(iter(vs)))
                for (t, a, b), vs in facts.items()
                if t == tag
                and len(vs) == 1
                and 350 <= (start - a).days <= 380
                and 350 <= (end - b).days <= 380
                and abs((b - a) - (end - start)).days <= 8
            ]
            if len(previous) == 1:
                a, b, prior = previous[0]
                report = IncomeReport(
                    filed,
                    acc,
                    form,
                    end,
                    start,
                    a,
                    b,
                    tag,
                    next(iter(facts[tag, start, end])),
                    prior,
                )
                break
        if report.income is None and (str(filed), acc) in filings:
            cik = str(company.get("cik", "")).zfill(10)
            report = _original_statement(cik, report)
            if report.income is None and reviewed_statements:
                report = reviewed_periodic_income.recover(cik, report)
        reports.append(report)
    return reports


def succession_histories(dataset):
    """Index only filings made while each verified registrant represented the listing."""
    histories = {}
    for listing in dataset.metadata.get("fundamentals", {}).get("coverage", ()):
        previous = listing.get("predecessor_issuers")
        if not previous:
            continue
        chain = sorted(previous, key=lambda issuer: issuer["effective"])
        history = []
        first = date.min
        for issuer in [*chain, {"cik": listing["cik"]}]:
            end = _date(issuer["effective"]) if "effective" in issuer else date.max
            expires = (
                _date(issuer["valid_before"])
                if issuer.get("valid_before")
                else date.max
            )
            for report in dataset.periodic_income.get(issuer["cik"], ()):
                if first <= report.filed < end:
                    history.append((issuer["cik"], report, expires))
            first = end
        histories[listing["symbol"]] = [r.filed for _, r, _ in history], history
    return histories


def load_reports(store, dataset):
    fundamentals = dataset.metadata.get("fundamentals", {})
    pinned = set(fundamentals.get("observation_ids", ()))
    policy = fundamentals.get("periodic_income_policy")
    if not pinned or not dataset.annual_income:
        raise ResearchError(MISSING)
    with store.connect() as db:
        captures = {}
        for row in db.execute(
            "SELECT id, resource, digest FROM observations WHERE provider='sec' AND (resource LIKE '%/companyfacts/CIK%.json?{}' OR resource LIKE '%/submissions/CIK%.json?{}')"
        ):
            if row["id"] in pinned:
                previous = captures.setdefault(row["resource"], row)
                if previous["digest"] != row["digest"]:
                    raise ResearchError(
                        "The saved snapshot contains conflicting SEC captures for the same issuer resource."
                    )

        def read(row):
            packed = db.execute(
                "SELECT body FROM observations WHERE id=?", (row["id"],)
            ).fetchone()[0]
            raw = (
                store._read_blob(db, row["digest"])
                if packed.startswith(b"@blob:")
                else gzip.decompress(packed)
            )
            if sha256(raw).hexdigest() != row["digest"]:
                raise ResearchError(
                    "The saved SEC filing source failed its integrity check."
                )
            return json.loads(raw)

        result = {}
        for url, row in captures.items():
            match = RESOURCE.fullmatch(url)
            if not match:
                continue
            cik = match[1]
            company = read(row)
            sub = captures.get(f"https://data.sec.gov/submissions/CIK{cik}.json?{{}}")
            if not sub:
                raise ResearchError(MISSING)
            submissions = read(sub)
            if any(
                str(source.get("cik", "")).zfill(10) != cik
                for source in (company, submissions)
            ):
                raise ResearchError(
                    "The saved SEC captures disagree on issuer identity."
                )
            result[cik] = normalize(
                company,
                submissions,
                reviewed_statements=policy == reviewed_periodic_income.VERSION,
            )
    issuers = {r["cik"] for rows in dataset.annual_income.values() for r in rows}
    if not result or issuers - result.keys():
        raise ResearchError(MISSING)
    return result


def research_dataset(store, dataset_id, recipe):
    dataset = store.dataset(dataset_id)
    if recipe.get("requires_periodic_income"):
        return replace(dataset, periodic_income=load_reports(store, dataset))
    return dataset
