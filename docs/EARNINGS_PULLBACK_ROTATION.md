# Earnings and Pullback Rotation

A weekly, long-only strategy available in Aperture under **Research → Earnings and Pullback Rotation → Backtest**. It uses saved daily bars, dated S&P 500 membership and original SEC periodic income. The strategy is research only.

## Selection and execution

1. Use the last exchange session of each week, plus the first session of the backtest. Require 253 timely stock and SPY sessions, at least 10 days of positive volume in the latest 20, and positive comparable net income from the most recent original 10-Q or 10-K. Filing evidence becomes eligible on the first exchange close after its filing date and stays eligible for up to 150 calendar days. Rank signals across qualifying stocks and restrict selection to the 100 with the highest 20-session median dollar volume. [SEC EDGAR data](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
2. When SPY's 126-session total return is at least −5%, average each stock's 63- and 126-session beta-adjusted log return ranks and give that average 80% of the score. Assign 20% to the year-over-year income-change rank. Subtract 126-session beta times SPY's corresponding log return to calculate each beta-adjusted return. Use square-root median dollar volume times beta clipped to 0.45–1.80 for sizing.
3. Below −5%, combine beta rank (35%), five-session pullback rank (30%), liquidity rank (20%) and income-change rank (15%). Divide the negative five-session log return by daily tracking volatility over 63 sessions, floored at 0.001, to measure the pullback. Use square-root median dollar volume for sizing. The higher-beta tilt can deepen losses when declines persist. [Daniel and Moskowitz](https://www.nber.org/papers/w20439)
4. Add 0.05 to the relative-strength score or 0.12 to the pullback score if the stock was in the previous target portfolio. Select up to 25 names, one listing per issuer and at most six names per sector. Apply the default 5% stock limit, 25% sector limit and 2% cash reserve. Trade at the next exchange open.

Income change divides current minus comparable prior income by the greater of their absolute values and 1. A flat SPY return window uses beta zero. Saved decisions expose the active selection rule, price signals and filing evidence.

## Historical Standard-cost comparison

To reproduce the comparison, choose snapshot `2c83efcbf8707d4a48b0a260`, $100,000 starting capital, Strict coverage, ex-date total-return accounting and Standard costs. Enter January 1, 2017 through November 18, 2026. The first valuation is on January 3, the first exchange session. Standard uses 5 bp of base slippage per side, a 1 bp fee, and a size-dependent slippage adjustment. All 15 prior strategies kept their registered cadence, including the six archived or hidden recipes.

| Portfolio | Net total return | CAGR | Max drawdown |
| --- | ---: | ---: | ---: |
| Earnings and Pullback Rotation | +695.21% | 23.37% | −30.32% |
| Earnings and Market Regime Rotation, highest prior return | +542.18% | 20.73% | −28.84% |
| SPY | +275.08% | 14.33% | −33.78% |

The strategy led SPY in six of ten calendar periods. It used pullback selection on 42 of 516 decisions. Comparable filings covered 256,792 of 258,655 price-qualified stock-weeks. Strict price and action coverage included all 704 historical securities.

The strategy was selected in sample from 12,480 overlapping approximate variants. The Higher-cost replay returned +557.29%. With no switch to pullbacks, the Standard-cost replay returned +441.48%. Forward performance remains untested.
