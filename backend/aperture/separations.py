"""Reviewed separation share counts, distinct from vendor adjustment factors.

These exact historical quote cohorts retain the continuing parent and value
spun-off shares under the existing closing-price total-return convention. Raw
provider observations and displaced native instructions remain in provenance.
"""

from dataclasses import replace
from datetime import date, timedelta

from .action_evidence import primary_matches
from .domain import ResearchError, ZERO, ONE, decimal

VERSION = "reviewed-separations-v1"
ARCONIC = {
    "url": "https://www.sec.gov/Archives/edgar/data/4281/000110465920043824/tm2015094d1_8k.htm",
    "sha256": "d6c40d8f10e6440ceda0b5139e551b903ed5e4174415a7063b386beca651ed99",
    "content_sha256": "d6c40d8f10e6440ceda0b5139e551b903ed5e4174415a7063b386beca651ed99",
    "basis": "Old Arconic Inc. continued as Howmet (HWM), retaining one parent share and distributing 0.25 new Arconic Corporation shares per old share on April 1, 2020. HWM prices continue the old parent; the child's later $30 merger does not terminate that parent. Spun-off value is reinvested at the closing parent price in total-return research, not delivered as spendable opening cash.",
}
DOW = {
    "url": "https://www.sec.gov/Archives/edgar/data/1666700/000119312519095042/d725044d8k.htm",
    "sha256": "39d771937890f6757c6176cacb8765671e2a47f4d3e394e023fad106694530e9",
    "content_sha256": "8cc91682c97fb66ab46eb73cadf8803bfc30c4b72c5f57c7d37af17f08ff7b6b",
    "basis": "DowDuPont distributed one DOW share per three parent shares before regular trading April 2, 2019. The 1.487 vendor adjustment factor is not an issuance of additional parent shares. Research values the child at its actual opening/closing prices and reinvests at the parent's close.",
}
CORTEVA = {
    "url": "https://www.sec.gov/Archives/edgar/data/1666700/000119312519163322/d715311d8k.htm",
    "sha256": "8e40a004f5bf9178a7d148dbe660ac758f039d4b44ba1aa26d2902da73a95069",
    "content_sha256": "1e429a5c30e0aa5b0c9fab41f5e15d12a69c90dff9e78da6ab6c2c824515d8c3",
    "basis": "One CTVA share per three old DowDuPont shares, followed by a one-for-three parent reverse split and DD rename, takes effect in the June 3, 2019 session. Per new parent share, the research distribution equals one CTVA share. Native 0.4725/absent split factors are not the contractual 1/3 parent-share conversion.",
}
INCEPTION = {
    "url": "https://www.sec.gov/Archives/edgar/data/1666700/000166670019000006/a2018dwdp10-k.htm",
    "sha256": "f5d5972ff0d7e4ffaf638ce39617a5a5c136b30eedb4512ffb23a1e832a965d2",
    "content_sha256": "037795a1fdbaf63b17922363d1a8b5a241a21f28dd1e70c3e6ebc376950ffffd",
    "basis": "Item 5 dates the new DowDuPont common stock's first trading session to September 1, 2017. Earlier quotes belong to predecessor securities and cannot provide an unverified new-stock momentum history. DD here is the continuing DowDuPont issuer, not the separately captured DD.OLD predecessor.",
}
LISTINGS = {
    "ARNC": "08fcb75d-c165-4928-977d-3fe3d026f881",
    "HWM": "6f9bf0b0-4114-495f-87e4-720b2db3772a",
    "DWDP": "0cd6180e-3abd-40c7-96cf-bf80eb2d1e49",
    "DD": "72b0cd73-1037-413e-a43c-12d68c760d9e",
    "DOW": "d59870fe-9add-43f2-960c-b2ec4f29d8d3",
    "CTVA": "fc0da839-9b1d-4c5e-ac1a-148c774d1c1f",
}
PROXIES = {
    "ba1fd3b3-0526-4aab-aefe-40a9901f2a67": (
        "ARNC",
        "2020-04-01",
        "reverse_splits",
        "0.25",
    ),
    "646911b1-d521-4e71-8729-04dfde18632b": (
        "DWDP",
        "2019-04-02",
        "forward_splits",
        "1.487",
    ),
    "b4fcc1fc-5210-458d-9e9e-c08b52cd9b7b": (
        "DD",
        "2019-06-03",
        "reverse_splits",
        "0.4725",
    ),
}


def dependencies(names, first, last):
    result = set()
    if set(names) & {"ARNC", "HWM"} and first <= date(2020, 4, 1) <= last:
        result.update(("ARNC", "HWM"))
    if (
        set(names) & {"DWDP", "DD"}
        and first <= date(2019, 6, 3)
        and last >= date(2017, 9, 1)
    ):
        result.update(("DWDP", "DD", "DOW", "CTVA"))
    return result - set(names)


def dependency_asof(symbol, primary, default):
    if symbol not in primary:
        return {"ARNC": date(2020, 4, 3), "DWDP": date(2019, 5, 31)}.get(
            symbol, default
        )
    return default


def apply(bars, identities, native, events, income, first, last, api, issue, quotes):
    """Apply only verified cohorts after frozen historical blocks are assembled."""
    additions = []
    receipts = {}

    def listing(symbol):
        return identities.get(symbol, {}).get("candidate_ids") == [LISTINGS[symbol]]

    def document(proof):
        if not primary_matches(api.document(proof["url"]), proof):
            raise ResearchError(
                "Reviewed separation source fingerprint changed; recheck the primary filing."
            )

    def record(symbol, day, proof, **extra):
        return {
            "id": f"reviewed-{symbol}-{day}-separation",
            "source": symbol,
            "effective": str(day),
            "kind": "reviewed_separations",
            "reviewed_evidence": {"version": VERSION, **proof},
            **extra,
        }

    def matching(row, quote):
        return (
            row is not None
            and quote is not None
            and all(
                getattr(row, field) == getattr(quote, field)
                for field in ("open", "high", "low", "close", "volume")
            )
        )

    def structural(parents, day):
        displaced = []
        for event in native:
            symbol = event.get("symbol") or event.get("source_symbol")
            when = (
                event.get("ex_date")
                or event.get("effective_date")
                or event.get("process_date")
            )
            kind = event["kind"]
            if (
                symbol not in parents
                or when != str(day)
                or kind
                not in (
                    "forward_splits",
                    "reverse_splits",
                    "stock_dividends",
                    "spin_offs",
                    "reorganizations",
                )
            ):
                continue
            expected = PROXIES.get(event["id"])
            ratio = decimal(event.get("new_rate", 0)) / decimal(
                event.get("old_rate", 1)
            )
            if not expected or (symbol, when, kind, str(ratio.normalize())) != (
                *expected[:3],
                str(decimal(expected[3]).normalize()),
            ):
                raise ResearchError(
                    f"{symbol}: unreviewed native separation instruction; no share-count override applied."
                )
            displaced.append(event)
        return displaced

    def distribution(parents, child, day, ratio, split, proof, asof):
        if not first <= day <= last:
            return
        document(proof)
        if not listing(child) or any(not listing(p) for p in parents):
            raise ResearchError("Reviewed separation listing identity changed.")
        displaced = structural(parents, day)
        observed = quotes(
            ["DWDP", child], day - timedelta(days=7), day + timedelta(days=4), asof
        )
        child_row = observed.get(child, {}).get(day)
        if child_row is None or not matching(bars.get(child, {}).get(day), child_row):
            raise ResearchError(
                f"{child}: separation delivery price is missing or changed."
            )
        for parent in parents:
            row = bars.get(parent, {}).get(day)
            # DD as of May 2019 denotes the old, ceased DuPont security.
            # The reviewed DWDP cohort supplies CIK1666700 quotes across
            # the continuing parent's June DD rename.
            reference = observed.get("DWDP", {}).get(day)
            if not matching(row, reference):
                raise ResearchError(
                    f"{parent}: separation parent quote basis is unverified."
                )
            legal_split = decimal(split)
            per_new_share = ratio / legal_split
            amount = per_new_share * child_row.close
            if row.research_distribution not in (ZERO, amount):
                raise ResearchError(
                    f"{parent}: other spin-off consideration requires reconciliation."
                )
            bars[parent][day] = replace(
                row, split=legal_split, research_distribution=amount
            )
            income.setdefault(str(day), {})[parent] = str(
                per_new_share * child_row.open
            )
            issue(
                parent,
                day,
                "Reviewed spin-off share delivery uses closing-price total-return research; strict payment-date delivery is unsupported.",
                "cash_payment",
            )
            additions.append(
                record(
                    parent,
                    day,
                    proof,
                    target=child,
                    ratio=str(ratio),
                    ratio_basis="per_pre_split_parent_share",
                    parent_split=str(legal_split),
                    source_records=displaced,
                    child_open=str(child_row.open),
                    quote_instrument="DWDP as of 2019-05-31",
                    child_close=str(child_row.close),
                )
            )

    # Both labels represent CIK1666700 after the 2017 merger; DD.OLD is separate.
    parents = [s for s in ("DWDP", "DD") if bars.get(s)]
    if parents and first < date(2017, 9, 1):
        if any(not listing(s) for s in parents):
            raise ResearchError("DowDuPont inception identity changed.")
        document(INCEPTION)
        for symbol in parents:
            bars[symbol] = {
                d: b for d, b in bars[symbol].items() if d >= date(2017, 9, 1)
            }
            additions.append(
                record(symbol, date(2017, 9, 1), INCEPTION, lifetime_start="2017-09-01")
            )
    if parents and last >= date(2017, 9, 1):
        if "DWDP" in parents and identities["DWDP"].get("asof") != "2019-05-31":
            raise ResearchError("DowDuPont historical quote vintage changed.")
        distribution(parents, "DOW", date(2019, 4, 2), ONE / 3, ONE, DOW, "2019-05-31")
        distribution(
            parents, "CTVA", date(2019, 6, 3), ONE / 3, ONE / 3, CORTEVA, "2019-05-31"
        )

    day = date(2020, 4, 1)
    if bars.get("ARNC") and bars.get("HWM") and first <= day <= last:
        document(ARCONIC)
        if (
            not listing("ARNC")
            or not listing("HWM")
            or identities["ARNC"].get("asof") != "2020-04-03"
        ):
            raise ResearchError("Arconic/Howmet reviewed quote cohort changed.")
        displaced = structural({"ARNC", "HWM"}, day)
        observed = quotes(
            ["ARNC", "HWM"],
            day - timedelta(days=12),
            day + timedelta(days=4),
            "2020-04-03",
        )
        child, parent = (
            observed.get("ARNC", {}).get(day),
            observed.get("HWM", {}).get(day),
        )
        if child is None or not matching(bars["HWM"].get(day), parent):
            raise ResearchError(
                "Arconic separation parent/child prices are unavailable."
            )
        row = bars["ARNC"].get(day)
        if not (matching(row, child) or matching(row, parent)):
            raise ResearchError(
                "Arconic's mixed quote series changed before reconciliation."
            )
        prior = [d for d in observed["ARNC"] if d < day]
        prior = [d for d in prior if d >= first]
        if (first <= day - timedelta(days=12) and len(prior) < 5) or any(
            not matching(bars["ARNC"].get(d), observed["ARNC"][d]) for d in prior
        ):
            raise ResearchError("Arconic's original-parent price prefix is unverified.")
        amount = child.close / 4
        if bars["HWM"][day].research_distribution not in (ZERO, amount):
            raise ResearchError(
                "Howmet has additional unreviewed separation consideration."
            )
        bars["HWM"][day] = replace(
            bars["HWM"][day], split=ONE, research_distribution=amount
        )
        income.setdefault(str(day), {})["HWM"] = str(child.open / 4)
        prefix = {
            d: replace(b, symbol="HWM") for d, b in bars["ARNC"].items() if d < day
        }
        for d in prefix.keys() & bars["HWM"].keys():
            if not matching(prefix[d], bars["HWM"][d]):
                raise ResearchError(
                    "Howmet's supplied parent prefix conflicts with original Arconic quotes."
                )
        bars["HWM"].update(prefix)
        bars["ARNC"] = {
            **{d: b for d, b in bars["ARNC"].items() if d < day},
            **{
                d: replace(b, symbol="ARNC") for d, b in bars["HWM"].items() if d >= day
            },
        }
        income[str(day)]["ARNC"] = str(child.open / 4)
        # The exact later $30 cash merger belongs to the spun-off child.
        fixed = []
        for event in events:
            if (
                event["source"] == "ARNC"
                and event["kind"]
                in (
                    "cash_mergers",
                    "stock_mergers",
                    "stock_and_cash_mergers",
                    "rejected_native_merger",
                )
                and event["effective"] >= str(day)
            ):
                raw = event.get("source_record") or {}
                if (
                    event["id"] != "5382e441-ecf1-4bcd-8d03-8a93e2ce3a29"
                    or raw.get("acquiree_cusip") != "03966V107"
                    or event["effective"] != "2023-08-21"
                    or decimal(event.get("cash", 0)) != 30
                    or decimal(event.get("ratio", 0)) != 0
                    or event.get("target")
                ):
                    raise ResearchError(
                        "Unreviewed later Arconic-child merger instructions."
                    )
                event = {
                    **event,
                    "original_kind": event.get("original_kind", event["kind"]),
                    "kind": "rejected_native_merger",
                    "reviewed_rejection": {"version": VERSION, **ARCONIC},
                }
            fixed.append(event)
        events = fixed
        for symbol in ("ARNC", "HWM"):
            issue(
                symbol,
                day,
                "Reviewed spin-off share delivery uses closing-price total-return research; strict payment-date delivery is unsupported.",
                "cash_payment",
            )
            receipt = record(
                symbol,
                day,
                ARCONIC,
                target="ARNC",
                ratio="0.25",
                parent_split="1",
                source_records=displaced,
                continuation="HWM",
                child_open=str(child.open),
                child_close=str(child.close),
                parent_open=str(parent.open),
                parent_close=str(parent.close),
                price_prefix="ARNC before 2020-04-01; HWM from 2020-04-01",
            )
            additions.append(receipt)
            identities[symbol]["reviewed_separation"] = receipt
            receipts[symbol] = receipt
    # Replace derived evidence by stable ID on repeated immutable updates.
    ids = {e["id"] for e in additions}
    return [e for e in events if e["id"] not in ids] + additions, receipts
