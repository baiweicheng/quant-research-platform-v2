# Strategy research against SPY · November 18, 2026

Liquidity-Weighted Momentum returned **287.31%** versus **277.69%** for SPY after Standard costs from January 3, 2017 through November 6, 2026. It is available in Research as a long-only recipe. Its result was sensitive to costs and period selection. It trailed SPY at Higher costs and was selected after several full-window construction tests.

## What the online research supported

| Family | Evidence | Fit for Aperture |
| --- | --- | --- |
| Cross-sectional momentum | [Jegadeesh and Titman](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x) document a winner-minus-loser spread over intermediate horizons. [Novy-Marx](https://doi.org/10.1016/j.jfineco.2011.05.003) finds that older returns contribute materially. | Daily returns are already captured. Test shortened and intermediate horizons with the existing long-only and execution limits. |
| Risk-adjusted momentum | [S&P DJI](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-momentum-indices.pdf) scales formation returns by realized volatility. [MSCI](https://www.msci.com/documents/10199/248121/MSCI_Momentum_Index_Investor_Insight.pdf/49830602-ca1d-4b56-b4b3-858f4b5e72bd) combines two risk-adjusted horizons in an investable index methodology. | Two return windows and daily volatility use the same bars. The platform's 100-stock liquidity screen, 25-name portfolio, square-root weighting and weekly timing are local design choices. |
| Highs and continuous trends | [George and Hwang](https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf) study closeness to the trailing high. [Da, Gurun and Warachka](https://www3.nd.edu/~zda/Frog.pdf) find that more continuous information strengthens momentum. | Split-adjusted closing highs and the signs of daily returns are available. Short-term turnover and ties matter in a 25-stock weekly portfolio. The continuity weighting tested here is a simple adaptation. |
| Residual momentum and trend timing | [Blitz, Huij and Martens](https://pure.eur.nl/ws/files/46882404/ResidualMomentum-2011.pdf) use multifactor residual returns. [Han, Zhou and Zhu](https://doi.org/10.1016/j.jfineco.2016.01.029) combine trends across horizons. [Goulding, Harvey and Mazzoleni](https://doi.org/10.1016/j.jfineco.2023.05.007) analyze fast and slow signals near turning points. | Test a single-market SPY adjustment and simple moving-average and trend agreement scores from existing bars. The academic multifactor method would need more dated inputs and a more complex model. |
| Turnover and crash risk | [Novy-Marx and Velikov](https://academic.oup.com/rfs/article-abstract/29/1/104/1844518) find that stricter entry than holding rules can mitigate costs. [Daniel and Moskowitz](https://www.nber.org/papers/w20439) find momentum can lose sharply in market rebounds. | Compare a 20% retention band, monthly cadence and Higher costs. Results can differ from long-short studies and risk-managed leveraged implementations. |
| Value, earnings surprises and industry momentum | [Asness, Moskowitz and Pedersen](https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere) find diversification across value and momentum. [Bernard and Thomas](https://www.sciencedirect.com/science/article/pii/016541019090008R) study earnings drift. [Moskowitz and Grinblatt](https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00146) study industry momentum. | Use existing filing-dated EPS only for the incumbent value controls. Defer drift because timely comparable quarterly surprises and announcement times need their own ingestion and coverage verification. Retrospective sectors can distort an industry-selection signal. |

The research supports testing these families in this setting. Original papers, often using long-short spreads, cover different portfolios and samples. [Hou, Xue and Zhang](https://doi.org/10.1093/rfs/hhy131) show sensitivity to portfolio construction and multiple testing. [McLean and Pontiff](https://onlinelibrary.wiley.com/doi/10.1111/jofi.12365) document weaker effects out of sample and after publication.

## Data and execution

All candidates used the frozen S&P 500 market and SEC snapshot `97438cf4bd2fc415cac3c976` with dated membership and the same captured SPY series. Finalists only need as-traded daily closes, share volume, existing corporate actions and the existing membership and sector inputs. Alpaca documents free historical SIP queries ending at least 15 minutes in the past. The platform's regular market download and update already acquire these fields. [Alpaca market data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq)

The full-window comparison uses $100,000, strict coverage, ex-date total-return accounting, 25 positions, a 5% position cap, a 25% sector cap and a 2% cash floor. Signal windows end at the modeled after-close cutoff and orders use the next session's open. SPY starts at that same open. Standard uses a 5 bp adverse base adjustment per side and Higher uses 15 bp. Both include a 1 bp fee allowance and the same order-size adjustment. See the [research contract](RESEARCH_CONTRACT.md).

## Chronological screen

The first screen compared three existing controls and 20 additional rules through December 29, 2023. The 2024–2026 data stayed outside candidate comparisons until two finalists were selected. Existing full-window control results were already known. Each number is return minus SPY in percentage points. The 2022–2023 block continues the prior holdings and measures from the last 2021 close.

| Rule | 2017–2021 | 2022–2023 | 2017–2023 |
| --- | ---: | ---: | ---: |
| 12–1 Momentum | -79.28 pp | +14.63 pp | -59.96 pp |
| Defensive Low Volatility | -52.45 pp | -0.62 pp | -55.26 pp |
| Value + Momentum | -61.75 pp | +11.71 pp | -44.18 pp |
| 12–1 Momentum with retention | -76.98 pp | +16.23 pp | -54.81 pp |
| Value + Momentum with retention | -68.97 pp | +6.41 pp | -60.96 pp |
| 12–1 risk-adjusted momentum | -70.80 pp | +8.90 pp | -59.04 pp |
| 6–1 and 12–1 risk-adjusted momentum | -79.58 pp | +3.98 pp | -76.24 pp |
| 12–7 intermediate momentum | -87.82 pp | +25.40 pp | -54.84 pp |
| 52-week high proximity | -96.62 pp | -20.68 pp | -127.14 pp |
| Continuity-weighted momentum | -76.19 pp | +11.01 pp | -61.84 pp |
| Market-adjusted residual momentum | -90.86 pp | +3.20 pp | -89.41 pp |
| 6–1 momentum | -80.15 pp | +0.84 pp | -81.52 pp |
| 52-week high with 6–1 tiebreak | -100.15 pp | -20.74 pp | -130.13 pp |
| Liquid 12–1 risk-adjusted momentum | -43.71 pp | +1.58 pp | -42.22 pp |
| Liquid 6–1 and 12–1 risk-adjusted momentum | -41.96 pp | +3.19 pp | -37.37 pp |
| Liquid 6–1 momentum | -52.21 pp | +6.24 pp | -42.89 pp |
| Monthly 12–1 risk-adjusted momentum | -73.66 pp | +1.77 pp | -73.32 pp |
| Monthly dual-horizon risk-adjusted momentum | -68.68 pp | +3.04 pp | -66.04 pp |
| Multi-window moving-average trend | -92.96 pp | -8.19 pp | -107.13 pp |
| Liquid multi-window moving-average trend | -63.39 pp | -12.28 pp | -85.79 pp |
| Liquid 12–1 with trend confirmation | -82.28 pp | -11.33 pp | -101.57 pp |
| Monthly liquid moving-average trend | -18.92 pp | -10.42 pp | -41.41 pp |
| Liquid 63- and 252-session trend agreement | -71.87 pp | -19.15 pp | -104.30 pp |

The two highest 2017–2023 candidates advanced. Liquid dual-horizon momentum with equal allocation returned 265.12% over the full window, trailing SPY by 12.57 pp. Monthly liquid moving-average trend returned 237.64%, 40.05 pp behind. The equal-weight dual-horizon candidate averaged 92.99% invested and incurred $20,352.61 in modeled costs. This motivated follow-up construction checks.

The existing full-window Standard controls returned 212.04% for 12–1 Momentum, 137.46% for Defensive Low Volatility and 269.38% for Value + Momentum. An allocation replay matched all 3,084 stored decisions across the three strategies and both cost profiles after the weighted allocator was introduced.

## Full-window follow-up

These rules used the already-inspected 2017–2026 period. Several adjust allocation with the same dual-horizon rankings. Sector-aware selection, retention and monthly rebalance tested breadth and turnover. A rank tilt and position-weight tilt tested the effect of emphasizing liquidity. A single-horizon risk-adjusted control tested whether both windows mattered. Month-end Value + Momentum tested cadence with the existing EPS signal unchanged.

| Rule | Standard net return | Relative to SPY |
| --- | ---: | ---: |
| Sector-aware selection | 259.06% | -18.63 pp |
| Top-30 retention | 242.60% | -35.09 pp |
| Sector-aware selection and retention | 253.08% | -24.61 pp |
| Month-end dual-horizon rebalance | 242.32% | -35.37 pp |
| Liquidity tilt in the rank score | 273.30% | -4.39 pp |
| Liquidity-Weighted Momentum | 287.31% | +9.62 pp |
| Liquid 12–1 risk-adjusted momentum | 254.09% | -23.60 pp |
| Month-end Value + Momentum | 161.85% | -115.84 pp |

## Released strategy and verification

At each decision, screen for the 100 highest median dollar volumes over the last 20 sessions among members with 253 complete sessions and at least 10 positive-volume observations. Compute daily economic returns using point-in-time split and cash distributions. Rank the average of the 231- and 105-session returns divided by the corresponding annualized daily volatility. Both windows end 21 sessions before the decision. Use only positive blended scores and select up to 25. Target weight is proportional to the square root of median dollar volume, then capped and redistributed. This softens the influence of extreme volume. The weighting is based on trading activity and adds no vendor, filing signal or acquisition step.

| Measure | Strategy | SPY | Difference |
| --- | ---: | ---: | ---: |
| Standard · full window | 287.31% | 277.69% | +9.62 pp |
| Standard · through 2023 | 104.41% | 136.42% | -32.01 pp |
| Standard · since last 2023 close | 89.48% | 59.75% | +29.72 pp |
| Higher · full window | 224.45% | 277.31% | -52.86 pp |

Standard-cost drawdown was -34.10%. Modeled strategy trading debits were $20,443.79 at Standard and $47,692.50 at Higher. The Standard run averaged 92.99% stock exposure. Both profiles covered all 704 period stocks with zero strict coverage exclusions. The universe had 259,166 member decision windows. Missing or late signal history affected 1,511 (0.58%). Insufficient volume affected 0. The top-100 screen is a deliberate portfolio rule.

Chromium submitted both final backtests through the Research library, verified desktop, 390 px and 320 px saved results, and checked that paper settings exclude the recipe and the API rejects it. Independent replay matched 36,797 saved scores, 12,840 target weights, 29,412 fills and 9,904 daily portfolio and SPY valuations. The two cost profiles use the same 514 decisions. Automated verification passed 741 backend tests, 68 frontend tests and the production build.

The positive Standard gap emerged after 2023. The released weighting was chosen after inspecting full-window results, so the same window is a historical selection result. Sector proxies, retrospective roster timing and daily-bar execution uncertainty remain. All paper and live activation is separately scoped.

Saved verification results are `c1f5bbbc-7747-40b4-8c76-dc15355b1007` (Standard) and `e778790d-bb00-4dde-9f7c-6a175323425d` (Higher) in the isolated D-048 research workspace. Use the same immutable D-047 snapshot, dates and recipe from Research to reproduce the test. The report and accepted recipe are versioned in the repository.
