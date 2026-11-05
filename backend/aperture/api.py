"""Local API: bounded inputs, persisted research and approved PAPER operations."""

from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__

from .domain import STRATEGIES, ResearchError, decimal, strategy
from .ingest import MAX_BYTES, TEMPLATE, parse_csv
from .store import Store
from .config import settings
from . import membership
from .presentation import dataset_view, result_view, decision_view


class ImportRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=500)
    price_basis: Literal["as_traded"]
    csv: str = Field(max_length=MAX_BYTES)


class TaskRequest(BaseModel):
    dataset_id: str = Field(max_length=40)
    strategy_id: str = Field(max_length=40)
    start: date | None = None
    end: date | None = None
    capital: str = Field(default="100000", max_length=20)
    dividend_model: Literal["ex_date", "pay_date"] = "ex_date"
    coverage_mode: Literal["strict", "coverage_limited"] = "coverage_limited"


class DownloadRequest(BaseModel):
    name: str = Field(default="S&P 500", min_length=1, max_length=100)
    universe: Literal["sp500", "sp500_current", "sp500_historical", "custom"] = "sp500"
    symbols: list[str] = Field(default_factory=list, max_length=1500)
    start: date
    end: date
    include_fundamentals: Literal[True] = True


class ProtocolRequest(TaskRequest):
    name: str = Field(min_length=1, max_length=100)
    hypothesis: str = Field(min_length=10, max_length=2000)
    start: date
    end: date
    holdout_start: date


class EvaluationRequest(BaseModel):
    phase: Literal["development", "holdout"]
    acknowledge: bool = False


class PaperConfigRequest(BaseModel):
    strategy_id: str = Field(max_length=40)
    mode: Literal["manual", "automatic"] = "manual"
    execution: Literal["broker_market", "local_limit"] = "broker_market"
    funding_policy: Literal["cash_only", "paper_margin"] = "paper_margin"
    universe: Literal["sp500", "custom"] = "sp500"
    symbols: list[str] = Field(default_factory=list, max_length=1500)
    data_start: date
    positions: int = Field(default=25, ge=1, le=100)
    max_weight: str = Field(default="0.05", max_length=20)
    sector_cap: str = Field(default="0.25", max_length=20)
    cash_reserve: str = Field(default="0.05", max_length=20)
    max_drift: str = Field(default="0.03", max_length=20)


class PaperApprovalRequest(BaseModel):
    config_hash: str = Field(max_length=64)
    confirmation: str = Field(max_length=100)
    rationale: str = Field(min_length=10, max_length=2000)
    acknowledge_limits: bool
    allow_automatic: bool = False


class RebalanceApprovalRequest(BaseModel):
    acknowledge: bool = False


def create_app(
    db_path: str | Path = "var/aperture.sqlite3",
    web_path: str | Path | None = "web/dist",
) -> FastAPI:
    store = Store(db_path)

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = FastAPI(
        title="Aperture local research", version=__version__, lifespan=lifespan
    )
    app.state.store = store
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("x-aperture-client") != "1":
                return JSONResponse(
                    {"detail": "Use the local Aperture interface to make changes."},
                    status_code=403,
                )
            length = request.headers.get("content-length")
            if length and (
                not length.isdigit() or int(length) > MAX_BYTES + 1024 * 1024
            ):
                return JSONResponse(
                    {"detail": "Request exceeds the local import limit."},
                    status_code=413,
                )
            # Enforce a streamed limit too; a missing Content-Length cannot bypass it.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BYTES + 1024 * 1024:
                    return JSONResponse(
                        {"detail": "Request exceeds the local import limit."},
                        status_code=413,
                    )
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.exception_handler(ResearchError)
    async def domain_error(request: Request, error: ResearchError):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.get("/api/state")
    def state():
        snapshot = store.preference("paper_snapshot")
        return {
            "version": __version__,
            "datasets": [dataset_view(d) for d in store.datasets()],
            "strategies": STRATEGIES,
            "jobs": store.jobs(),
            "runs": store.results("backtest"),
            "reviews": store.results("review"),
            "account": {
                "connected": bool(snapshot),
                "planning_capital": "100000",
                "mode": "paper" if snapshot else "research",
                "snapshot": snapshot,
            },
        }

    @app.get("/api/results/{identifier}")
    def result(identifier: str, view: bool = False, download: bool = False):
        body = store.result(identifier)
        if download:
            return JSONResponse(
                body,
                headers={
                    "Content-Disposition": f'attachment; filename="aperture-{identifier}.json"'
                },
            )
        return result_view(body, f"/results/{identifier}") if view else body

    @app.get("/api/results/{identifier}/decisions/{session}")
    def result_decision(identifier: str, session: date):
        return decision_view(store.result(identifier), session.isoformat())

    @app.get("/api/datasets/{identifier}/metadata")
    def dataset_metadata(identifier: str):
        body = next((d for d in store.datasets() if d["id"] == identifier), None)
        if body is None:
            raise ResearchError("That dataset was not found. Choose one from Data.")
        return JSONResponse(
            body,
            headers={
                "Content-Disposition": f'attachment; filename="aperture-dataset-{identifier}.json"'
            },
        )

    @app.get("/api/research/protocols")
    def research_protocols():
        from .experiments import protocols, history

        with store.connect() as db:
            attempts = db.execute(
                "SELECT count(*) FROM jobs WHERE kind IN ('backtest','validation')"
            ).fetchone()[0]
        return {
            "protocols": protocols(store),
            "trials": history(store),
            "workspace_attempts": attempts,
        }

    @app.post("/api/research/protocols", status_code=201)
    def create_protocol(payload: ProtocolRequest):
        from .experiments import create

        return create(store, payload.model_dump(mode="json"))

    @app.post("/api/research/protocols/{identifier}/evaluate", status_code=202)
    def evaluate_protocol(identifier: str, payload: EvaluationRequest):
        from .experiments import enqueue

        return enqueue(store, identifier, payload.phase, payload.acknowledge)

    @app.get("/api/research/trials/{identifier}")
    def research_trial(identifier: str, view: bool = False, download: bool = False):
        from .experiments import trial

        body = trial(store, identifier)
        if download:
            return JSONResponse(
                body,
                headers={
                    "Content-Disposition": f'attachment; filename="aperture-trial-{identifier}.json"'
                },
            )
        return result_view(body, f"/research/trials/{identifier}") if view else body

    @app.get("/api/research/trials/{identifier}/decisions/{session}")
    def trial_decision(identifier: str, session: date):
        from .experiments import trial

        return decision_view(trial(store, identifier), session.isoformat())

    @app.post("/api/research/protocols/{identifier}/retire")
    def retire_protocol(identifier: str):
        from .experiments import retire

        return retire(store, identifier)

    @app.get("/api/paper")
    def paper_state():
        from .paper import public_state

        return public_state(store)

    @app.post("/api/paper/config")
    def paper_config(payload: PaperConfigRequest):
        from .paper import save_configuration

        return save_configuration(store, payload.model_dump(mode="json"))

    @app.post("/api/paper/approval")
    def paper_approval(payload: PaperApprovalRequest):
        from .paper import approve_strategy

        return approve_strategy(store, payload.model_dump())

    @app.post("/api/paper/revoke")
    def paper_revoke():
        from .paper import revoke

        revoke(store)
        return {"revoked": True}

    @app.post("/api/paper/membership/apply")
    def apply_membership():
        from .paper import apply_membership_update

        return apply_membership_update(store)

    @app.post("/api/paper/actions/{kind}", status_code=202)
    def paper_action(kind: Literal["sync", "prepare", "cancel", "stop", "resume"]):
        from .paper import configuration, stop, resume

        if kind == "stop":
            stop(store)
            return {"stopped": True}
        if kind == "resume":
            return resume(store)
        settings().headers()
        if kind == "cancel":
            stop(store)
        cfg = configuration(store)
        if kind == "prepare" and not cfg:
            raise ResearchError(
                "Save your paper strategy, universe and risk settings first."
            )
        return store.enqueue(
            "paper_" + kind, {"config_hash": cfg["hash"] if cfg else None}
        )

    @app.post("/api/paper/plans/{identifier}/approve")
    def approve_rebalance(identifier: str, payload: RebalanceApprovalRequest):
        from .staged import approve_and_stage

        if not payload.acknowledge:
            raise ResearchError(
                "Acknowledge the specific paper orders and execution bounds before approving this rebalance."
            )
        return approve_and_stage(store, identifier)

    @app.get("/api/providers")
    def providers():
        from .calendar import latest_complete

        cfg = settings()
        current = store.membership("current")
        watchlist = store.preference("watchlist", {})
        return {
            "alpaca_configured": cfg.configured,
            "sec_configured": "@" in cfg.sec_agent,
            "latest_session": str(latest_complete()),
            "first_session": "2016-01-04",
            "membership": {
                "current": membership.summary(current),
                "historical": membership.summary(store.membership("historical")),
            },
            "watchlist": {
                "name": watchlist.get("name", "S&P 500"),
                "universe": watchlist.get("universe", "sp500"),
                "symbols": watchlist.get("symbols", []),
                "start": watchlist.get("start", "2016-01-04"),
            },
            "paper_default_symbols": sorted(
                {m["symbol"] for m in current["members"]}
                | set(watchlist.get("symbols", []))
                | {"SPY"}
            )
            if current
            else [],
        }

    @app.post("/api/membership/{kind}/refresh", status_code=202)
    def refresh_membership(kind: Literal["all", "current", "historical"]):
        return store.enqueue("membership", {"kind": kind})

    @app.post("/api/providers/check", status_code=202)
    def check_provider():
        settings().headers()
        return store.enqueue("connection", {})

    @app.post("/api/downloads", status_code=202)
    def queue_download(payload: DownloadRequest):
        settings().headers()
        if payload.include_fundamentals and "@" not in settings().sec_agent:
            raise ResearchError(
                "Configure SEC_USER_AGENT once in the private .env file. Downloads include market data and SEC filings together."
            )
        data = payload.model_dump(mode="json")
        data["symbols"] = membership.symbols(
            data["symbols"], allow_empty=payload.universe != "custom"
        )
        from .calendar import latest_complete

        if (
            payload.start < date(2016, 1, 4)
            or payload.end > latest_complete()
            or payload.start >= payload.end
        ):
            raise ResearchError(
                "Choose a valid completed-session period from 2016 onward, with the end after the start."
            )
        store.set_preference(
            "watchlist",
            {
                "name": data["name"],
                "symbols": data["symbols"],
                "start": data["start"],
                "universe": data["universe"],
            },
        )
        return store.enqueue("download", data)

    @app.get("/api/template.csv")
    def template():
        return Response(
            TEMPLATE,
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="aperture-template.csv"'
            },
        )

    @app.post("/api/datasets", status_code=201)
    def import_dataset(payload: ImportRequest):
        dataset, raw, warnings = parse_csv(payload.csv, payload.name, payload.source)
        return store.save_dataset(dataset, raw, warnings)

    @app.post("/api/practice", status_code=202)
    def practice():
        return store.enqueue("practice", {})

    @app.post("/api/fundamentals/{dataset_id}", status_code=202)
    def queue_fundamentals(dataset_id: str):
        if "@" not in settings().sec_agent:
            raise ResearchError(
                "Configure SEC_USER_AGENT with your name and contact email in the private .env file first."
            )
        dataset = store.dataset(dataset_id)
        if dataset.kind == "synthetic":
            raise ResearchError(
                "Choose actual market data, not fictional practice symbols."
            )
        return store.enqueue(
            "fundamentals",
            {"dataset_id": dataset.metadata.get("price_dataset_id", dataset.id)},
        )

    @app.post("/api/datasets/{dataset_id}/update", status_code=202)
    def update_dataset(dataset_id: str):
        dataset = next((d for d in store.datasets() if d["id"] == dataset_id), None)
        if dataset is None:
            raise ResearchError("That dataset was not found. Choose one from Data.")
        if (
            dataset["kind"] == "synthetic"
            or dataset.get("metadata", {}).get("provider") != "alpaca"
        ):
            raise ResearchError(
                "Choose a downloaded Alpaca dataset to update. Import a new CSV for other sources."
            )
        settings().headers()
        if "@" not in settings().sec_agent:
            raise ResearchError(
                "Configure SEC_USER_AGENT before updating a dataset with SEC fundamentals."
            )
        from .snapshots import latest

        source = latest(store, dataset_id)
        return store.enqueue("dataset_update", {"dataset_id": source["id"]})

    @app.post("/api/tasks/{kind}", status_code=202)
    def task(kind: Literal["backtest", "review"], payload: TaskRequest):
        strategy(payload.strategy_id)
        summary = next(
            (row for row in store.datasets() if row["id"] == payload.dataset_id), None
        )
        if summary is None:
            raise ResearchError("Choose an available dataset from Data first.")
        if summary.get("metadata", {}).get("bundle_role") == "prices":
            raise ResearchError(
                "This download's SEC stage is unfinished. In Data, use Complete SEC download before running research."
            )
        from .fundamentals import FUNDAMENTAL_STRATEGIES

        if payload.strategy_id in FUNDAMENTAL_STRATEGIES and not summary.get(
            "metadata", {}
        ).get("fundamentals", {}).get("record_count"):
            raise ResearchError(
                "Add SEC fundamentals to this market dataset in Data first. Price-only inputs cannot run this strategy."
            )
        if kind == "backtest":
            if (
                payload.start is None
                or payload.end is None
                or payload.start >= payload.end
            ):
                raise ResearchError(
                    "Choose a start and end date, with the end after the start."
                )
            if payload.start < date.fromisoformat(
                summary["start"]
            ) or payload.end > date.fromisoformat(summary["end"]):
                raise ResearchError(
                    f"Choose dates within dataset coverage: {summary['start']} to {summary['end']}."
                )
            if not 100 <= decimal(payload.capital) <= 1_000_000_000:
                raise ResearchError(
                    "Starting capital must be between $100 and $1 billion."
                )
        return store.enqueue(kind, payload.model_dump(mode="json"))

    @app.post("/api/paper/plans/{identifier}/retry-quote")
    def retry_paper_quote(identifier: str, payload: RebalanceApprovalRequest):
        from .paper import retry_quote

        if not payload.acknowledge:
            raise ResearchError(
                "Acknowledge the same frozen plan before retrying its quote check."
            )
        return retry_quote(store, identifier)

    if web_path and Path(web_path).is_dir():
        app.mount("/", StaticFiles(directory=web_path, html=True), name="web")
    return app
