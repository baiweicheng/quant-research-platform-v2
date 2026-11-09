# Historical coverage improvements

Engine 0.6.0 narrows the price history required for exploratory backtests and adds reviewed missing merger terms. The normal Download and Update workflows apply the data supplements automatically. Original snapshots and saved results remain frozen.

## What the prior implementation established

The read-only v1 review found retrospective constituent membership and explicit daily Yahoo acquisition. It also found skipped ticker/action failures, forward-filled quotes, and exits using the last available close or a price-based bankruptcy proxy. These choices can make a calculation finish without establishing the historical terminal return. V2 does not adopt those exit assumptions. No v1 code, configuration or tests were reused, and no v1 application or database was run.

## Prices needed by the actual workflow

A stock needs prices while it is an eligible member and until the opening execution after the next ordinary rebalance decision following departure. The trading schedule is unchanged. It does not need years of unrelated post-membership prices after that execution.

A supported cash or stock conversion can end the original security's price path. Missing sessions **before** conversion still block inclusion. Stock consideration requires the recipient's prices and verified inputs through the possible holding period, including subsequent supported conversions. An incomplete merger, unpriced contingent right, ambiguous identity or missing liquidation-session quote remains a blocker. A missing history is never converted into an assumed sale or zero recovery.

Cessation filtering does not treat a ticker with subsequent quotes or a later index re-entry as permanently dead. Source and recipient identity checks also apply to held or incoming positions in strict research. Non-trading legal effective dates enter the daily accounting loop on the first exchange session; reviewed after-close transactions retain their separate legal and market dates.

Coverage-limited selection still uses future availability relative to a decision. Its exclusions are frozen before simulation, disclosed and exported. This remains exploratory subset research with potential survivorship and selection bias. It is not a certified full S&P 500 history.

## Reviewed missing completed mergers

These exceptions require the exact captured old listing ID, the reviewed primary filing content fingerprint and the expected final source quote session. They fill absent vendor events without replacing native consideration. Original provider captures and primary response bytes remain available. Cash payment dates are not invented; cash-flow simulation remains stricter than the approved total-return research convention.

| Old security | First converted market session | Contractual consideration | Primary evidence |
| --- | --- | --- | --- |
| EVHC | 2018-10-11 | $46 cash | [Completed acquisition and pre-open suspension](https://www.sec.gov/Archives/edgar/data/1678531/000119312518297466/d637722dex991.htm) |
| XL | 2018-09-12 | $57.60 cash | [Completed old XL insurer acquisition, Items 2.01 and 3.01](https://www.sec.gov/Archives/edgar/data/875159/000087515918000068/axaclosing8-k.htm) |
| ESRX | 2018-12-21 | $48.75 plus 0.2434 new CI shares | [Completed exchange and first regular-way session](https://www.sec.gov/Archives/edgar/data/1739940/000114036118045479/form8k12b.htm) |
| SCG | 2019-01-02 | 0.6690 D shares | [January 1 legal closing and January 2 suspension](https://www.sec.gov/Archives/edgar/data/754737/000119312519000643/d678624d8k.htm) |
| DISCK | 2022-04-11 | One WBD Series A common share | [Completed reclassification, Items 3.01 and 3.03](https://www.sec.gov/Archives/edgar/data/1437107/000119312522103051/d328161d8k.htm) |

The DISCK terms alone do **not** resolve the WBD recipient's historical identity gap. That exclusion remains. ANDV's election/proration terms, CELG/WBA contingent rights, MYL/VTRS market timing and other unresolved events are not assigned a convenient terminal value.

## Measured coverage effect

On the captured 703-stock January 3, 2017–November 6, 2026 universe, the revised holding-window checks recover 17 names before the new missing-merger supplements. Four supplements make additional names price/action eligible, reducing 138 exclusions to 117 for momentum, low volatility and value + momentum. The shorter fundamental lookback gives 115 exclusions for quality and quality value. An annual filing must still be available for a fundamental strategy to select a stock; price/action eligibility does not create a missing financial statement.

The 21 recovered names in the 253-session case are AIV, ALXN, CERN, DNB, DWDP, ESRX, ETFC, EVHC, EXE, FLIR, KSU, MXIM, NBL, PBCT, SCG, TIF, VAR, XEC, XL, XLNX and XRX. No previously covered stock is newly excluded in that comparison.

In the updated normal snapshot, the 117 momentum exclusions include 74 paths with unavailable historical listing identity, 11 with multiple listing identities, and 53 with missing holding-period sessions. These categories overlap; they are not additive. Five paths retain split-evidence conflicts and four retain dividend-evidence conflicts. More quote downloads alone cannot establish the missing issuer identity or terminal consideration.

All five full-period updated normal-workspace runs completed together through the browser. Their complete financial outputs and coverage audits match the isolated candidate. Independent replay matches every daily cash balance, portfolio value and SPY value exactly across 12,380 valuations, including actual merger holdings. Filing-component and EPS-unit checks also pass. This establishes accounting consistency for those captured inputs, not completeness of the remaining history. See [validation](VALIDATION.md) and [remaining free-data gaps](FREE_DATA_GAPS.md).
