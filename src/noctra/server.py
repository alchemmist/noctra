"""Minimal stdlib HTTP server and static asset serving.

NOTE: this layer is slated to be replaced by FastAPI (plan phase 2). It is kept
deliberately thin and free of business logic, which lives in ``queue_store``.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .logging_setup import LOGGER
from .queue_store import QueueStore

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

#: Hard cap on request bodies to avoid unbounded memory use on POST.
MAX_BODY_BYTES = 8 * 1024 * 1024

MIME_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def load_web_asset(name: str) -> tuple[bytes, str]:
    path = WEB_DIR / name
    if not path.exists():
        raise FileNotFoundError(name)
    content_type = MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return path.read_bytes(), content_type


class AppHandler(BaseHTTPRequestHandler):
    store: QueueStore

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        LOGGER.debug("http %s", format % args)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            self._send_json({"error": "request too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return None
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_asset("index.html")
        elif parsed.path == "/app.js":
            self._serve_asset("app.js")
        elif parsed.path == "/styles.css":
            self._serve_asset("styles.css")
        elif parsed.path == "/api/state":
            self._send_json(self.store.snapshot())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/enqueue":
            payload = self._read_json()
            if payload is None:
                return
            paths = payload.get("paths", [])
            if not isinstance(paths, list):
                self._send_json({"error": "paths must be a list"}, HTTPStatus.BAD_REQUEST)
                return
            result = self.store.enqueue([str(p) for p in paths])
            self._send_json(result)
        elif parsed.path == "/api/control":
            payload = self._read_json()
            if payload is None:
                return
            action = payload.get("action")
            if action == "start":
                self.store.start_queue()
            elif action == "clear":
                self.store.clear_all()
            else:
                self._send_json({"error": "unknown action"}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "state": self.store.snapshot()})
        else:
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


class LoggingThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request: Any, client_address: Any) -> None:
        LOGGER.exception("Error handling request from %s", client_address)


def make_handler(store: QueueStore) -> type[AppHandler]:
    return type("ConfiguredHandler", (AppHandler,), {"store": store})
