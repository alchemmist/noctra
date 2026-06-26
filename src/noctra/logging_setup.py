"""File-based logging with hooks for uncaught (incl. thread) exceptions."""

from __future__ import annotations

import datetime as dt
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

LOG_DIR = Path(".noctra_logs")
LOGGER = logging.getLogger("noctra")


def setup_logging(log_dir: Path = LOG_DIR) -> Path:
    log_dir.mkdir(exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"noctra-{timestamp}-{os.getpid()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8")],
        force=True,
    )
    logging.captureWarnings(True)

    def handle_uncaught(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        LOGGER.critical("Uncaught exception", exc_info=(exc_type, exc, tb))

    def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        thread_name = args.thread.name if args.thread is not None else "unknown"
        if args.exc_value is None:
            LOGGER.critical("Uncaught thread exception in %s", thread_name)
            return
        LOGGER.critical(
            "Uncaught thread exception in %s",
            thread_name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_uncaught
    threading.excepthook = handle_thread_exception
    return log_path
