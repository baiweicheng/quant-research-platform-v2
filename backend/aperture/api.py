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

    @app.post("/api/tasks/{kind}", status_code=202)
    def task(kind: Literal["backtest", "review"], payload: TaskRequest):
        strategy(payload.strategy_id)
        summary = next(
            (row for row in store.datasets() if row["id"] == payload.dataset_id), None
        )
        if summary is None:
            raise ResearchError("Choose an available dataset from Data first.")
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
