# Aperture

A local quantitative research workspace for weekly, long-only US equity strategies. Built from scratch with a React/TypeScript interface and a Python calculation worker.

This first milestone is a **research application**. It does not connect to a broker, approve a strategy, submit paper/live orders, or show fabricated account performance.

## Run on a Mac

Requires [uv](https://docs.astral.sh/uv/) and Node.js 22.12+ with npm. Dependencies and the Python runtime are downloaded on first setup; subsequent research runs are local.

Double-click `Launch Aperture.command`, or run from the repository root:

```sh
UV_CACHE_DIR=.cache/uv UV_PYTHON_INSTALL_DIR=.tools/python uv sync --locked --python 3.13
npm --prefix web ci
npm --prefix web run build
.venv/bin/python -m aperture
```

Open **http://127.0.0.1:8000**. Keep the terminal open while tasks are running; press Control-C to stop the API and worker. All application data is under ignored `var/`, in `aperture.sqlite3`. The server binds only to this machine. Hosting and authentication are a later milestone.

For frontend development, run `npm --prefix web run dev` alongside the Python service. Vite proxies `/api` to port 8000. Build the frontend again before using the Python-served production preview.

## Try the complete workflow

1. Open **Data → Create practice data**. This explicitly opts into fictional prices, including a fictional SPY series.
2. Open **Research**, inspect a strategy’s explanation, and run a backtest. Default dates leave room for signal warm-up.
3. Follow progress in **Activity**, then open the completed result. Try every chart period, inspect simulated fills, and export the full result.
4. Run the other price strategy with identical inputs. Select both experiments to compare.
5. Select **Prepare weekly review**. Saved data must cover the latest completed session. Inspect the read-only allocation in **Portfolio**. No orders or strategy approvals are created.

The app opens empty. Practice data is never silently loaded. Account metrics remain unavailable until actual paper-account history exists.

## Supported in this milestone

- Immutable CSV datasets with source fingerprints, idempotent imports, validation, and retained submitted CSV content.
- Authenticated Alpaca SIP history, split/dividend normalization, per-stock coverage and captured source responses through the Data interface.
- A persisted background queue, visible progress, atomic saved results, duplicate task protection, and interrupted-task recovery.
- 12–1 momentum and defensive low-volatility strategies; shared stock/sector/cash allocation rules.
- Calendar-aware after-close decisions and following-session opening-price simulation, fractional quantities, explicit costs, split/dividend accounting and no borrowing.
- Saved backtests, comparison, SPY benchmark, common chart periods, and read-only current allocation reviews.
- Approved Weekly Focus layout, responsive top navigation, empty/error states and explanations.

Alpaca market-data downloads are now available under Data. Point-in-time fundamentals, the quality/value/hybrid strategies, AI-assisted discovery, strategy approvals, broker reconciliation and both manual/automatic paper execution remain future milestones. None are represented as working features. Real-money trading requires a later readiness review and explicit authorization.

## Accuracy boundaries

No software or free data source can guarantee zero errors. Passing tests establishes specific behavior under tested assumptions, not the absence of defects or future investment performance.

Current tests use a **fixed imported list**. Historical membership, delisted-security coverage, US listing eligibility, sector histories and vendor adjustment conventions are not independently verified. These results are exploratory and must not be called survivorship-safe. Missing held-stock prices stop the simulation; the engine never invents a delisting exit or forward-fills a held stock.

For input requirements, formulas, timing and financial conventions see [the research contract](docs/RESEARCH_CONTRACT.md). For the service boundary and recovery behavior see [architecture](docs/ARCHITECTURE.md).

## Verification

```sh
.venv/bin/pytest -q
npm --prefix web test
npm --prefix web run build
```

The backend suite includes independent accounting examples, future-price perturbation, late observations, holiday/early-close cutoffs, missing-price failures, persistence/recovery/API tests, and property tests for cash and allocation constraints. Browser UAT is recorded separately in [validation](docs/VALIDATION.md). Unit tests are not a substitute for actual user-style validation or vendor-data audits.

## Local data and backups

Application state and submitted imports are local and Git-ignored. Stop Aperture before copying the entire `var/` directory for a consistent backup, and keep it private. Exported results include provenance and the full simulation ledger, but are not a full database backup. No telemetry or remote analytics is configured.

## Provider setup

Copy `.env.example` to ignored `.env` and set `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` with **paper** keys. Set `SEC_USER_AGENT` to a descriptive name and your contact email for SEC requests. Keys are read locally, are never sent to the browser, and must never be committed. In Data, test the connection, edit the watchlist/date range and select Download & validate. The default watchlist is a manageable research starting point, not a buy recommendation or historical index universe.

See [milestone validation](docs/MILESTONES.md) for actual provider checks, coverage limits and subsequent build stages.
