"""Runtime configuration.

Values come from (in order of precedence): CLI arguments → environment
variables / ``.env`` → built-in defaults. Centralizing these here removes the
hardcoded constants that used to live at the top of ``main.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Whisper model sizes selectable from the UI / CLI, smallest (fastest) first.
#: These are the canonical faster-whisper model names; the engine downloads and
#: caches each one on first use.
AVAILABLE_MODELS: tuple[str, ...] = (
    "tiny",
    "base",
    "small",
    "medium",
    "large-v2",
    "large-v3",
)

#: Transcript output formats selectable from the UI / CLI.
AVAILABLE_FORMATS: tuple[str, ...] = ("txt", "srt", "vtt")

#: Transcription languages offered in the UI. ``auto`` lets Whisper detect it;
#: the rest are ISO codes for the most common languages.
AVAILABLE_LANGUAGES: tuple[str, ...] = (
    "auto",
    "ru",
    "en",
    "uk",
    "de",
    "fr",
    "es",
    "it",
    "pt",
    "pl",
    "nl",
    "tr",
    "zh",
    "ja",
    "ko",
    "ar",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOCTRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = "large-v3"
    #: Default output formats as a comma-separated string (e.g. ``"txt,srt"``).
    output_formats: str = "txt"
    language: str = "ru"
    device: str = "cpu"
    compute_type: str = "int8"
    host: str = "127.0.0.1"
    port: int = 8787
    db_path: str = ".noctra/queue.db"
    #: Where files uploaded through the UI are stored before transcription.
    upload_dir: str = ".noctra/uploads"


def load_settings(**overrides: Any) -> Settings:
    """Build :class:`Settings`, applying non-``None`` CLI overrides on top."""
    clean = {key: value for key, value in overrides.items() if value is not None}
    return Settings(**clean)


#: Default fields editable from the UI and persisted across restarts.
OVERLAY_KEYS = ("model", "language", "output_formats")


def _overlay_path(settings: Settings) -> Path:
    return Path(settings.db_path).parent / "settings.json"


def apply_overlay(settings: Settings) -> None:
    """Overlay UI-saved defaults (``.noctra/settings.json``) onto ``settings``."""
    path = _overlay_path(settings)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for key in OVERLAY_KEYS:
        value = data.get(key)
        if value:
            setattr(settings, key, value)


def save_overlay(settings: Settings) -> None:
    """Persist the UI-editable defaults from ``settings`` to disk."""
    path = _overlay_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {key: getattr(settings, key) for key in OVERLAY_KEYS}
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
