from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noctra.api.app import create_app
from noctra.config import Settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(Settings())
    # `with` triggers lifespan: store + worker are created on enter.
    with TestClient(app) as test_client:
        yield test_client


def _audio(tmp_path: Path, name: str = "a.m4a") -> Path:
    f = tmp_path / name
    f.write_bytes(b"x")
    return f


def test_state_empty(client: TestClient) -> None:
    resp = client.get("/api/state")
    assert resp.status_code == 200
    body = resp.json()
    assert body["jobs"] == []
    assert body["running"] is False
    assert body["pending"] == 0


def test_enqueue_and_state(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    resp = client.post("/api/enqueue", json={"paths": [str(audio)]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["added"]) == 1
    assert body["added"][0]["status"] == "pending"
    assert body["missing"] == []

    state = client.get("/api/state").json()
    assert state["pending"] == 1
    assert state["jobs"][0]["path"] == str(audio.resolve())


def test_enqueue_validation_error(client: TestClient) -> None:
    resp = client.post("/api/enqueue", json={"paths": "not-a-list"})
    assert resp.status_code == 422  # pydantic rejects, no handler code needed


def test_control_start_and_clear(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/enqueue", json={"paths": [str(_audio(tmp_path))]})

    started = client.post("/api/control", json={"action": "start"})
    assert started.status_code == 200
    assert started.json()["ok"] is True

    cleared = client.post("/api/control", json={"action": "clear"})
    assert cleared.status_code == 200
    assert cleared.json()["state"]["jobs"] == []


def test_control_unknown_action(client: TestClient) -> None:
    resp = client.post("/api/control", json={"action": "explode"})
    assert resp.status_code == 422  # Literal["start","clear"] rejects it


def test_static_index_served(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_websocket_pushes_snapshot(client: TestClient, tmp_path: Path) -> None:
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["jobs"] == []
        # Enqueue over HTTP, expect the socket to push an updated snapshot.
        client.post("/api/enqueue", json={"paths": [str(_audio(tmp_path))]})
        for _ in range(20):
            snap = ws.receive_json()
            if snap["pending"] == 1:
                break
        assert snap["pending"] == 1
