"""Local API: bounded inputs, persisted jobs, and no broker capabilities."""

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
from .providers import DEFAULT_SYMBOLS, validate_symbols


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


class DownloadRequest(BaseModel):
    name: str = Field(default="US stock watchlist", min_length=1, max_length=100)
    symbols: list[str] = Field(min_length=1, max_length=100)
    start: date
    end: date


class ProtocolRequest(TaskRequest):
    name: str = Field(min_length=1, max_length=100)
    hypothesis: str = Field(min_length=10, max_length=2000)
    start: date
    end: date
    holdout_start: date


class EvaluationRequest(BaseModel):
    phase: Literal["development", "holdout"]
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
        return {
            "version": __version__,
            "datasets": store.datasets(),
            "strategies": STRATEGIES,
            "jobs": store.jobs(),
            "runs": store.results("backtest"),
            "reviews": store.results("review"),
            "account": {
                "connected": False,
                "planning_capital": "100000",
                "mode": "research",
            },
        }

    @app.get("/api/results/{identifier}")
    def result(identifier: str):
        return store.result(identifier)

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
    def research_trial(identifier: str):
        from .experiments import trial

        return trial(store, identifier)

    @app.post("/api/research/protocols/{identifier}/retire")
    def retire_protocol(identifier: str):
        from .experiments import retire

        return retire(store, identifier)

    @app.get("/api/providers")
    def providers():
        from .calendar import latest_complete

        cfg = settings()
        return {
            "alpaca_configured": cfg.configured,
            "sec_configured": "@" in cfg.sec_agent,
            "latest_session": str(latest_complete()),
            "first_session": "2016-01-04",
            "watchlist": store.preference(
                "watchlist",
                {
                    "name": "US stock watchlist",
                    "symbols": DEFAULT_SYMBOLS,
                    "start": "2022-01-03",
                },
            ),
        }

    @app.post("/api/providers/check", status_code=202)
    def check_provider():
        settings().headers()
        return store.enqueue("connection", {})

    @app.post("/api/downloads", status_code=202)
    def queue_download(payload: DownloadRequest):
        settings().headers()
        data = payload.model_dump(mode="json")
        data["symbols"] = validate_symbols(data["symbols"])
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
            {"name": data["name"], "symbols": data["symbols"], "start": data["start"]},
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

    @app.post("/api/tasks/{kind}", status_code=202)
    def task(kind: Literal["backtest", "review"], payload: TaskRequest):
        strategy(payload.strategy_id)
        summary = next(
            (row for row in store.datasets() if row["id"] == payload.dataset_id), None
        )
        if summary is None:
            raise ResearchError("Choose an available dataset from Data first.")
        from .fundamentals import FUNDAMENTAL_STRATEGIES

        if payload.strategy_id in FUNDAMENTAL_STRATEGIES and not summary.get(
            "metadata", {}
        ).get("fundamentals"):
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

    if web_path and Path(web_path).is_dir():
        app.mount("/", StaticFiles(directory=web_path, html=True), name="web")
    return app
