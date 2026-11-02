# Research milestone validation

Verified on a local Mac, 2026-11-02. This record covers the first research milestone, not paper/live readiness or a vendor-data certification.

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
- No real provider downloads, original-file binary archive, historical universe certification, point-in-time fundamentals, cash-account settlement simulation, broker fills, strategy activation, paper orders or live orders were validated or implemented.
- No clean-machine installation, VoiceOver audit, real-device touch testing or prolonged unattended run is claimed. Responsive testing used browser viewport overrides.
- Zero defects, unbiased vendor history and future profitability are not guaranteed by these checks.
