"""Narrow, dated primary-source corrections; original vendor records survive.

Never infer a continuation merely from a 1:1 ratio or an unchanged ticker.
Only these reviewed event/security/date signatures qualify. A changed provider
record fails closed and returns to the normal incomplete-consideration gate.
"""

import hashlib
import re
from dataclasses import replace
from datetime import date
from decimal import Decimal

from .domain import decimal, ResearchError

VERSION = "reviewed-corporate-actions-v4-stable-primary"
MISSING_SPLITS = {
    "CP": {
        "symbol": "CP",
        "effective": "2021-05-14",
        "ratio": "5",
        "listing_id": "143fc802-6cb5-4905-9161-dbaf899d283a",
        "url": "https://www.sec.gov/Archives/edgar/data/16875/000001687521000032/R23.htm",
        "sha256": "e32e355963c30f1e0bdb00240592871d77d7759bea2ff9bd31a1b3edcd5e73b7",
        "content_sha256": "0a1f0371c0b5f23a302d330c3b6e8ae73028e795d899e5edaa0278c0fc6e4d44",
        "basis": "The issuer's filed interim statements confirm five shares for each prior common share, with split-basis trading from May 14, 2021. The exact listing and raw/split-adjusted price-unit check are required before adding this missing action.",
    }
}
CONTINUATIONS = {
    "df44824a-c47a-46fa-b9fc-2f7574b6f21f": {
        "symbol": "APO",
        "sha256": "d5fc334f7e22eb9a0a410320fad9cdf0de8ddb8e7d421640b8b794ec97ee480b",
        "content_sha256": "7cbaf800866e0819fe70cd35849e1780d610a12cdf95eb15fb41d09e9e73d02a",
        "effective": "2022-01-01",
        "old_cusip": "03768E105",
        "new_cusip": "03769M106",
        "url": "https://www.sec.gov/Archives/edgar/data/1858681/000119312522000274/d285518d8k12b.htm",
        "basis": "Completed merger, Item 2.01: each publicly held Apollo Class A share converted to one new Apollo common share; the distinct Athene 1.149 conversion does not apply to APO.",
    },
    "e6e0cd45-d2d6-4a41-8c52-974c40a5f08e": {
        "symbol": "FRT",
        "sha256": "cd85b108c503bbcef3488625a1b56e54d1431879eacfb15cc7766d1efed95aad",
        "content_sha256": "8c9248d1a9b18d49ec6cb62a60b15cd41e6073335235444c56c20a1de0101ead",
        "effective": "2022-01-01",
        "old_cusip": "313747206",
        "new_cusip": "313745101",
        "url": "https://www.sec.gov/Archives/edgar/data/34903/000119312522002748/d275243d8k.htm",
        "basis": "Completed holding-company reorganization: outstanding capital shares converted one for one into equivalent new holding-company shares; common trading symbol remains FRT.",
    },
    "9586659d-39b6-4d05-9f4c-2c515214dc03": {
        "symbol": "J",
        "sha256": "a6a2fb8851816c6d95ce78c7506339246859cb5f011dc0e49b5dc6f5b23845c3",
        "content_sha256": "37cd66361418c383656fc850efcd2645bbe6141b3a65afdb95eb1fa0f293c04c",
        "effective": "2022-08-29",
        "old_cusip": "469814107",
        "new_cusip": "46982L108",
        "url": "https://www.sec.gov/Archives/edgar/data/52988/000119312522232264/d373758d8k12g3.htm",
        "basis": "Same ownership and common-share count in the holding-company exchange; uninterrupted J trading, with new CUSIP 46982L108. Dated issuer transaction announcement and filed successor registration substantiate the exchange.",
    },
    "744052c7-da90-4f7b-bf82-3983155d3c38": {
        "symbol": "LIN",
        "sha256": "ca1f1e103c89a6efa43453cb3cb00556ddbe0f7e5d34b3103f9677e2190ba0d4",
        "content_sha256": "44a321f00173361c8ca6d7234def3e6d690535eb741d57911209c1c35900a636",
        "effective": "2023-03-01",
        "old_cusip": "G5494J103",
        "new_cusip": "G54950103",
        "url": "https://www.sec.gov/Archives/edgar/data/1707925/000162828023013457/lin-20230331.htm",
        "basis": "Completed intercompany reorganization, Note 11: one new holding-company share for each old Linde share; LIN trading continues.",
    },
}


def primary_fingerprint(raw):
    """Ignore only the SEC's trailing injected external-script URL.

    Keep every filing byte, including text, markup and whitespace. This exact
    empty, root-relative script immediately before the closing body is added by
    the SEC edge service and varies between identical document responses. The
    unmodified response and its raw digest remain in the captured source store.
    """
    content = re.sub(
        rb'<script type="text/javascript"  src="/(?!/)[A-Za-z0-9/_-]+"></script>(?=</body>\s*</html>(?:\s*</TEXT>\s*</DOCUMENT>)?\s*$)',
        b"",
        raw,
        flags=re.IGNORECASE,
    )
    return hashlib.sha256(content).hexdigest()


def primary_matches(raw, proof):
    return hashlib.sha256(raw).hexdigest() == proof["sha256"] or (
        bool(proof.get("content_sha256"))
        and primary_fingerprint(raw) == proof["content_sha256"]
    )


def continuation(event):
    proof = CONTINUATIONS.get(event.get("id"))
    if not proof:
        return None
    if (
        event.get("kind") != "stock_mergers"
        or event.get("acquiree_symbol") != proof["symbol"]
        or event.get("effective_date") != proof["effective"]
        or event.get("acquiree_cusip") != proof["old_cusip"]
        or event.get("acquirer_cusip") != proof["new_cusip"]
        or event.get("acquirer_symbol") not in ("", proof["symbol"])
        or decimal(event.get("acquiree_rate", 0)) != 1
        or decimal(event.get("acquirer_rate", 0)) != 1
        or decimal(event.get("cash_rate", 0)) != 0
        or decimal(event.get("rate", 0)) != 0
    ):
        return None
    return {"version": VERSION, "event_id": event["id"], **proof}


def verified_continuation(event, api):
    proof = continuation(event)
    if proof is None:
        return None
    raw = api.document(proof["url"])
    if not primary_matches(raw, proof):
        raise ResearchError(
            f"{proof['symbol']}: the reviewed corporate-action source fingerprint changed. Recheck the dated source before using this correction."
        )
    return proof


def supplement_splits(bars, adjusted, identities, api):
    """Restore only a missing reviewed action, never guess from a price fall."""
    corrections = []
    half = Decimal(".005")
    for symbol, proof in MISSING_SPLITS.items():
        day = date.fromisoformat(proof["effective"])
        rows, checks = bars.get(symbol, {}), adjusted.get(symbol, {})
        if day not in rows or rows[day].split != 1:
            continue  # A supplied action must not be applied a second time.
        if identities.get(symbol, {}).get("candidate_ids") != [proof["listing_id"]]:
            continue
        before = max((d for d in rows if d < day), default=None)
        if before is None or before not in checks or day not in checks:
            continue
        pa, pb = checks[before].close, checks[day].close
        if min(pa, pb) <= half:
            continue
        ratio = decimal(proof["ratio"])
        expected = rows[day].close * ratio / rows[before].close
        if (
            not (pb - half) / (pa + half) - Decimal(".00000001")
            <= expected
            <= (pb + half) / (pa - half) + Decimal(".00000001")
        ):
            continue  # Already-adjusted or contradictory quotes remain blocked.
        raw = api.document(proof["url"])
        if not primary_matches(raw, proof):
            raise ResearchError(
                f"{symbol}: reviewed split source fingerprint changed. Recheck the primary source."
            )
        rows[day] = replace(rows[day], split=ratio)
        corrections.append(
            {
                "id": f"reviewed-{symbol}-{day}-split",
                "kind": "reviewed_splits",
                "source": symbol,
                "effective": str(day),
                "ratio": str(ratio),
                "reviewed_evidence": {"version": VERSION, **proof},
                "original_provider_split": "1",
            }
        )
    return corrections
