"""Core domain types: job model, statuses, and the cancellation signal.

This module is framework-agnostic on purpose — it has no HTTP, no faster-whisper
and no threading. Everything here is trivially unit-testable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class JobStatus(StrEnum):
    """Lifecycle states of a transcription job.

    Being a :class:`StrEnum`, each member compares and serializes as its string
    value (``"pending"`` etc.), which keeps the JSON API backward compatible
    while giving us type safety and protection against typos.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


#: Statuses that still occupy a slot in the queue (not yet terminal).
ACTIVE_STATUSES = frozenset({JobStatus.PENDING, JobStatus.PROCESSING})


class JobCanceledError(Exception):
    """Raised inside transcription to signal a cooperative cancellation.

    Replaces the previous ``str(exc) == "canceled"`` sentinel-string check,
    which was fragile and easy to break.
    """


@dataclass
class Job:
    id: int
    path: str
    queue_order: int = 0
    status: JobStatus = JobStatus.PENDING
    text_path: str = ""
    error: str = ""
    progress: float = 0.0
    duration: float = 0.0
    cancel_requested: bool = False
    source_dir: str = ""

    @property
    def path_obj(self) -> Path:
        return Path(self.path)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation with ``status`` as a plain string."""
        data = asdict(self)
        data["status"] = str(self.status)
        return data
