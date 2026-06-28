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
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse

from ..config import (
    AVAILABLE_FORMATS,
    AVAILABLE_LANGUAGES,
    AVAILABLE_MODELS,
    Settings,
    save_overlay,
)
from ..paths import AUDIO_EXTENSIONS, output_path_for
from ..queue_store import QueueStore
from .schemas import (
    ConfigResponse,
    ControlRequest,
    ControlResponse,
    EnqueueRequest,
    EnqueueResponse,
    JobControlRequest,
    SettingsResponse,
    SettingsUpdate,
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


def _settings_dict(settings: Settings) -> dict:
    return {
        "model": settings.model,
        "language": settings.language,
        "formats": [f for f in settings.output_formats.split(",") if f] or ["txt"],
        "device": settings.device,
        "compute_type": settings.compute_type,
    }


@router.get("/api/settings", response_model=SettingsResponse)
def read_settings(settings: SettingsDep) -> dict:
    return _settings_dict(settings)


@router.put("/api/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate, settings: SettingsDep) -> dict:
    """Update the UI-editable default model/language/formats and persist them."""
    if body.model is not None:
        if body.model not in AVAILABLE_MODELS:
            raise HTTPException(status_code=400, detail="unknown model")
        settings.model = body.model
    if body.language is not None:
        if body.language not in AVAILABLE_LANGUAGES:
            raise HTTPException(status_code=400, detail="unknown language")
        settings.language = body.language
    if body.formats is not None:
        chosen = [f for f in body.formats if f in AVAILABLE_FORMATS]
        if not chosen:
            raise HTTPException(status_code=400, detail="no valid format")
        settings.output_formats = ",".join(chosen)
    save_overlay(settings)
    return _settings_dict(settings)


@router.get("/api/config", response_model=ConfigResponse)
def get_config(settings: SettingsDep) -> dict:
    return {
        "models": list(AVAILABLE_MODELS),
        "default_model": settings.model,
        "formats": list(AVAILABLE_FORMATS),
        "default_formats": [f for f in settings.output_formats.split(",") if f] or ["txt"],
        "languages": list(AVAILABLE_LANGUAGES),
        "default_language": settings.language,
    }


@router.get("/api/state", response_model=StateResponse)
def get_state(store: StoreDep) -> dict:
    return store.snapshot()


def _resolve_formats(requested: list[str], settings: Settings) -> str:
    chosen = [f for f in requested if f in AVAILABLE_FORMATS]
    return ",".join(chosen) if chosen else settings.output_formats


def _resolve_language(requested: str, settings: Settings) -> str:
    return requested if requested in AVAILABLE_LANGUAGES else settings.language


@router.post("/api/enqueue", response_model=EnqueueResponse)
def enqueue(body: EnqueueRequest, store: StoreDep, settings: SettingsDep) -> dict:
    model = body.model or settings.model
    formats = _resolve_formats(body.formats, settings)
    language = _resolve_language(body.language, settings)
    return store.enqueue(body.paths, model=model, formats=formats, language=language)


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
    language: Annotated[str, Form()] = "",
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
    resolved_language = _resolve_language(language, settings)
    result = store.enqueue(
        saved, model=resolved_model, formats=resolved_formats, language=resolved_language
    )
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
    elif body.action == "delete":
        ok = store.delete(body.id)
    else:
        ok = store.move(body.id, body.action)  # "up" / "down"
    return {"ok": ok, "state": store.snapshot()}


@router.get("/api/job/{job_id}/download")
def download_transcript(job_id: int, store: StoreDep, fmt: str = "txt") -> FileResponse:
    """Serve a job's transcript file in the requested format for download."""
    if fmt not in AVAILABLE_FORMATS:
        raise HTTPException(status_code=400, detail="unsupported format")
    job = store.find(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    out_file = output_path_for(job.path_obj, fmt)
    if not out_file.exists():
        raise HTTPException(status_code=404, detail="transcript not found")
    return FileResponse(out_file, filename=out_file.name, media_type="text/plain")


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
