# Earnings and Market Capture

Open **Research → Earnings and Market Capture → Backtest**. Choose the latest completed S&P 500 market and SEC snapshot, keep the default dates, and select **Higher costs**. **Calendar-year returns** shows the comparison with SPY. **Why these stocks?** shows the filed income and average daily relative returns on weak and strong market days.

## Weekly decision

1. At the initial close and the final trading close of each subsequent exchange week, use roster membership effective on that date. Require 253 timely sessions for each stock and SPY and at least ten positive-volume sessions in the latest 20. The strategy trades at the next session’s modeled open.
2. Require positive income in the latest original 10-Q or 10-K filed before the decision, at most 150 calendar days old. Compare the current and prior-year periods using the same income concept from that filing. Scale income to a year using the actual reporting duration. Divide the change by the larger absolute income value, with a one-dollar floor. The shared SEC method, including dated issuer succession and comparable income concepts, is documented in the [Weekly Earnings Reaction Tracker](WEEKLY_EARNINGS_TRACKER.md#financial-inputs).
3. Group the last 126 sessions by SPY’s daily log total return. Weak days are at or below the 25th percentile and strong days are at or above the 75th percentile. Within each group, calculate the average stock log total return minus SPY’s. Both signals use captured splits and distributions. Include days at a group boundary when their returns tie.
4. Rank each measure across eligible profitable stocks. Screen the best 50 by a blend of 60% annualized reported income rank and 40% median dollar-volume rank. For selection, give 39% of the score to weak-day relative returns, 21% to strong-day relative returns, 20% to income scale and 20% to income growth. Percentiles use average ordinal ranks divided by the number of eligible stocks.
5. Select up to 25 listings, one per issuer and up to six per sector. At each addition, score the candidate’s centered blend times 0.10, add 0.02 if it was held in the last target portfolio, and subtract a tracking-risk penalty. For a basket of size *k*, the penalty is `4 × 252 / (2 × k)` times the mean squared sum of its daily active log returns over 126 sessions. Each stock’s active return for this penalty is its log total return minus SPY’s log total return divided by the policy’s investable fraction.
6. Size the selected positions using the 20-session median dollar volume raised to 0.75. Redistribute weights proportionally as caps bind, with a 5% stock cap, a 25% sector cap and at least 2% cash under the default policy. A read-only allocation review reconstructs the weekly targets from the snapshot’s default start to determine incumbents.

The market-capture signal uses all qualifying weak and strong SPY sessions in a rolling window. The Weekly Earnings Reaction Tracker uses the price move around individual SEC filings. Earnings and Market Regime Rotation switches rules based on the current market trend, while market capture evaluates both tails at every decision. The conditional market split was motivated by research on asymmetric market exposure. The portfolio was also informed by work on trading volume, industry momentum and entry versus retention rules. [Ang, Chen and Xing](https://www.nber.org/papers/w11824) · [Lee and Swaminathan](https://doi.org/10.1111/0022-1082.00280) · [Moskowitz and Grinblatt](https://doi.org/10.1111/0022-1082.00146) · [Novy-Marx and Velikov](https://www.nber.org/papers/w20721)

On the same 516 historical decision dates, the two weekly income strategies shared an average of 15.2 holdings and 54.0% of portfolio weight. Their funded stock sets differed all 516 weeks.

## Historical results

The frozen snapshot `2c83efcbf8707d4a48b0a260` covers the default backtest from January 3, 2017 through November 18, 2026. The run starts at $100,000 and uses strict full-index coverage and ex-date total-return accounting. Higher costs apply 15 basis points of adverse base slippage and a one-basis-point fee per side, plus the platform’s order-size charge. SPY pays its own modeled costs. [Execution and accounting rules](RESEARCH_CONTRACT.md#timing-and-execution)

The strategy returned **+377.13%** versus **+274.70%** for SPY at Higher costs. At Standard costs it returned **+396.55%** versus **+275.08%** for SPY. Maximum drawdown at Higher costs was **30.18%**.

| Calendar period | Strategy | SPY | Lead |
|---|---:|---:|---:|
| 2017 | +22.99% | +20.41% | +2.58 pp |
| 2018 | -3.52% | -4.95% | +1.43 pp |
| 2019 | +31.32% | +31.13% | +0.19 pp |
| 2020 | +18.56% | +18.49% | +0.07 pp |
| 2021 | +30.00% | +28.62% | +1.38 pp |
| 2022 | -15.97% | -18.17% | +2.21 pp |
| 2023 | +29.76% | +26.19% | +3.57 pp |
| 2024 | +27.38% | +24.89% | +2.50 pp |
| 2025 | +27.58% | +17.72% | +9.86 pp |
| 2026 through Nov 18 | +12.11% | +7.92% | +4.19 pp |

For each calendar year, the engine starts from the preceding year-end valuation when available. Leads are calculated from unrounded returns.

## Discovery, coverage and sensitivity

The initial screen compared downside resilience, two-sided capture, relative-return consistency, lottery avoidance and short-term reversal. Further screens varied price and volume confirmation, sector-peer signals, selection risk, turnover and allocation. The four discovery grids evaluated about 4,400 overlapping portfolio configurations using the same evaluation history. The simple screen used approximate costs and return paths. Shortlisted portfolios and the released recipe were rerun in Aperture’s strict ledger with corporate events and next-open fills. All years shown participated in selection. Forward performance remains untested.

Strict price and action coverage included 704 historical stocks with zero exclusions. Across 516 weekly decisions, 258,655 stock-weeks met the price and liquidity requirements. Comparable earnings were available for 256,792 of those stock-weeks (99.28%). The weakest annual coverage was 97.94% in partial 2026. The remaining gaps include unpaired, stale or unavailable filings. The default uses the latest original filing and records missing values as unavailable. The source data retain the platform’s retrospective roster and historical sector limitations. [Historical coverage](HISTORICAL_COVERAGE.md)

| Same dates and source snapshot | Calendar periods ahead of SPY | Smallest lead |
|---|---:|---:|
| Standard costs, 5 bp base slippage | 10/10 | +0.70 pp |
| Higher costs, 15 bp | 10/10 | +0.07 pp |
| 25 bp base slippage | 8/10 | -0.57 pp |
| 35 bp base slippage | 8/10 | -1.19 pp |
| Higher costs, remove weak and strong market signals | 7/10 | -2.11 pp |
| Higher costs, allow an earlier comparable report up to 150 days old when the latest is unavailable | 8/10 | -2.58 pp |

Allowing older filings added 564 stock-weeks and changed the selections enough to lose the 2020 and 2022 comparisons. The latest-report rule removes stale signals when a new filing lacks a comparable pair.

Earnings and Market Capture is available for backtests and read-only allocation reviews.
