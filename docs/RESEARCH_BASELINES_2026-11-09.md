# Coverage research baselines — November 9, 2026

Historical engine 0.6.0 checkpoint. See the [0.7.0 lightweight study](RESEARCH_BASELINES_2026-11-09_LIGHTWEIGHT.md) for newer validation. The subsequent user-requested fresh start removed the app's downloaded data and saved results; preservation statements below describe this earlier checkpoint, not the final empty workspace.

All five strategies were selected and submitted together through the normal production browser interface, engine **0.6.0**, for **January 3, 2017–November 6, 2026**. The ordinary Update workflow produced the shared combined snapshot. These are exploratory, coverage-limited, ex-date total-return calculations; no strategy was approved or activated for trading.

| Recipe | Net return | Largest decline | Mean stock exposure | Exclusions |
| --- | ---: | ---: | ---: | ---: |
| 12–1 Momentum | +225.41% | -36.00% | 92.94% | 117 |
| Defensive Low Volatility | +132.01% | -26.97% | 84.40% | 117 |
| Profitability / Quality | +175.36% | -32.80% | 92.51% | 115 |
| Quality Value | +238.78% | -35.43% | 93.46% | 115 |
| Value + Momentum | +279.13% | -38.96% | 93.01% | 117 |

The fully invested SPY benchmark is **+277.70%**, including distributions and the same modeled execution costs. Policy remains $100,000 initial capital, weekly decisions, at most 25 stocks, 5% per-stock cap, 25% sector cap, 2% minimum cash reserve, 5 basis points slippage and 1 basis point fee. Ex-date distributions reinvest at the close and cannot fund opening purchases. No parameter or recipe tuning was performed.

The snapshot is `9e878b130b680319a110c815`, with **1,784,094 price rows / 762 captured symbols**, **22,330 normalized annual statements** and **6,467 filing checks** (5,580 compatible common-share checks). Inputs begin January 4, 2016. Original snapshots and saved results remain unchanged. Sector caps retain the disclosed current/last-known approximation.

## Coverage changes and interpretation

Prices are required throughout possible member holding periods through the next scheduled execution after departure, or through supported contractual conversion and any recipient path. Unrelated years after the position must have exited no longer create an exclusion. Missing conversion-session consideration, recipient identities/prices, contingent rights and required source prices still block inclusion. Five reviewed missing merger records are acquired automatically within Download/Update, guarded by exact old listing, source fingerprint and quote lifetime.

The 253-session cases recover **21 names**, reducing **138 exclusions to 117**, with no newly excluded name in the same frozen-input comparison. The shorter fundamental lookback produces **115** exclusions for quality/quality value. Filing availability remains an independent selection requirement. DISCK stays excluded because its WBD recipient identity is unresolved. See [the complete source and holding-window explanation](HISTORICAL_COVERAGE.md).

Compared with the [0.5.0 baselines](RESEARCH_BASELINES_2026-11-08.md), returns change from +225.30% to +225.41% for momentum, +138.66% to +132.01% for low volatility, +175.36% to +175.36% for quality, +238.40% to +238.78% for quality value, and +277.51% to +279.13% for value + momentum. Improved coverage can lower a result as well as raise it. SPY and the financial price/annual inputs remain equivalent; the holding-window policy and contractual events change the simulated stock path. These are captured-input comparisons, not evidence of improved predictive accuracy.

The remaining exclusions are material. Availability-based omissions still consider future dates relative to a decision and can introduce selection/survivorship bias. Public historical membership remains retrospective. Unknown cash payment dates, terminal values, contingent rights, historical identities and original-vintage financial data remain limitations. B-033 stays open; these are not complete-index or survivorship-safe results. Yahoo was investigated without adopting a blanket price fallback.

## Independent verification

A separate read-only Decimal replay, without calling platform backtest, ledger, signals, portfolio or metrics functions, exactly matches cash, NAV and SPY at all **12,380 daily valuations**. It verifies fills, costs, splits, distributions/reinvestment, actual merger holdings, final positions, target membership/caps, returns and drawdowns. The replay checks **367,888 filing components** and **349,596 EPS share-unit calculations** against captured statements and dated class evidence.

All five current normal-workspace financial outputs match the independently audited isolated candidate. The seven prior result-body hashes and twelve prior dataset digests are preserved. SQLite integrity and protected configuration/separate historical paper-audit hashes pass; no paper orders, plans or approvals were created. Detailed reports remain under ignored `var/uat/followup-2026-11-08/`. See [validation](VALIDATION.md) and [performance](PERFORMANCE.md) for UAT and timing limits.
