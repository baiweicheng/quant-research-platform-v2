# Free-data coverage backlog

Tracked as **B-033 (open)** in the local project backlog; requested November 4, 2026. The target is market/SEC inputs from January 2016, supporting strict full-index research from January 2017 through the latest completed session. A successful exploratory backtest does not close this item.

## Evidence and remaining work

- **Dividend payment dates:** captured Alpaca events have ex-dates and amounts, but payment dates are frequently missing before 2020. Keep the known ex-date amount separate from a verified cash entitlement. Do not manufacture payment dates. [Alpaca corporate actions](https://docs.alpaca.markets/us/reference/corporateactions-1) explains that even processed records may remain incomplete.
- **Historical identities:** symbols can be reused, and a current listing directory is not a historical security master. Dated original labels are needed for Yahoo/AABA, Delphi/APTV, Wyndham and Baker Hughes; unrelated META, IR, PX, XL and LLL listings demonstrate why arbitrary rename chains are unsafe. [Alpaca bars](https://docs.alpaca.markets/us/reference/stockbars) documents dated symbol mapping and raw-symbol fallback. Audit permanent identities and corporate succession, including equity cancellation, before certification. Recovered original-ticker quotes remain quarantined for affected periods until the original corporate actions are reconciled; prices alone do not establish valid total returns.
- **Prices and terminal values:** some departed members lack sessions around mergers, suspensions or delistings; a daily-bar service may not cover subsequent OTC trading. Missing held prices cannot be replaced by assumed sales or zero-valued contingent rights. Investigate official halt/delisting records, cancellation terms and actual proceeds.
- **Corporate actions:** captured split and spin-off records can conflict with issuer terms or their own adjusted series. Examples: WestRock's May 2016 Ingevity distribution, HCP's October/November 2016 QCP distribution, and old IR's March 2020 distribution/new IR identity. Unquoted child shares, warrants, contingent rights, missing merger recipients/ratios and cash-settlement dates need explicit treatment. A held position must never disappear at an assumed zero recovery when a merger record lacks its consideration. [Ingevity issuer release](https://www.ingevity.com/news/press-releases/ingevity-corporation-formed-with-completion-of-spinoff-from-westrock-company/), [HCP annual report](https://filecache.investorroom.com/mr5ir_healthpeakproperties/251/download/HCP%202016%20Annual%20Report.pdf), [Trane filing](https://www.sec.gov/Archives/edgar/data/1466258/000146625822000031/tt-20211231.htm).
- **SEC inputs:** current ticker-to-CIK maps do not certify historical identities. Some issuers use unsupported IFRS/custom taxonomies, multiple share classes or incomplete comparable annual facts. Keep these exclusions visible and preserve filing availability and amendment versions.
- **Membership and sectors:** retrospective constituent histories do not certify original announcement vintages, historical permanent identities or historical sector classifications. Current classifications must not be backfilled into historical decisions.

## Approved research workaround

The user approved two independent choices:

1. Total-return research reinvests known distributions at the ex-date close; strict cash-flow simulation requires verified payment/delivery dates.
2. Coverage-limited research saves every excluded stock and its reasons, while strict full-index mode requires complete supported inputs.

Coverage-limited selection considers availability throughout the test window, including future dates relative to a decision. It may introduce survivorship and selection bias. Results describe the retained subset, not the complete S&P 500; chronological validation does not remove this limitation. Neither choice approves a strategy for paper/live trading.

## Completion criteria

Preserve representative captured source fixtures and exact dated exceptions. Resolve each gap with issuer/exchange/regulator evidence or a verified additional source within the user's free-resource constraint. Publish counts by symbol/date/type/accounting model and reconcile price/share/distribution units independently. All five recipes must complete the January 2017-to-latest strict historical-index case with audited benchmark and terminal accounting, while unchanged snapshots reproduce prior results. Until then, B-033 remains open. No paid subscription is authorized.
