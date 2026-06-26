from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FakeModel, FakeSegment, make_audio
from noctra.domain import JobCanceledError
from noctra.engine import TranscriptionEngine
from noctra.paths import output_path_for


def _engine_with(model: FakeModel) -> TranscriptionEngine:
    engine = TranscriptionEngine("fake", "cpu", "int8", "ru")
    engine._model = model  # inject fake, bypass faster-whisper
    return engine


def test_transcribe_writes_text_and_reports_progress(tmp_path: Path) -> None:
    audio = make_audio(tmp_path)
    model = FakeModel([FakeSegment(5.0, "hello"), FakeSegment(10.0, "world")], duration=10.0)
    engine = _engine_with(model)

    seen: list[float] = []
    out_file, duration = engine.transcribe_file(audio, on_progress=seen.append)

    assert out_file == output_path_for(audio)
    assert out_file.read_text(encoding="utf-8") == "hello\nworld\n"
    assert duration == 10.0
    assert seen[-1] == 1.0  # always reports completion
    # no leftover temp file
    assert not out_file.with_suffix(".txt.part").exists()


def test_transcribe_skips_blank_segments(tmp_path: Path) -> None:
    audio = make_audio(tmp_path)
    model = FakeModel([FakeSegment(5.0, "  "), FakeSegment(10.0, "kept")], duration=10.0)
    engine = _engine_with(model)
    out_file, _ = engine.transcribe_file(audio)
    assert out_file.read_text(encoding="utf-8") == "kept\n"


def test_named_models_are_cached_and_reused() -> None:
    loaded: list[str] = []
    engine = TranscriptionEngine("default", "cpu", "int8", "ru")
    engine._load_model = lambda name: loaded.append(name) or FakeModel([], 0.0)  # type: ignore[assignment]

    first = engine.model("small")
    second = engine.model("small")
    other = engine.model("medium")

    assert first is second  # same instance, loaded once
    assert other is not first
    assert loaded == ["small", "medium"]  # default model never loaded here


def test_transcribe_uses_requested_model(tmp_path: Path) -> None:
    audio = make_audio(tmp_path)
    default_model = FakeModel([FakeSegment(1.0, "default")], duration=1.0)
    named_model = FakeModel([FakeSegment(1.0, "named")], duration=1.0)
    engine = _engine_with(default_model)
    engine._models["small"] = named_model

    out_file, _ = engine.transcribe_file(audio, model_name="small")

    assert out_file.read_text(encoding="utf-8") == "named\n"
    assert default_model.calls == []  # default untouched


def test_transcribe_cancel_raises_and_cleans_up(tmp_path: Path) -> None:
    audio = make_audio(tmp_path)
    model = FakeModel([FakeSegment(5.0, "a"), FakeSegment(10.0, "b")], duration=10.0)
    engine = _engine_with(model)

    with pytest.raises(JobCanceledError):
        engine.transcribe_file(audio, should_cancel=lambda: True)

    # output never created, temp cleaned up
    assert not output_path_for(audio).exists()
    assert not output_path_for(audio).with_suffix(".txt.part").exists()
