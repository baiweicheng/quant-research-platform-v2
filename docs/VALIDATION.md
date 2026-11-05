# Research milestone validation

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
