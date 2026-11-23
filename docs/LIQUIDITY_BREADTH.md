# Liquidity and Breadth

Aperture 0.17.0 adds Liquidity and Breadth v1.0.0 to Research. It evaluates long-only stock targets weekly using daily returns, trading volume and the share of stocks above their 200-session averages. Its target weights favor stocks with lower beta to SPY as market breadth falls. The dataset's dated membership and sector labels define the universe and peer groups. The strategy needs no financial statements or additional data subscription.

## Research candidates

| Signal family | Aperture test |
| --- | --- |
| Peer-relative pullbacks | Favor large, short-horizon declines relative to sector peers, with variants for quiet trading and a still-positive intermediate trend. The strongest exact quiet-reversal variant returned +279.73% and led SPY in seven periods. [Hameed and Mian](https://doi.org/10.1017/S0022109014000404) · [de Groot, Huij and Zhou](https://doi.org/10.1016/j.jbankfin.2011.07.015) |
| Volume pressure | Test whether the direction and size of relative returns on unusually active days add information. The selected exact volume-pressure check returned +254.85% and led in six periods. [Lee and Swaminathan](https://doi.org/10.1111/0022-1082.00280) |
| Volatility compression and liquidity | Compare intermediate trends with relatively quiet recent returns and a longer liquidity window. The best narrow-gap exact equal-weight variant returned +417.60% and led in nine periods. It fell short in 2022 by 1.60 percentage points. A low-price-impact variant also led in nine periods. [George and Hwang](https://doi.org/10.1111/j.1540-6261.2004.00695.x) · [Amihud](https://doi.org/10.1016/S1386-4181(01)00024-6) |
| Breadth and beta sizing | Blend in sector participation and respond to broad weakness with a low-beta tilt within a fully allocated stock basket. The released rule led in all ten periods. Aperture's long-only sizing and its breadth thresholds are local design choices. [Asness, Frazzini and Pedersen](https://www.aqr.com/insights/research/journal-article/low-risk-investing-without-industry-bets) · [Moreira and Muir](https://www.nber.org/papers/w22208) |

Liquidity-Weighted Momentum ranks six- and twelve-month winners and weights by dollar volume. Liquidity and Breadth uses intermediate total return and volatility compression in the stock score, sector participation in the selection, and historical market beta in the target weights. The study also compared against the mechanisms of Defensive Low Volatility and the earnings-based market regime and market capture strategies.

## Recipe

1. Use 253 consecutive completed daily bars through the decision close. Require positive trading volume on at least ten of the latest 20 sessions. Compute signals using economic close-to-close returns with captured splits and distributions and use as-traded close times shares for daily dollar volume. Include the 48 highest 126-session median dollar volumes among eligible stocks.
2. Rank liquidity in the 48-stock group. Among all qualifying members, rank the cumulative log return over 58 sessions ending five sessions before the decision. Separately, rank low values of the 21-session to 126-session daily volatility ratio using stock log returns minus SPY log returns. Combine the return and compression ranks at 55% and 45%, then blend that measure with the liquidity rank at 25% and 75%. Use average ranks for ties.
3. Compute market and sector breadth as the fraction of qualifying stocks above their own 200-session total-return average. Increase the share of the sector breadth rank from zero to 30% as overall breadth falls from 55% to 20% and SPY's 200-session trend gap falls from zero to minus 7.5%. Multiply the two clipped ramps. Reduce the base score by the same share.
4. Select up to 25 listings sequentially, with at most six per sector. Use a tenth of the centered blended percentile, add 0.022 for previous targets and penalize the basket's 63-session squared tracking deviation from SPY. The tracking score uses the same 98% stock exposure reference as the standard default portfolio.
5. Reweight the selected listings using the cross-sectional rank of lower 126-session beta to SPY. The proportional sizing factor is exp(strength × (rank − 0.5)), where strength rises linearly from zero at 60% market breadth to two at 25%. Apply the 5% listing cap, 25% sector cap and 2% cash floor. At normal breadth, sizing starts equally weighted. The backtest seeds the portfolio on the selected start date and follows the exchange week thereafter. Fills use the next regular-session open.

The saved decision audit exposes long-window liquidity, intermediate return, relative volatility ratio, sector breadth and SPY beta. Exported decisions also preserve market breadth, sizing strength and incumbency.

## Frozen Higher-cost result

Snapshot `2c83efcbf8707d4a48b0a260`, January 3, 2017 through November 18, 2026, starting capital $100,000. The long-only strategy and SPY both use the [research contract](RESEARCH_CONTRACT.md) and ex-date total-return accounting. Higher costs use 15 basis points of adverse base slippage per side, the size-dependent charge and the fee allowance. All 704 historical stocks passed strict price/action coverage.

| Calendar period | Liquidity and Breadth | SPY | Difference |
| --- | ---: | ---: | ---: |
| 2017 | +21.50% | +20.41% | +1.09 pp |
| 2018 | −4.14% | −4.95% | +0.81 pp |
| 2019 | +32.23% | +31.13% | +1.09 pp |
| 2020 | +20.08% | +18.49% | +1.59 pp |
| 2021 | +30.25% | +28.62% | +1.63 pp |
| 2022 | −17.21% | −18.17% | +0.96 pp |
| 2023 | +39.35% | +26.19% | +13.16 pp |
| 2024 | +31.27% | +24.89% | +6.39 pp |
| 2025 | +19.51% | +17.72% | +1.79 pp |
| 2026 through November 18 | +9.26% | +7.92% | +1.34 pp |
| Full window | **+376.33%** | **+274.70%** | **+101.62 pp** |

The strategy's maximum drawdown was 33.03%. Modeled strategy trading debits were $9,942.87 across 12,946 fills. Raising base slippage to 25 and 35 basis points retained ten yearly leads, with minimum leads of 0.57 and 0.34 percentage points respectively.

The approximate search evaluated 37,236 overlapping combinations. The cash-exposure pass accounts for 22,800 of these and found zero passing variants. The later sizing screen produced 39 approximate qualifiers, and six of its finalists cleared the same period in exact ledger replays. The released defaults were chosen using the full history shown here. Forward performance remains untested. Historical membership, sector proxies and slippage estimated from daily data retain the documented research limitations. Select the strategy in **Portfolio → Paper Settings** for paper trading under the [paper execution contract](PAPER_TRADING.md).
