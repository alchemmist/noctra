"""Background worker thread that drains the queue one job at a time."""

from __future__ import annotations

import threading

from .domain import Job, JobCanceledError, JobStatus
from .engine import TranscriptionEngine
from .logging_setup import LOGGER
from .queue_store import QueueStore


class Worker(threading.Thread):
    def __init__(self, store: QueueStore, engine: TranscriptionEngine) -> None:
        super().__init__(daemon=True, name="noctra-worker")
        self.store = store
        self.engine = engine
        self._stop_event = threading.Event()
        self._current_job_id: int | None = None
        self._current_lock = threading.Lock()

    def stop(self, *, graceful: bool = False) -> None:
        if graceful:
            with self._current_lock:
                job_id = self._current_job_id
            if job_id is not None:
                self.store.request_cancel(job_id)
            self.store.stop_queue()
        self._stop_event.set()
        with self.store.condition:
            self.store.condition.notify_all()

    def run(self) -> None:
        while not self._stop_event.is_set():
            job = self.store.claim_next()
            if job is None:
                with self.store.condition:
                    self.store.condition.wait(timeout=1.0)
                continue

            with self._current_lock:
                self._current_job_id = job.id
            try:
                self._process(job)
            finally:
                with self._current_lock:
                    self._current_job_id = None

    def _process(self, job: Job) -> None:
        audio_path = job.path_obj
        formats = tuple(f for f in job.formats.split(",") if f) or ("txt",)
        try:
            LOGGER.info("Transcribing: %s", audio_path)
            out_file, duration = self.engine.transcribe_file(
                audio_path,
                model_name=job.model or None,
                formats=formats,
                language=job.language or None,
                on_progress=lambda value: self.store.update(job.id, progress=value),
                should_cancel=lambda: self._stop_event.is_set() or self._is_canceled(job.id),
            )
            self.store.update(
                job.id,
                text_path=str(out_file),
                duration=duration,
                progress=1.0,
            )
            self.store.complete(job.id)
            LOGGER.info("Done: %s", out_file)
        except JobCanceledError:
            current = self.store.find(job.id)
            current_progress = current.progress if current is not None else job.progress
            self.store.update(
                job.id, status=JobStatus.CANCELED, error="", progress=current_progress
            )
            LOGGER.info("Canceled: %s", audio_path)
        except Exception as exc:
            self.store.fail(job.id, str(exc))
            LOGGER.exception("Failed: %s", audio_path)

    def _is_canceled(self, job_id: int) -> bool:
        return self.store.should_cancel(job_id)
