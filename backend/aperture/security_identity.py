"""Small reviewed identity conflicts; no guessed cross-issuer accounting."""

from datetime import date


def reconcile_current_listings(api, candidates, members, first_membership):
    """Resolve duplicate provider IDs only in a supported current-index cohort.

    Match every descriptive listing field, the unique active record and an
    individual lookup. The first eligible date must be no earlier than the
    current constituent's recorded admission. Old/reused tickers and different
    classes/names remain unresolved; all original IDs remain in the audit.
    """
    from urllib.parse import quote

    from .config import PAPER_URL
    from .domain import ResearchError

    audit = {}
    for symbol, observed in members.items():
        rows = list(candidates.get(symbol, {}).values())
        if (
            len(rows) < 2
            or not observed.get("date_added")
            or symbol not in first_membership
        ):
            continue
        if first_membership[symbol] < date.fromisoformat(observed["date_added"]):
            continue
        fields = ("symbol", "name", "exchange", "class")
        if (
            any(not r.get(k) for r in rows for k in fields)
            or len({tuple(r[k] for k in fields) for r in rows}) != 1
        ):
            continue
        active = [r for r in rows if r.get("status") == "active"]
        if len(active) != 1:
            continue
        asset = api.get(
            "alpaca", PAPER_URL + "/v2/assets/" + quote(symbol, safe=""), ttl=86400
        )
        if (
            not isinstance(asset, dict)
            or asset.get("id") != active[0]["id"]
            or asset.get("status") != "active"
            or any(asset.get(k) != active[0][k] for k in fields)
        ):
            raise ResearchError(
                f"{symbol}: individual and bulk listing identities disagree."
            )
        audit[symbol] = {
            "basis": "Matching provider lookup and identical listing descriptors, within the current constituent admission cohort",
            "all_candidate_ids": sorted(candidates[symbol]),
            "selected_id": asset["id"],
            "date_added": observed["date_added"],
            "first_eligible": str(first_membership[symbol]),
        }
        candidates[symbol] = {asset["id"]: asset}
    return audit


def supplement_listing_directory(api, candidates, names):
    """Resolve omissions in bulk assets without overriding a listed collision.

    The individual endpoint can retain inactive listings omitted by both bulk
    directories. This supplies the same provider metadata, not certification of
    an issuer's entire history. Existing corporate-action/identity gates apply.
    """
    from urllib.parse import quote

    from .config import PAPER_URL
    from .domain import ResearchError
    from .providers import ResourceMissing

    lookups = {}
    for symbol in sorted(set(names)):
        if candidates.get(symbol):
            continue
        try:
            asset = api.get(
                "alpaca", PAPER_URL + "/v2/assets/" + quote(symbol, safe=""), ttl=86400
            )
        except ResourceMissing:
            lookups[symbol] = {"status": "not_found"}
            continue
        if (
            not isinstance(asset, dict)
            or asset.get("symbol") != symbol
            or not isinstance(asset.get("id"), str)
            or not asset["id"]
            or not asset.get("name")
        ):
            raise ResearchError(
                f"{symbol}: individual asset lookup returned inconsistent listing metadata."
            )
        candidates[symbol][asset["id"]] = asset
        lookups[symbol] = {"status": "found", "listing_id": asset["id"]}
    return lookups


BNY_GAP = (
    "BNY bank prices are paired with unrelated former BNY municipal-fund actions "
    "in the provider capture. The bank/fund action identities are not reconciled; "
    "this security is excluded rather than applying the fund's merger or income. "
    "https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html "
    "https://www.sec.gov/Archives/edgar/data/882150/000119312526043113/d104966d425.htm"
)


DOW_GAP = (
    "DOW history before April 2, 2019 mixes the old Dow Chemical listing, its "
    "2017 DowDuPont conversion and the new Dow Inc. listing. The provider "
    "returns zero-volume flat quotes through the intervening period without "
    "the old merger terms. This historical identity path is not reconciled. "
    "https://investors.dow.com/en/news/news-details/2019/Dow-completes-separation-from-DowDuPont/default.aspx "
    "https://www.sec.gov/Archives/edgar/data/1666700/000166670017000026/dowdupont3q17093017.htm"
)


def known_gaps(names, first, last):
    gaps = []
    if "BNY" in names:
        gaps.append(
            {
                "symbol": "BNY",
                "start": str(first),
                "end": str(last),
                "kind": "identity",
                "reason": BNY_GAP,
            }
        )
    if "DOW" in names and first < date(2019, 4, 2):
        gaps.append(
            {
                "symbol": "DOW",
                "start": str(first),
                "end": str(min(last, date(2019, 4, 1))),
                "kind": "identity",
                "reason": DOW_GAP,
            }
        )
    return gaps


def freeze_historical_quotes(base, symbol, asof, begin):
    """Do not ask an expired/ambiguous vintage for today's unrelated quotes.

    Preserve its complete saved history, including prior scheduled exits. A
    new/current cohort is still refreshed normally; full Download revalidates.
    """
    return bool(
        base
        and symbol in base.bars
        and asof < begin
        and (not base.bars[symbol] or max(b.session for b in base.bars[symbol]) < begin)
    )
