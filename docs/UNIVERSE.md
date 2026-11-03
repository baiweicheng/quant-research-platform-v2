# S&P 500 universe contract

Data defaults to **the full current S&P 500 plus optional additional symbols**, with SPY reserved for benchmarking. An index can contain more than 500 securities because multiple share classes are distinct listings. Extra symbols never replace the core roster. An explicit Custom list only mode remains available and is labelled exploratory.

## Current membership and refresh

Current membership is read from the [Wikipedia constituent table](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies), including company name, current sector and CIK. This public secondary source is not a licensed index feed. The parser requires the expected columns, plausible security count, unique valid symbols and complete identity fields. Source changes or download failures preserve existing captures and fail the requested refresh. No different provider is silently substituted.

Data → Refresh current membership saves an immutable capture, source URL, SHA-256 digest, retrieval timestamp, and additions/removals relative to the previous capture. The original response is retained locally. Each new S&P download checks the capture age and refreshes it if over 24 hours old. Refresh is also available without Alpaca keys. Navigation performs no provider downloads. This is an on-demand refresh, with no new scheduled task or always-on guarantee.

The captured roster is frozen into each price dataset and its source fingerprint. Refreshing membership does not change old datasets, results or strategy approvals. A current roster supports a current review using the latest completed prices; this explicitly means selection from the roster observed now. **Current-roster price snapshots cannot run historical backtests**, even when they contain many years of warm-up prices. Historical tests must use historical membership. Older CSV/fixed-list snapshots retain their original exploratory interpretation.

## Historical membership

Data → Refresh historical membership reads [fja05680's historical roster archive](https://github.com/fja05680/sp500). Its author maintains an original history with later changes and explicitly describes completeness and delisted-price limitations. These are third-party retrospective rosters, **not a certified as-known archive**. At verification on November 3, 2026, it contained 2,720 effective-dated rosters from January 2, 1996 through August 18, 2026. Market ingestion itself starts in 2016. A refresh can extend this coverage when the upstream archive is updated; retrieving an unchanged file never extends its final effective date.

Choose Historical S&P 500 members for a backtest download. The app:

1. Checks both requested boundaries against the historical archive before downloading stocks. It never assumes that the last roster remains valid indefinitely.
2. Includes the union of the roster already in effect at the start and every membership change through the end, including stocks that subsequently departed. Supplemental names and SPY are added and deduplicated.
3. Captures active and inactive listing metadata. Missing or conflicting ticker identities stop ingestion; an inactive stock can provide historical prices without being eligible for execution.
4. Requests raw bars, actions and independent split-adjusted bars in batches of at most 100 symbols. The bounded limit is 1,500 securities including SPY and 4,000,000 daily bars. It retains the existing action/accounting checks.
5. Requires a price on every in-period session for each then-member. It stops on an unavailable member instead of treating missing data as a reason to drop that member. Prices before a stock joins may be used for signal warm-up, but the stock cannot be selected before its effective membership date.
6. Filters the cross-section on every decision date **before** factor ranks and target weights. An effective-date roster replaces the prior roster starting on that date; removal/re-entry are supported. Execution still follows the next-session model. A missing held-stock price remains a hard failure; no delisting exit or recovery is invented.
7. Freezes the relevant timeline, capture time, source digest, supplements and membership snapshot ID into the dataset and exported research audit. SEC enrichment preserves it.

The file has effective dates but lacks original announcement timestamps and verified permanent security identifiers. Retrieval time is retained separately and is never passed off as original announcement time. Ticker reuse, retrospective corrections, source omissions, delisted data, historic share classes and corporate actions remain material uncertainties. The public archive's dates are used only for explicitly labelled retrospective research. **No result is certified survivorship-safe or fully point-in-time correct.** A validated vintage/security-master archive plus complete departed-security prices/actions would be needed for that stronger claim.

Historical sectors are Unknown rather than backfilled from today's GICS classification. They share the configured sector cap; this can keep substantial cash. Extra stocks form an explicitly fixed supplement, which can introduce selection/survivorship bias even when the S&P core varies correctly over time.

## Paper boundaries

Paper settings retain a concrete frozen symbol list and account/strategy/policy fingerprint. The current captured S&P roster is offered as an editable starting list when settings have not yet been saved. Subsequent membership refreshes never widen an existing approved paper universe. Changing its symbols requires a new matching approval. Asset tradability is checked independently by paper planning/submission; historical ingestion of an inactive listing cannot authorize an order.

No strategies are activated and no orders are submitted by membership refresh or market downloads.
