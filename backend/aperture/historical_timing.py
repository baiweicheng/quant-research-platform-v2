"""Reviewed market timing for native mergers; legal dates remain in provenance."""

from datetime import date

from .action_evidence import primary_matches
from .domain import ResearchError, decimal

VERSION = "reviewed-native-merger-timing-v1"
TIMING = {
    "ANSS": {
        "event_id": "945b474d-5b29-4f86-a71b-8fc0bae5bae3",
        "listing_id": "d48dfc03-80c7-4054-a3b1-e41bbfe2a92f",
        "cusip": "03662Q105",
        "kind": "stock_and_cash_mergers",
        "source_effective": "2025-07-18",
        "legal_effective": "2025-07-17",
        "effective": "2025-07-17",
        "last_trading": "2025-07-16",
        "target": "SNPS",
        "target_cusip": "871607107",
        "ratio": "0.3399",
        "cash": "199.91",
        "url": "https://www.sec.gov/Archives/edgar/data/1013462/000114036125026141/ef20052066_8k.htm",
        "sha256": "325ac76a936ba8f6dbc02d48316226f89b6ce7719eaad9bbe3453029e6b95f8c",
        "content_sha256": "426bf69a6bb880823207f8d84fc5337d2ef697122d58b87f5e2805a3997c4ee2",
        "basis": "Completed merger 8-K confirms July 17 closing and pre-open suspension, 0.3399 SNPS shares plus $199.91. The vendor's July 18 effective date is retained in source provenance; its captured cash payment date is unchanged.",
    },
    "CTLT": {
        "event_id": "ab2c0cec-c280-49a4-950e-5ab7717a83d9",
        "listing_id": "6fc7c918-3c22-46b3-b8cf-0339c6f325be",
        "cusip": "148806102",
        "kind": "cash_mergers",
        "source_effective": "2024-12-19",
        "legal_effective": "2024-12-18",
        "effective": "2024-12-18",
        "last_trading": "2024-12-17",
        "target": None,
        "ratio": "0",
        "cash": "63.5",
        "url": "https://www.sec.gov/Archives/edgar/data/1596783/000119312524280922/d902883d8k.htm",
        "sha256": "af8020f90073a07d5699ffc7c5e9109bc2394ab9f10568d72e65caecf77bc65e",
        "content_sha256": "b37d91b7e7c32f8de364489ca542efeab9c53fc3cbc1a545fc6aa67710b91425",
        "basis": "Completed merger 8-K confirms $63.50 per share and suspension before the December 18 open. The vendor's December 19 effective date and cash payment field remain in provenance; the payment date is not moved earlier.",
    },
    "HES": {
        "event_id": "325b0d26-96bd-4e07-9cf8-eb30e8b5979d",
        "listing_id": "945cfc7c-88e3-4db8-9f17-a4889b038cc5",
        "cusip": "42809H107",
        "kind": "stock_mergers",
        "source_effective": "2025-07-21",
        "legal_effective": "2025-07-18",
        "effective": "2025-07-18",
        "last_trading": "2025-07-17",
        "target": "CVX",
        "target_cusip": "166764100",
        "ratio": "1.025",
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/4447/000095014225001950/eh250651090_8k.htm",
        "sha256": "be047631e330ad26fcbe0ba5f20c99eb727963dce26efb59675913774c3dd7d9",
        "content_sha256": "f0bdbe694d6db9d01d7c86d2d85de863cb9fc683c2c90434889b106b53bd79c6",
        "basis": "Completed merger 8-K confirms July 18 pre-open suspension and 1.025 CVX shares. Native July 21 timing is corrected only after reconciling the exact stale September 2024 instruction; raw source records remain available.",
        "rejected_events": {
            "153142bf-39cd-4723-9dd8-56c7c7fa075d": {
                "source_effective": "2024-09-30",
                "kind": "stock_mergers",
                "target": "CVX",
                "ratio": "1.025",
                "cash": "0",
                "basis": "Rejected September 30, 2024 conversion instruction: the completed-merger filing establishes that Hess common stock instead remained outstanding until its July 18, 2025 conversion. This stale source record does not execute or create consideration.",
            }
        },
    },
    "AGN": {
        "event_id": "dfd703bf-adad-46e4-bd18-c4fcbc6ed81d",
        "listing_id": "a6b00615-8b89-493c-9fe3-e31e13be219e",
        "cusip": "G0177J108",
        "kind": "stock_and_cash_mergers",
        "legal_effective": "2020-05-08",
        "effective": "2020-05-11",
        "last_trading": "2020-05-08",
        "target": "ABBV",
        "target_cusip": "00287Y109",
        "ratio": "0.866",
        "cash": "120.3",
        "url": "https://www.sec.gov/Archives/edgar/data/1578845/000119312520137717/d927229d8k.htm",
        "sha256": "c0fb364d8920eafc85be6c9f7c6faf3cda6f132573aed380eb6a6a8a81ca319c",
        "content_sha256": "adaeeb958488ff91ee716296799b7a7edaf0e12d22fae7e138a7d3d4891166e7",
        "basis": "Completed scheme 8-K, Item 3.01: suspend before May 11 open; Item 2.01 confirms $120.30 and 0.866 ABBV shares.",
    },
    "CXO": {
        "event_id": "3056730b-819c-4706-8db0-c04acbc692c8",
        "listing_id": "bb8ae97d-559d-440b-a039-ae36901528d4",
        "cusip": "20605P101",
        "kind": "stock_mergers",
        "legal_effective": "2021-01-15",
        "effective": "2021-01-19",
        "last_trading": "2021-01-15",
        "target": "COP",
        "target_cusip": "20825C104",
        "ratio": "1.46",
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/876661/000087666121000081/ruleprovisionnotice.htm",
        "sha256": "0c3ad531ced998d232324040d73606a1b7b3604cf87926a298500e3a13f1fed5",
        "content_sha256": "0c3ad531ced998d232324040d73606a1b7b3604cf87926a298500e3a13f1fed5",
        "basis": "NYSE filed removal notice confirms suspension before January 19 open following January 15 consummation; native 1.46 COP terms independently match ConocoPhillips filed Note 3.",
        "terms_source": {
            "url": "https://www.sec.gov/Archives/edgar/data/1163165/000156276221000304/R10.htm",
            "sha256": "d6bc3ec236f1d8351d7ac4ec03871c8c4198c797cc9b413ac0b4fc957cf0ce9c",
            "content_sha256": "4b7caab19a1952675b60547bf5f2a5b2083de05cfa44bea4090b04d059a94ee3",
        },
    },
    "NLSN": {
        "event_id": "90b61614-a996-4832-8ec9-f1253a3c12a8",
        "listing_id": "80d95be0-032d-4182-96f9-da6ee08c027e",
        "cusip": "G6518L108",
        "kind": "cash_mergers",
        "legal_effective": "2022-10-11",
        "effective": "2022-10-12",
        "last_trading": "2022-10-11",
        "target": None,
        "ratio": "0",
        "cash": "28",
        "url": "https://www.sec.gov/Archives/edgar/data/1492633/000119312522260583/d407513d8k.htm",
        "sha256": "7e3fec236640766bfd9055b2e34fe80b669ede7cdcda16db3db78f68a10a5cdd",
        "content_sha256": "885ab14ca762a713c8c209108e9615a758fa2f41bf6cbfa5d5a2376d07575c78",
        "basis": "Completed acquisition 8-K: $28 per ordinary share, suspend before October 12 open following October 11 closing.",
    },
    "ATVI": {
        "event_id": "eca55553-3794-4802-9a86-5541ffc6aeb9",
        "listing_id": "4fd68286-4b8d-4208-a9b6-99d212efd4b9",
        "cusip": "00507V109",
        "kind": "cash_mergers",
        "legal_effective": "2023-10-13",
        "effective": "2023-10-13",
        "last_trading": "2023-10-12",
        "zero_volume_mark": "2023-10-13",
        "target": None,
        "ratio": "0",
        "cash": "95",
        "url": "https://www.sec.gov/Archives/edgar/data/718877/000110465923108985/tm2328253d1_8k.htm",
        "sha256": "88fdea02f0ec4f1306a0b47e83ffb85eae36906d02e961ea3b5ffb331808e5f3",
        "content_sha256": "88fdea02f0ec4f1306a0b47e83ffb85eae36906d02e961ea3b5ffb331808e5f3",
        "basis": "Completed merger 8-K: halt before October 13 open, $95 cash. Nasdaq ECA2023-588 confirms last trading October 12. Only the exact flat zero-volume closing-date mark is non-executable.",
    },
}


def apply_timing(events, identities, bars, api, issue):
    result = []
    rejections = {}
    for event in events:
        proof = TIMING.get(event["source"])
        native = event.get("source_record") or {}
        if not proof or event["id"] != proof["event_id"]:
            result.append(event)
            continue
        # Native event/date/security/economics all have to match. A changed
        # instruction stays unresolved, rather than inheriting the old proof.
        if (
            identities.get(event["source"], {}).get("candidate_ids")
            != [proof["listing_id"]]
            or native.get("acquiree_cusip") != proof["cusip"]
            or native.get("effective_date")
            != proof.get("source_effective", proof["legal_effective"])
            or (
                proof.get("target_cusip")
                and native.get("acquirer_cusip") != proof["target_cusip"]
            )
            or event["kind"] != proof["kind"]
            or event.get("target") != proof["target"]
            or decimal(event.get("ratio", 0)) != decimal(proof["ratio"])
            or decimal(event.get("cash", 0)) != decimal(proof["cash"])
        ):
            issue(
                event["source"],
                event["effective"],
                "Reviewed merger timing no longer matches the captured listing or native terms.",
            )
            result.append(event)
            continue
        alternatives = [
            e
            for e in events
            if e["source"] == event["source"]
            and (e.get("source_record") or {}).get("effective_date")
            == proof.get("source_effective", proof["legal_effective"])
            and (
                e["kind"],
                e.get("target"),
                decimal(e.get("cash", 0)),
                decimal(e.get("ratio", 0)),
            )
            != (
                event["kind"],
                event.get("target"),
                decimal(event.get("cash", 0)),
                decimal(event.get("ratio", 0)),
            )
        ]
        if alternatives:
            issue(
                event["source"],
                event["effective"],
                "Alternative native merger instructions prevent the reviewed market-date correction.",
            )
            result.append(event)
            continue
        rejected = {}
        if proof.get("rejected_events"):
            unresolved = False
            for other in events:
                if (
                    other["source"] != event["source"]
                    or other["id"] == event["id"]
                    or other["kind"]
                    not in (
                        "stock_mergers",
                        "cash_mergers",
                        "stock_and_cash_mergers",
                        "rejected_native_merger",
                    )
                ):
                    continue
                rejected_proof = proof["rejected_events"].get(other["id"])
                source = other.get("source_record") or {}
                original_kind = other.get("original_kind", other["kind"])
                if (
                    not rejected_proof
                    or original_kind != rejected_proof["kind"]
                    or other["effective"] != rejected_proof["source_effective"]
                    or source.get("effective_date")
                    != rejected_proof["source_effective"]
                    or source.get("acquiree_cusip") != proof["cusip"]
                    or source.get("acquirer_cusip") != proof["target_cusip"]
                    or other.get("target") != rejected_proof["target"]
                    or decimal(other.get("ratio", 0))
                    != decimal(rejected_proof["ratio"])
                    or decimal(other.get("cash", 0)) != decimal(rejected_proof["cash"])
                ):
                    unresolved = True
                    break
                rejected[other["id"]] = {
                    "version": VERSION,
                    "url": proof["url"],
                    "sha256": proof["sha256"],
                    "content_sha256": proof["content_sha256"],
                    "basis": rejected_proof["basis"],
                    "verified_conversion": proof["effective"],
                }
            if unresolved:
                issue(
                    event["source"],
                    event["effective"],
                    "Unreconciled additional merger instructions prevent the reviewed market-date correction.",
                )
                result.append(event)
                continue
        rows = bars.get(event["source"], {})
        last = date.fromisoformat(proof["last_trading"])
        expected = date.fromisoformat(
            proof.get("zero_volume_mark", proof["last_trading"])
        )
        valid = bool(rows and max(rows) == expected and last in rows)
        if valid and "zero_volume_mark" in proof:
            mark = rows[expected]
            valid = mark.volume == 0 and all(
                getattr(mark, k) == rows[last].close
                for k in ("open", "high", "low", "close")
            )
        if not valid:
            issue(
                event["source"],
                event["effective"],
                "Reviewed merger timing conflicts with the captured price lifetime or non-trading mark.",
            )
            result.append(event)
            continue
        for source in [
            proof,
            *([proof["terms_source"]] if "terms_source" in proof else []),
        ]:
            if not primary_matches(api.document(source["url"]), source):
                raise ResearchError(
                    f"{event['source']}: reviewed merger timing source fingerprint changed."
                )
        result.append(
            {
                **event,
                "effective": proof["effective"],
                "legal_effective": proof["legal_effective"],
                **(
                    {"source_effective": proof["source_effective"]}
                    if "source_effective" in proof
                    else {}
                ),
                "reviewed_market_timing": {"version": VERSION, **proof},
            }
        )
        rejections.update(rejected)
    return [
        {
            **event,
            "original_kind": event.get("original_kind", event["kind"]),
            "kind": "rejected_native_merger",
            "reviewed_rejection": rejections[event["id"]],
        }
        if event["id"] in rejections
        else event
        for event in result
    ]


def verified_nontrading_tail(event, rows):
    """A reviewed halt-day mark cannot invalidate contractual conversion.

    Preserve the original captured bar, but never treat it as an executable
    quote or use it to infer a price-based terminal recovery.
    """
    proof = event.get("reviewed_market_timing") or {}
    expected = TIMING.get(event.get("source"))
    if (
        not expected
        or proof != {"version": VERSION, **expected}
        or event.get("id") != expected["event_id"]
        or event.get("effective") != expected["effective"]
        or not proof.get("zero_volume_mark")
    ):
        return False
    last = date.fromisoformat(proof["last_trading"])
    final = date.fromisoformat(proof["zero_volume_mark"])
    by_day = {b.session: b for b in rows}
    if last not in by_day or not rows or rows[-1].session != final:
        return False
    tail = [b for b in rows if b.session > last]
    return (
        len(tail) == 1
        and tail[0].volume == 0
        and all(
            getattr(tail[0], k) == by_day[last].close
            for k in ("open", "high", "low", "close")
        )
    )
