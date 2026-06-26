"""Pydantic request/response schemas for the HTTP API.

These mirror the dicts produced by :class:`noctra.queue_store.QueueStore`, so
FastAPI validates and documents every payload without changing the wire format.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class JobSchema(BaseModel):
    id: int
    path: str
    queue_order: int
    status: str
    text_path: str
    error: str
    progress: float
    duration: float
    cancel_requested: bool
    source_dir: str
    model: str
    formats: str
    language: str


class StateResponse(BaseModel):
    next_id: int
    running: bool
    jobs: list[JobSchema]
    pending: int
    processing: int
    done: int
    failed: int
    canceled: int


class EnqueueRequest(BaseModel):
    paths: list[str]
    #: Whisper model to use; empty/omitted falls back to the server default.
    model: str = ""
    #: Output formats to write; empty/omitted falls back to the server default.
    formats: list[str] = []
    #: Transcription language code / "auto"; empty falls back to the default.
    language: str = ""


class ConfigResponse(BaseModel):
    models: list[str]
    default_model: str
    formats: list[str]
    default_formats: list[str]
    languages: list[str]
    default_language: str


class EnqueueResponse(BaseModel):
    added: list[JobSchema]
    skipped: list[str]
    missing: list[str]


class ControlRequest(BaseModel):
    action: Literal["start", "clear"]


class JobControlRequest(BaseModel):
    id: int
    action: Literal["cancel", "retry", "delete", "up", "down"]


class ControlResponse(BaseModel):
    ok: bool
    state: StateResponse
