from __future__ import annotations

import sqlite3
from pathlib import Path

from noctra.domain import JobStatus
from noctra.persistence import JobRepository
from noctra.queue_store import QueueStore


def _audio(tmp_path: Path, name: str) -> Path:
    f = tmp_path / name
    f.write_bytes(b"x")
    return f


def _reopen(db_path: Path) -> tuple[QueueStore, JobRepository]:
    repo = JobRepository(db_path)
    return QueueStore(repo), repo


def test_jobs_survive_restart(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    a = _audio(tmp_path, "a.m4a")
    b = _audio(tmp_path, "b.m4a")

    store, repo = _reopen(db)
    store.enqueue([str(a), str(b)])
    repo.close()

    # Fresh process: new store over the same DB file.
    store2, repo2 = _reopen(db)
    snap = store2.snapshot()
    assert len(snap["jobs"]) == 2
    assert {j["path"] for j in snap["jobs"]} == {str(a.resolve()), str(b.resolve())}
    repo2.close()


def test_done_status_persists(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    a = _audio(tmp_path, "a.m4a")

    store, repo = _reopen(db)
    store.enqueue([str(a)])
    store.start_queue()
    job = store.claim_next()
    assert job is not None
    store.complete(job.id)
    repo.close()

    store2, repo2 = _reopen(db)
    snap = store2.snapshot()
    assert snap["done"] == 1
    assert snap["jobs"][0]["status"] == "done"
    repo2.close()


def test_inflight_job_requeued_on_restart(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    a = _audio(tmp_path, "a.m4a")

    store, repo = _reopen(db)
    store.enqueue([str(a)])
    store.start_queue()
    job = store.claim_next()  # -> processing, persisted
    assert job is not None and job.status == JobStatus.PROCESSING
    repo.close()  # simulate crash while processing

    store2, repo2 = _reopen(db)
    snap = store2.snapshot()
    assert snap["processing"] == 0
    assert snap["pending"] == 1  # processing rolled back to pending
    assert snap["jobs"][0]["progress"] == 0.0
    repo2.close()


def test_next_ids_continue_after_restart(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    a = _audio(tmp_path, "a.m4a")
    b = _audio(tmp_path, "b.m4a")

    store, repo = _reopen(db)
    store.enqueue([str(a)])
    repo.close()

    store2, repo2 = _reopen(db)
    store2.enqueue([str(b)])
    ids = sorted(j["id"] for j in store2.snapshot()["jobs"])
    assert ids == [1, 2]  # no id collision across restarts
    repo2.close()


def test_model_persists(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    a = _audio(tmp_path, "a.m4a")

    store, repo = _reopen(db)
    store.enqueue([str(a)], model="small")
    repo.close()

    store2, repo2 = _reopen(db)
    assert store2.snapshot()["jobs"][0]["model"] == "small"
    repo2.close()


def test_migration_adds_model_column_to_old_db(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    # Simulate a pre-5.1 database: jobs table without the `model` column.
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY, path TEXT NOT NULL, queue_order INTEGER NOT NULL,
            status TEXT NOT NULL, text_path TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '', progress REAL NOT NULL DEFAULT 0,
            duration REAL NOT NULL DEFAULT 0, cancel_requested INTEGER NOT NULL DEFAULT 0,
            source_dir TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO jobs (id, path, queue_order, status) VALUES (1, '/x/a.m4a', 1, 'pending');
        """
    )
    conn.commit()
    conn.close()

    # Opening through the repository migrates the schema and loads the old row.
    repo = JobRepository(db)
    jobs = repo.load_all()
    assert len(jobs) == 1
    assert jobs[0].model == ""  # backfilled with the default
    repo.close()


def test_clear_all_wipes_db(tmp_path: Path) -> None:
    db = tmp_path / "queue.db"
    a = _audio(tmp_path, "a.m4a")

    store, repo = _reopen(db)
    store.enqueue([str(a)])
    store.clear_all()
    repo.close()

    store2, repo2 = _reopen(db)
    assert store2.snapshot()["jobs"] == []
    repo2.close()
