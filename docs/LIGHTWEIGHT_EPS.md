# Lightweight EPS research policy

Engine **0.7.0** keeps all five recipes and uses structured SEC annual financial facts for ordinary Download, Update and weekly paper preparation. It no longer downloads thousands of historical report bodies to establish each accession's share class. This is an intentional research approximation, accepted for exploratory usability. It is not an independent earnings audit or a certification of historical share units.

## Retained checks and limitations

Inputs still require the intended issuer CIK, supported annual 10-K/10-K/A facts, 330–400-day flow periods, consistent periods, USD amounts, USD/shares diluted EPS, unambiguous reported values, filing-date availability, staleness limits and the known split path. Current ticker counts do not determine historical compatibility. Company facts are entity-level data; matching units alone cannot prove that EPS belongs to a particular listed class. An unrecognized class conversion can remain undetected. Annual earnings yield is neither TTM nor a forward estimate.

The reviewed unequal-share exclusion identifies **Berkshire Hathaway by CIK**, so a ticker alias cannot bypass it. Berkshire reports Class A and Class B per-share amounts on materially different bases; the lightweight policy excludes its EPS instead of guessing a 1,500:1 conversion. Entity-level profitability remains separately usable when supported. See the [issuer's annual report](https://www.berkshirehathaway.com/2025ar/202510-k.pdf).

A separate major input guard excludes **BNY** from research while the provider mixes bank prices with unrelated municipal-fund actions. The bank announced its [BK-to-BNY change effective May 21, 2026](https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html); the former BNY fund had a [different merger into MYN in February 2026](https://www.sec.gov/Archives/edgar/data/882150/000119312526043113/d104966d425.htm). No guessed conversion or terminal value is applied. Raw source events remain in the archive, with an explicit identity exclusion. This guard applies to price recipes too.

Full backfill also exposed DOW's old/new listing splice: the provider supplies zero-volume flat quotes between the 2017 merger and the 2019 new listing, without the old conversion. A dated identity guard blocks the path before April 2, 2019. It does not permanently exclude the current Dow listing. See the [2017 filed merger/delisting record](https://www.sec.gov/Archives/edgar/data/1666700/000166670017000026/dowdupont3q17093017.htm) and [new Dow separation announcement](https://investors.dow.com/en/news/news-details/2019/Dow-completes-separation-from-DowDuPont/default.aspx).

Multiple distinct merger instructions for one security/date also block that path until reconciled; exact duplicates do not create this conflict. Paramount's separate $15 cash and one-share records are alternatives subject to election and proration, as its [closing filing](https://www.sec.gov/Archives/edgar/data/2041610/000119312525175046/d841914d8k12b.htm) confirms. The platform does not choose an election, add both alternatives or invent a proration rule. This validation applies to archived snapshots as well as new acquisition.

These reviewed cases are a small exception set, not a comprehensive security master. Missing identities, prices, action terms and historical membership still matter. Coverage-limited results retain their exclusions and selection-bias warnings; strict requirements are unchanged. See [remaining free-data gaps](FREE_DATA_GAPS.md).

## Change-aware refresh

The annual financial-history cache is shared by issuer. Normal updates check submissions, including annual accession, form, filing/report dates, primary document and archived-file manifest. A changed annual signature or amendment fetches company facts again. Otherwise a captured history with the expected issuer and source digest can be reused for at most **30 days**. Incomplete metadata, changed captures or an expired check cannot authorize reuse. A quarterly filing alone does not invalidate annual inputs; its comparative revisions can therefore wait until the periodic check. This delay is part of the speed tradeoff.

The optional **Refresh SEC financial data** action forces a fresh history capture. It is a repair option; ordinary users continue using the existing Download, Update or weekly preparation action. Requests retain the shared eight-starts-per-second SEC budget and identifying contact. The [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) describes company facts and submissions; this bounded reuse policy belongs to Aperture.

Each new snapshot records `structured-eps-v1`, the per-accession assumption/exclusion, source IDs, hashes and refresh counts. Data calls EPS accessions **usable**, rather than verified. Value research and paper reviews carry the approximation warning. Earlier dated-verification snapshots remain interpretable with their saved metadata and source archive when retained; a newer policy never relabels their checks.

## Evaluation

The controlled study uses the same frozen prices, source facts, dates, portfolio constraints and BNY identity guard for both policies. Pure-price results match exactly. Value rankings change materially as previously unavailable EPS enters the eligible cross-section. Profitability can also change when additional EPS-only records alter latest-period/ambiguity selection; it does not use EPS in its score.

A separate read-only source sample checks the twenty highest newly admitted target-exposure cases, one accession per issuer, against the original captured filing tags. All twenty sampled diluted-EPS values match the relevant entity/class USD-per-share tags, with no tenfold class-ratio flag in that sample. This is useful sensitivity evidence, not an error-rate estimate or proof that every class is correct. The pilot's BNY case was rejected due to the independent identity problem above.

Return differences measure changed portfolio construction, not an accuracy loss or a forecast of paper performance. A higher result does not establish a better policy. The final paired results and fresh-workspace baselines are recorded with [validation](VALIDATION.md); acquisition and storage measurements are in [performance](PERFORMANCE.md).


## Controlled EPS-policy sensitivity

The paired ten-run study keeps old captured prices and SEC facts fixed and applies the same BNY guard to both policies. The word strict below means the dated EPS-verification control; every simulation still uses coverage-limited market data. No strategy or risk parameters were tuned.

| Recipe | Dated EPS control return | Lightweight return | Changed target decisions / 514 |
| --- | ---: | ---: | ---: |
| momentum | +226.14% | +226.14% | 0 |
| low_volatility | +132.01% | +132.01% | 0 |
| quality | +175.36% | +181.15% | 21 |
| quality_value | +238.78% | +248.87% | 486 |
| value_momentum | +278.66% | +246.52% | 503 |

Price-recipe financial outputs, signals and coverage match exactly between these paired controls. The quality change reflects latest-period/ambiguity selection after additional EPS-only records become representable; EPS is not its profitability score. Quality Value and Value + Momentum admit many formerly unmapped EPS records, changing cross-sectional ranks. Common-component checks for matching accessions/periods remain equal. Returns are sensitivity results, not an accuracy score.

A read-only November 6 exploratory allocation comparison on the same frozen exclusions changes three of 25 selected names for Quality Value and two of 25 for Value + Momentum. Technical and profitability targets are unchanged on that date. This is not a paper execution test. Strict current-index ranking on these historical snapshots remains blocked by BNY and other unresolved identities; the lighter EPS policy does not waive those market-input requirements. Normal paper preparation captures its own current window and remains subject to those checks and separate strategy/account approval.
