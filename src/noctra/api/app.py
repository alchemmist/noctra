"""FastAPI application factory and lifecycle wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .. import __version__
from ..config import Settings
from ..engine import TranscriptionEngine
from ..logging_setup import LOGGER
from ..persistence import JobRepository
from ..queue_store import QueueStore
from ..worker import Worker
from .routes import router

#: Built SPA / static assets directory, served at the application root.
WEB_DIR = Path(__file__).resolve().parents[3] / "web"
WEB_DIST = WEB_DIR / "dist"

#: Hard cap on request bodies to avoid unbounded memory use on POST.
MAX_BODY_BYTES = 8 * 1024 * 1024


class BodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # File uploads are legitimately large; the cap only guards JSON endpoints.
        if request.url.path != "/api/upload":
            content_length = request.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > self.max_bytes:
                return JSONResponse({"error": "request too large"}, status_code=413)
        return await call_next(request)


def _static_dir() -> Path | None:
    """Prefer a built SPA (``web/dist``), fall back to raw assets (``web/``)."""
    if WEB_DIST.exists():
        return WEB_DIST
    if WEB_DIR.exists():
        return WEB_DIR
    return None


def create_app(settings: Settings, files: list[str] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repo = JobRepository(Path(settings.db_path))
        store = QueueStore(repo)
        store.stop_queue()
        if files:
            result = store.enqueue(files)
            if result["added"]:
                LOGGER.info("Queued at startup: %d", len(result["added"]))

        engine = TranscriptionEngine(
            settings.model, settings.device, settings.compute_type, settings.language
        )
        worker = Worker(store, engine)
        worker.start()
        app.state.store = store
        app.state.worker = worker
        app.state.settings = settings
        try:
            yield
        finally:
            worker.stop(graceful=True)
            worker.join(timeout=2.0)
            repo.close()

    app = FastAPI(title="Noctra", version=__version__, lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware)
    app.include_router(router)

    static_dir = _static_dir()
    if static_dir is not None:
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")

    return app
