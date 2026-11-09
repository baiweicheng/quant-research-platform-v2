# Lightweight EPS research baselines — November 9, 2026

These are acceptance-run results. After verification, the user explicitly requested an empty workspace. The downloaded archives and app backtests were deleted; this report and compact audit evidence remain. New research requires a fresh download and new runs. The original frozen source archive is no longer available locally for byte-for-byte reproduction.

Engine **0.7.0**, **January 3, 2017–November 6, 2026**. All five strategies were selected together and submitted through the production browser interface after ordinary Update. These are coverage-limited, ex-date total-return experiments. No strategy parameters, risk limits or trading approvals were changed.

| Recipe | Net return | Largest decline | Mean stock exposure | Exclusions |
| --- | ---: | ---: | ---: | ---: |
| 12–1 Momentum | +226.14% | -36.00% | 92.94% | 118 |
| Defensive Low Volatility | +132.01% | -26.97% | 84.40% | 118 |
| Profitability / Quality | +181.15% | -32.80% | 92.53% | 116 |
| Quality Value | +248.87% | -34.27% | 92.72% | 116 |
| Value + Momentum | +246.52% | -39.89% | 92.58% | 118 |

SPY returns **+277.70%** under the same modeled costs and ex-date convention. Policy remains $100,000 initial capital, weekly decisions, at most 25 stocks, 5% per-stock cap, 25% sector cap, 2% minimum cash reserve, 5 basis points slippage and 1 basis point fee. Actual stock exposure varies with the eligible cross-section and caps. Historical sectors retain the disclosed current/last-known approximation.

The combined snapshot is `a5d6306a49aea26dbcde9242`, digest `a5d6306a49aea26dbcde924275b3126ff9e92ecde0490e92772667dfb750c2c3`, with **1,786,705 daily rows / 762 symbols** and **23,512 normalized annual statements**. Input history starts January 4, 2016. Data exports preserve the structured EPS policy, 6,467 accession assumptions/exclusions, source captures and refresh history. Those usable assumptions are not labelled verified historical classes.

## Interpretation and checks

The final financial outputs and every target decision exactly match the frozen-input lightweight candidate with the BNY guard: curves, windows, fills, holdings, exposure and policy. Excluded security sets also match. This separates EPS-policy sensitivity from fresh source collection. See [the paired dated-proof/lightweight study](LIGHTWEIGHT_EPS.md#controlled-eps-policy-sensitivity). The two price recipes are identical between those paired policies; the value portfolios change materially. A return difference is not an estimate of accuracy loss or future performance.

Expired ticker histories and their warnings remain frozen during Update. A full DOW backfill is retained as captured data, with its unsafe pre-2019 listing path blocked. BNY bank/fund identity is blocked. Distinct merger instructions, including Paramount cash/share elections, cannot become a guessed terminal recovery. The first fresh QA batch that admitted Paramount was rejected and removed before publication; its accounting report remains a diagnostic, not this baseline. No last-close liquidation, zero recovery or blanket Yahoo substitution was introduced.

A separate read-only Decimal replay, without platform backtest, ledger, signals, portfolio or metrics functions, exactly matches cash, NAV and SPY over **12,380 daily valuations**. It checks fills/costs, entitlements, splits, reinvestment, merger holdings, final positions, target membership/caps, returns and drawdowns. It also checks **394,041 filing components** and **389,268 EPS/split calculations**. Arithmetic consistency does not certify provider identities or every reported share basis.

Historical gaps remain material. Availability-based omissions can introduce selection and survivorship bias; public membership and sector history remain retrospective. Strict full-index/current-snapshot checks are still blocked where required identities or actions are unresolved. The exploratory allocation sensitivity is not a complete-index paper preparation, broker test or trading approval. B-033 remains open.

Detailed timing, source samples, comparison hashes and replay reports remain under ignored `var/uat/lean-eps-2026-11-09/`. See [performance](PERFORMANCE.md), [policy limitations](LIGHTWEIGHT_EPS.md) and [validation](VALIDATION.md).
