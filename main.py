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
    def __init__(self):
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.jobs: list[Job] = []
        self._next_job_id = 1
        self._next_order = 1
        self._queue_running = False
        self._clear_requested = False
        self._directory_cache: dict[str, tuple[int, list[tuple[Path, str]]]] = {}

    def _now(self) -> float:
        return time.time()

    def _queue_running_locked(self) -> bool:
        return self._queue_running

    def start_queue(self) -> None:
        with self.condition:
            self._queue_running = True
            self._clear_requested = False
            self.condition.notify_all()

    def stop_queue(self) -> None:
        with self.condition:
            self._queue_running = False
            self.condition.notify_all()

    def _job_dicts_locked(self) -> list[dict[str, Any]]:
        jobs = sorted(self.jobs, key=lambda job: (job.queue_order, job.id))
        return [asdict(job) for job in jobs]

    def _counts_locked(self) -> dict[str, int]:
        counts = {
            "pending": 0,
            "processing": 0,
            "done": 0,
            "failed": 0,
            "canceled": 0,
        }
        for job in self.jobs:
            counts[job.status] = counts.get(job.status, 0) + 1
        return counts

    def _next_order_locked(self) -> int:
        return self._next_order

    def _next_job_id_locked(self) -> int:
        job_id = self._next_job_id
        self._next_job_id += 1
        return job_id

    def _find_locked(self, job_id: int) -> Job | None:
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

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
        cached = self._directory_cache.get(str(directory))
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

        files: list[tuple[Path, str]] = []
        for child in sorted(directory.rglob("*")):
            if child.is_file() and child.suffix.lower() in AUDIO_EXTENSIONS:
                files.append((child.resolve(), str(directory)))
        self._directory_cache[str(directory)] = (mtime_ns, files)
        return files

    def snapshot(self) -> dict[str, Any]:
        with self.condition:
            jobs = self._job_dicts_locked()
            counts = self._counts_locked()
            return {
                "next_id": self._next_order_locked(),
                "running": self._queue_running_locked(),
                "jobs": jobs,
                **counts,
            }

    def enqueue(self, raw_paths: list[str]) -> dict[str, Any]:
        with self.condition:
            expanded, missing = self._expand_raw_paths_locked(raw_paths)
            added: list[dict[str, Any]] = []
            skipped: list[str] = []
            seen = {job.path for job in self.jobs}
            queue_order = self._next_order_locked()
            now = self._now()

            for path, source_dir in expanded:
                path_str = str(path)
                if path_str in seen:
                    skipped.append(path_str)
                    continue
                job = Job(
                    id=self._next_job_id_locked(),
                    path=path_str,
                    queue_order=queue_order,
                    status="pending",
                    text_path=str(output_path_for(path)),
                    error="",
                    progress=0.0,
                    duration=0.0,
                    cancel_requested=False,
                    source_dir=source_dir,
                )
                self.jobs.append(job)
                added.append(asdict(job))
                seen.add(path_str)
                queue_order += 1
            self.condition.notify_all()

            self._next_order = queue_order

        return {"added": added, "skipped": skipped, "missing": missing}

    def claim_next(self) -> Job | None:
        with self.condition:
            if not self._queue_running_locked() or self._clear_requested:
                return None
            job = next(
                (
                    item
                    for item in sorted(self.jobs, key=lambda item: (item.queue_order, item.id))
                    if item.status == "pending" and not item.cancel_requested
                ),
                None,
            )
            if job is None:
                if not any(item.status in {"pending", "processing"} for item in self.jobs):
                    self._queue_running = False
                return None
            job.status = "processing"
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

    def complete(self, job_id: int, *, progress: float = 1.0) -> None:
        self.update(job_id, status="done", progress=progress, error="")

    def fail(self, job_id: int, error: str) -> None:
        self.update(job_id, status="failed", error=error)

    def clear_all(self) -> None:
        with self.condition:
            self._clear_requested = True
            self._queue_running = False
            self.jobs.clear()
            self.condition.notify_all()

    def request_cancel(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            if job is None or job.status not in {"pending", "processing"}:
                return False
            job.cancel_requested = True
            job.status = "canceled"
            job.error = ""
            self.condition.notify_all()
            return True

    def should_cancel(self, job_id: int) -> bool:
        with self.condition:
            job = self._find_locked(job_id)
            return bool(self._clear_requested or (job is not None and job.cancel_requested))


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

    def warm_up(self) -> None:
        self.model()

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
                    current_progress = current.progress if current is not None else job.progress
                    self.store.update(job.id, status="canceled", error="", progress=current_progress)
                    print(f"Canceled: {audio_path}")
                else:
                    self.store.fail(job.id, str(exc))
                    print(f"Failed: {audio_path} -> {exc}")
            finally:
                with self._current_lock:
                    self._current_job_id = None

    def _is_canceled(self, job_id: int) -> bool:
        return self.store.should_cancel(job_id)


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
        if parsed.path == "/api/control":
            payload = self._read_json()
            action = payload.get("action")
            if not isinstance(action, str):
                self._send_json({"error": "invalid payload"}, HTTPStatus.BAD_REQUEST)
                return
            if action == "start":
                self.store.start_queue()
                ok = True
            elif action == "clear":
                self.store.clear_all()
                ok = True
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
    store = QueueStore()
    store.start_queue()
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
            pending = state["pending"] + state["processing"] > 0
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


def warm_up_model(args: argparse.Namespace) -> int:
    engine = TranscriptionEngine(args.model, args.device, args.compute_type, args.language)
    engine.warm_up()
    print(f"Model ready: {args.model}")
    return 0


def run_server(files: list[str], args: argparse.Namespace) -> int:
    store = QueueStore()
    store.stop_queue()
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
    parser.add_argument(
        "--download-model",
        action="store_true",
        help="Download and cache the model, then exit.",
    )
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
    if args.download_model:
        return warm_up_model(args)
    files = args.files
    if args.serve or not files:
        return run_server(files, args)
    return run_headless(files, args)


if __name__ == "__main__":
    raise SystemExit(main())
