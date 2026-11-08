# Free-data coverage backlog

Tracked as **B-033 (open)** in the local project backlog; requested November 4, 2026. The target is market/SEC inputs from January 2016, supporting strict full-index research from January 2017 through the latest completed session. A successful exploratory backtest does not close this item.

## Evidence and remaining work

- **Dividend payment dates:** captured Alpaca events have ex-dates and amounts, but payment dates are frequently missing before 2020. Keep the known ex-date amount separate from a verified cash entitlement. Do not manufacture payment dates. [Alpaca corporate actions](https://docs.alpaca.markets/us/reference/corporateactions-1) explains that even processed records may remain incomplete.
- **Historical identities:** symbols can be reused, and a current listing directory is not a historical security master. Dated original labels are needed for Yahoo/AABA, Delphi/APTV, Wyndham and Baker Hughes; unrelated META, IR, PX, XL and LLL listings demonstrate why arbitrary rename chains are unsafe. [Alpaca bars](https://docs.alpaca.markets/us/reference/stockbars) documents dated symbol mapping and raw-symbol fallback. Audit permanent identities and corporate succession, including equity cancellation, before certification. Recovered original-ticker quotes remain quarantined for affected periods until the original corporate actions are reconciled; prices alone do not establish valid total returns.
- **Prices and terminal values:** some departed members lack sessions around mergers, suspensions or delistings; a daily-bar service may not cover subsequent OTC trading. Missing held prices cannot be replaced by assumed sales or zero-valued contingent rights. Investigate official halt/delisting records, cancellation terms and actual proceeds.
- **Corporate actions:** captured split and spin-off records can conflict with issuer terms or their own adjusted series. Examples: WestRock's May 2016 Ingevity distribution, HCP's October/November 2016 QCP distribution, and old IR's March 2020 distribution/new IR identity. Unquoted child shares, warrants, contingent rights, missing merger recipients/ratios and cash-settlement dates need explicit treatment. A held position must never disappear at an assumed zero recovery when a merger record lacks its consideration. [Ingevity issuer release](https://www.ingevity.com/news/press-releases/ingevity-corporation-formed-with-completion-of-spinoff-from-westrock-company/), [HCP annual report](https://filecache.investorroom.com/mr5ir_healthpeakproperties/251/download/HCP%202016%20Annual%20Report.pdf), [Trane filing](https://www.sec.gov/Archives/edgar/data/1466258/000146625822000031/tt-20211231.htm).
- **SEC inputs:** current ticker-to-CIK maps do not certify historical identities. Some issuers use unsupported IFRS/custom taxonomies, multiple share classes or incomplete comparable annual facts. Keep these exclusions visible and preserve filing availability and amendment versions.
- **Membership and sectors:** retrospective constituent histories do not certify original announcement vintages, historical permanent identities or historical sector classifications. The approved November 5 research compromise allows explicitly disclosed static current/last-known sector proxies while retaining sector caps. It does not establish point-in-time sector history. See [the sector contract](RESEARCH_CONTRACT.md#sector-classifications).

## Approved research workaround

The user approved two independent choices:

1. Total-return research reinvests known distributions at the ex-date close; strict cash-flow simulation requires verified payment/delivery dates.
2. Coverage-limited research saves every excluded stock and its reasons, while strict full-index mode requires complete supported inputs.

Coverage-limited selection considers availability throughout the test window, including future dates relative to a decision. It may introduce survivorship and selection bias. Results describe the retained subset, not the complete S&P 500; chronological validation does not remove this limitation. Neither choice approves a strategy for paper/live trading.

## Completion criteria

Preserve representative captured source fixtures and exact dated exceptions. Resolve each gap with issuer/exchange/regulator evidence or a verified additional source within the user's free-resource constraint. Publish counts by symbol/date/type/accounting model and reconcile price/share/distribution units independently. All five recipes must complete the January 2017-to-latest strict historical-index case with audited benchmark and terminal accounting, while unchanged snapshots reproduce prior results. Until then, B-033 remains open. No paid subscription is authorized.

## November 8 source investigation and narrow repairs

The normalizer recognizes four reviewed, one-for-one successor exchanges whose
Alpaca records omit the recipient symbol: APO (January 1, 2022), FRT (January 1,
2022), J (August 29, 2022), and LIN (March 1, 2023). These transactions retain the
same number of publicly held common shares. The repair requires the exact
captured event ID, date, old/new CUSIPs, symbols and 1:1 ratio, no cash, and the
fingerprint of the reviewed primary filing. It preserves the original provider
record and source evidence. Other incomplete mergers remain blocked; an empty
recipient is never generally interpreted as a continuation. A full acquisition
applies these historical corrections; an incremental update preserves older
frozen inputs outside its overlap window.

Primary sources: [Apollo completed transaction, Item 2.01](https://www.sec.gov/Archives/edgar/data/1858681/000119312522000274/d285518d8k12b.htm),
[Federal Realty completed reorganization](https://www.sec.gov/Archives/edgar/data/34903/000119312522002748/d275243d8k.htm),
[Jacobs completed exchange, Items 1.01 and 8.01](https://www.sec.gov/Archives/edgar/data/52988/000119312522232264/d373758d8k12g3.htm),
[Linde completed exchange, Note 11](https://www.sec.gov/Archives/edgar/data/1707925/000162828023013457/lin-20230331.htm).

Yahoo Finance was tested directly with explicit daily start/end requests, not
only a library's defaults. It returned daily series for AAPL, CP, RJF, J, LIN,
MRP and THNPF. It returned no history for ABMD, AABA, WBA, SIVB and SIVBQ in this
probe. THNPF starts February 18, 2021, after the February 16 distribution that
needs an ex-date valuation; MRP starts February 5, 2025, after the January 21
vendor event requiring review. Neither later price establishes an executable
or fair ex-date value. These are observed source responses, not a universal
claim about all free history or all Yahoo access methods.

An unrestricted Yahoo `range=max` request silently returned quarterly AAPL
bars despite requesting `interval=1d`; explicit date bounds returned daily
bars. Always validate returned granularity and dates. Yahoo's Close and
Adjusted Close use adjustment conventions that differ from the raw-price ledger;
`auto_adjust=False` alone does not establish original share units. Its dividend
and split series also do not establish historical issuer identity, merger/CVR
proceeds or verified payment dates. See [Yahoo historical data](https://sg.help.yahoo.com/kb/finance-for-web/download-historical-data-yahoo-finance-sln2311.html),
[Yahoo adjusted close](https://in.help.yahoo.com/kb/adjusted-close-sln28256.html)
and the [yfinance maintainers' repair documentation](https://github.com/ranaroussi/yfinance/blob/main/doc/source/advanced/price_repair.rst).

The public Stooq CSV route tested returned HTTP 404 even for the AAPL control,
so access/coverage was not established; those responses do not prove that Stooq
lacks the securities. No paid resource, cookie/authentication workaround or
unverified series substitution was used. Additional sources remain candidates
for individually reconciled gaps, rather than a blanket fallback. B-033 stays
open until its strict coverage and accounting criteria above are satisfied.

A further cross-source check identified a concrete missing CP split in the
captured Alpaca actions: raw quotes change from roughly $401 to $80 on May 14,
2021, but the source action normalization supplied a factor of 1. Yahoo's split
history reports 5:1 on that date. The issuer's [filed interim financial statements](https://www.sec.gov/Archives/edgar/data/16875/000001687521000032/R23.htm)
confirm the completed split and the first ex-distribution trading date. The
normalizer supplies factor 5 only for the reviewed listing, a missing original
split, matching raw/split-adjusted price units and the captured primary-source
fingerprint. An already supplied split is never applied twice. Contradictory,
already-adjusted or unverified inputs remain blocked. This uses supplementary
action evidence; Yahoo prices are not substituted into the ledger.

For 2,726 overlapping daily closes in each of AAPL, CP and RJF, converting
Yahoo's split units largely reconciled their prices with Alpaca, but residual
price differences above two cents remained on 34, 1 and 1 dates respectively.
Thus even a matching ticker and broadly matching series do not establish an
exact raw-price replacement. Captured probe responses and discrepancy audits
are retained locally; the available supplementary data did not justify a
blanket price fallback or resolve missing cash settlement/CVR values.
