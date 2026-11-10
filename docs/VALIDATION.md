# Research milestone validation

## 2026-11-10 — separation share units and 51 restored financial histories

Input contract `dated-research-inputs-v8-reviewed-separations` passes **486
backend / 63 UI tests**, TypeScript/production build, Ruff F lint, changed-file
Python formatting, frontend formatting and whitespace checks. Tests distinguish
real parent shares from adjustment factors, value the Arconic child while
retaining Howmet, reject the child's later acquisition as a parent liquidation,
and keep pre/post-split distribution units separate for Corteva. Source,
listing, quote-vintage, price-prefix and native-instruction changes fail closed.
A frozen-update contract verifies that a reviewed historical repair survives
assembly of the earlier blocks and does not mutate the old snapshot.

Actual isolated browser Update completed in **256.253 seconds**, creating
`9240bf1b070e51b2822e5462`. It restores **51 financial histories / 1,636 annual
records**, reuses 622 histories and downloads 46. Shared issuers account for
the difference between history and download counts. All 51 restored histories
have annual records. The reviewed registry contains 64 mappings; the snapshot
has 25,691 annual records in total. Existing date/unit/conflict/split and known
unequal-share safeguards remain in place.

Independent financial-source audit verifies **64 primary fingerprints** and
**4,802 numerical fields across 2,170 mapped annual records** against exact raw
SEC accession, period, unit and filing dates. Separate source/price checks verify
four separation/inception filings and three bounded raw-quote queries. All
**617 earlier financial blocks remain identical**. Only ARNC, HWM, DWDP and DD
historical series change; there are no unrelated price revisions in this
acceptance. HWM gains the original-parent prefix, old ARNC follows the continuing
parent, and the new DowDuPont issuer discards pre-inception predecessor quotes.
Three old DWDP shares deliver one DD and one CTVA share before research
reinvestment, rather than applying the vendor's adjustment factors as share counts.

A second actual browser Update completed in **214.365 seconds**, creating
`b2926146443bfc004c9f4b3a`, reusing **668 histories / zero company-facts downloads**.
Every price block, annual block, normalized action and opening distribution mark
is identical to the first candidate. This verifies repeated-update idempotence
and cache reuse. These are warm-update observations; no new empty-cache timing
is claimed for this group.

All five unchanged recipes completed January 3, 2017–November 6, 2026 through
the browser on that final snapshot. Their submitted dataset/date payloads were
verified before acceptance. Independent replay exactly matches **12,380 daily
cash/NAV/SPY valuations**, **418,281 filing components** and **413,290 EPS/split
checks**, including restored issuers, actual mergers, costs, membership, caps and
final quantities. These are data/accounting validation runs; strategy tuning
and SPY-outperformance research are outside the user's updated goal.

The browser displays 27 reviewed action corrections and 64 issuer mappings with
primary links, including the rejected Arconic-child instruction. The revised
Update disclosure distinguishes retained history from reviewed corrections.
Both source sections fit a 320px viewport with document width 320px. All five
correct-period tasks were observed complete in Activity; screenshots are retained.
An earlier isolated attempt with unretained browser date edits was stopped before
any results were saved and its five tasks retained as superseded failures. It is
not accepted validation and did not affect normal research.

Reports, independent scripts and screenshots are under ignored
`var/uat/paper-readiness-2026-11-09/separation-group/`. The original normal
workspace's seven result bodies and three dataset digests are preserved.
Isolated paper orders/plans/approvals remain zero and integrity checks pass.

The remaining **66/64 price/action exclusions are material**. A wider inventory
also identifies unusual adjustment factors requiring primary review; these
include genuine stock changes as well as potential further distribution/cohort
defects. They are not automatically classified as errors or exclusions. The
data-gap goal remains incomplete and continuation is paused at this handoff;
arithmetic replay does not establish complete economic source certification. See [historical coverage](HISTORICAL_COVERAGE.md).

## 2026-11-10 — native merger dates, rejected HES instruction and issuer histories

Input contract `dated-research-inputs-v7-native-date-reconciliation` passes
**420 backend / 62 UI tests**, TypeScript/production build, Ruff F lint,
changed Python formatting, frontend formatting and whitespace checks. Exact
source/quote/signature guards cover ANSS, CTLT and HES. Held-position tests
prove that the rejected HES September 2024 instruction does not execute,
conversion occurs once on July 18, 2025, and unknown alternatives remain
blocked. CTLT's conversion does not advance its captured cash payment date.
Data displays rejected evidence separately from accepted market-date corrections.

Actual isolated browser Update first completed the price/action repair in
**154.601 seconds**, creating `70f72545dea8bc8abe154908`; all 85,867 price blocks
and 614 annual blocks remained identical. Coverage improved **69/67 to 66/64**
without newly excluded names. Acceptance then caught the missing original
financial-issuer mappings for all three recovered names; those mappings were
added before final acceptance rather than treating price eligibility as enough.

The final ordinary browser Update completed in **209.176 seconds**, creating
`7d0f657b032fb05be84fb550`, reusing 614 financial histories and downloading three.
It adds **114 annual records** (45 ANSS, 36 CTLT, 33 HES). All original annual
blocks and normalized actions match the preceding snapshot exactly. All tested
prices through November 6 and all OHLC fields are unchanged. The provider revised
374 volume values on November 9, outside the tested period; the acceptance
report explicitly records those differences rather than claiming whole-archive
price-block equality. No new empty-cache timing is claimed.

Independent source audit verifies all **13 primary-document fingerprints**,
original CIKs/quote vintages, **534 annual records / 1,268 numerical fields**
against accession/period/unit/filed-date-matched raw SEC companyfacts, and six
active duplicate-listing checks. All five final January 3, 2017–November 6, 2026
runs were submitted through the production browser and completed. Independent
replay exactly matches **12,380 cash/NAV/SPY valuations**, **400,817 filing
components** and **396,044 EPS/split checks**, including costs, membership,
caps, merger holdings and final quantities. Net returns are **216.960% momentum,
132.944% low volatility, 182.192% quality, 238.227% quality value and 252.213%
value + momentum**, versus **277.699% SPY**. No recipe parameters were tuned.

Desktop/mobile source disclosure and the rejected HES label were observed;
320px document width remained 320px. Final completed tasks were observed in
Activity. Reports and screenshots are retained under ignored
`var/uat/paper-readiness-2026-11-09/native-group/`, with final financial/source
audits in `issuer-complete/`. Original normal-workspace inputs/results remain
unchanged; isolated paper orders/plans/approvals are zero and integrity passes.

The **66/64 remaining price/action exclusions are still material**. A separate
membership audit also finds **51 otherwise price-eligible historical members
without issuer financial mappings**, so the exclusion count alone does not
measure complete fundamental coverage. Both these gaps and net SPY
outperformance remain unachieved; the full paper-readiness goal stays active.

## 2026-11-09 — dated historical issuers and current listing duplicates

Input contract `dated-research-inputs-v6-dated-issuers` and annual normalizer
`annual-us-gaap-v4-dated-issuers` pass **403 backend / 61 UI tests**, production
and TypeScript build, Ruff F lint, changed-file Python formatting, frontend
formatting and whitespace checks. Tests require exact primary-source/quote-vintage
evidence, reject tampered mapping metadata and changed documents, retain issuer
mismatch and future-filing gates, and verify immutable targeted revalidation.
Current duplicate reconciliation requires matching descriptors, admission cohort,
unique active record and matching active individual lookup; former/reused symbols
and differing names/classes stay unresolved. Clearing one directory-warning kind
cannot accidentally clear another unsupported kind.

Actual isolated browser Update completed in **156.126 seconds**, reusing 610
annual histories and downloading four. It creates snapshot
`b3efdac6f4a55de632732d34`, adds 420 annual records across ten historical ticker
mappings, and recovers 15 more names: ADS, BBBY, COHR, COR, ECHO, ENDP, FTR, GPS,
HRS, KORS, LHX, MNK, P, SYMC and TMK. Exclusions improve **84/82 to 69/67**, a
total of 49 recoveries from the user's original 118/116. There are no newly
excluded names. All **85,867 price blocks**, original annual records, corporate
actions and original saved result bodies remain identical. The normal workspace
retains the user's five original backtests and is not modified by this acceptance.

Independent source checks verify all ten captured primary-document fingerprints,
exact quote vintages, original CIKs, and **1,009 numerical fields** across the
420 added annual records against their accession/period/unit/filed-date-matched
SEC companyfacts. Six current duplicate resolutions match active lookup responses;
IR retains its separate action blockers. This establishes the specific mappings,
not a complete historical security master or exhaustive share-class certification.

All five unchanged January 3, 2017–November 6, 2026 strategies were submitted in
one actual browser batch and completed after restart with the final source.
Independent Decimal replay exactly matches **12,380 cash/NAV/SPY valuations**,
**399,041 filing components** and **394,268 EPS/split checks**, including actual
merger holdings, costs, membership, caps and final quantities. Net cumulative
returns are **206.850% momentum, 132.944% low volatility, 182.192% quality,
228.689% quality value and 247.409% value + momentum**, versus **277.699% SPY**.
The results change materially when missing names return; no recipe tuning or
outperformance claim is made. The remaining exclusions are material and the
two-part paper-readiness goal remains incomplete.

The Data evidence disclosure shows all ten mappings, quote dates and primary
filing links. Actual 320px review has document width 320px, readable wrapped
sources and reachable controls. All five completed tasks and the successful
Update were observed in Activity. Detailed reports and scripts are retained in
ignored `var/uat/paper-readiness-2026-11-09/issuer-group/`. These are warm-update
measurements, not new empty-cache timing. No paper activation, account reset or
order submission occurred; isolated paper plan/order/approval counts remain zero.

## 2026-11-09 — first paper-readiness coverage repair group

Input contract `dated-research-inputs-v5-listing-and-market-timing` passes **380 backend / 61 UI tests**, production/TypeScript build, changed-file format, Ruff F lint and whitespace checks. Tests cover exact individual-listing recovery, retained fund/collision/error gates, immutable targeted historical revalidation, native merger signatures, conflicting alternatives, primary-source changes, quote lifetime and exact non-trading-mark checks. The ordinary update route retains support for v4 snapshots.

The isolated combined acquisition completed in **5m39** using a copy of existing caches; this is **not cold-download timing**. Every one of the original **85,736 price blocks** is identical. Original annual statements are unchanged; six EMR/TEL records newly filed November 9 become available November 10, after the tested period. Individual lookups recover 30 in-period names; four primary-source native merger timing corrections recover four more. Exclusions improve **118→84** for long lookbacks and **116→82** for short fundamental lookbacks. Remaining gaps are material; B-033 and the full paper-readiness goal remain open.

All five January 3, 2017–November 6, 2026 backtests were submitted through the production browser in the isolated workspace. Independent Decimal replay matches **12,380 cash/NAV/SPY valuations**, **394,378 filing components** and **389,605 EPS/split calculations**, including actual merger holdings, costs, caps, dated membership and final positions. Net returns are 219.916% momentum, 131.821% low volatility, 181.146% quality, 248.280% quality value and 246.158% value + momentum versus **277.699% SPY**. No recipe or portfolio parameter was tuned; no candidate beats SPY yet.

After restart, actual browser **Update dataset** from the original v4 family completed in **2m27.63s**, automatically revalidating 49 captured listing warnings, applying all four timing corrections and reusing **604 annual histories / zero facts downloads**. The same historical-window coverage is 84/82. Independent checks preserve **85,102 pre-overlap price blocks/partial blocks**, original result hashes and normal-workspace result hashes; SQLite integrity passes. The Data audit visibly presents all **14 reviewed corporate-action corrections** with primary links. Original snapshots remain unchanged. These tests used isolated research data, with zero paper plans/orders/approvals; no broker account or order action occurred. Detailed reports remain under ignored `var/uat/paper-readiness-2026-11-09/`.

## 2026-11-09 — lightweight EPS, final source guards and empty workspace

Engine **0.7.0** passes **359 backend / 60 UI tests**, TypeScript/production build, Ruff F lint/format, frontend formatting, offline locked dependencies and whitespace checks. The new checks cover assumed versus verified EPS labels, Berkshire CIK aliases, retained units/dates/conflicts, annual/amendment/cache invalidation, force/30-day expiry, malformed submissions and wrong-issuer capture rejection, two issuer pipelines, expired quote cohorts and warnings, empty-member full backfill, dated DOW/BNY identity guards, conflicting merger alternatives and read-only review disclosure. Full Ruff style rules beyond the established F check are outside this release's validation scope.

Actual browser Download into a truly empty workspace completed in **11m33** for the 2016–November 2026 combined universe. Subsequent validated Update runs completed in **3m36** and **3m06**, reusing 604 annual histories with zero company-facts downloads. The repeated final-guard update preserves every price and annual block exactly while adding unreconciled-merger warnings. Ordinary acquisition has no bulk historical EPS report downloads and no parsed full-report cache records. The shared eight-starts-per-second SEC request gate remains. These are local observations with different evidence work from the older exhaustive policy, not guaranteed future durations or equivalent class certification.

Ten frozen-input dated-proof/lightweight controls isolate the EPS policy with identical prices and a common BNY identity guard. Pure-price outputs match exactly. Quality/value portfolio selection changes are documented in [the policy study](LIGHTWEIGHT_EPS.md). Twenty highest newly admitted exposure cases, one accession per issuer, match captured source EPS tags with no tenfold share-class ratio flag in that sample. Known Berkshire units are excluded without guessed scaling. This sample cannot establish a general accuracy-loss percentage or certify all historical classes.

New and archived snapshots block multiple distinct merger instructions until election/proration or overlapping terms are reconciled. A first fresh QA batch that admitted Paramount after stale ticker tails were removed was rejected; its separate cash/share records are alternatives, not assumed recovery. The final five corrected UI submissions exactly match the guarded controlled candidate's complete financial fields, all target decisions and exclusion sets. Independent Decimal replay matches cash/NAV/SPY over **12,380 daily valuations**, with **394,041 filing-component / 389,268 EPS-split checks**. All normal and test paper-order/plan/approval counts remain zero. Full-index historical/current input gates remain strict; B-033 is still open.

Browser UAT verified all five saved results, retained approximation warnings, the 320px batch dialog without whole-page overflow, legacy proof labels, and full metadata export containing 6,467 explicitly unverified accession assumptions/exclusions plus source IDs. Unmapped rows in new snapshots say unavailable rather than incorrectly prompting a legacy refresh. The candidate archive compacted from the old **5.282 GB** workspace to **439 MB**, with all 87,045 required shared blocks present and protected file hashes unchanged.

**Final user-directed state:** after candidate acceptance, the user explicitly requested an empty workspace. All normal datasets, backtests/results, jobs, memberships, observations, financial-cache preferences and shared source/data blocks were removed. Connection configuration, watchlist, minimum attempted-period markers and the separate historical actual-paper audit remain. Actual browser UAT confirms zero datasets/backtests and the first-use screens; the database is **147,456 bytes**. Completed research-only UAT databases, obsolete source archives and the two temporary metadata downloads were removed; concise reports remain. `var` is about **143 MB**, including the protected audit, verification reports and tool caches. No further data download was performed after this request. Launch normally and start from Data → Download & validate.

Agent-owned servers/workers are stopped, browser tabs closed and viewport reset. No broker reset, strategy activation or new order occurred. Accepted inputs/results are now historical verification reports rather than populated app data. See [baseline report](RESEARCH_BASELINES_2026-11-09_LIGHTWEIGHT.md) and [performance](PERFORMANCE.md).


## 2026-11-09 — historical holding windows and bounded acquisition

Engine **0.6.0**: **341 backend / 59 UI tests passed**, with TypeScript/production build, Ruff F lint/format, frontend formatting, offline lockfile and whitespace checks. New regressions cover scheduled departure executions, missing pre-conversion and recipient quotes, re-entry and reused tickers, non-trading conversion dates, strict held/received identities, exact reviewed merger signatures, update preservation outside recent overlap, shared SEC limits, two independent issuer pipelines, fresh-connection retries and worker shutdown. Reviewed-source tests preserve raw captures and reject changed economic text while tolerating only the narrowly identified SEC trailing script.

Read-only v1 inspection found Yahoo daily acquisition, skipped download/action failures, quote forward fills, and last-real-close or price-proxy bankruptcy exits. It did not establish complete historical proceeds. V2 uses independently defined holding windows and verified contractual consideration; it does not copy these assumptions or run v1. Five primary-source missing merger supplements are integrated into normal Download/Update. Four improve eligibility; DISCK remains excluded because its WBD recipient identity is unresolved. See [historical coverage](HISTORICAL_COVERAGE.md).

The controlled empty-cache 20-issuer filing sample improves from **105.969 to 81.649 seconds**, about **23%**, with the exact same 213 proofs/197 compatible decisions and similar peak memory. Two issuer pipelines share four accession readers and an eight-starts-per-second SEC budget, including retries. A separate real empty-workspace full acquisition completed after transport failures/restarts, preserving saved prices and completed evidence. Its **85,762 price blocks**, **22,330 annual statements** and **6,467 filing checks** match the previously accepted financial inputs. Raw source hashes are retained even when the SEC response wrapper changes. Only those capture-hash fields are excluded from semantic comparison. Interruptions prevent an honest uninterrupted full-acquisition timing claim; see [performance](PERFORMANCE.md).

Actual isolated browser UAT completed all five revised full-period strategies and independently replayed **12,380** daily cash/NAV/SPY valuations exactly, with **367,888** filed-component and **349,596** EPS-unit checks. Coverage exclusions improve from 138 to **117**, or **115** for the shorter fundamental lookback. The 21 recovered long-lookback names include ordinary index departures and supported merger paths; no previously covered name is newly excluded in that frozen-input comparison. This remains coverage-limited research with material historical gaps and selection bias, not full-index certification.

The normal workspace's ordinary Update completed in **5 minutes 56 seconds** on snapshot `9e878b130b680319a110c815`, with all price/annual blocks and detailed filing checks identical to its parent. A single actual browser submission then completed all five January 2017–November 2026 backtests on that snapshot. Their complete financial output fields and coverage audits match the independently audited isolated candidate. The twelve prior dataset digests and seven prior result-body hashes remain intact, as do configuration, prior research-date history and the separate paper audit. No research reset was needed. The updated normal baselines are documented [here](RESEARCH_BASELINES_2026-11-09.md).

Browser checks cover the existing batch form, named Activity/results, expanded coverage and primary-source audits, interrupted-acquisition completion through ordinary Update, restart and 320-pixel layouts. All ten reviewed action corrections are shown with their source links; bare vendor events are not labeled reviewed. Coverage reasons wrap without page overflow. An actual launcher termination leaves both parent and worker stopped and releases the port and worker lock.

## 2026-11-08 — filing performance, fresh acquisition and corrected baselines

Engine **0.5.0**: **304 backend / 53 UI tests passed**, with TypeScript/production build, Ruff F lint/format, frontend formatting, offline lockfile and whitespace checks. Regression coverage includes persistent proof reuse, parser/source/identity/cache invalidation, amended accessions, bounded SEC concurrency and document reads, transport failures, equivalent monthly storage, combined updates for both research-input versions, and retained original-ticker action gates outside the update overlap.

Actual browser **Download & validate** started with an empty database and provider cache, January 4, 2016–November 6, 2026. It completed in **72 minutes 42 seconds**, saving 1,783,977 bars for 762 symbols and 22,330 annual records, with 6,467 dated filing checks. Initial acquisition made 11,758 SEC archive and 1,770 SEC JSON requests, including retries; this network cost remains material. Four oversized-source markers and other unsupported/ambiguous evidence remain explicit. The final CP correction was then applied by replaying the captured market responses: one split factor changed, while every other price field, annual-value block and filing proof stayed identical. No additional market-data request was permitted during that replay.

Two actual normal **Update dataset** runs took **7 minutes 35 seconds** and **7 minutes 45 seconds** of active work. The second timing excludes time queued behind the five backtests. It reused **6,460** filing checks; four bounded-evidence exceptions remained explicit. It shared all **85,762** price blocks and retained identical annual blocks, class proofs, sector labels and five saved-result hashes. The first update exposed a lost historical-alias warning; the fix preserves the frozen original-ticker evidence and action gates, passes the full suite, and passed the second actual update for AABA, APTV, BHGE and WYND. Its defective disposable snapshot/task was removed before delivery.

All five full-period baselines completed through the browser, January 3, 2017–November 6, 2026, with unchanged default caps and costs. An independent Decimal replay exactly matches cash, NAV and SPY at all **12,380** daily valuations, and checks holdings, costs, membership, target caps, returns and drawdowns. It independently checks **367,096** filing components and **348,854** EPS share-unit calculations. See [the complete baseline report](RESEARCH_BASELINES_2026-11-08.md) for returns, exposure, inputs and limitations. All five retain **138** whole-window exclusions, down from 142; this is not strict full-index certification. Yahoo probes and five guarded primary-source action corrections are documented in [free-data gaps](FREE_DATA_GAPS.md); that backlog remains open.

Paired frozen-input checks preserve complete output while reducing a ten-year backtest from **262.27 to 98.31 seconds** and snapshot-load peak memory from **3,386.92 to 2,514.50 MiB**. All 125 ranking audits, 46 filed-proof comparisons and 85,736 canonical price blocks match their controls. Detailed timings and measurement limits are in [performance](PERFORMANCE.md). The native browser metadata download retains all 6,467 filing checks and complete source references. Data/optional-control layout at 320 px has no page overflow. Preparation stays within the existing Download/Update actions, with optional repairs and source details collapsed.

The user-authorized normal research reset installs the verified fresh archive and five baselines. Ten minimal prior research-date markers survive, preserving honest holdout history. Connection settings, `.env` and the separate historical paper audit are preserved; protected-file hashes match. Database integrity and all five result hashes pass after cleanup/promotion. No paper orders, plans or approvals were created, and no broker account was reset. This checkpoint does not establish clean-machine installation, accessibility certification, complete historical coverage or unattended operation.

## 2026-11-05 — research cleanup and selected audit corrections

Engine **0.4.0**: **264 backend tests / 53 UI tests passed**, with TypeScript/production build, formatting, F lint, lockfile and whitespace checks. The existing dependency deprecations and bundle-size advisory remain non-failing. Regression checks cover ticker-order-independent cash allocation, dated filed common-share evidence, protected paper records, dependency cascades, stale previews, concurrent enqueue/deletion, retained research exposure, and shared-input/audit-block reachability.

Actual browser acceptance on an isolated database created a practice backtest, canceled a deletion preview, deleted the result/task while retaining its inputs, ran eight validation trials, restarted the service and deleted the evaluation as a complete group. Dataset cleanup then removed its dependent allocation review, protocol and task records together. Minimal attempted-period records survived; paper records were excluded. Search, categories, bulk selection, stale selected-result handling and 320 px manager/confirmation layouts passed. The normal workspace was read only throughout this follow-up.

Read-only SEC acquisition verified 13 AAPL, 12 BA and 12 JPM annual accessions, including five legacy XBRL instances per issuer. All nine GOOGL accessions remained excluded from arbitrary common-class EPS mapping; entity profitability is independent. Source documents are accession-specific and fingerprinted. Moving the evidence into shared per-security blocks preserved every captured price and normalized statement exactly. The browser's native metadata download retained all **46** detailed filing checks while screen responses stayed bounded. A corrected-input value/momentum browser backtest completed on the four-stock fixture; this establishes functionality, not a full-index performance estimate.

Independent review of the five saved full-period capped strategies reproduced every old curve/trade/holding, matched 25 fresh ranking spot checks, and independently matched all **12,370 SPY benchmark valuations** exactly. Keeping saved selections/inputs fixed, pooled funding changes no return in three recipes and only +0.0064 / −0.0407 percentage points in quality value / value + momentum. The latter returns **286.72%** versus fully invested SPY **293.89%**; a separate weekly 98%-SPY/2%-cash control returns **283.76%**. Removing modeled costs raises its diagnostic return to **334.36%**. These compounded counterfactuals explain costs/exposure, not assured alpha or permission to tune policy.

The normal dataset retains its legacy share-class eligibility until **Data → Refresh SEC filings & share classes** creates a new snapshot. Corrected full-index value-strategy performance has not yet been measured. Saved results stay immutable; engine versions are visible. The 142 whole-window exclusions, static-sector approximation and remaining B-033 source gaps still constrain interpretation. No broker mutations, account replacement, strategy approval or orders occurred. See [research management](RESEARCH_LIBRARY.md) for deletion and refresh instructions; detailed investigation and isolated artifacts remain in local project context and ignored `var/uat/`.

## 2026-11-05 — sector coverage and portfolio exposure repair

**238 backend tests and 48 UI tests passed**, with TypeScript/production build, formatting, changed-module F lint and whitespace checks. Tests cover sector-source validation, cache/refresh, public requests without credentials, ticker/issuer ambiguity, normalized sector names, capped allocation, immutable shared metadata vintages, legacy exposure, acquisition/update/recovery, source audits and snapshot-parent visibility. Dependency deprecations and Vite bundle-size advisories are non-failing; accessibility and formal performance certification remain separate.

Actual sector refresh classified **760 stock/warrant entries across 11 sectors, with zero unresolved**. SPY and one municipal bond fund are explicitly not applicable. Evidence comprises 503 current roster labels, 220 public archive labels, 4 reviewed historical ticker aliases, 15 dated public classifications, 14 explicitly marked issuer-business proxies and 4 warrant issuer-exposure mappings. This is the approved static current/last-known research compromise, not certified point-in-time GICS history. Per-symbol methods, source links and fingerprints remain in the audit.

The derived snapshot reuses all **85,736 price blocks and 604 filing blocks**, with identical membership and identity/action issues. All five full **January 3, 2017–November 4, 2026** backtests were submitted and completed through the actual browser with the original 25% sector cap, 5% stock cap, 2% cash floor and costs:

| Strategy | Return | Mean stock exposure | Largest decline |
| --- | ---: | ---: | ---: |
| 12–1 Momentum | +242.68% | 92.97% | -36.25% |
| Defensive Low Volatility | +146.69% | 84.18% | -25.85% |
| Profitability / Quality | +182.82% | 92.52% | -32.80% |
| Quality Value | +262.52% | 92.02% | -34.08% |
| Value + Momentum | +286.76% | 97.33% | -40.34% |

SPY remains +293.89%. Independent saved-output checks verify all 514 decisions per run: unchanged original rankings/components/exclusions, sector/name/cash target caps, no Unknown target sectors, nonnegative daily cash/receivables, final holdings/cash/receivables versus NAV and return arithmetic. Every SPY valuation equals its original counterpart across 2,474 dates per run. All five original compressed result bodies retain their exact SHA-256 hashes. These remain coverage-limited runs with the original 142 exclusions and selection bias; higher returns do not establish effectiveness or trading readiness.

Actual browser fresh download of AAPL/MSFT/PG/XOM/JPM plus SPY automatically acquired sectors and SEC data: 16,356 bars through November 4. Update automatically refreshed sectors/prices/filings through November 5 (16,362 bars), sharing 780 of 786 price blocks and preserving the old vintage. The completed chain no longer offers a misleading SEC-completion prompt for its intermediate sector-price parent. Data source search, original/new-result comparison, all seven chart periods and actual 320 px Data/result layouts passed. Every period's exposure agrees with independent saved-curve arithmetic. The isolated acquisition browser had no warning/error logs. Evidence remains under ignored `var/uat/sector-*` and local project context.

No paper/live orders or strategy approvals were created. Historical sector certification and separate identity/action/payment-date gaps remain open. The user's normal app was restarted with the fix; the isolated acquisition service was stopped.

## Historical foundation checkpoint — November 2, 2026

Verified on a local Mac, 2026-11-02. The original record below covers the foundation checkpoint; subsequent real-data and SEC checks are recorded in [the incremental build record](MILESTONES.md). Neither record certifies paper/live readiness or vendor history.

## Automated checks

- Python: **37 tests passed**, including property tests of allocation caps and cash accounting.
- Frontend: **10 tests passed** with Vitest and Testing Library.
- Strict TypeScript check and Vite production build passed.
- Source formatting, launcher syntax and Git whitespace checks passed.

The financial fixtures independently cover next-session opening fills, exact momentum horizons, missing and late inputs, future-price perturbation, split value conservation, ex-date entitlement versus pay-date cash, benchmark absence, metric arithmetic, holidays/early closes, unsafe numeric history, and no-borrowing/allocation invariants. Storage/API checks cover duplicate imports/tasks, malformed rows, immutable result provenance, failed-task isolation, stale-review failure, and interrupted-job recovery.

Known non-failing tool output: dependency deprecation warnings from the current Starlette/httpx test adapter and pandas calendar internals; Vite warns that the lazily loaded chart chunk is about 516 kB before compression. These do not establish a measured performance regression; no formal performance benchmark is claimed.

## Actual browser UAT

Used the production-built interface and a separate running Python worker, with an isolated ignored test database. Actions were performed through the interface:

| Scenario | Observed outcome |
| --- | --- |
| Empty first visit and weekly preparation without data | Honest planning capital, unavailable account returns, and guidance to Data; no synthetic history loaded automatically. |
| Explicit practice-data creation | Fictional 32-stock universe and synthetic SPY saved in a background job; pages remained usable. |
| Momentum and low-volatility backtests | Real calculations completed and saved; Activity opened the specific completed result. |
| Edited date versus submitted date | Found and fixed a date-editor/state mismatch. Retest saved exactly the visibly selected 2024-01-03 start; regression test covers native edits before a React change callback. |
| Strategy comparison | Matching data/dates/capital produced comparable rows; mismatched assumptions display a caution. Selection is limited to three without silently dropping an earlier choice. |
| Every chart period | 1W/1M/3M/6M/YTD/1Y/All updated actual dates, curve and all metrics together. |
| Short history and missing SPY | Available dates disclosed; no manufactured warm-up trades; benchmark unavailable and no phantom SPY legend. |
| Invalid then corrected CSV | Row-specific OHLC error, then successful atomic import through Paste CSV. |
| Repeat import | Original snapshot retained; no extra dataset created. |
| Read-only allocation review | Targets, cash, exclusions and intended session visible; no trading approval or order controls. |
| Stale data | Task failed with an update instruction; no new partial allocation published. |
| Reload and normal service restart | Saved datasets, experiments and reviews remained available. Crash recovery is covered by automated tests, not claimed as a killed-mid-job browser scenario. |
| Launch script and normal stop | Executed the launch script with a clean default database; build/API/worker startup and empty first-use UI passed. Fixed a noisy worker interrupt traceback and retested clean shutdown. Finder double-click and clean-machine installation remain separate manual checks. |
| Full-result export | Downloaded valid JSON containing 710 valuations, 3,697 recorded fills, every chart window and source provenance. Synthetic test artifact moved into the ignored project evidence directory. |
| Keyboard dialogs | Tab focus remained in the dialog; Escape closed it. |
| Responsive views | Inspected 1280 px desktop, 768 px tablet, 390 px phone, and 320 px compact layouts. No page-level horizontal overflow. Tables scroll within their containers. Fixed cramped percentage-point metrics at 320 px. |

Observed browser logs contained no application exceptions or warnings during the verified workflows. Screenshots and test exports are kept locally under ignored `var/uat/`; test account/data state is not committed.

## Remaining validation limits

- The in-app browser’s file chooser exposed a filename but did not supply a usable FileList to the page during automation. The actual native file-picker import path remains a manual UAT item. File selection/reading is covered by an automated component test, and Paste CSV ingestion was verified end to end in the actual browser.
- At the foundation checkpoint, real providers, fundamentals and broker execution were absent. Subsequent checkpoints below cover captured inputs and authorized paper fills. Historical universe certification, cash-account settlement in historical simulations and live orders remain unsupported; paper funding waits use their separate documented convention.
- No clean-machine installation, VoiceOver audit, real-device touch testing or prolonged unattended run is claimed. Responsive testing used browser viewport overrides.
- Zero defects, unbiased vendor history and future profitability are not guaranteed by these checks.

## Typography refinement · 2026-11-02

Increased the smallest text to a 12px minimum, supporting text and controls to 14px, main text/navigation to 16px, and small headings to 18px. Chart axes and tooltips now use 14px text. Prominent balances and large headings retain their hierarchy. Shared CSS typography variables keep the scale consistent across breakpoints; navigation moves to a second top row sooner, and supporting content wraps rather than shrinking.

Verified the production build, 10 existing frontend tests, and actual-browser readability/layout at desktop, tablet and compact sizes (1280/1024/980/768/390/320px). All five main screens fit at 320px without page-level horizontal overflow; inspected the strategy library, backtest form, saved result and chart period controls. No new tests were added for this visual adjustment. Local screenshots are stored under ignored `var/uat/typography-*.png`.

## M-04 · 2026-11-03

72 backend tests and 18 frontend tests passed; strict TypeScript/production build and whitespace checks passed. New checks cover chronological/disjoint folds, immutable fingerprints, cross-snapshot locked dates, prior failed/pending exposures, final-release sequencing and once-only behavior, failed/interrupted trial retention, retirement, exact form dates, explicit release acknowledgement and future-data perturbation.

Actual-browser UAT on isolated `var/release-uat.sqlite3`: froze a real-data Value + Momentum protocol; ran eight development trials; released one final trial; verified exposure labels, saved metrics/dates, signal/filing audit, short-history 1Y handling, responsive 320px local table scrolling and persistence after reload. Browser warning/error logs were empty. Screenshot: ignored `var/uat/m04-validation.png`. No broker writes. Existing dependency deprecations and chart-bundle size notice remain non-failing.

## M-05 launch-style acceptance · 2026-11-03

**122 backend tests and 23 frontend tests passed**, with strict TypeScript, production build, frontend formatting, new-module lint/format checks and Git whitespace validation. Tests use independent small-number accounting examples and invariant checks, including exact momentum endpoints, sample volatility, tied percentile blends, sector water-filling, signal timing, splits/dividend receivables, next-open fees/slippage, bounded order sizing and daily external cash flows. They establish the specified cases, not universal data correctness or absence of defects.

| Journey / calculation | Evidence and observed result |
| --- | --- |
| Launch and clean first use | Actual launch script against normal database after stopping UAT servers; honest $100k planning capital, no connected account or fabricated history. Empty data/results/jobs/paper state verified separately. Clean-launch browser warning/error log was empty. |
| Ingestion | Actual browser invalid OHLC paste error, corrected atomic import and repeat-import deduplication; explicit practice generation and background download/progress. Actual market/SEC provenance checks remain recorded in M-02/M-03. Native picker remains unpassed. |
| Strategies/backtests/comparison | Both price recipes rerun in browser on practice data and saved; both selected in comparison with matching dates/capital. Fundamental/blended real-data runs, filing audit and repeated-result equality were checked in M-03/M-04. Independent signal/factor/ledger fixtures pass. |
| Research allocations | Stale saved prices failed visibly in Activity; current practice snapshot produced a saved 21-name/2%-cash read-only review. Target builder invariants and small-number cap/cash examples pass. |
| Validation | Eight development trials and one final test through real-data UI, locked/exposed dates and full audits. Atomic repeat-release prevention, retirement and failed/interrupted trials tested. |
| Paper setup/approval | Actual browser account refresh, version/policy/phrase/rationale, manual default and separate unchecked automatic permission. Changed policy requires fresh approval. New plan acknowledgement resets; same-plan quote retry requires its own acknowledgement. |
| End-to-end actual paper fills | Exact user-approved refreshed 16-name manual review; all 16 filled and positions reconciled. All share/dollar/price bounds independently audited; cash difference below $0.01; unique client references; no open broker orders. |
| Failure/recovery | Broker-free browser fixture: full cycle, partial waiting, owned-order cancellation and rejected-order stop. Automated: one-attempt ambiguous POST reconciliation, restart without duplicates, external cash/position changes, market-close race, temporary/wide quotes, eligibility, all sells before conservative settlement, bank holidays and missed sessions. Actual worker restart preserved completed fills without reposting. |
| Automatic mode | Broker-free browser setting change showed separate approval requirement and remained unapproved; paused afterward. Deterministic clock tests cover week-end preparation, once-only schedule and explicit automatic scope. Actual account was never approved for automatic operation. |
| Reporting | All seven periods inspected in deterministic browser history. Independent deposit/withdrawal, seed-history exclusion, split/dividend SPY and reset/missing-history tests pass. Actual account has only its first completed baseline, so returns remain unavailable. Alpaca paper dividend omissions and end-of-day flow approximation are visible. |
| Visual/accessibility basics | Five screens inspected at desktop/tablet/390/320 px; local table scrolling, readable typography and chart controls. Fixed a compact resume-button overflow and card spacing; loaded 320px Portfolio now has 320px page width. Dialog keyboard focus/Escape checked. No formal VoiceOver audit. |
| Persistence/export | Saved plans, inputs, orders, audits and results survive reload/restart; JSON API round-trips covered. Full backtest JSON download was browser-verified at foundation. New paper export file download was not separately exercised through the native download path. |
| Handover | Actual account refreshed after stop/revoke: no open broker orders, no active test approval, execution paused. Normal database remains free of test records. Current paper account retains test holdings, as authorized; it is not reset/deleted. |

Local evidence: `var/uat/m05-fill-audit.json`, `m05-completed-paper.png`, `m05-clean-first-use.png`, `m05-portfolio-320.png`, plus isolated `var/release-uat.sqlite3` and `var/contract-uat.sqlite3`. Credentials and account exports are not committed.

The native file chooser remains a manual acceptance item because browser automation stalled without delivering file bytes. Clean-machine installation/Finder double-click, actual VoiceOver/touch input, multi-week unattended scheduling, paid/consolidated quote access and live execution were not certified. A local worker must stay running; no hosted uptime is promised. Fixed-list history and current issuer/class/sector mapping remain exploratory. Existing dependency deprecations and chart-bundle warning are unchanged.

## Launcher browser opening · 2026-11-03

The launcher now opts into opening the system default browser after successful server startup. Verified by running the actual launcher script on this Mac: Safari opened `http://127.0.0.1:8000` automatically and showed the correct empty Overview. Stopping the service shut down its worker; the temporary test tab was closed. All 122 existing backend tests, entrypoint lint/format, launcher syntax, CLI help and production build passed. Finder double-click itself remains separate from this shell-invoked launcher check. Screenshot: ignored `var/uat/auto-browser-launch.png`.


## S&P 500 membership follow-up — November 3, 2026

Local validation: 141 backend tests and 26 UI tests; strict TypeScript/production build, backend format, changed-module Python F checks and whitespace passed. New cases cover full-index defaults and optional supplements; source format/count/duplicate validation; immutable refreshes, failures and stale capture handling; dated additions/removals/re-entry; future-roster perturbation; current-roster historical-test rejection; missing departed members; next-session fills; active versus archived identities and per-symbol metadata recovery; whole-index batching; and a greater-than-80,000-row download. Existing accounting, filing availability, research validation and paper approval/execution tests still pass.

Actual production-browser UAT used isolated `var/membership-uat.sqlite3`: refreshed 503 current securities and 2,720 historical rosters; downloaded all 503 current securities plus HIMS and SPY (505 total, 1,010 rows, October 28–29); followed queued work through Activity to saved Data; confirmed historical-mode source-bound dates and an explicit rejection beyond August 18, 2026. Full-source parsing was tested against live downloaded source content. The first real downloads exposed inactive KVUE metadata omitted by the bulk directory and an active/archived ECHO ticker collision. Those ingestion paths were fixed and regression tested. Existing paper permissions were not expanded. No account endpoints or orders were needed for this UAT.

A separate October 30–November 2 real read stopped at the existing AON foreign-dividend currency guard: Alpaca supplied `foreign=true` without a currency for the November 2 event. This was preserved, not guessed away. Arbitrary full-index periods can still stop on unsupported actions, ambiguous historical tickers or unavailable departed-stock prices. Public historical coverage currently ends August 18; announcement-time/security-master/delisting certification remains unavailable. Results must not be called survivorship-safe. See [universe contract](UNIVERSE.md).

The default database was checked read-only separately; test snapshots/jobs remain isolated. Validation is local, not a claim of GitHub CI or prolonged unattended operation.

## Unified S&P 500 download — November 3, 2026

Local final checks: 152 backend tests and 27 UI tests passed, together with strict TypeScript, production build, Python/frontend formatting, changed-module F lint and whitespace checks. Existing dependency deprecation warnings and the chart bundle-size advisory remain; no new build failures.

One S&P selection now acquires today's roster plus the members recorded during the requested period, and one refresh action updates both sources. Integration cases verify union/deduplication, downloads extending beyond the historical tail, periods with no historical overlap, missing required historical members, historical identity collisions, current-only active identity precedence, zero-bar current members preserved through storage reload, unchanged covered-period backtest fills, current review sectors, and rejection of the unverified membership gap. Frontend cases cover the two-option selector, optional supplements, custom lists, unified refresh and independent price dates.

Production-browser UAT used only `var/unified-membership-uat.sqlite3` on port 8022. The single refresh saved both sources and displayed 503 current securities plus 1,209 unique historical symbols, with source/capture/change details under one disclosure. The combined selector downloaded all current securities plus HIMS and SPY for October 28–29: 505 symbols and 1,010 actual daily bars. Activity completion and the saved dataset were inspected. An August 17–18 combined current/former-member request correctly stopped on an unresolved COR identity collision and published no partial dataset. Successful full historical-union ingestion is established by controlled provider integration tests, not by that blocked live request. The historical source still lacks later dated changes; this UI change does not repair the archive or certify identity/delisting completeness.

Desktop visual review and a 320px-wide browser check passed: controls remained reachable and document width stayed 320px. Custom-list switching and source disclosure were exercised; browser warning/error logs were empty. Screenshots are ignored `var/uat/unified-sp500-download.png` and `var/uat/unified-sp500-mobile.png`. No account endpoints, paper approvals or order submissions were part of this UAT. The prior paper contract fixture used real wall time against fixed November 2 prices, causing after-close failures; its test clocks now follow the fixture's November 3 trading time. Production timing and order guards were unchanged.


## Weekend staging, automatic membership and acquisition follow-up · 2026-11-04

Final automated checks: **183 backend tests / 31 UI tests passed**, TypeScript/production build, frontend formatting, changed-module Python formatting/lint and whitespace checks passed. Existing dependency deprecations and chart chunk-size notice remain non-failing. New independent contracts cover API approval completing broker acceptance without execution ticks, overlapping API/worker attempts with one POST per client ID, weekend staging, next-open deadlines, paper-margin buy-first/failed-sell debits, frozen cash-only compatibility, uncertain/partial/rejected/canceled/expired records, restart/revocation reconciliation, recent-batch status, automatic membership/backfill/adoption gates and exit-only departures. No actual Alpaca order submission was authorized for this update.

Actual browser evidence uses ignored isolated databases and production-built UI:

- `var/night-workflow-uat.sqlite3`: full read-only Alpaca 2016-01-04–2026-11-03 acquisition completed with 1,693,700 daily bars across 751 requested symbols. The current roster has 503 listings; the captured historical archive has 1,209 unique symbols across its full history. LHX matched duplicate listing identities with corroborating direct lookup/date evidence and retained 2,725 sessions with no missing prices. Its historical dividend pay-date gap remains flagged. Combined capture retains raw prices and 593 explicit unavailable/unverified security inputs; affected research remains blocked. This is not a certification of valid full-index backtests. An invalid ALL pay-before-ex date was found and handled as an explicit accounting issue rather than a whole-universe acquisition failure.
- Browser verified three universe options/defaults/matching names, 2016 start, hidden supplemental field for index-only, source/coverage warnings, background progress and saved capture persistence. Duplicate-name dataset selectors now show dates/capture times; no snapshot rename or overwrite.
- `var/manual-margin-uat/paper.sqlite`: simulated Sunday review, paper-margin acknowledgement and 5% policy, explicit strategy permission and separate manual batch approval. The test harness has no execution tick; approval itself produced two accepted Market DAY instructions and only then reported success. This uses deterministic broker fixtures, never actual broker orders.
- App shutdown/reopen with simulated external records showed one filled order at 125 versus 100 reference (+25%) and one expired order, with the same IDs. Review remaining trades generated a fresh next-session plan from actual held 39.96 shares, with 9.490999 additional reference AAPL shares and 49.450999 MSFT, rather than cloning old 49.95 quantities. New acknowledgement stayed unchecked. No remainder was auto-posted. An earlier two-filled startup case also reconciled to complete without duplicate submissions. Paper-margin debit/failure cases have independent automated coverage.
- Broader browser regression: practice generation and Momentum backtest completed; saved result/fills and 1Y chart/metrics inspected; Overview planning-capital honesty, empty paper setup, default manual/S&P/2016/5% settings, Activity completion/errors, and current weekly guidance checked. Compact Data and paper-policy/recovery layouts fit 320px with local table scrolling; captured browser warning/error logs were empty. This is a scoped UX pass, not a new claim of clean-machine, VoiceOver or prolonged hosted acceptance.

Proof images are local ignored `var/uat/universe-defaults-final.png`, `weekend-acceptance-final.png` and `off-hours-fills-final.png`. Fake permissions were revoked/paused; real test permissions and user account remain untouched. Existing historical archive coverage still ends at its last recorded 2026-08-18 change because later changes are missing; this release does not reconstruct them.


## Membership repair, incremental snapshots and storage · 2026-11-04

Final automated checks: **204 backend tests and 34 UI tests passed**, with TypeScript/production build, frontend formatting, changed Python formatting/F lint and whitespace checks. The 21 new snapshot/source cases include exact old-backtest reproduction after updates and compaction; revised/deleted overlap bars; split/dividend replacement; versioned SEC amendments; newcomer full backfill and dated entry/removal; preserved unresolved inputs and approval preferences; identity/transport/SEC failures; interrupted-job recovery; API deduplication without materializing prices; legacy inline conversion/zero-bar names; content-hash corruption/missing-block rejection; transaction rollback; repeated snapshot reuse; compaction integrity/idempotence/worker-lock guards; and a new completed session requiring verification before the 24-hour age limit. Existing dependency deprecations and chart-size notices remain non-failing.

Actual public-source UAT reconstructed the archive tail from S&P primary effective-date tables and the reviewed issuer ticker-change evidence. The final roster reconciled exactly to 503 observed listings, with 1,215 unique historical symbols and coverage through November 4. Independently checked September 21 substitutions, Vylor's temporary October 1 roster of 504, October 6 departures/additions and PSKY→SKYD, and KVUE remaining eligible through November 3 before OKTA enters November 4. October 30 is Okta's announcement date, not its effective date. Evidence is retained in immutable membership captures and ignored `var/uat/membership-effective-audit.json`. This strengthens the retrospective tail; it is not an as-known/survivorship-safe certification.

Browser UAT on an isolated provider fixture completed a price + SEC update from May 6 to May 13, retained both older vintages, displayed a newly versioned amendment and distinct selectors, and ran a Profitability / Quality backtest through saved results, fills and chart. Data controls fit 320px without document overflow; real final UI warning/error logs were empty. Screenshots: `var/uat/snapshot-mobile.png` and `snapshot-update-final.png`. A final normal-workspace restart showed all four datasets and the updated membership/current-session fields.

Actual read-only acquisition through the new UI updated the user's saved S&P dataset to November 4: **752 symbols, 1,696,721 bars and 23,178 annual filing records**. The old November 3 price/SEC snapshots remain frozen. The new price snapshot reused **80,860 of 81,457 old price blocks**, adding 717 new/revised blocks totaling **226,852 compressed bytes**; this excludes source responses, metadata and filings. The full index still has **603 flagged identity/action inputs**, so affected backtests remain blocked. Membership bounds are repaired; those independent inputs were not fabricated or silently cleared. No strategy was activated and no broker orders were submitted.

Storage cleanup first compacted a consistent full-size SQLite backup: all dataset logical hashes and 1,630 observation hashes were verified, then integrity checks passed. Before replacing the closed user database, compared every retained table's records (excluding transformed physical payload encodings), preserved the two datasets/nine prior results/thirteen jobs and zero paper orders/approvals/plans, and verified again after replacement. Normal database size fell from 452,988,928 to 445,243,392 bytes before the new data update. Removed 603,595,737 bytes of obsolete isolated acquisition-UAT/source copies after confirming no orders/approvals/plans; retained screenshots/reports and the separate real-paper-test audit database. Compacted that retained audit database without deleting its 16 orders. Temporary backup copies were removed only after verification. SQLite shared blocks, backup requirements and the bounded recent-update window are documented in `docs/SNAPSHOTS.md`.

## Research recovery and combined snapshots · 2026-11-05

Engine **0.3.0**: **229 backend / 43 UI tests**, TypeScript/production build, Python formatting/F lint, frontend formatting and Git whitespace checks passed. Existing Starlette/httpx and pandas deprecations and the chart chunk-size notice remain non-failing. The new contracts cover dated action/identity issues, payment-date versus ex-date accounting, opening entitlement valuation without future closing prices, incomplete merger consideration/contingent rights, conservative quote-alias quarantine, USD dividend checks, typed SEC 404 versus transport failure, combined-download completion/recovery, immutable replay and incremental overlap/backfill/storage reuse. A final review found and fixed interval-spanning identity warnings being lost at the refresh boundary; the regression also preserves older merger events for newly backfilled symbols. Screen payloads are bounded, decision audits load on demand, and complete exports retain the full ledger/provenance. A custom-list null-membership regression found during browser UAT was fixed and retested.

Actual production-UI acceptance used isolated workers and **2016-01-04–2026-11-04** data: **1,782,709 bars, 762 captured symbols and 23,182 annual filing records**. All five recipes completed **2017-01-03–2026-11-04**, 2,474 sessions each, with ex-date total-return accounting and explicit coverage-limited research:

| Recipe | Recorded fills | Excluded securities |
| --- | ---: | ---: |
| 12–1 Momentum | 14,721 | 142 |
| Defensive Low Volatility | 13,229 | 142 |
| Profitability / Quality | 12,819 | 142 |
| Quality Value | 13,365 | 142 |
| Value + Momentum | 14,786 | 142 |

An independent acceptance calculation rebuilt every SPY benchmark valuation from the captured raw prices, opening costs, splits and closing dividend reinvestment: **maximum difference zero in all five runs**. It also checked nonnegative cash/receivables, final holdings plus cash versus equity, every target's dated membership/exclusion status and stock/sector/cash caps, and real filing profitability and split-adjusted EPS units. This validates these calculations against their captured inputs; it does not certify vendor completeness or turn the retained subset into the full index.

Fresh-use browser UAT performed a real one-click market+SEC download for AAPL/MSFT/JNJ/PG/XOM plus benchmark SPY (16,356 bars / 213 filings), a January-2017 first backtest, update, older-snapshot selection and exact original-result replay. The actual update reused **786 of 786 price blocks**, added **6,115 compressed content-blob bytes**, and requested prices from October 23 rather than 2016. The byte figure excludes per-snapshot metadata, job records and SQLite/WAL overhead. Tests separately exercise subsequent sessions, changed/deleted overlap rows/actions, newcomer backfill and unchanged historical blocks.

Browser checks passed latest-only Data cards, archived snapshots, latest-only update choice, 20 px updater spacing, grouped latest/older research selectors, comparison of two full-history strategies, all seven chart periods, first/last filing decisions and source audit, restart persistence, and full native result/metadata/protocol/trial exports. The exported full-index result exactly matched the saved 14,786-fill / 514-decision body including provenance; screen projections did not truncate exports. Eight development/sensitivity trials and the one-time final test completed; restart retained its released state. Sensitivity details use their actual policy, and benchmark differences display percentage points. A 2021 onward strict payment-date control completed; the 2017 control stopped with the expected missing-payment-date explanation and no partial result. Compact updater, backtest form and results fit 320 px without page-level overflow. Final result and fresh-start browser logs had no warnings/errors.

User explicitly authorized a fresh local data reset. After stopping workers and acquiring exclusive locks, removed the old normal research database and both disposable acquisition/first-use databases, reclaiming **1,312,968,704 bytes**. Verified unchanged configuration and the separate historical 16-order release audit; no broker mutation or new strategy approval/order occurred. The empty normal workspace was reopened through the actual UI: S&P current+historical default, 2016 start, latest completed end and enabled combined download. Own services/tabs stopped and temporary viewport reset. Small reports, representative gap evidence and screenshots remain ignored under `var/uat/research/`; large temporary export files were removed.

**B-033 remains open:** missing departed-stock prices, historical identities, action terms and verified cash dates still prevent certified strict full-index research. Each exploratory result records all 142 exclusions and warns that whole-window availability can introduce survivorship/selection bias. Original source vintages and historical sector classifications remain uncertified. Clean-machine installation, VoiceOver, native picker and prolonged unattended operation remain outside this scoped acceptance. See [free-data gaps](FREE_DATA_GAPS.md) and [snapshot/storage semantics](SNAPSHOTS.md).

## November 8 multi-strategy backtests — 0.5.1

313 backend and 58 frontend tests pass, including atomic batch rollback, common inputs, duplicate active tasks, invalid fundamental selections, reserved final-test windows, and named Activity rows. TypeScript/production build, Ruff F checks, Python/frontend formatting and whitespace checks pass.

Actual isolated browser UAT submitted all five strategies together for January 3, 2017–November 6, 2026. Five ordinary results completed. All curves, trades, decisions, holdings, coverage, performance windows and other financial output fields exactly match the prior individual 0.5.0 baselines (12,380 daily valuations). A second two-strategy October–November batch completed with distinct strategy names in Activity after restart. At 320 pixels, all selections and submission controls are readable with no horizontal overflow. The normal database, connection settings and paper records were not changed. This verifies batch orchestration, not broader historical-data completeness or strategy readiness.
