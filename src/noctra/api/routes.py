"""HTTP and WebSocket routes.

Business logic stays in :class:`QueueStore`; these handlers only translate
between it and the wire. The store lives on ``app.state.store`` (set up in the
lifespan handler) and is injected via :func:`get_store`.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)

from ..config import AVAILABLE_FORMATS, AVAILABLE_MODELS, Settings
from ..paths import AUDIO_EXTENSIONS
from ..queue_store import QueueStore
from .schemas import (
    ConfigResponse,
    ControlRequest,
    ControlResponse,
    EnqueueRequest,
    EnqueueResponse,
    JobControlRequest,
    StateResponse,
)

#: How often the WebSocket loop re-checks the queue for changes.
WS_POLL_SECONDS = 0.4

router = APIRouter()


def get_store(request: Request) -> QueueStore:
    return request.app.state.store


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


StoreDep = Annotated[QueueStore, Depends(get_store)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/api/config", response_model=ConfigResponse)
def get_config(settings: SettingsDep) -> dict:
    return {
        "models": list(AVAILABLE_MODELS),
        "default_model": settings.model,
        "formats": list(AVAILABLE_FORMATS),
        "default_formats": [f for f in settings.output_formats.split(",") if f] or ["txt"],
    }


@router.get("/api/state", response_model=StateResponse)
def get_state(store: StoreDep) -> dict:
    return store.snapshot()


def _resolve_formats(requested: list[str], settings: Settings) -> str:
    chosen = [f for f in requested if f in AVAILABLE_FORMATS]
    return ",".join(chosen) if chosen else settings.output_formats


@router.post("/api/enqueue", response_model=EnqueueResponse)
def enqueue(body: EnqueueRequest, store: StoreDep, settings: SettingsDep) -> dict:
    model = body.model or settings.model
    formats = _resolve_formats(body.formats, settings)
    return store.enqueue(body.paths, model=model, formats=formats)


def _unique_path(directory: Path, filename: str) -> Path:
    """A collision-free destination inside ``directory`` for ``filename``."""
    base = Path(filename).name or "audio"
    candidate = directory / base
    stem, suffix = candidate.stem, candidate.suffix
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


@router.post("/api/upload", response_model=EnqueueResponse)
async def upload(
    store: StoreDep,
    settings: SettingsDep,
    files: list[UploadFile],
    model: Annotated[str, Form()] = "",
    formats: Annotated[str, Form()] = "",
) -> dict:
    """Save dropped/selected audio files, then enqueue them like any path."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    rejected: list[str] = []
    for upload_file in files:
        name = Path(upload_file.filename or "audio").name
        if Path(name).suffix.lower() not in AUDIO_EXTENSIONS:
            rejected.append(name)
            continue
        dest = _unique_path(upload_dir, name)
        with dest.open("wb") as out:
            shutil.copyfileobj(upload_file.file, out)
        saved.append(str(dest))

    resolved_model = model or settings.model
    resolved_formats = _resolve_formats([f for f in formats.split(",") if f], settings)
    result = store.enqueue(saved, model=resolved_model, formats=resolved_formats)
    result["missing"] = [*result["missing"], *rejected]
    return result


@router.post("/api/control", response_model=ControlResponse)
def control(body: ControlRequest, store: StoreDep) -> dict:
    if body.action == "start":
        store.start_queue()
    else:
        store.clear_all()
    return {"ok": True, "state": store.snapshot()}


@router.post("/api/job", response_model=ControlResponse)
def job_control(body: JobControlRequest, store: StoreDep) -> dict:
    if body.action == "cancel":
        ok = store.request_cancel(body.id)
    elif body.action == "retry":
        ok = store.retry(body.id)
    else:
        ok = store.delete(body.id)
    return {"ok": ok, "state": store.snapshot()}


@router.websocket("/ws")
async def state_ws(websocket: WebSocket) -> None:
    """Push a fresh state snapshot whenever it changes (replaces polling)."""
    store: QueueStore = websocket.app.state.store
    await websocket.accept()
    last: dict | None = None
    try:
        while True:
            snapshot = store.snapshot()
            if snapshot != last:
                await websocket.send_json(snapshot)
                last = snapshot
            await asyncio.sleep(WS_POLL_SECONDS)
    except WebSocketDisconnect:
        return
