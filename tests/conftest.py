"""Shared test fixtures and fakes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FakeSegment:
    end: float
    text: str
    start: float = 0.0


@dataclass
class FakeInfo:
    duration: float


class FakeModel:
    """Stand-in for faster_whisper.WhisperModel used in engine tests."""

    def __init__(self, segments: list[FakeSegment], duration: float) -> None:
        self._segments = segments
        self._duration = duration
        self.calls: list[str] = []
        self.last_kwargs: dict[str, object] = {}

    def transcribe(self, audio: str, **kwargs: object) -> tuple[list[FakeSegment], FakeInfo]:
        self.calls.append(audio)
        self.last_kwargs = kwargs
        return self._segments, FakeInfo(self._duration)


def make_audio(tmp_path: Path, name: str = "clip.m4a") -> Path:
    audio = tmp_path / name
    audio.write_bytes(b"not really audio")
    return audio
