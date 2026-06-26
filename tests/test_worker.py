from __future__ import annotations

import time
from pathlib import Path

from noctra.domain import JobCanceledError, JobStatus
from noctra.engine import TranscriptionEngine
from noctra.paths import output_path_for
from noctra.queue_store import QueueStore
from noctra.worker import Worker


class FakeEngine(TranscriptionEngine):
    def __init__(self, behavior: str) -> None:
        super().__init__("fake", "cpu", "int8", "ru")
        self.behavior = behavior

    def transcribe_file(  # type: ignore[override]
        self,
        audio_path,
        *,
        model_name=None,
        formats=("txt",),
        language=None,
        on_progress=None,
        should_cancel=None,
    ):
        if self.behavior == "cancel":
            raise JobCanceledError(audio_path.name)
        if self.behavior == "fail":
            raise RuntimeError("kaboom")
        out = output_path_for(audio_path)
        out.write_text("done\n", encoding="utf-8")
        if on_progress:
            on_progress(1.0)
        return out, 42.0


def _claimed_job(tmp_path: Path, store: QueueStore):
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")
    store.enqueue([str(audio)])
    store.start_queue()
    job = store.claim_next()
    assert job is not None
    return job


def test_worker_processes_to_done(tmp_path: Path) -> None:
    store = QueueStore()
    job = _claimed_job(tmp_path, store)
    worker = Worker(store, FakeEngine("ok"))

    worker._process(job)

    updated = store.find(job.id)
    assert updated is not None
    assert updated.status == JobStatus.DONE
    assert updated.duration == 42.0
    assert updated.progress == 1.0
    assert Path(updated.text_path).read_text(encoding="utf-8") == "done\n"


def test_worker_marks_canceled(tmp_path: Path) -> None:
    store = QueueStore()
    job = _claimed_job(tmp_path, store)
    worker = Worker(store, FakeEngine("cancel"))

    worker._process(job)

    updated = store.find(job.id)
    assert updated is not None
    assert updated.status == JobStatus.CANCELED
    assert updated.error == ""


def test_worker_marks_failed(tmp_path: Path) -> None:
    store = QueueStore()
    job = _claimed_job(tmp_path, store)
    worker = Worker(store, FakeEngine("fail"))

    worker._process(job)

    updated = store.find(job.id)
    assert updated is not None
    assert updated.status == JobStatus.FAILED
    assert "kaboom" in updated.error


def test_worker_run_loop_drains_queue(tmp_path: Path) -> None:
    store = QueueStore()
    for i in range(3):
        audio = tmp_path / f"clip{i}.m4a"
        audio.write_bytes(b"x")
        store.enqueue([str(audio)])
    store.start_queue()

    worker = Worker(store, FakeEngine("ok"))
    worker.start()
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if store.snapshot()["done"] == 3:
                break
            time.sleep(0.02)
    finally:
        worker.stop(graceful=True)
        worker.join(timeout=2.0)

    snap = store.snapshot()
    assert snap["done"] == 3
    assert snap["running"] is False
    assert not worker.is_alive()
