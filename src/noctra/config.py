"""Runtime configuration.

Values come from (in order of precedence): CLI arguments → environment
variables / ``.env`` → built-in defaults. Centralizing these here removes the
hardcoded constants that used to live at the top of ``main.py``.
"""

from __future__ import annotations

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
