"""SQLite persistence for the job queue.

A thin repository over stdlib :mod:`sqlite3` (no ORM). All access happens while
the :class:`~noctra.queue_store.QueueStore` lock is held, so the connection is
shared across threads (``check_same_thread=False``) without extra locking.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .domain import Job, JobStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY,
    path             TEXT    NOT NULL,
    queue_order      INTEGER NOT NULL,
    status           TEXT    NOT NULL,
    text_path        TEXT    NOT NULL DEFAULT '',
    error            TEXT    NOT NULL DEFAULT '',
    progress         REAL    NOT NULL DEFAULT 0,
    duration         REAL    NOT NULL DEFAULT 0,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    source_dir       TEXT    NOT NULL DEFAULT ''
);
"""

_COLUMNS = (
    "id, path, queue_order, status, text_path, error, "
    "progress, duration, cancel_requested, source_dir"
)

_UPSERT = f"""
INSERT INTO jobs ({_COLUMNS})
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    path=excluded.path,
    queue_order=excluded.queue_order,
    status=excluded.status,
    text_path=excluded.text_path,
    error=excluded.error,
    progress=excluded.progress,
    duration=excluded.duration,
    cancel_requested=excluded.cancel_requested,
    source_dir=excluded.source_dir
"""


def _row_to_job(row: tuple) -> Job:
    return Job(
        id=row[0],
        path=row[1],
        queue_order=row[2],
        status=JobStatus(row[3]),
        text_path=row[4],
        error=row[5],
        progress=row[6],
        duration=row[7],
        cancel_requested=bool(row[8]),
        source_dir=row[9],
    )


def _job_to_row(job: Job) -> tuple:
    return (
        job.id,
        job.path,
        job.queue_order,
        str(job.status),
        job.text_path,
        job.error,
        job.progress,
        job.duration,
        int(job.cancel_requested),
        job.source_dir,
    )


class JobRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def load_all(self) -> list[Job]:
        rows = self._conn.execute(
            f"SELECT {_COLUMNS} FROM jobs ORDER BY queue_order, id"
        ).fetchall()
        return [_row_to_job(row) for row in rows]

    def upsert(self, job: Job) -> None:
        self._conn.execute(_UPSERT, _job_to_row(job))
        self._conn.commit()

    def upsert_many(self, jobs: Iterable[Job]) -> None:
        rows = [_job_to_row(job) for job in jobs]
        if not rows:
            return
        self._conn.executemany(_UPSERT, rows)
        self._conn.commit()

    def delete_all(self) -> None:
        self._conn.execute("DELETE FROM jobs")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
