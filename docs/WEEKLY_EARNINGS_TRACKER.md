# Weekly Earnings Reaction Tracker

Open **Research → Weekly Earnings Reaction Tracker → Backtest**, select the latest completed S&P 500 market and SEC snapshot, keep the default dates and choose **Higher costs**. The saved result shows each calendar year's return against SPY. Open **Why these stocks?** to inspect an individual week's filing, income and price reaction.

## How the portfolio is formed

The strategy looks for two pieces of evidence about a profitable business. The original filing shows how earnings changed. The stock’s return relative to SPY shows how the market priced information around the filing. To limit the risk of an entire year turning on a single sector or market exposure, the portfolio also favors combinations of stocks that historically moved with SPY. The price reaction uses the periodic filing date, which can be later than the earnings release. [Brandt, Kishore, Santa-Clara and Venkatachalam, *Earnings Announcements are Full of Surprises*](https://www.anderson.ucla.edu/documents/areas/fac/finance/santa_clara_surprises.pdf) · [Mutunge and Haugland, *Minimizing the tracking error of cardinality constrained portfolios*](https://doi.org/10.1016/j.cor.2017.09.002)

1. At the initial close and the last trading close of each subsequent exchange week, use membership effective on that date. Require 253 consecutive available closes for the stock and SPY, and positive volume on at least ten of the latest 20 sessions. The first exchange week also receives its scheduled closing review. Trades are modeled at the following session’s open.
2. Use the latest original 10-Q or 10-K filed before the decision date, at most 150 calendar days old. Match the current and prior-year periods under the same income concept in that filing. Prefer the longest supported reporting period, which usually gives year-to-date income. A newer filing with missing comparable income supersedes the older signal. The report becomes eligible at the first trading close after its filing date.
3. Keep profitable filers. Rank earnings growth, calculated as the income change divided by the larger absolute income value with a $1 floor. Separately rank the sum of three stock log returns minus the corresponding SPY returns, ending at the first close after filing. Returns include captured splits and distributions. Calculate both ranks among profitable, price-qualified members. Screen the 50 listings with the largest positive income after annualizing it by the actual reporting-period length.
4. Among those 50, build a basket of up to 25, adding one listing per issuer and up to six names per sector. Each candidate receives an annual return tilt equal to `0.08 × (average rank percentile − 0.5)`. For selection, incumbents receive a further 1.32 percentage points of annualized preference to limit turnover. Each addition balances that benefit against the past 126 sessions' mean squared portfolio return difference from SPY, allowing for the cash reserve.
5. Start from feasible equal weights. Use 252 sessions of benchmark-relative return covariance and the earnings/filing tilt to improve the allocation with transfers between stocks. Stop when no transfer materially improves the objective or after 65 transfers. A candidate may receive zero weight. The default policy holds at least 2% cash and caps each stock at 5% and each sector at 25%. The same model runs each week, including weeks when the resulting orders could be zero. A current allocation review rebuilds the incumbent history through the latest completed exchange week.

## What was explored

The search began with six hypotheses, including 52-week-high anchoring, trend persistence, information diffusion among profitable peers and short-term reversals. The first 32 portfolios won at most five of the ten calendar periods. Later trials included options term structure, recurring calendar flows, benchmark-aware stock selection and several ways to size the selected stocks. Event-date coverage ruled out one proposed earnings-announcement proxy. The final strategy combines a filed earnings-growth signal, a filing-price reaction and benchmark-aware construction. The selection process used approximately 670 overlapping configurations and controls on this history. All ten calendar periods participated in discovery. Future performance remains untested.

## Financial inputs

Research reads the snapshot’s saved SEC company facts, submissions and dated issuer evidence. The quarterly or annual filings supply both sides of each income comparison. In order of preference the strategy uses net income attributable to the parent, consolidated profit or loss, or basic income available to common stockholders. It requires both periods to use the same concept and USD units in the same original filing. Income available to common shareholders can reflect preferred dividends or other allocations. The stock-level audit identifies the basis used. Where a listing changed SEC registrants, the snapshot’s verified succession dates determine which filings represent its shares. Quarterly and annual filing changes now trigger a refresh of the shared company-facts cache. [SEC EDGAR data API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)

The November 2026 Citigroup company-facts capture ended at its previous 10-K. Three original 10-Q cash-flow statements disclosed year-to-date net income attributable to Citigroup and the prior-year comparable in USD millions. The reviewed values apply only when the snapshot identifies the exact issuer, accession, form, filing date and reporting period, and the structured comparable is missing. [March filing](https://www.sec.gov/Archives/edgar/data/831001/000083100126000019/c-20260331.htm) · [June filing](https://www.sec.gov/Archives/edgar/data/831001/000083100126000045/c-20260630.htm) · [September filing](https://www.sec.gov/Archives/edgar/data/831001/000083100126000056/c-20260930.htm)

## Default historical result

The default backtest on snapshot `2c83efcbf8707d4a48b0a260` starts with $100,000 on January 3, 2017 and ends November 18, 2026. It uses the historical S&P membership, strict market-data coverage and the app’s ex-date total-return model. Higher costs charge 15 basis points of adverse slippage and a 1-basis-point fee per side, plus a size-dependent charge. The portfolio and SPY each pay their own simulated trading costs. Net cumulative returns were **+367.40% for the strategy and +274.70% for SPY**. The strategy’s largest peak-to-trough decline was 30.90%.

| Year | Strategy | SPY | Lead |
|---|---:|---:|---:|
| 2017 | +26.83% | +20.41% | +6.42 pp |
| 2018 | -3.37% | -4.95% | +1.58 pp |
| 2019 | +31.78% | +31.13% | +0.65 pp |
| 2020 | +19.75% | +18.49% | +1.26 pp |
| 2021 | +28.90% | +28.62% | +0.29 pp |
| 2022 | -15.66% | -18.17% | +2.51 pp |
| 2023 | +26.59% | +26.19% | +0.40 pp |
| 2024 | +27.28% | +24.89% | +2.40 pp |
| 2025 | +25.73% | +17.72% | +8.01 pp |
| 2026 through Nov 18 | +9.74% | +7.92% | +1.82 pp |

Each year's return starts at the preceding year-end valuation when available. The engine compares unrounded returns. 2026 is a year-to-date observation.

## Coverage and sensitivity

Strict price and corporate-action coverage included 704 historical securities with zero exclusions. Across 516 weekly decisions, 1,517 member observations lacked the required price history or recent trading volume. Of the 258,655 price-qualified stock-weeks, 256,792 had comparable reported earnings (99.28%). The lowest annual coverage was 97.94% in 2026. These exceed the study's thresholds of 98% overall and 95% in each year. Stock-level inspection verified 12,525 funded stock-week records, 2,448 distinct income observations, each filing reaction and target limit, and the separate daily strategy and SPY ledgers.

Of the 1,863 missing earnings observations, 1,149 lacked a comparable pair, 604 lacked a dated issuer or report, and 110 had a stale filing. Within the 50 most liquid stocks each week, 25,768 of 25,800 observations had earnings evidence. Kraft Heinz accounted for the ten missing observations whose last known annual income exceeded that week's candidate cutoff. Its 2018 annual filing arrived after the June 7, 2019 close. The production rule excludes stale information. [Original Kraft Heinz filing record](https://www.sec.gov/Archives/edgar/data/1637459/000163745919000049/0001637459-19-000049-index.htm)

| Same dates and accounting, one change per row | Periods ahead of SPY | Smallest annual lead |
|---|---:|---:|
| Released rule, Higher costs | 10/10 | +0.29 pp |
| Allow the latest earlier comparable filing for up to 240 days when the current signal is missing (986 additional stock-weeks) | 10/10 | +0.30 pp |
| Require parent or consolidated income, excluding the common-shareholder fallback | 9/10 | -0.76 pp |
| Raise base slippage to 25 bp per side | 7/10 | -0.92 pp |
| Raise base slippage to 35 bp per side | 5/10 | -2.11 pp |
| Remove the earnings-growth rank, retaining the profitability and size screen | 7/10 | -6.67 pp |
| Remove the filing-price-reaction rank | 5/10 | -3.40 pp |
| Allocate equal weights under the same limits | 9/10 | -1.65 pp |

The original half-equal, half-optimized design cleared all ten periods on narrower earnings inputs and fell behind in 2020 when the additional filings were included. Rechecking the original full-strength tracking allocation on the broader inputs produced the released rule. This choice used the same historical outcomes. The data sensitivity tests establish what happened under those specific changes. Daily bars approximate opening execution, and historical index rosters and fallback sector labels are retrospective. The strategy is available for research and read-only allocation reviews. Forward validation remains open.
