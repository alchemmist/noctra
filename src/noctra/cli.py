"""Command-line entry points and run modes."""

from __future__ import annotations

import argparse
import time

from .config import Settings, load_settings
from .engine import TranscriptionEngine
from .logging_setup import LOGGER, setup_logging
from .queue_store import QueueStore
from .server import LoggingThreadingHTTPServer, make_handler
from .worker import Worker


def _engine(settings: Settings) -> TranscriptionEngine:
    return TranscriptionEngine(
        settings.model, settings.device, settings.compute_type, settings.language
    )


def run_headless(files: list[str], settings: Settings) -> int:
    store = QueueStore()
    store.start_queue()
    result = store.enqueue(files)
    LOGGER.info(
        "Queued: %d, skipped: %d, missing: %d",
        len(result["added"]),
        len(result["skipped"]),
        len(result["missing"]),
    )

    worker = Worker(store, _engine(settings))
    worker.start()
    try:
        while True:
            state = store.snapshot()
            if state["pending"] + state["processing"] == 0:
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        worker.stop(graceful=True)
        worker.join(timeout=2.0)
        return 130

    worker.stop(graceful=True)
    worker.join(timeout=2.0)
    return 0


def warm_up_model(settings: Settings) -> int:
    _engine(settings).warm_up()
    LOGGER.info("Model ready: %s", settings.model)
    return 0


def run_server(files: list[str], settings: Settings) -> int:
    store = QueueStore()
    store.stop_queue()
    if files:
        result = store.enqueue(files)
        if result["added"]:
            LOGGER.info("Queued at startup: %d", len(result["added"]))

    worker = Worker(store, _engine(settings))
    worker.start()

    server = LoggingThreadingHTTPServer((settings.host, settings.port), make_handler(store))
    LOGGER.info("Open http://%s:%s", settings.host, settings.port)
    print(f"Open http://{settings.host}:{settings.port}")
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
    parser = argparse.ArgumentParser(
        prog="noctra",
        description="Sequential audio transcription queue with a local web UI.",
    )
    parser.add_argument("files", nargs="*", help="Audio files or directories to enqueue.")
    parser.add_argument("--serve", action="store_true", help="Run local web UI and worker.")
    parser.add_argument(
        "--download-model", action="store_true", help="Download and cache the model, then exit."
    )
    parser.add_argument("--host", default=None, help="Host for web UI.")
    parser.add_argument("--port", type=int, default=None, help="Port for web UI.")
    parser.add_argument("--model", default=None, help="Whisper model name.")
    parser.add_argument("--language", default=None, help="Language code.")
    parser.add_argument("--device", default=None, help="Model device (cpu/cuda/mps).")
    parser.add_argument("--compute-type", dest="compute_type", default=None, help="Compute type.")
    return parser.parse_args()


def main() -> int:
    setup_logging()
    args = parse_args()
    settings = load_settings(
        model=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        host=args.host,
        port=args.port,
    )
    if args.download_model:
        return warm_up_model(settings)
    if args.serve or not args.files:
        return run_server(args.files, settings)
    return run_headless(args.files, settings)
