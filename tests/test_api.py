from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noctra.api.app import create_app
from noctra.config import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        db_path=str(tmp_path / "queue.db"),
        upload_dir=str(tmp_path / "uploads"),
    )
    app = create_app(settings)
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


def test_config_lists_models(client: TestClient) -> None:
    body = client.get("/api/config").json()
    assert "large-v3" in body["models"]
    assert body["default_model"] == "large-v3"  # Settings default
    assert body["formats"] == ["txt", "srt", "vtt"]
    assert body["default_formats"] == ["txt"]
    assert "auto" in body["languages"]
    assert body["default_language"] == "ru"  # Settings default


def test_enqueue_with_formats_records_them(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    resp = client.post("/api/enqueue", json={"paths": [str(audio)], "formats": ["txt", "srt"]})
    assert resp.json()["added"][0]["formats"] == "txt,srt"


def test_enqueue_language(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    chosen = client.post("/api/enqueue", json={"paths": [str(audio)], "language": "auto"})
    assert chosen.json()["added"][0]["language"] == "auto"
    # unknown/empty language falls back to the server default ("ru")
    audio2 = _audio(tmp_path, "b.m4a")
    fallback = client.post("/api/enqueue", json={"paths": [str(audio2)], "language": "xx"})
    assert fallback.json()["added"][0]["language"] == "ru"


def test_enqueue_without_formats_uses_default(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    resp = client.post("/api/enqueue", json={"paths": [str(audio)]})
    assert resp.json()["added"][0]["formats"] == "txt"


def test_enqueue_with_model_records_it(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    resp = client.post("/api/enqueue", json={"paths": [str(audio)], "model": "small"})
    assert resp.status_code == 200
    assert resp.json()["added"][0]["model"] == "small"


def test_enqueue_without_model_uses_default(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    resp = client.post("/api/enqueue", json={"paths": [str(audio)]})
    assert resp.json()["added"][0]["model"] == "large-v3"  # server default


def test_settings_read_and_update(client: TestClient) -> None:
    initial = client.get("/api/settings").json()
    assert initial["model"] == "large-v3"
    assert initial["device"] == "cpu"  # read-only, env/CLI-driven

    resp = client.put("/api/settings", json={"model": "small", "formats": ["txt", "srt"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "small"
    assert body["formats"] == ["txt", "srt"]

    # the change drives the defaults advertised by /api/config
    assert client.get("/api/config").json()["default_model"] == "small"


def test_settings_update_rejects_unknown(client: TestClient) -> None:
    assert client.put("/api/settings", json={"model": "huge"}).status_code == 400
    assert client.put("/api/settings", json={"language": "zz"}).status_code == 400
    assert client.put("/api/settings", json={"formats": ["doc"]}).status_code == 400


def test_settings_persist_across_restart(tmp_path: Path) -> None:
    settings = Settings(
        db_path=str(tmp_path / "queue.db"),
        upload_dir=str(tmp_path / "uploads"),
    )
    with TestClient(create_app(settings)) as c:
        c.put("/api/settings", json={"model": "medium", "language": "en"})

    # A fresh app over the same db dir picks up the saved overlay.
    settings2 = Settings(
        db_path=str(tmp_path / "queue.db"),
        upload_dir=str(tmp_path / "uploads"),
    )
    with TestClient(create_app(settings2)) as c2:
        body = c2.get("/api/settings").json()
        assert body["model"] == "medium"
        assert body["language"] == "en"


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


def test_upload_saves_audio_and_rejects_other(client: TestClient) -> None:
    resp = client.post(
        "/api/upload",
        files=[
            ("files", ("talk.m4a", b"audio-bytes", "audio/m4a")),
            ("files", ("notes.txt", b"nope", "text/plain")),
        ],
        data={"model": "small", "formats": "txt,srt"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["added"]) == 1
    job = body["added"][0]
    assert job["path"].endswith("talk.m4a")
    assert job["model"] == "small"
    assert job["formats"] == "txt,srt"
    assert "notes.txt" in body["missing"]  # non-audio rejected

    # the file landed in the configured upload dir and is queued
    assert client.get("/api/state").json()["pending"] == 1


def test_upload_too_large_not_blocked_by_body_limit(client: TestClient) -> None:
    # 9 MiB payload exceeds the 8 MiB JSON cap but uploads are exempt.
    big = b"x" * (9 * 1024 * 1024)
    resp = client.post("/api/upload", files=[("files", ("big.mp3", big, "audio/mpeg"))])
    assert resp.status_code == 200
    assert len(resp.json()["added"]) == 1


def test_job_delete_removes_it(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path)
    job_id = client.post("/api/enqueue", json={"paths": [str(audio)]}).json()["added"][0]["id"]

    resp = client.post("/api/job", json={"id": job_id, "action": "delete"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["state"]["jobs"] == []


def test_download_transcript(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path, "talk.m4a")
    job_id = client.post("/api/enqueue", json={"paths": [str(audio)]}).json()["added"][0]["id"]
    # Simulate a finished transcript next to the audio.
    audio.with_suffix(".txt").write_text("hello world\n", encoding="utf-8")

    resp = client.get(f"/api/job/{job_id}/download", params={"fmt": "txt"})
    assert resp.status_code == 200
    assert resp.text == "hello world\n"
    assert "talk.txt" in resp.headers.get("content-disposition", "")


def test_download_missing_transcript_404(client: TestClient, tmp_path: Path) -> None:
    audio = _audio(tmp_path, "talk.m4a")
    job_id = client.post("/api/enqueue", json={"paths": [str(audio)]}).json()["added"][0]["id"]
    # No .srt was produced.
    assert client.get(f"/api/job/{job_id}/download", params={"fmt": "srt"}).status_code == 404


def test_download_bad_format_400(client: TestClient) -> None:
    assert client.get("/api/job/1/download", params={"fmt": "exe"}).status_code == 400


def test_job_retry_unknown_id_returns_ok_false(client: TestClient) -> None:
    resp = client.post("/api/job", json={"id": 999, "action": "retry"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_job_control_invalid_action(client: TestClient) -> None:
    resp = client.post("/api/job", json={"id": 1, "action": "explode"})
    assert resp.status_code == 422  # Literal rejects it


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
