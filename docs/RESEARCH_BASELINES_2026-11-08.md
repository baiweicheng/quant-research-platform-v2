# Corrected research baselines — November 8, 2026

All five recipes were submitted through the production browser interface on the same corrected snapshot, engine **0.5.0**, for **January 3, 2017–November 6, 2026**. Inputs begin January 4, 2016. These are exploratory, coverage-limited, ex-date total-return calculations; no strategy was approved or activated for trading.

| Recipe | Net return | Largest decline | Mean stock exposure |
| --- | ---: | ---: | ---: |
| 12–1 Momentum | +225.30% | -36.25% | 92.93% |
| Defensive Low Volatility | +138.66% | -26.50% | 84.46% |
| Profitability / Quality | +175.36% | -32.80% | 92.51% |
| Quality Value | +238.40% | -35.43% | 93.45% |
| Value + Momentum | +277.51% | -38.15% | 93.02% |

The fully invested SPY total-return benchmark is **+277.70%**, using the same modeled execution costs. The unchanged default policy is $100,000 initial capital, weekly decisions, at most 25 stocks, 5% per-stock cap, 25% sector cap, 2% minimum cash reserve, 5 basis points slippage and 1 basis point fee. Actual exposure can be lower than the stock target because of caps, eligible selections and costs. Ex-date distributions reinvest at the close; they cannot fund opening purchases.

The saved baseline snapshot is `93362a3e34eecf097f14c79f`, with 762 captured symbols, 1,784,094 price rows and 22,330 normalized annual records. Its SEC coverage retains 6,467 dated filing checks, of which 5,580 establish compatible common-share units. Missing or ambiguous units affect EPS eligibility; they do not fabricate company profitability. Sector caps retain the disclosed current/last-known classification approximation, with 760 stock/warrant entries classified and two funds/benchmarks not applicable.

## What changed in the inputs

Five narrow primary-source corporate-action corrections are applied automatically: APO, FRT, J and LIN one-for-one successor exchanges, plus the missing CP five-for-one split. Exact event/listing/date/terms and source fingerprints guard each correction. The final split replay changed exactly one price record's split factor, from 1 to 5, and preserved all other price fields, annual-value blocks and filing proofs. Details and source links are in [the free-data investigation](FREE_DATA_GAPS.md).

Compared with the prior November 4 baseline, the new full-period runs exclude **138 instead of 142** in-period securities: APO, FRT, J and LIN are newly usable; no new security is excluded in that comparison. CP is an acquisition dependency rather than an additional eligible S&P constituent. All exclusions and reasons remain saved. A recent update also retains original-ticker evidence and unresolved historical-action warnings for AABA, APTV, BHGE and WYND while their older prices stay frozen.

Across the complete fresh input window, action-related issue records fall from 39 to 34. The 104 historical identity issues and 7,931 payment-date issue records remain unresolved. An incremental update can split a spanning warning into adjacent intervals; that is not a new distinct security problem. Strict full-index research still blocks. Ex-date accounting avoids assuming unknown payment dates but does not repair identities, missing terminal proceeds, contingent rights or unavailable market sessions. Whole-window availability exclusions and retrospective membership can introduce selection and survivorship bias.

The comparison also extends the endpoint by two sessions and uses freshly captured market/SEC data and filing-specific eligibility. Return changes cannot be attributed solely to a particular repair. No recipe or policy tuning was performed. Yahoo was evaluated as a supplementary source; its prices were not substituted into this ledger.

## Independent verification

A separate read-only Decimal calculation uses the captured prices, saved fills and source statements, without calling the platform's backtest, ledger, signal, portfolio or metrics functions. For all **12,380 daily valuations** across the five runs, reconstructed cash, NAV and SPY are exactly equal to the saved values. It verifies splits, overnight dividend/distribution entitlements, reinvestment, merger consideration, fees, slippage and final quantities. It also checks target membership, position/name/sector/cash limits, total returns and drawdowns.

All **367,096 dated filing components** satisfy the recorded filing/availability cutoff and independent profitability arithmetic. All **348,854 EPS component checks** require compatible dated class evidence and independently reconcile subsequent split factors, EPS and earnings yield. These checks validate the calculation against captured inputs; they do not certify the inputs as an exhaustive historical security master or original-vintage fundamental database.

SQLite integrity passes and the fresh research workspace contains no paper orders, plans or approvals. Detailed scripts, source probes, timings and exact result hashes are retained locally under ignored `var/uat/`. See [validation](VALIDATION.md) and [performance measurements](PERFORMANCE.md).
