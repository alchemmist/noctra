"""HTTP and WebSocket routes.

Business logic stays in :class:`QueueStore`; these handlers only translate
between it and the wire. The store lives on ``app.state.store`` (set up in the
lifespan handler) and is injected via :func:`get_store`.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

from ..config import AVAILABLE_MODELS, Settings
from ..queue_store import QueueStore
from .schemas import (
    ConfigResponse,
    ControlRequest,
    ControlResponse,
    EnqueueRequest,
    EnqueueResponse,
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
    return {"models": list(AVAILABLE_MODELS), "default_model": settings.model}


@router.get("/api/state", response_model=StateResponse)
def get_state(store: StoreDep) -> dict:
    return store.snapshot()


@router.post("/api/enqueue", response_model=EnqueueResponse)
def enqueue(body: EnqueueRequest, store: StoreDep, settings: SettingsDep) -> dict:
    model = body.model or settings.model
    return store.enqueue(body.paths, model=model)


@router.post("/api/control", response_model=ControlResponse)
def control(body: ControlRequest, store: StoreDep) -> dict:
    if body.action == "start":
        store.start_queue()
    else:
        store.clear_all()
    return {"ok": True, "state": store.snapshot()}


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
