# Research contract · price inputs and annual SEC fundamentals

## Inputs

CSV columns: `symbol,date,open,high,low,close,volume`; optional `split,dividend,pay_date,sector,available_at`. Dates are ISO calendar dates. `available_at` is an ISO timestamp with time zone. Rows may be unordered; duplicate symbol/date pairs are rejected. At most 1,500 symbols, 80,000 rows and 16 MB per import. All dates must be completed XNYS sessions, from 1990 onward.

OHLC must be **as-traded** prices: the actual units traded on that date. Already split-adjusted OHLC or total-return-adjusted prices are unsupported. Never mix adjusted close with unadjusted open. A vendor label such as “raw” is not independently sufficient evidence of this convention.

- `split`: new shares per old share, effective before the session open; default 1. A 2-for-1 split is 2, a 1-for-10 reverse split is 0.1.
- `dividend`: cash per post-split share on the ex-date; default 0. A nonzero dividend requires its actual pay date on or after the ex-date. Overnight holders accrue a receivable; new ex-date buyers do not.
- `sector`: one static label per symbol in this milestone. Missing values become one shared Unknown bucket. Static historical sectors are not point-in-time evidence.
- `available_at`: cannot precede session close plus 15 minutes. If blank, that time is a modeled availability convention, not proof of a vendor’s historical publication time. Late observations are excluded from historical signals until their timestamp.
- `SPY` is reserved for the benchmark and excluded from stock selection. The importer is responsible for restricting other names to US-listed stocks. Listing identity, ticker reuse, foreign-market symbols and delisted coverage are not resolved by this release.

Positive finite prices, OHLC bounds, nonnegative integer volume, valid actions, exchange sessions and duplicate keys are validated before the whole dataset is atomically stored. Identical submitted UTF-8 text, price contract and source description deduplicate; changed inputs create a new immutable snapshot. A source fingerprint and compressed submitted UTF-8 CSV text are retained. Browser file decoding may remove an encoding marker; this is not a byte-for-byte archive of the original file. Imported data is never silently overwritten.

## Universe membership

Data defaults to the full current S&P 500 plus optional supplements; SPY is only a benchmark. See [universe contract](UNIVERSE.md) for immutable roster refreshes, historical effective dates, coverage limits, and free-source uncertainty. Current-roster snapshots are blocked from historical backtests. Historical downloads include the union of in-period members and use only the roster effective on each decision date; unavailable identities/prices/actions remain visible in combined downloads and block affected backtests. Raw price availability does not certify action accounting; flagged SPY inputs suppress comparisons. Archived/inactive listings can supply historical prices without becoming tradable. Fixed-list CSV inputs remain explicitly exploratory.

## Signals and allocation

Momentum and volatility signals require 253 complete sessions available by the decision cutoff. Profitability and quality value require 20 complete price sessions plus the required available filing. Total-return levels use the gross economic return `split × (close + dividend) / previous_close`. This ex-date index is for ranking; it is separate from the spendable-cash ledger.

- **12–1 momentum v1.0.0:** cumulative total return from 252 sessions ago through 21 sessions ago. Rank descending; nonpositive scores are ineligible.
- **Defensive low volatility v1.0.0:** sample standard deviation of 252 daily total returns; rank lowest first. No volatility forecast or leverage.
- **Profitability / quality v1.0.0:** positive annual gross profit / fiscal-year-end assets, highest first. Use reported GrossProfit or same-accession, same-duration revenue minus cost of revenue; assets must match the accession and fiscal end. This is one profitability measure, not a full Quality Minus Junk replication.
- **Quality value v1.0.0:** equal average of profitability and earnings-yield percentile ranks among stocks eligible for both positive factors.
- **Value + Momentum v1.0.0:** equal average of positive earnings-yield and positive 12–1 momentum percentile ranks among stocks eligible for both. The value measure is annual reported diluted EPS / decision close, not book-to-market; this is an explicit implementation choice, not replication of an academic portfolio.
- Percentile ranks use `(strictly lower count + (tie count - 1) / 2) / (eligible count - 1)`; a one-stock cross-section receives 0.5. Missing or nonpositive blend inputs exclude a stock; there is no single-factor fallback.
- Ties use symbol order. Zero total volume over the latest 20 sessions excludes a stock. This is a minimum data check, not an institutional liquidity/capacity model.

Select up to 25 names, equal-weight under a 5% stock cap, 25% sector cap and 2% cash floor. One shared construction function is used for simulations and read-only weekly reviews. Infeasible constraints leave more cash; they are never relaxed to force a fully invested portfolio. These are provisional research defaults, not user approval of a live risk policy.

## Sector classifications

Downloads and dataset updates acquire sector information alongside prices and SEC filings. Data → Refresh sectors can derive a classified snapshot from existing prices and filings without downloading those series again. Prior datasets and results stay frozen; use the newest snapshot for a new backtest.

The approved research compromise uses captured current or last-known sectors when a complete historical sector timeline is unavailable. Current S&P roster labels are combined with the [public current/former-constituent archive](https://github.com/lawcal/sp500-components-history), reviewed dated S&P announcements, and explicitly labeled issuer-business proxies for remaining gaps. The archive is maintained by Calvin Law from Wikipedia revisions; it is retrospective public data, not an official GICS point-in-time history. Its code is MIT-licensed; Wikipedia attribution and underlying data limitations remain applicable. Reviewed source links and evidence dates travel with every relevant symbol.

The eleven sector names are normalized consistently (for example, Technology and Information Technology cannot become separate cap buckets). Historical ticker aliases are reviewed individually; original DuPont and Dow remain distinct from newer issuers. Price-period/constituent intervals help distinguish recycled archive labels. A sector mapping does not resolve price identity, actions, filings or trading eligibility. Warrants carry an explicit issuer-exposure proxy, while SPY and identified pooled funds have no operating-company sector. Every unresolved stock remains in one shared Unknown bucket under the same cap; neither unique fake sectors nor silent cap relaxation is used.

These static classifications can use information after a historical decision and introduce classification look-ahead bias. A dated announcement is evidence of a classification on that date, not proof of a complete timeline before or after it. This compromise applies in both data-coverage modes; strict price/action coverage does not certify historical sector accuracy. Data exposes counts, every classification/method/source, and unresolved names. Full metadata/result exports retain the audit and source fingerprints. Acquisition failures stop completion of the new stage and preserve earlier snapshots; retries do not replace old inputs.

## SEC fundamental snapshots

Data → Add SEC fundamentals reads the official issuer directory, submissions metadata and companyfacts API, then saves a separate immutable price + SEC snapshot. Issuer CIKs are cross-checked; raw responses and content fingerprints are retained locally. Refreshing an enriched dataset starts from its original price parent. Identical inputs and policy deduplicate.

Supported inputs are annual standard US-GAAP whole-entity facts in 10-K and 10-K/A filings, with 330–400-day flow durations (including 52/53-week years), exact USD amounts and USD/shares EPS. Quarterly/YTD, IFRS, custom taxonomy, foreign-currency and mismatched periods are not prorated or substituted. Conflicting values for the same tag/accession/period disable that component.

EPS compatibility is determined for each source accession using that filing's own common-share evidence, not today's SEC ticker count. Inline XBRL cover securities/tickers and reported common-share/EPS class contexts must establish a matching common security without contradictory or unmapped classes. Preferred/debt listings do not count as additional common classes. For older filings, official SEC manifests/indexes identify the filed XBRL instance; an undivided common-share and diluted-EPS reporting basis with no contradictory named common classes can support compatibility. This reported-basis check does not certify exhaustive class history or a historical security master. Class-specific EPS conversion, ambiguous common classes, unsupported documents, missing evidence and unverified ticker aliases remain excluded from valuation; entity-level profitability can still be used.

Evidence retains accession, filing date, issuer, method, source URL and document fingerprints. The class policy is frozen with the dataset; no later filing changes an earlier accession's eligibility. Data shows supported filing counts and historical gaps, and full metadata exports preserve each source check. Legacy `annual-us-gaap-v1` snapshots retain their former current-ticker screen: refresh SEC filings/share classes to create corrected inputs, or explicitly retain the legacy assumptions in exploratory reproduction. Existing results are never rewritten.

Each record retains accession, fiscal start/end, filing date, form, source tags and modeled availability. Availability is close + 15 minutes on the **first exchange session strictly after the filing date**. At a decision, choose the latest fiscal end then its latest available filing version; amendments never rewrite an earlier decision. Conflicting annual durations at that version are excluded. Fiscal ends older than 550 calendar days are stale. Same-day press releases are not substituted for filings.

EPS uses the share basis reported by the selected filing, divided by all split factors strictly after filing through the decision. Complete price/action coverage from the session after filing through the decision is required for this conversion, even if a shorter signal warm-up would otherwise suffice. Future splits cannot adjust earlier decisions. This assumes a filing's EPS basis corresponds to the shares in effect at filing; anticipatory split presentation, complex class reorganizations and source corrections need separate filing-level verification. Such cases are not certified for trading. Annual earnings yield is not TTM or a forward estimate.

Current SEC responses are filing-versioned inputs, not a commercial vintage database proving original dissemination times or exhaustive historical coverage. Current ticker/CIK and share-class mapping does not resolve historical ticker reuse or survivorship bias. Inspect the filing links, exclusions, and decision components before interpreting exploratory results. All components and source policy accompany saved exports.

Sources: [SEC API scope and units](https://www.sec.gov/search-filings/edgar-application-programming-interfaces), [SEC fair access](https://www.sec.gov/about/developer-resources), [gross profitability research](https://www.nber.org/papers/w15940), [value and momentum research](https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere). Evidence for a research family does not establish the effectiveness of these particular long-only recipes, universe, weekly schedule or cost model.

## Timing and execution

Backtests make an initial decision after the first requested session close, then after each week’s final actual exchange session close. The last decision without a following session in the test is not executed. Prices on later dates cannot affect earlier signals. The XNYS calendar handles holidays, early closes and daylight saving.

Orders are simulated at the next actual session’s open with 5 basis points adverse slippage and a 1 basis point fee per side. Fees round to cents; monetary accounting and quantities use Decimal. Quantities round down to six decimals; corporate-action fractions are retained on full exits. A conservative cost buffer reduces target sizing; sells precede buys and buys cannot exceed actual simulated cash after a cash reserve. When unavailable entitlements or other cash constraints leave less money than the aggregate buy need, all buy budgets scale proportionally together; ticker order cannot decide which security receives funding. Opening prices determine executable quantities from yesterday’s target weights, not yesterday’s ranking. No fill, auction access, fractional-order availability or capacity guarantee is implied.

Stock and sector caps apply to target allocation at rebalance; price drift can exceed them between rebalances. No stop-loss, drawdown halt or live broker risk engine is implemented. Paper execution has separate quote, cash, approval and reconciliation checks; see [the paper contract](PAPER_TRADING.md). Those checks do not change this historical simulation's assumptions.

Splits adjust held shares before orders. Dividends accrue on ex-date to overnight holdings and become cash on pay date, before that session’s modeled orders. Receivables are included in equity but cannot fund purchases. Cash earns 0%. Missing held-stock prices abort; there is no assumed delisting recovery. Taxes and settlement restrictions are not modeled. In particular, immediate simulated reuse of sale proceeds is **not** a cash-account settlement assurance for live trading.

SPY must have every requested session to enable comparisons. It is purchased from the same following-session open with the same costs; paid dividends are reinvested at that pay session’s open with the same costs. This is an explicit comparable simulation rather than a claim to replicate a published index.

## Results

Results retain the engine version, input contract, dataset fingerprint, recipe version, dates, capital, costs, allocation settings, decisions, fills, daily cash, receivables, equity and benchmark. They are immutable. Backtest returns are not account returns.

Saved experiments and comparisons disclose average daily stock/cash exposure. The detail view recomputes exposure for the displayed period, including its initial valuation. Stock value excludes cash and receivables. SPY remains the fully invested buy-and-hold reference, so exposure differences must be considered when interpreting its return gap. The cash floor is a minimum, not a target: sector concentration or other constraints can leave substantially more cash. Legacy exposure is derived for display without rewriting old result bodies.

Chart periods share their dates with the metrics. Boundaries include the last valuation on or before the calendar cutoff, when available, so the first return is not dropped. Short history is labeled with actual dates. Relative performance is a percentage-point difference. Drawdown is the largest fall from a prior peak within the displayed period. Annual volatility uses sample daily-return deviation × sqrt(252), with at least 20 returns. CAGR requires at least 365 calendar days and uses actual elapsed days / 365.25. Sharpe is deferred until a defensible risk-free series and convention are supported.

Fixed-list and synthetic results do not establish effectiveness. Frozen chronological protocols, sensitivity trials and one-time final-test reservations are now available in Research → Validation; see [research validation](RESEARCH_VALIDATION.md). Trial counts are disclosed, but no multiple-testing correction or significance claim is made.

## Security lifetimes and coverage

Exploratory coverage checks require dated-member prices through the next scheduled execution after departure, or through supported contractual conversion and the recipient holding path. They never create an extra sale merely because quotes stop. Missing source prices before conversion, recipient identities/quotes, contingent consideration and unresolved cash dates remain explicit limitations. Strict research also checks held and incoming securities. See [the source and holding-window contract](HISTORICAL_COVERAGE.md).
