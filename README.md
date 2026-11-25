# Aperture

A local research and paper-trading workspace for weekly and monthly long-only US equity strategies. Built from scratch with a React/TypeScript interface and a Python calculation worker.

Includes captured market/SEC inputs, reproducible backtests and research validation, and version-approved manual/automatic **Alpaca paper trading**. Live trading is unavailable. Each strategy, policy and account needs explicit approval; building or backtesting a strategy never activates it.

## Run on a Mac

Requires [uv](https://docs.astral.sh/uv/) and Node.js 22.12+ with npm. Dependencies and the Python runtime are downloaded on first setup; subsequent research runs are local.

Double-click `Launch Aperture.command`. It opens your default browser automatically once the local service is ready. Alternatively, run from the repository root:

```sh
UV_CACHE_DIR=.cache/uv UV_PYTHON_INSTALL_DIR=.tools/python uv sync --locked --python 3.13
npm --prefix web ci
npm --prefix web run build
.venv/bin/python -m aperture
```

Open **http://127.0.0.1:8000**. Keep the terminal open while tasks are running; press Control-C to stop the API and worker. All application data is under ignored `var/`, in `aperture.sqlite3`. The server binds only to this machine. Hosting and authentication are a later milestone.

For frontend development, run `npm --prefix web run dev` alongside the Python service. Vite proxies `/api` to port 8000. Build the frontend again before using the Python-served production preview.

## Try the complete workflow

1. Configure the sources below and open **Data → Download research data → Download & validate**.
2. Open **Research**, inspect a strategy’s explanation, and run a backtest. Default dates leave room for signal warm-up.
3. Follow progress in **Activity**, then open the completed result. Try every chart period, inspect simulated fills, and export the full result.
4. Run the other price strategy with identical inputs. Select both experiments to compare.
5. Use **Portfolio → Research allocations → Prepare weekly review** to inspect read-only targets. Saved data must cover the latest completed session. Research reviews never submit orders.
6. Use **Research → Validation** for a frozen hypothesis, chronological windows, sensitivity trials and a one-time final-test reservation.
7. For actual paper operation, follow the account/approval sequence below.

A fresh workspace opens without a dataset. Account metrics appear once paper-account history is available.

## Supported workflows

- Authenticated Alpaca SIP history, split/dividend normalization, per-stock coverage and captured source responses through the Data interface.
- A persisted background queue, visible progress, atomic saved results, duplicate task protection, and interrupted-task recovery.
- Weekly 12–1 Momentum and Liquidity and Breadth strategies with shared stock, sector and cash allocation limits.
- Filing-versioned SEC annual fundamentals, stock-level coverage/exclusions, profitability, quality value and technical/fundamental Value + Momentum strategies. Historical decision audits link back to original filings.
- Calendar-aware after-close decisions and following-session opening-price simulation, fractional quantities, explicit costs, split/dividend accounting and no borrowing.
- Saved backtests, comparison, SPY benchmark, common chart periods, and read-only current allocation reviews.
- Searchable research management with previewed individual/bulk deletion of backtests, allocation reviews, validation outputs, task history and datasets; linked inputs and paper audit records are protected. See [research cleanup](docs/RESEARCH_LIBRARY.md).
- Frozen research protocols, forward windows, cost/allocation/frequency sensitivity, trial audits, exposure labels and once-only final-test release.
- Paper account reconciliation, immutable reviews and explicit strategy and policy approvals. Manual and automatic modes follow the selected strategy's cadence.
- Broker-staged Market DAY orders with explicit paper-margin funding, durable client references, partial/rejected/uncertain-order handling, stop/cancel controls and restart reconciliation.
- Actual broker holdings/equity, daily cash-flow-adjusted estimates and SPY comparison with explicit simulator limits.
- Approved Weekly Focus layout, responsive top navigation, empty/error states and explanations.

Use **Data → Download research data → Download & validate** to create a snapshot. The normal download always includes daily market data and filing-dated SEC fundamentals; price-only strategies simply ignore the fundamental portion. Backtests default to the latest complete snapshot, with older versions grouped separately. January 2016 inputs default research dates to January 2017 through the latest saved session. Review factor values, filing availability and exclusions under “Why these stocks?” in the result. Annual US-GAAP support is deliberately limited; unsupported inputs are excluded. See the research contract before interpreting results.

To bring existing research forward, use **Data → Update a saved dataset → Update dataset**, then select the new snapshot in Research. Only the latest version of each saved dataset is offered for update. Existing stocks refresh a recent overlap plus new sessions; new members receive historical backfill, and SEC company facts refresh when a 10-Q or 10-K changes, an amendment arrives or the 30-day check is due. Unchanged prices, filings and provider responses share storage. See [snapshot updates and storage](docs/SNAPSHOTS.md) for older-history, reproducibility, recovery and backup limits.

Downloads and updates include the required source checks automatically. There is no routine second SEC/share-class step. **More refresh options** contains optional stage-specific repairs; an interrupted download can complete its SEC stage using the prices already saved. Structured SEC facts replace bulk EPS report downloads. Profitability additionally verifies derived revenues/costs against compact primary income-statement reports; source proofs are reused automatically. See [profitability support and definition limits](docs/PROFITABILITY.md). Ordinary share comparability is a disclosed approximation, with known unequal-share cases excluded; unchanged annual histories can be reused for up to 30 days. Activity shows progress while the rest of the workspace remains usable. See [the lightweight EPS policy](docs/LIGHTWEIGHT_EPS.md). Reviewed corporate-action corrections and their primary sources are expandable in Data.

**Research → New backtest** lets you select several strategies, including Select all, with one shared dataset, date range and policy. One submission queues separate named tasks and results. The worker runs them in sequence to keep memory bounded; Open **Saved backtests** in **Backtest results** to select or compare saved results.

**Session Strength and Liquidity** and **Earnings and Market Regime Rotation** are available in the Research catalog. Both use complete SPY and stock history plus comparable annual SEC net income. Their results show calendar-year returns against SPY, with the valuation dates for partial years. See the [strategy definitions and historical limitations](docs/RESEARCH_CONTRACT.md#signals-and-allocation).

**Weekly Earnings Reaction Tracker** uses quarterly or annual filed net income, price reactions to those filings and portfolio tracking risk. Open its Research card to backtest it or prepare a research allocation. [Strategy rules and historical results](docs/WEEKLY_EARNINGS_TRACKER.md)

**Earnings and Market Capture** combines filed earnings with relative returns on weak and strong SPY days. It rebalances weekly and is available in Research. [Strategy rules and annual results](docs/EARNINGS_MARKET_CAPTURE.md)

**Liquidity and Breadth** is a weekly technical strategy that uses sustained trading liquidity, relative volatility, sector participation and SPY beta. [Strategy rules and annual results](docs/LIQUIDITY_BREADTH.md)

**Earnings and Pullback Rotation** is a weekly hybrid that combines filed earnings and beta-adjusted relative strength, with a pullback rule after broad market declines. [Strategy rules and full-period Standard-cost comparison](docs/EARNINGS_PULLBACK_ROTATION.md)

**Liquidity and Volatility Rotation** is a weekly research strategy that uses filed profitability as an eligibility screen, with volatility-adjusted liquidity, risk-adjusted trends and a rebound rule after broad market declines. [Strategy rules and annual results](docs/LIQUIDITY_VOLATILITY_ROTATION.md)

To start fresh, open **Data → Workspace maintenance → Reset workspace**. Review the preview, type **RESET WORKSPACE**, then choose **Reset permanently**. The reset clears saved research and downloads and preserves paper trading history and configuration. See the [workspace reset details](docs/RESEARCH_LIBRARY.md#reset-the-research-workspace).

Research setup separates **total-return research** (ex-date closing reinvestment) from **payment-date cash-flow simulation** (verified settlement dates). It also separates **coverage-limited research**, which saves every omitted security and reason, from **strict full-index coverage**, which stops on unresolved required inputs. Coverage-limited results can have survivorship/selection bias and are not complete S&P 500 results. The unresolved free-data gaps remain open in [B-033](docs/FREE_DATA_GAPS.md); these options do not approve trading.

AI-assisted discovery and broader operational reliability/automation remain future milestones. Real-money trading requires a separate later readiness review and explicit authorization.

## Start paper trading deliberately

1. Configure paper keys/contact below, then **Portfolio → Paper portfolio → Refresh paper account**. The app reads the actual account; it never resets its balance. Use a dedicated long-only USD paper account.
2. Choose an available strategy in Paper Settings, then save the stock universe, history start, risk policy and mode. Profitable Liquidity Leaders, Session Strength and Liquidity, and Earnings and Market Regime Rotation use month-end timing. Manual is selected initially. Suggested limits remain proposals until explicitly approved.
3. Review research, validation and data limits. Record explicit paper approval with the exact displayed strategy/version phrase and a rationale. Automatic operation needs its separate permission checkbox.
4. Select **Prepare weekly paper review** or **Prepare month-end paper review**, as shown for the strategy. This task reconciles the account, refreshes membership, backfills new members and updates prices and SEC filings before freezing proposed targets and orders. Aim to prepare and stage after the period's final session data is available and before the next regular open. If you miss month-end, **Prepare month-end catch-up** is available for a regular open within seven calendar days of the original open. A changed index list requires adoption and new approval.
5. In manual mode, inspect the specific review and separately approve its following-session paper rebalance. Keep Aperture running until all Market DAY instructions are confirmed accepted at Alpaca. You may then close it; the next launch checks fills, cash and positions. Actual fill prices may differ, and paper margin can bridge sale proceeds under an explicitly approved policy. A simulated debit can remain overnight; new settings default to a 5% cash reserve.
6. Use **Stop future submissions**, **Stop & cancel Aperture orders**, account refresh and the order lifecycle table when anything needs attention. Cancellation can race fills and never reverses a fill.
7. A new paper account has a separate identity/baseline and inherits no strategy approval. Update its keys privately and refresh/reapprove before use.

See [paper execution](docs/PAPER_TRADING.md) and [research validation](docs/RESEARCH_VALIDATION.md) for exact boundaries. Automatic mode runs only while the local worker is alive; it does not wake a stopped Mac or guarantee hosting. Alpaca paper does not credit dividends, while SPY includes them; the account comparison gap includes this simulator difference. Daily cash-flow adjustment uses an end-of-day approximation, not exact intraday time-weighted returns.

## Accuracy boundaries

No software or free data source can guarantee zero errors. Passing tests establishes specific behavior under tested assumptions, not the absence of defects or future investment performance.

Data defaults to **S&P 500 — current and historical members**, with separate S&P 500 + custom list and Custom list only choices, matching default dataset names, and a January 4, 2016 default start. One download includes today's roster and every recorded member during the selected period, including departures. One membership refresh updates both sources; Data shows price dates separately from supported historical backtest membership. Newer prices do not supply missing membership changes. See [the universe contract](docs/UNIVERSE.md). Public historical membership is retrospective; delisted-security coverage, historical security identities, sector histories and vendor adjustment conventions are not independently verified. These results are exploratory and must not be called survivorship-safe. Missing required member or held-stock prices stop validation; the engine never invents a delisting exit or forward-fills a held stock.

For input requirements, formulas, timing and financial conventions see [the research contract](docs/RESEARCH_CONTRACT.md). For the service boundary and recovery behavior see [architecture](docs/ARCHITECTURE.md).

## Verification

```sh
.venv/bin/pytest -q
npm --prefix web test
npm --prefix web run build
```

The backend suite includes independent accounting examples, future-price perturbation, late observations, holiday/early-close cutoffs, missing-price failures, persistence/recovery/API tests, and property tests for cash and allocation constraints. Browser UAT is recorded separately in [validation](docs/VALIDATION.md). Unit tests are not a substitute for actual user-style validation or vendor-data audits.

See the [hybrid strategy study](docs/HYBRID_STRATEGY_RESEARCH_2026-11-18.md), [price-only strategy study](docs/STRATEGY_RESEARCH_2026-11-18.md), [historical coverage improvements](docs/HISTORICAL_COVERAGE.md), and [remaining free-data gaps](docs/FREE_DATA_GAPS.md) for the current research checkpoint.

## Local data and backups

Application state is local and Git-ignored. Stop Aperture before copying the entire `var/` directory for a consistent backup, and keep it private. Exported results include provenance and the full simulation ledger, but are not a full database backup. No telemetry or remote analytics is configured.

## Provider setup

Copy `.env.example` to ignored `.env` and set `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` with **paper** keys. Set `SEC_USER_AGENT` to a descriptive name and your contact email for SEC requests. Keys are read locally, are never sent to the browser, and must never be committed. In Data, test the connection, select the universe and date range, then choose Download & validate. The default is the S&P 500 current and historical universe; custom lists remain exploratory and are not buy recommendations.

See [milestone validation](docs/MILESTONES.md) for actual provider checks, coverage limits and subsequent build stages.
