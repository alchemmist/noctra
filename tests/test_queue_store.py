from __future__ import annotations

import threading
from pathlib import Path

from noctra.domain import JobStatus
from noctra.queue_store import QueueStore


def _audio(tmp_path: Path, name: str) -> Path:
    f = tmp_path / name
    f.write_bytes(b"x")
    return f


def test_enqueue_dedups_and_reports(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    store = QueueStore()
    first = store.enqueue([str(a)])
    assert len(first["added"]) == 1
    assert first["missing"] == []

    second = store.enqueue([str(a), str(tmp_path / "missing.m4a")])
    assert second["added"] == []
    assert second["skipped"] == [str(a.resolve())]
    assert second["missing"] == [str(tmp_path / "missing.m4a")]


def test_snapshot_counts_and_order(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    b = _audio(tmp_path, "b.m4a")
    store = QueueStore()
    store.enqueue([str(a), str(b)])

    snap = store.snapshot()
    assert snap["pending"] == 2
    assert snap["done"] == 0
    assert [j["status"] for j in snap["jobs"]] == ["pending", "pending"]
    # queue_order ascending
    assert snap["jobs"][0]["queue_order"] <= snap["jobs"][1]["queue_order"]


def test_claim_next_requires_running(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    store = QueueStore()
    store.enqueue([str(a)])
    assert store.claim_next() is None  # not running yet

    store.start_queue()
    job = store.claim_next()
    assert job is not None
    assert job.status == JobStatus.PROCESSING
    # nothing else pending
    assert store.claim_next() is None


def test_claim_next_stops_queue_when_drained(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    store = QueueStore()
    store.enqueue([str(a)])
    store.start_queue()
    job = store.claim_next()
    assert job is not None
    store.complete(job.id)
    # queue should auto-stop once nothing active remains
    assert store.claim_next() is None
    assert store.is_running() is False


def test_complete_and_fail(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    b = _audio(tmp_path, "b.m4a")
    store = QueueStore()
    store.enqueue([str(a), str(b)])
    store.start_queue()
    j1 = store.claim_next()
    j2 = store.claim_next()
    assert j1 and j2
    store.complete(j1.id)
    store.fail(j2.id, "boom")
    snap = store.snapshot()
    assert snap["done"] == 1
    assert snap["failed"] == 1
    failed = next(j for j in snap["jobs"] if j["status"] == "failed")
    assert failed["error"] == "boom"


def test_cancel_pending(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    store = QueueStore()
    store.enqueue([str(a)])
    job = store.snapshot()["jobs"][0]
    assert store.request_cancel(job["id"]) is True
    assert store.should_cancel(job["id"]) is True
    assert store.request_cancel(job["id"]) is False  # already terminal
    assert store.snapshot()["canceled"] == 1


def test_retry_requeues_failed_and_resumes(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    store = QueueStore()
    store.enqueue([str(a)])
    store.start_queue()
    job = store.claim_next()
    assert job is not None
    store.fail(job.id, "boom")
    assert store.claim_next() is None  # nothing active -> queue auto-stops
    assert store.is_running() is False

    assert store.retry(job.id) is True
    snap = store.snapshot()
    assert snap["pending"] == 1
    assert snap["failed"] == 0
    assert snap["running"] is True  # retry resumes the queue
    assert snap["jobs"][0]["error"] == ""

    # retry only applies to failed/canceled jobs
    assert store.retry(job.id) is False  # now pending


def test_delete_removes_job_but_not_while_processing(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    b = _audio(tmp_path, "b.m4a")
    store = QueueStore()
    store.enqueue([str(a), str(b)])
    pending_id = store.snapshot()["jobs"][1]["id"]

    assert store.delete(pending_id) is True
    assert len(store.snapshot()["jobs"]) == 1
    assert store.delete(pending_id) is False  # already gone

    store.start_queue()
    processing = store.claim_next()
    assert processing is not None
    assert store.delete(processing.id) is False  # can't delete a running job


def test_clear_all_resets(tmp_path: Path) -> None:
    a = _audio(tmp_path, "a.m4a")
    store = QueueStore()
    store.enqueue([str(a)])
    store.clear_all()
    snap = store.snapshot()
    assert snap["jobs"] == []
    assert snap["running"] is False
    # ids restart after clear
    store.enqueue([str(a)])
    assert store.snapshot()["jobs"][0]["id"] == 1


def test_concurrent_enqueue_is_thread_safe(tmp_path: Path) -> None:
    files = []
    for i in range(50):
        f = _audio(tmp_path, f"f{i}.m4a")
        files.append(str(f))
    store = QueueStore()

    def worker(chunk: list[str]) -> None:
        store.enqueue(chunk)

    threads = [threading.Thread(target=worker, args=(files[i::5],)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snap = store.snapshot()
    assert len(snap["jobs"]) == 50
    ids = [j["id"] for j in snap["jobs"]]
    assert len(set(ids)) == 50  # no duplicate ids under contention
