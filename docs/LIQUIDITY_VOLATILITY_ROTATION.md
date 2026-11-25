# Liquidity and Volatility Rotation

Liquidity and Volatility Rotation v1.0.0 is available for backtests and research allocations. It makes a decision after each exchange week's final close and executes at the next regular open. A backtest also makes an initial decision after its first session closes.

## Signals and allocation

Stocks need 253 timely daily bars, including the decision close, and at least ten sessions with positive volume in the last 20. The latest comparable original 10-Q or 10-K must show positive net income and be no more than 150 calendar days old. Filings become usable at the first exchange close following filing. Positive income is an eligibility screen. The amount and growth of earnings do not affect the stock ranking.

**Liquidity and trend rule.** Rank eligible stocks on the natural log of the ratio of 20-session median dollar volume to the square root of 20-session daily log-return volatility (90%) and 126-session total log return divided by 63-session daily log-return volatility (10%). Use a 0.001 floor on the latter volatility. Add 0.14 to the score of a stock in the prior targets. Select up to 22 stocks from the 110 with the highest recent dollar volume. Before portfolio caps, size positions in proportion to dollar volume raised to 0.30, times the square root of 126-session SPY beta clipped to 0.45–1.80, divided by 63-session daily volatility floored at 0.004.

**Rebound rule.** Use this rule when SPY's total-return level is more than 6.5% below its 252-session average. Rank 126-session SPY beta (40%), negative five-session total log return divided by 63-session daily tracking volatility versus SPY (30%), and recent median dollar volume (30%). Floor tracking volatility at 0.001. Add 0.12 for prior targets. Select up to 25 stocks from the 100 with the highest recent dollar volume and size positions by its square root before caps.

Both rules compute percentile ranks across the eligible set before narrowing to the liquidity pool. Ties in each signal share a percentile. The portfolio allows one listing per issuer and at most six stocks per sector, with Aperture's 5% target stock cap, 25% target sector cap and 2% target cash reserve. Differences in price between rebalances can move actual exposures away from the targets.

## Default Higher-cost backtest

January 3, 2017 through November 23, 2026, using snapshot `929bc41021fc36750e4e776a`, $100,000 initial capital, Strict coverage and ex-date total-return accounting. Higher costs apply 15 basis points of base slippage per side, a 1 basis point fee allowance and size-based slippage, including for the benchmark. Strict coverage validated all 704 in-period members with zero whole-run exclusions. The default Coverage-limited setting produced the same returns on this snapshot, with zero whole-run exclusions. Comparable filed income was available for 257,462 of 259,155 assessed stock-weeks (99.35%), including filings with nonpositive income. The rebound rule operated in 28 of 517 decisions, including the first-session setup in the total decision count.

| Metric | Strategy | SPY |
| --- | ---: | ---: |
| Cumulative net return | +652.57% | +270.64% |
| Ending equity | $752,571.77 | $370,642.92 |
| Annualized net return | 22.65% | |
| Maximum drawdown | −32.49% | |

| Calendar period | Strategy | SPY | Lead |
| --- | ---: | ---: | ---: |
| 2017 | +23.36% | +20.41% | +2.95 pp |
| 2018 | −2.66% | −4.95% | +2.29 pp |
| 2019 | +36.97% | +31.13% | +5.84 pp |
| 2020 | +32.18% | +18.49% | +13.69 pp |
| 2021 | +31.73% | +28.62% | +3.12 pp |
| 2022 | −15.66% | −18.17% | +2.51 pp |
| 2023 | +42.30% | +26.19% | +16.11 pp |
| 2024 | +34.26% | +24.89% | +9.38 pp |
| 2025 | +42.74% | +17.72% | +25.02 pp |
| 2026 through November 23 | +14.25% | +6.75% | +7.50 pp |

Portfolio and benchmark holdings carry across calendar boundaries. Pass/fail uses unrounded returns.

## Sensitivity and limits

At 25 basis points of base slippage per side, the strategy returned +620.37% and its smallest lead was +1.44 percentage points. Moving the SPY trigger to −6.0% or −7.0% at Higher costs returned +658.31% or +662.23%, with minimum leads of +1.88 and +2.29 percentage points respectively. The study used the full history for discovery and selection, including 49,500 overlapping approximate evaluations followed by exact engine replays. Forward performance is untested. Reported results use captured roster and sector histories and the platform's modeled opening execution. [Research and execution assumptions](RESEARCH_CONTRACT.md)
