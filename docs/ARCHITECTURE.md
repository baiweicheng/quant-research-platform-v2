# Local architecture

The React/TypeScript/Vite client uses React Query for saved server state, Radix dialog/tooltip primitives and a lazily loaded ECharts line chart. Navigation and chart interactions do not execute calculations. The production build is served by FastAPI on loopback. A separate Python worker reads a persistent SQLite queue. No Streamlit or v1 code is used.

`python -m aperture` starts API + worker and stops its child on shutdown. One worker per database is enforced with an OS file lock. On worker startup, interrupted running jobs are marked failed with an actionable explanation; queued jobs continue. Identical active task requests deduplicate. Progress is persisted. Result insertion and job completion share one transaction, so a failed computation cannot publish a partial result. SQLite uses WAL and transactions; schema v1 is recorded explicitly. Future schema changes need ordered migrations.

The API validates bounded request bodies and strategy/data availability. Mutations require a custom same-origin client header; CORS is not enabled. Trusted hostnames and loopback binding narrow the local boundary. This is not an authenticated multi-user/hosted application. Do not expose it publicly before the hosting/security milestone.

The database stores compressed immutable dataset bodies, compressed submitted UTF-8 source content, task payloads and saved results. Application data and local environment files are ignored by Git. No credentials or brokerage integration are present. Dependency versions are locked in `uv.lock` and `web/package-lock.json`.

The core domain is independent of the HTTP layer: `signals.py` controls historical observation cutoffs, `portfolio.py` constructs constrained targets, `ledger.py` handles corporate actions and simulated fills, and `metrics.py` calculates display-window statistics. Both backtests and read-only reviews use the same strategy definitions and target construction. Broker order planning will be a separate milestone that uses the same policy semantics plus current account constraints.
