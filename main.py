#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "faster-whisper",
#     "tqdm",
# ]
# ///

from __future__ import annotations

import argparse
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_MODEL = "large-v3"
DEFAULT_LANGUAGE = "ru"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
STATE_FILE = Path(".noctra_queue.sqlite3")
LEGACY_STATE_FILE = Path(".noctra_queue.json")
WEB_DIR = Path(__file__).with_name("web")

MIME_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".m4b",
    ".mka",
    ".mkv",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".webm",
    ".wma",
}


def normalize_paths(raw_paths: list[str]) -> tuple[list[Path], list[str]]:
    result: list[Path] = []
    missing: list[str] = []
    for raw in raw_paths:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in AUDIO_EXTENSIONS:
                    result.append(child.resolve())
            continue
        if path.exists():
            result.append(path.resolve())
        else:
            missing.append(str(path))
    return result, missing


def output_path_for(audio_path: Path) -> Path:
    return audio_path.with_suffix(".txt")


def load_web_asset(name: str) -> tuple[bytes, str]:
    path = WEB_DIR / name
    if not path.exists():
        raise FileNotFoundError(name)
    content_type = MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return path.read_bytes(), content_type


@dataclass
class Job:
    id: int
    path: str
    queue_order: int = 0
    status: str = "pending"
    text_path: str = ""
    error: str = ""
    progress: float = 0.0
    duration: float = 0.0
    cancel_requested: bool = False
    source_dir: str = ""

    @property
    def path_obj(self) -> Path:
        return Path(self.path)


class QueueStore:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.conn = sqlite3.connect(self.db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=DELETE")
        self.conn.execute("PRAGMA synchronous=FULL")
        self._init_schema()
        self._migrate_legacy_json()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    queue_order INTEGER NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    text_path TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    progress REAL NOT NULL DEFAULT 0.0,
                    duration REAL NOT NULL DEFAULT 0.0,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    source_dir TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scanned_dirs (
                    path TEXT PRIMARY KEY,
                    mtime_ns INTEGER NOT NULL,
                    scanned_at REAL NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dir_files (
                    dir_path TEXT NOT NULL,
                    file_path TEXT NOT NULL UNIQUE,
                    file_mtime_ns INTEGER NOT NULL,
                    PRIMARY KEY (dir_path, file_path)
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_status_order ON jobs(status, queue_order)"
            )

    def _migrate_legacy_json(self) -> None:
        if not LEGACY_STATE_FILE.exists():
            return
        with self.condition:
            count = self.conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
            if count:
                return
            try:
                data = json.loads(LEGACY_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                return

            raw_jobs = data.get("jobs", [])
            now = time.time()
            order = 1
            for raw in raw_jobs:
                status = raw.get("status", "pending")
                if status == "processing":
                    status = "pending"
                path = str(raw["path"])
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs (
                        path, queue_order, status, text_path, error, progress, duration,
                        cancel_requested, source_dir, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        path,
                        order,
                        status,
                        str(raw.get("text_path", "")),
                        str(raw.get("error", "")),
                        float(raw.get("progress", 0.0)),
                        float(raw.get("duration", 0.0)),
                        int(bool(raw.get("cancel_requested", False))),
                        str(Path(path).parent),
                        now,
                        now,
                    ),
                )
                order += 1
            self.conn.commit()

    def _now(self) -> float:
        return time.time()

    def _job_from_row(self, row: sqlite3.Row) -> Job:
        return Job(
            id=int(row["id"]),
            path=str(row["path"]),
            queue_order=int(row["queue_order"]),
            status=str(row["status"]),
            text_path=str(row["text_path"]),
            error=str(row["error"]),
            progress=float(row["progress"]),
            duration=float(row["duration"]),
            cancel_requested=bool(row["cancel_requested"]),
            source_dir=str(row["source_dir"]),
        )

    def _job_dicts_locked(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT id, path, queue_order, status, text_path, error, progress, duration,
                   cancel_requested, source_dir
            FROM jobs
            ORDER BY queue_order ASC, id ASC
            """
        ).fetchall()
        return [asdict(self._job_from_row(row)) for row in rows]

    def _counts_locked(self) -> dict[str, int]:
        counts = {
            "pending": 0,
            "paused": 0,
            "processing": 0,
            "done": 0,
            "failed": 0,
            "canceled": 0,
        }
        rows = self.conn.execute(
            "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
        ).fetchall()
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return counts

    def _next_order_locked(self) -> int:
        row = self.conn.execute("SELECT COALESCE(MAX(queue_order), 0) AS max_order FROM jobs").fetchone()
        return int(row["max_order"]) + 1

    def _expand_raw_paths_locked(self, raw_paths: list[str]) -> tuple[list[tuple[Path, str]], list[str]]:
        expanded: list[tuple[Path, str]] = []
        missing: list[str] = []
        for raw in raw_paths:
            if not raw:
                continue
            path = Path(raw).expanduser()
            if path.is_dir():
                expanded.extend(self._expand_directory_locked(path))
                continue
            if path.exists():
                resolved = path.resolve()
                expanded.append((resolved, str(resolved.parent)))
            else:
                missing.append(str(path))
        return expanded, missing

    def _expand_directory_locked(self, directory: Path) -> list[tuple[Path, str]]:
        try:
            directory = directory.resolve()
            mtime_ns = directory.stat().st_mtime_ns
        except FileNotFoundError:
            return []

        row = self.conn.execute(
            "SELECT mtime_ns FROM scanned_dirs WHERE path = ?",
            (str(directory),),
        ).fetchone()
        if row is not None and int(row["mtime_ns"]) == mtime_ns:
            cached = self.conn.execute(
                "SELECT file_path FROM dir_files WHERE dir_path = ? ORDER BY file_path ASC",
                (str(directory),),
            ).fetchall()
            if cached:
                return [(Path(item["file_path"]), str(directory)) for item in cached]

        files: list[tuple[Path, str]] = []
        for child in sorted(directory.rglob("*")):
            if child.is_file() and child.suffix.lower() in AUDIO_EXTENSIONS:
                files.append((child.resolve(), str(directory)))

        now = self._now()
        self.conn.execute(
            """
            INSERT INTO scanned_dirs(path, mtime_ns, scanned_at)
            VALUES(?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                mtime_ns = excluded.mtime_ns,
                scanned_at = excluded.scanned_at
            """,
            (str(directory), mtime_ns, now),
        )
        self.conn.execute("DELETE FROM dir_files WHERE dir_path = ?", (str(directory),))
        for file_path, _source_dir in files:
            try:
                file_mtime_ns = file_path.stat().st_mtime_ns
            except FileNotFoundError:
                file_mtime_ns = mtime_ns
            self.conn.execute(
                """
                INSERT OR REPLACE INTO dir_files(dir_path, file_path, file_mtime_ns)
                VALUES (?, ?, ?)
                """,
                (str(directory), str(file_path), file_mtime_ns),
            )
        return files

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            jobs = self._job_dicts_locked()
            counts = self._counts_locked()
            return {
                "next_id": self._next_order_locked(),
                "jobs": jobs,
                **counts,
            }

    def enqueue(self, raw_paths: list[str]) -> dict[str, Any]:
        with self.condition:
            expanded, missing = self._expand_raw_paths_locked(raw_paths)
            added: list[dict[str, Any]] = []
            skipped: list[str] = []
            known_paths = {
                str(row["path"])
                for row in self.conn.execute("SELECT path FROM jobs").fetchall()
            }
            seen = set(known_paths)
            queue_order = self._next_order_locked()
            now = self._now()

            for path, source_dir in expanded:
                path_str = str(path)
                if path_str in seen:
                    skipped.append(path_str)
                    continue
                self.conn.execute(
                    """
                    INSERT INTO jobs (
                        path, queue_order, status, text_path, error, progress, duration,
                        cancel_requested, source_dir, created_at, updated_at
                    )
                    VALUES (?, ?, 'pending', ?, '', 0.0, 0.0, 0, ?, ?, ?)
                    """,
                    (
                        path_str,
                        queue_order,
                        str(output_path_for(path)),
                        source_dir,
                        now,
                        now,
                    ),
                )
                job_row = self.conn.execute(
                    """
                    SELECT id, path, queue_order, status, text_path, error, progress, duration,
                           cancel_requested, source_dir
                    FROM jobs
                    WHERE path = ?
                    """,
                    (path_str,),
                ).fetchone()
                if job_row is not None:
                    added.append(asdict(self._job_from_row(job_row)))
                seen.add(path_str)
                queue_order += 1

            self.conn.commit()
            self.condition.notify_all()

        return {"added": added, "skipped": skipped, "missing": missing}

    def claim_next(self) -> Job | None:
        with self.condition:
            row = self.conn.execute(
                """
                SELECT id, path, queue_order, status, text_path, error, progress, duration,
                       cancel_requested, source_dir
                FROM jobs
                WHERE status = 'pending' AND cancel_requested = 0
                ORDER BY queue_order ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                return None
            now = self._now()
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'processing', error = '', progress = 0.0, updated_at = ?
                WHERE id = ?
                """,
                (now, int(row["id"])),
            )
            self.conn.commit()
            job = self._job_from_row(row)
            job.status = "processing"
            job.error = ""
            job.progress = 0.0
            return job

    def update(self, job_id: int, **changes: Any) -> None:
        with self.condition:
            existing = self._find_locked(job_id)
            if existing is None:
                return
            assignments: list[str] = []
            values: list[Any] = []
            for key, value in changes.items():
                assignments.append(f"{key} = ?")
                values.append(value)
            assignments.append("updated_at = ?")
            values.append(self._now())
            values.append(job_id)
            self.conn.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            self.conn.commit()

    def complete(self, job_id: int, *, progress: float = 1.0) -> None:
        self.update(job_id, status="done", progress=progress, error="")

    def fail(self, job_id: int, error: str) -> None:
        self.update(job_id, status="failed", error=error)

    def remove(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            if job is None:
                return False
            if job.status == "processing":
                self.conn.execute(
                    """
                    UPDATE jobs
                    SET cancel_requested = 1, status = 'canceled', error = '', updated_at = ?
                    WHERE id = ?
                    """,
                    (self._now(), job_id),
                )
            else:
                self.conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self.conn.commit()
            self.condition.notify_all()
            return True

    def request_cancel(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            if job is None or job.status not in {"pending", "processing"}:
                return False
            self.conn.execute(
                """
                UPDATE jobs
                SET cancel_requested = 1, status = 'paused', error = '', updated_at = ?
                WHERE id = ?
                """,
                (self._now(), job_id),
            )
            self.conn.commit()
            self.condition.notify_all()
            return True

    def request_resume(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            if job is None or job.status != "paused":
                return False
            self.conn.execute(
                """
                UPDATE jobs
                SET cancel_requested = 0, status = 'pending', error = '', progress = 0.0,
                    updated_at = ?
                WHERE id = ?
                """,
                (self._now(), job_id),
            )
            self.conn.commit()
            self.condition.notify_all()
            return True

    def move(self, job_id: int, direction: str) -> bool:
        with self.condition:
            jobs = self._ordered_jobs_locked()
            index = next((i for i, job in enumerate(jobs) if job.id == job_id), None)
            if index is None:
                return False
            job = jobs[index]
            if job.status == "processing":
                return True
            if job.status not in {"pending", "paused", "canceled", "failed", "done"}:
                return True

            if direction == "up":
                target = index - 1
                while target >= 0 and jobs[target].status == "processing":
                    target -= 1
            elif direction == "down":
                target = index + 1
                while target < len(jobs) and jobs[target].status == "processing":
                    target += 1
            else:
                return False

            if target < 0 or target >= len(jobs) or target == index:
                return True

            target_job = jobs[target]
            temp_order = -1
            now = self._now()
            self.conn.execute(
                "UPDATE jobs SET queue_order = ?, updated_at = ? WHERE id = ?",
                (temp_order, now, target_job.id),
            )
            self.conn.execute(
                "UPDATE jobs SET queue_order = ?, updated_at = ? WHERE id = ?",
                (target_job.queue_order, now, job.id),
            )
            self.conn.execute(
                "UPDATE jobs SET queue_order = ?, updated_at = ? WHERE id = ?",
                (job.queue_order, now, target_job.id),
            )
            self.conn.commit()
            self.condition.notify_all()
            return True

    def _ordered_jobs_locked(self) -> list[Job]:
        rows = self.conn.execute(
            """
            SELECT id, path, queue_order, status, text_path, error, progress, duration,
                   cancel_requested, source_dir
            FROM jobs
            ORDER BY queue_order ASC, id ASC
            """
        ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def _find_locked(self, job_id: int) -> Job | None:
        row = self.conn.execute(
            """
            SELECT id, path, queue_order, status, text_path, error, progress, duration,
                   cancel_requested, source_dir
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return self._job_from_row(row)


class TranscriptionEngine:
    def __init__(self, model_name: str, device: str, compute_type: str, language: str):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model: Any | None = None
        self._lock = threading.Lock()

    def model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from faster_whisper import WhisperModel
                    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency guard
                        raise RuntimeError(
                            "faster-whisper is not installed. Install dependencies before transcribing."
                        ) from exc
                    print(f"Loading model {self.model_name} on {self.device} ({self.compute_type})")
                    self._model = WhisperModel(
                        self.model_name,
                        device=self.device,
                        compute_type=self.compute_type,
                    )
        return self._model

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        on_progress: Any | None = None,
        should_cancel: Any | None = None,
    ) -> tuple[Path, float]:
        model = self.model()
        out_file = output_path_for(audio_path)
        temp_file = out_file.with_suffix(out_file.suffix + ".part")
        segments, info = model.transcribe(
            str(audio_path),
            language=self.language,
            vad_filter=True,
        )

        try:
            from tqdm import tqdm
        except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
            tqdm = None

        progress = tqdm(total=info.duration, unit="sec", desc=audio_path.name) if tqdm else None
        last_end = 0.0
        last_reported = 0.0

        try:
            with temp_file.open("w", encoding="utf-8") as handle:
                for segment in segments:
                    if should_cancel is not None and should_cancel():
                        raise RuntimeError("canceled")
                    current_end = max(last_end, float(segment.end))
                    if progress is not None:
                        progress.update(max(0.0, current_end - last_end))
                    last_end = current_end

                    if info.duration > 0:
                        current_progress = min(1.0, current_end / info.duration)
                        if on_progress is not None and current_progress - last_reported >= 0.01:
                            on_progress(current_progress)
                            last_reported = current_progress

                    text = segment.text.strip()
                    if text:
                        handle.write(text + "\n")

            temp_file.replace(out_file)
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            raise
        finally:
            if progress is not None:
                progress.close()

        if on_progress is not None:
            on_progress(1.0)
        return out_file, float(info.duration)


class Worker(threading.Thread):
    def __init__(self, store: QueueStore, engine: TranscriptionEngine):
        super().__init__(daemon=True)
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
                self.store.update(job_id, status="paused")
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

            audio_path = job.path_obj
            with self._current_lock:
                self._current_job_id = job.id
            try:
                print(f"Transcribing: {audio_path}")
                out_file, duration = self.engine.transcribe_file(
                    audio_path,
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
                print(f"Done: {out_file}")
            except Exception as exc:
                if str(exc) == "canceled":
                    current = self.store._find_locked(job.id)
                    current_status = current.status if current is not None else "canceled"
                    current_progress = current.progress if current is not None else job.progress
                    if current_status == "paused":
                        self.store.update(job.id, status="paused", error="", progress=current_progress)
                        print(f"Paused: {audio_path}")
                    else:
                        self.store.update(job.id, status="canceled", error="", progress=current_progress)
                        print(f"Canceled: {audio_path}")
                else:
                    self.store.fail(job.id, str(exc))
                    print(f"Failed: {audio_path} -> {exc}")
            finally:
                with self._current_lock:
                    self._current_job_id = None

    def _is_canceled(self, job_id: int) -> bool:
        with self.store.condition:
            job = self.store._find_locked(job_id)
            return bool(job and job.cancel_requested)


class AppHandler(BaseHTTPRequestHandler):
    store: QueueStore

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_asset("index.html")
            return
        if parsed.path == "/app.js":
            self._serve_asset("app.js")
            return
        if parsed.path == "/styles.css":
            self._serve_asset("styles.css")
            return
        if parsed.path == "/api/state":
            self._send_json(self.store.snapshot())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/enqueue":
            payload = self._read_json()
            paths = payload.get("paths", [])
            if not isinstance(paths, list):
                self._send_json({"error": "paths must be a list"}, HTTPStatus.BAD_REQUEST)
                return
            result = self.store.enqueue([str(p) for p in paths])
            self._send_json(result)
            return
        if parsed.path == "/api/job":
            payload = self._read_json()
            job_id = payload.get("id")
            action = payload.get("action")
            if not isinstance(job_id, int) or not isinstance(action, str):
                self._send_json({"error": "invalid payload"}, HTTPStatus.BAD_REQUEST)
                return
            if action == "delete":
                ok = self.store.remove(job_id)
            elif action == "cancel":
                ok = self.store.request_cancel(job_id)
            elif action == "resume":
                ok = self.store.request_resume(job_id)
            elif action in {"move_up", "move_down"}:
                ok = self.store.move(job_id, "up" if action == "move_up" else "down")
            else:
                self._send_json({"error": "unknown action"}, HTTPStatus.BAD_REQUEST)
                return
            if not ok:
                self._send_json({"error": "action not allowed"}, HTTPStatus.CONFLICT)
                return
            self._send_json({"ok": True, "state": self.store.snapshot()})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _serve_asset(self, name: str) -> None:
        try:
            data, content_type = load_web_asset(name)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def run_headless(files: list[str], args: argparse.Namespace) -> int:
    store = QueueStore(STATE_FILE)
    result = store.enqueue(files)
    if result["added"]:
        print(f"Queued: {len(result['added'])}")
    if result["skipped"]:
        print(f"Skipped duplicates: {len(result['skipped'])}")
    if result["missing"]:
        print(f"Missing paths: {len(result['missing'])}")

    engine = TranscriptionEngine(args.model, args.device, args.compute_type, args.language)
    worker = Worker(store, engine)
    worker.start()

    try:
        while True:
            state = store.snapshot()
            pending = state["pending"] + state["paused"] + state["processing"] > 0
            if not pending:
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        worker.stop(graceful=True)
        worker.join(timeout=2.0)
        return 130

    worker.stop(graceful=True)
    worker.join(timeout=2.0)
    return 0


def run_server(files: list[str], args: argparse.Namespace) -> int:
    store = QueueStore(STATE_FILE)
    if files:
        result = store.enqueue(files)
        if result["added"]:
            print(f"Queued at startup: {len(result['added'])}")

    engine = TranscriptionEngine(args.model, args.device, args.compute_type, args.language)
    worker = Worker(store, engine)
    worker.start()

    handler = type("ConfiguredHandler", (AppHandler,), {"store": store})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Open http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop(graceful=True)
        server.shutdown()
        server.server_close()
        worker.join(timeout=2.0)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sequential audio transcription queue with local web UI.")
    parser.add_argument("files", nargs="*", help="Audio files or directories to enqueue.")
    parser.add_argument("--serve", action="store_true", help="Run local web UI and background worker.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host for web UI, default: {DEFAULT_HOST}")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port for web UI, default: {DEFAULT_PORT}")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Whisper model name, default: {DEFAULT_MODEL}")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help=f"Language code, default: {DEFAULT_LANGUAGE}")
    parser.add_argument("--device", default=DEFAULT_DEVICE, help=f"Model device, default: {DEFAULT_DEVICE}")
    parser.add_argument(
        "--compute-type",
        default=DEFAULT_COMPUTE_TYPE,
        dest="compute_type",
        help=f"Whisper compute type, default: {DEFAULT_COMPUTE_TYPE}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    files = args.files
    if args.serve or not files:
        return run_server(files, args)
    return run_headless(files, args)


if __name__ == "__main__":
    raise SystemExit(main())
