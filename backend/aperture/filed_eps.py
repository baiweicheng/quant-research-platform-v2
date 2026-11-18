"""Recover class-specific annual EPS from a bounded set of issuer statements."""

import hashlib
import re
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP

from .eps_policy import EPS_TAGS, SCALE_REVIEW_THRESHOLD
from .filing_classes import xml
from .profitability_filings import parse_report, statement_reports
from .providers import EvidenceLimit, ResourceMissing


VERSION = "filed-class-eps-v1"
_CLASS_AXIS = "us-gaap_StatementClassOfStockAxis="
# Only reviewed exchange listings and issuer identities may use these scopes.
_CLASSES = {
    ("0001067983", "BRK.B"): ("brka_EquivalentClassBMember",),
    ("0001403161", "V"): ("us-gaap_CommonClassAMember",),
    ("0000047111", "HSY"): (
        "hsy_HersheyCommonStockMember",
        "us-gaap_CommonStockMember",
    ),
    ("0000016918", "STZ"): (
        "us-gaap_CommonClassAMember",
        "stz_ClassAStockMember",
        "stz_ClassACommonStockMember",
    ),
    ("0001437107", "DISCA"): ("disca_SeriesABandCCommonStockMember",),
    ("0001437107", "DISCK"): ("disca_SeriesABandCCommonStockMember",),
}


def extract(raw, cik, symbol):
    members = _CLASSES.get((cik, symbol), ())
    tags = ("EarningsPerShareBasic",) if symbol == "BRK.B" else EPS_TAGS[:2]
    result = {}
    for end, rows in parse_report(raw, displayed_values=True).items():
        for tag in tags:
            matching = {
                Decimal(r["displayed_value"])
                for r in rows
                if r["concept"] == "us-gaap_" + tag
                and r["scope"] in {_CLASS_AXIS + m for m in members}
            }
            if matching:
                if (
                    len(matching) == 1
                    and abs(next(iter(matching))) < SCALE_REVIEW_THRESHOLD
                ):
                    result[end] = (str(next(iter(matching))), tag)
                break
        else:
            # Older Berkshire statements present Class A earnings and explicitly
            # define the Class B relationship in that same table's footnote.
            if symbol != "BRK.B" or not re.search(
                rb"one[- ]fifteen[- ]hundredth|1\s*/\s*1,500", raw, re.IGNORECASE
            ):
                continue
            class_a = {
                Decimal(r["displayed_value"])
                for r in rows
                if r["concept"] == "us-gaap_EarningsPerShareBasic"
                and r["scope"] == _CLASS_AXIS + "us-gaap_CommonClassAMember"
            }
            if len(class_a) == 1:
                scaled = (next(iter(class_a)) / 1500).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if abs(scaled) < SCALE_REVIEW_THRESHOLD:
                    result[end] = (
                        str(scaled),
                        "ClassAEquivalentEarningsPerShareDividedBy1500",
                    )
    return result


def read(api, cik, accession, symbol):
    key = f"{VERSION}:{cik}:{accession}:{symbol}"
    store = getattr(api, "store", None)
    cached = store.filing_evidence(key) if store else None
    if cached:
        api.observations.extend(source["id"] for source in cached["sources"])
        return cached["proof"]
    start = len(api.observations)
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    proof = {}
    try:
        candidates = sorted(
            statement_reports(xml(api.document(folder + "FilingSummary.xml")))
        )
        if candidates:
            url = folder + candidates[0][2]
            raw = api.document(url)
            proof = {
                "url": url,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "periods": extract(raw, cik, symbol),
            }
    except (ResourceMissing, EvidenceLimit, SyntaxError, ValueError):
        return {}
    if store:
        store.save_filing_evidence(key, proof, api.observations[start:])
    return proof


def enrich(statements, api, first, last, class_evidence):
    """Check each decision-relevant annual accession only for a reviewed listing."""
    from .fundamentals import as_of

    if not statements or not hasattr(api, "document"):
        return statements
    if not any((r.cik, r.symbol) in _CLASSES for r in statements):
        return statements
    days = {first} | {
        row.available_at.date()
        for row in statements
        if first <= row.available_at.date() <= last
    }
    candidates = {
        (r.cik, r.accession, r.symbol): r
        for day in days
        if (r := as_of(statements, day)) is not None
        and r.eps is None
        and (r.cik, r.symbol) in _CLASSES
        and (r.symbol not in {"DISCA", "DISCK"} or str(r.filed) < "2022-04-11")
    }
    proofs = {key: read(api, *key) for key in sorted(candidates)}
    output = []
    for row in statements:
        proof = proofs.get((row.cik, row.accession, row.symbol), {})
        filed = proof.get("periods", {}).get(str(row.end))
        if row.eps is not None or filed is None:
            output.append(row)
            continue
        value, tag = filed
        class_evidence[row.accession] = {
            "version": VERSION,
            "symbol": row.symbol,
            "cik": row.cik,
            "accession": row.accession,
            "filed": str(row.filed),
            "compatible": True,
            "class_verified": True,
            "url": proof["url"],
            "sha256": proof["sha256"],
        }
        output.append(
            replace(
                row,
                eps=Decimal(value),
                eps_compatible=True,
                sources={
                    **row.sources,
                    "eps": tag,
                    "eps_policy": VERSION,
                    "share_class_evidence": proof["url"],
                    "share_class_evidence_sha256": proof["sha256"],
                },
                issues=tuple(
                    m
                    for m in row.issues
                    if not m.startswith(
                        (
                            "No dated filing-specific common-share mapping",
                            "Berkshire Class A and B",
                            "Compatible reported diluted EPS is unavailable",
                        )
                    )
                ),
            )
        )
    return tuple(output)
