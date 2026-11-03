# Incremental build record

Each milestone is checked with automated financial/contract tests and actual-browser UAT before its commit and push. User credentials and downloaded/account data remain in ignored local files. Strategy activation is separate from building the software.

## 1 — Real market data

- Added a UI-managed, editable current US watchlist and background Alpaca downloads using authenticated historical SIP bars with explicit raw prices and identity-as-of dates. SPY is included only as a benchmark. No fallback to IEX or Yahoo is silent.
- Validated current US listing metadata, positive OHLC, trading sessions, corporate-action identifiers/ratios/pay dates, per-stock gaps, pagination and incompatible actions. Split-adjusted prices are a cross-check with cent-rounding intervals; calculations use the original raw bars. Special cash distributions follow supplied ex/pay dates; unsupported currencies, due-bill cases, mergers/spin-offs and missing information stop publication.
- Added bounded retries/caching, immutable response-body archives/fingerprints, local credential redaction, and duplicate-safe snapshots. Original CSV imports remain available. Downloaded history remains fixed-list exploratory research; current selections/sectors and incomplete delisted coverage are not survivorship-safe.
- Real-provider checks: configured paper account read access, SIP history and corporate actions all returned successfully. Browser workflow saved **37,603 bars for 31 symbols**, mapped **564 cash/split events**, and reported **zero missing sessions** for 2022-01-03 through 2026-11-02. A real-data momentum backtest completed through the interface. No paper orders were submitted.
- UAT exposed and fixed a false split warning caused by adjusted-price cent rounding. It also exposed missing dividend currency information for a foreign listing, which is conservatively excluded from the starter list until units can be verified.
- Automated checks at this checkpoint: **49 backend tests**, **12 frontend tests**, strict TypeScript and production build. Existing Starlette/pandas deprecation and lazy-chart size warnings remain non-failing. Browser evidence is local under `var/uat/m1-*.png`.

Provider references: [historical bar contract](https://docs.alpaca.markets/us/reference/stockbars), [feed and aggregation rules](https://docs.alpaca.markets/us/docs/market-data-faq), [corporate actions and their publication limits](https://docs.alpaca.markets/us/reference/corporateactions-1).
