"""Thread-safe in-memory job queue.

The store owns all mutable queue state behind a single lock/condition. The
public API never exposes ``_locked`` internals — callers (the worker, the HTTP
layer) go through ``find``, ``snapshot``, ``claim_next`` and friends.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from .domain import ACTIVE_STATUSES, Job, JobStatus
from .logging_setup import LOGGER
from .paths import expand_directory, output_path_for

_COUNTED_STATUSES = (
    JobStatus.PENDING,
    JobStatus.PROCESSING,
    JobStatus.DONE,
    JobStatus.FAILED,
    JobStatus.CANCELED,
)


class QueueStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.jobs: list[Job] = []
        self._next_job_id = 1
        self._next_order = 1
        self._queue_running = False
        self._clear_requested = False
        self._directory_cache: dict[str, tuple[int, list[tuple[Path, str]]]] = {}

    # -- public read-only helpers --------------------------------------

    def find(self, job_id: int) -> Job | None:
        """Return a copy-free reference to the job, or ``None`` if absent."""
        with self.condition:
            return self._find_locked(job_id)

    def is_running(self) -> bool:
        with self.condition:
            return self._queue_running

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            jobs = [job.to_dict() for job in self._sorted_jobs_locked()]
            counts = self._counts_locked()
            return {
                "next_id": self._next_order,
                "running": self._queue_running,
                "jobs": jobs,
                **counts,
            }

    # -- queue control --------------------------------------------------

    def start_queue(self) -> None:
        with self.condition:
            self._queue_running = True
            self._clear_requested = False
            LOGGER.info("Queue started")
            self.condition.notify_all()

    def stop_queue(self) -> None:
        with self.condition:
            self._queue_running = False
            LOGGER.info("Queue stopped")
            self.condition.notify_all()

    def clear_all(self) -> None:
        with self.condition:
            self._clear_requested = True
            self._queue_running = False
            self.jobs.clear()
            self._next_job_id = 1
            self._next_order = 1
            LOGGER.info("Queue cleared")
            self.condition.notify_all()

    # -- enqueue / claim / update --------------------------------------

    def enqueue(self, raw_paths: list[str]) -> dict[str, Any]:
        with self.condition:
            expanded, missing = self._expand_raw_paths_locked(raw_paths)
            added: list[dict[str, Any]] = []
            skipped: list[str] = []
            seen = {job.path for job in self.jobs}
            queue_order = self._next_order

            for path, source_dir in expanded:
                path_str = str(path)
                if path_str in seen:
                    skipped.append(path_str)
                    continue
                job = Job(
                    id=self._next_job_id_locked(),
                    path=path_str,
                    queue_order=queue_order,
                    status=JobStatus.PENDING,
                    text_path=str(output_path_for(path)),
                    source_dir=source_dir,
                )
                self.jobs.append(job)
                added.append(job.to_dict())
                seen.add(path_str)
                queue_order += 1

            self._next_order = queue_order
            self.condition.notify_all()

        return {"added": added, "skipped": skipped, "missing": missing}

    def claim_next(self) -> Job | None:
        with self.condition:
            if not self._queue_running or self._clear_requested:
                return None
            job = next(
                (
                    item
                    for item in self._sorted_jobs_locked()
                    if item.status == JobStatus.PENDING and not item.cancel_requested
                ),
                None,
            )
            if job is None:
                if not any(item.is_active for item in self.jobs):
                    self._queue_running = False
                return None
            job.status = JobStatus.PROCESSING
            job.error = ""
            job.progress = 0.0
            return job

    def update(self, job_id: int, **changes: Any) -> None:
        with self.condition:
            existing = self._find_locked(job_id)
            if existing is None:
                return
            for key, value in changes.items():
                setattr(existing, key, value)
            self.condition.notify_all()

    def complete(self, job_id: int, *, progress: float = 1.0) -> None:
        self.update(job_id, status=JobStatus.DONE, progress=progress, error="")

    def fail(self, job_id: int, error: str) -> None:
        self.update(job_id, status=JobStatus.FAILED, error=error)

    # -- cancellation ---------------------------------------------------

    def request_cancel(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            if job is None or job.status not in ACTIVE_STATUSES:
                return False
            job.cancel_requested = True
            job.status = JobStatus.CANCELED
            job.error = ""
            self.condition.notify_all()
            return True

    def should_cancel(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            return bool(self._clear_requested or (job is not None and job.cancel_requested))

    # -- locked internals ----------------------------------------------

    def _find_locked(self, job_id: int) -> Job | None:
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def _sorted_jobs_locked(self) -> list[Job]:
        return sorted(self.jobs, key=lambda job: (job.queue_order, job.id))

    def _counts_locked(self) -> dict[str, int]:
        counts = {str(status): 0 for status in _COUNTED_STATUSES}
        for job in self.jobs:
            key = str(job.status)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _next_job_id_locked(self) -> int:
        job_id = self._next_job_id
        self._next_job_id += 1
        return job_id

    def _expand_raw_paths_locked(
        self, raw_paths: list[str]
    ) -> tuple[list[tuple[Path, str]], list[str]]:
        expanded: list[tuple[Path, str]] = []
        missing: list[str] = []
        for raw in raw_paths:
            if not raw:
                continue
            path = Path(raw).expanduser()
            if path.is_dir():
                expanded.extend(self._expand_directory_cached_locked(path))
                continue
            if path.exists():
                resolved = path.resolve()
                expanded.append((resolved, str(resolved.parent)))
            else:
                missing.append(str(path))
        return expanded, missing

    def _expand_directory_cached_locked(self, directory: Path) -> list[tuple[Path, str]]:
        try:
            directory = directory.resolve()
            mtime_ns = directory.stat().st_mtime_ns
        except FileNotFoundError:
            return []
        cached = self._directory_cache.get(str(directory))
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

        files = [(audio, str(directory)) for audio in expand_directory(directory)]
        self._directory_cache[str(directory)] = (mtime_ns, files)
        return files
