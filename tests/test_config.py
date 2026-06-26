from __future__ import annotations

import pytest

from noctra.config import load_settings


def test_defaults() -> None:
    s = load_settings()
    assert s.model == "large-v3"
    assert s.language == "ru"
    assert s.port == 8787


def test_cli_overrides_win() -> None:
    s = load_settings(model="small", port=9000, device=None)
    assert s.model == "small"
    assert s.port == 9000
    assert s.device == "cpu"  # None override ignored, falls back to default


def test_env_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOCTRA_LANGUAGE", "en")
    monkeypatch.setenv("NOCTRA_PORT", "1234")
    s = load_settings()
    assert s.language == "en"
    assert s.port == 1234
