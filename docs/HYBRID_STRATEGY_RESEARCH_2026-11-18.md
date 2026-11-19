# Profitable Liquidity Leaders · November 18, 2026

The strategy earned **299.16% net versus 277.31% for SPY**, a **21.84 percentage point lead** under Higher trading costs from January 3, 2017 through November 6, 2026. The initial $100,000 grew to $399,155 versus $377,314 for the benchmark. The recipe is available for research only.

## Rule and inputs

At the start of a test and after each month end:

1. In the dated S&P 500 universe, require a complete 253-session stock history and at least 10 positive-volume observations in the last 20 sessions.
2. Require strictly positive whole-issuer net income from the most recent comparable original 10-K available by the decision. A supported record uses same-accession current and prior-year income of the same US-GAAP concept and duration, plus starting assets to confirm the period.
3. Require the stock's economic total-return level to be above its 200-session arithmetic average. The level includes only corporate actions and marks available by the decision.
4. Rank eligible stocks by 20-session median dollar volume. For an issuer with multiple eligible share classes, keep the most liquid class. Take up to 25 stocks and allocate in proportion to square-root median dollar volume within the 5% stock, 25% sector and 2% cash constraints. Simulate fills at the next session open.

The monetary threshold has an accounting meaning. The moving-average window is a conventional trend measure, and month-end formation reduces churn when audited fundamentals update annually. These choices were defined before comparing the recipe's returns and were not optimized through a parameter grid. The economic idea is to hold established, actively traded businesses with reported earnings and an uptrend. It has different entry and ranking rules from the platform's risk-adjusted return strategy and Value + Momentum.

## Research basis and alternatives

The study compared distinct mechanisms and checked coverage before opening performance for each round. The literature provides support for those mechanisms on other samples and portfolios. The released rule is a local design.

| Mechanism | Basis and outcome |
| --- | --- |
| Filed earnings improvement with price strength | Prior studies associate earnings news with return continuation. Same-accession net-income improvement was available in 98.18% of tested monthly stock windows. The simple joint ranking trailed SPY by 43.74 pp at Higher costs. Keeping positions until improvement or trend failed led by 11.04 pp, with a lead concentrated after 2023. [Chan, Jegadeesh and Lakonishok](https://www.nber.org/system/files/working_papers/w5375/w5375.pdf) · [Novy-Marx](https://www.nber.org/system/files/working_papers/w20984/w20984.pdf) |
| Sales confirmation and cash-flow productivity | The required joint sales and earnings signal had 92.87% coverage. Cash-flow productivity had 90.57% coverage under the original same-period rules. Both were dropped before performance tests. [Jegadeesh and Livnat](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=903767) · [Ball and coauthors](https://www.sciencedirect.com/science/article/pii/S0304405X16300307) |
| Conservative investment | Annual asset growth covered 99.14% of monthly windows. The conservative-investment and price-strength blend trailed by 86.37 pp under Higher costs. [Cooper, Gulen and Schill](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2008.01370.x) |
| Economic-size weighting and profitability ranks | Weighting on absolute annual income after applying a trend gate trailed by 87.68 pp under Higher costs. Ranking on annual income divided by beginning assets after the trend gate trailed by 33.68 pp, after leading through 2023. Fundamental indexation inspired economic-size weighting, while the study used net income as its own trial metric. [Arnott, Hsu and Moore](https://www.hillsdaleinv.com/uploads/Fundamental_Indexation%2C_Robert_D._Arnott%2C_Jason_Hsu%2C_Philip_Moore%2C_Financial_Analysts_Journal%2C_MarchApril_2005%2C_Pages_83-99.pdf) |
| Market and filing-price confirmation | Marketwide trend timing paired with earnings improvement trailed by 238.90 pp. Requiring a positive market-relative price response to the dated filing trailed by 80.48 pp. The latter measures returns around the actual filing, which can occur after earnings news is public. [Brock, Lakonishok and LeBaron](https://onlinelibrary.wiley.com/doi/full/10.1111/j.1540-6261.1992.tb04681.x) · [Martineau](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607) |
| Profitability screening of liquidity leaders | Ranking liquid stocks on an established trend cleared Higher costs in a technical control. Adding positive annual income reduced trading in unprofitable companies and increased the observed full-window lead. The annual-data recipe was selected for its result across both subperiods, performance relative to both controls and use of the existing annual acquisition path. |

Sequential quarterly earnings acceleration was dropped at 97.60% coverage. Positive recent earnings improvement as a screen for liquidity leaders was tested and trailed by 22.29 pp at Higher costs. The study used the predeclared 98% overall and 95% per-year input-availability floor as an operational definition of near-full coverage.

## Matched results

| Profile or segment | Strategy | SPY | Difference |
| --- | ---: | ---: | ---: |
| Higher, entire window | 299.16% | 277.31% | +21.84 pp |
| Higher, through December 29, 2023 | 141.03% | 136.18% | +4.84 pp |
| Higher, from the December 29, 2023 close | 65.61% | 59.75% | +5.85 pp |
| Standard, entire window | 326.70% | 277.69% | +49.01 pp |

The second segment carries forward the portfolio and starts from the last 2023 close. Higher uses 15 basis points of adverse base slippage per side. Standard uses 5. Both add the same 1 bp fee allowance and order-size adjustment. The strategy's simulated trading debits were $21,876.54 at Higher and $8,781.06 at Standard. Full-window maximum drawdown at Higher was 24.08%.

The controls start from the same input-covered cohort and retain one listing per issuer, the same liquidity ranks and weights, date range, benchmark and costs.

| Higher-cost rule | Return relative to SPY | Decision dates with different holdings vs full rule |
| --- | ---: | ---: |
| Both signals | +21.84 pp | — |
| Drop the positive annual income condition | +13.40 pp | 85 of 119 |
| Drop the price-trend condition | +3.11 pp | 118 of 119 |

These are historical comparisons. Earlier results informed the design of later structural hypotheses, and the final selection used the full tested period. The two reported segments characterize the chosen result and are not untouched forward tests. Roster, sector and opening-fill assumptions remain as described in the [research contract](RESEARCH_CONTRACT.md).

## Coverage and implementation

The comparable net-income signal was available for **58,537 of 59,648** monthly stock/decision observations with complete market inputs (**98.14%**). The weakest year was 2017 at 95.82%, and the weakest sector was Consumer Discretionary at 96.67%. This includes negative and zero net income as available observations. The strict market coverage plan covered 704 stocks with zero price/action exclusions in both runs. Availability is measured before filtering on either signal.

The standard SEC submissions and CompanyFacts responses already acquired by the app support the signal. CompanyFacts supplies whole-entity, standard-taxonomy values by accession and unit. The original annual filing, matched report periods and delayed availability are retained. No extra endpoint or source-specific filing repairs were required. The existing annual refresh policy remains in use. [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

The isolated ordinary SEC attach replay on frozen source captures produced 9,957 usable net-income records and kept all previous annual financial records, prices, sector labels, actions and rosters byte- or value-identical. The attach took 57.0 seconds and a repeat took 49.5 seconds, which reused the same snapshot and added no filing captures. These timings measure captured-source processing.

Chromium submitted the two final backtests and verified the net-income decision audit and desktop, 390 px and 320 px layouts. It also verified stale-snapshot and paper eligibility restrictions. Independent replay matched all 119 decision dates, 33,708 ranked signals and SEC evidence rows, 2,975 target weights, 7,467 fills and 9,904 daily valuations. The automated suite passed 743 backend and 68 frontend tests and the production build.

To reproduce, add or refresh SEC financials in Data, then open Profitable Liquidity Leaders in Research. The original frozen verification snapshot is `cabb17f30c2b4166f6730398`. Use the dates above, $100,000, strict market coverage, ex-date total-return accounting and Higher costs.
