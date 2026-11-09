"""Narrow supplementary completed-merger terms for captured old listings.

These fill absent events, never guess a last-close exit or override supplied
consideration. Raw primary documents and original provider records survive.
"""

from datetime import date

from .action_evidence import primary_matches
from .domain import ResearchError

VERSION = "reviewed-missing-mergers-v2-stable-primary"
MERGERS = {
    "EVHC": {
        "listing_id": "3517b188-1d83-4689-b9ca-c53424bc3afe",
        "last_quote": "2018-10-10",
        "effective": "2018-10-11",
        "legal_effective": "2018-10-11",
        "target": None,
        "ratio": "0",
        "cash": "46",
        "basis": "Completed acquisition: all common shares convert to $46 cash; trading suspended before October 11 open.",
        "url": "https://www.sec.gov/Archives/edgar/data/1678531/000119312518297466/d637722dex991.htm",
        "sha256": "749678aabaa4f12b657938d95268731cee393985cbb14b1790deefa89816b9f9",
        "content_sha256": "cf9da63c5567a918949be00a864093e4f110779127d7e9b850fa95422a0f3ebd",
    },
    "XL": {
        "listing_id": "2fc13407-9775-44e2-b95a-8c807361a957",
        "last_quote": "2018-09-11",
        "effective": "2018-09-12",
        "legal_effective": "2018-09-12",
        "target": None,
        "ratio": "0",
        "cash": "57.60",
        "basis": "Completed AXA acquisition: each ordinary share converts to $57.60; suspended before September 12 open. This is the old insurer, not a later reused XL listing.",
        "url": "https://www.sec.gov/Archives/edgar/data/875159/000087515918000068/axaclosing8-k.htm",
        "sha256": "62bc1aa3b3dee77b5483b271462bee7df561a6704fc310673cb62feec951216b",
        "content_sha256": "00b342334ddbc5d0b29cba58ff215d1f800726af25b4aa9616282e97fd0dd37a",
    },
    "SCG": {
        "listing_id": "388a10f6-1978-4c63-9304-ae4a573dd1d0",
        "last_quote": "2018-12-31",
        "effective": "2019-01-02",
        "legal_effective": "2019-01-01",
        "target": "D",
        "ratio": "0.6690",
        "cash": "0",
        "basis": "Completed merger: each common share converts to 0.6690 Dominion shares; January 1 legal closing first enters the daily ledger on January 2, the first trading session.",
        "url": "https://www.sec.gov/Archives/edgar/data/754737/000119312519000643/d678624d8k.htm",
        "sha256": "7cfd6f5b1b086e8a2ccca7b4e0aa4d49456a2197c77a8948e0de68c74b28644f",
        "content_sha256": "30166e01b12b7afe60d98c672ea1aef7ecf29b53ae096d8cf167a47a12c834f8",
    },
    "ESRX": {
        "listing_id": "f0063b71-fecd-419d-981c-1dc6a3f78469",
        "last_quote": "2018-12-20",
        "effective": "2018-12-21",
        "legal_effective": "2018-12-20",
        "target": "CI",
        "ratio": "0.2434",
        "cash": "48.75",
        "basis": "Completed New Cigna combination: 0.2434 new Cigna shares plus $48.75 cash per Express Scripts share; first suspended market session December 21. Regular-way source shares trade through December 20.",
        "url": "https://www.sec.gov/Archives/edgar/data/1739940/000114036118045479/form8k12b.htm",
        "sha256": "2e3e478b441eb5432efbfaa018755ba6e7ea30e0990e89026fee919c89e7ec82",
        "content_sha256": "60c155d22d16180880a8af35c2af7cceec4d1d23ea5baa0863241e64f90df563",
    },
    "DISCK": {
        "listing_id": "1d27e066-67b9-4e11-b3a9-a6b50ca524e1",
        "last_quote": "2022-04-08",
        "effective": "2022-04-11",
        "legal_effective": "2022-04-08",
        "target": "WBD",
        "ratio": "1",
        "cash": "0",
        "basis": "Filed completed reclassification, Item 3.03: one WBD Series A common share for each Discovery Series C common share; first regular-way WBD session April 11. The separate AT&T distribution ratio does not apply.",
        "url": "https://www.sec.gov/Archives/edgar/data/1437107/000119312522103051/d328161d8k.htm",
        "sha256": "47beaf2ab285eab3925c24404a73d37f7a818964cfa20d58c7cdc7f20d66773f",
        "content_sha256": "00606b52e6a128d58b79bc1ae8fb09ad8e1423c915bb2eab6f53c818ecd50c0d",
    },
}


def candidates(names, listings, events, first, last, api):
    result = []
    for symbol in sorted(set(names) & MERGERS.keys()):
        proof = MERGERS[symbol]
        if not str(first) <= proof["effective"] <= str(last):
            continue
        if sorted(listings[symbol]) != [proof["listing_id"]]:
            continue
        if any(
            e["kind"] in {"cash_mergers", "stock_mergers", "stock_and_cash_mergers"}
            and e.get("acquiree_symbol") == symbol
            for e in events
        ):
            continue  # Never replace native consideration or an unresolved CVR.
        raw = api.document(proof["url"])
        if not primary_matches(raw, proof):
            raise ResearchError(
                f"{symbol}: reviewed merger source fingerprint changed. Recheck the primary filing."
            )
        result.append(
            {
                "id": f"reviewed-{symbol}-{proof['effective']}-merger",
                "kind": "cash_mergers"
                if not proof["target"]
                else "stock_and_cash_mergers"
                if proof["cash"] != "0"
                else "stock_mergers",
                "source": symbol,
                "target": proof["target"],
                "effective": proof["effective"],
                "legal_effective": proof["legal_effective"],
                "ratio": proof["ratio"],
                "cash": proof["cash"],
                "pay_date": None,
                "source_record": None,
                "reviewed_evidence": {"version": VERSION, "symbol": symbol, **proof},
            }
        )
    return result


def apply_missing(events, supplements, bars, issue):
    """Run after preserving a parent's prices/actions outside update overlap."""
    result = list(events)
    for event in supplements:
        proof = event["reviewed_evidence"]
        rows = bars.get(event["source"], {})
        if not rows or max(rows) != date.fromisoformat(proof["last_quote"]):
            result = [e for e in result if e["id"] != event["id"]]
            issue(
                event["source"],
                event["effective"],
                "Reviewed merger conflicts with the captured source price lifetime; the old listing's terminal consideration is not established.",
            )
            continue
        if not any(e["id"] == event["id"] for e in result):
            result.append(event)
        if event["cash"] != "0":
            issue(
                event["source"],
                event["effective"],
                "Merger cash payment date is unavailable.",
                "cash_payment",
            )
    return result
