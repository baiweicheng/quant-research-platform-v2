"""Small reviewed identity conflicts; no guessed cross-issuer accounting."""

from datetime import date

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
