"""Transcription engine wrapping faster-whisper.

The model is loaded lazily and only once (double-checked locking), so importing
this module stays cheap and tests can inject a fake model.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .domain import JobCanceledError
from .logging_setup import LOGGER
from .paths import output_path_for

ProgressCallback = Callable[[float], None]
CancelCheck = Callable[[], bool]


class TranscriptionEngine:
    def __init__(self, model_name: str, device: str, compute_type: str, language: str) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        #: Cache for the default model; named models live in ``_models``.
        self._model: Any | None = None
        self._models: dict[str, Any] = {}
        self._lock = threading.Lock()

    def model(self, name: str | None = None) -> Any:
        """Return a loaded model, lazily loading and caching it by name.

        ``name=None`` (or the configured default) uses the ``_model`` slot so
        tests can inject a fake default model; any other name is cached in
        ``_models`` so switching models per job doesn't reload on every run.
        """
        if name is None or name == self.model_name:
            if self._model is None:
                with self._lock:
                    if self._model is None:
                        self._model = self._load_model(self.model_name)
            return self._model
        with self._lock:
            model = self._models.get(name)
            if model is None:
                model = self._load_model(name)
                self._models[name] = model
            return model

    def _load_model(self, name: str) -> Any:
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency guard
            raise RuntimeError(
                "faster-whisper is not installed. Install dependencies before transcribing."
            ) from exc
        LOGGER.info("Loading model %s on %s (%s)", name, self.device, self.compute_type)
        return WhisperModel(name, device=self.device, compute_type=self.compute_type)

    def warm_up(self) -> None:
        self.model()

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        model_name: str | None = None,
        on_progress: ProgressCallback | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> tuple[Path, float]:
        model = self.model(model_name)
        out_file = output_path_for(audio_path)
        temp_file = out_file.with_suffix(out_file.suffix + ".part")
        segments, info = model.transcribe(
            str(audio_path),
            language=self.language,
            vad_filter=True,
        )

        progress_bar = self._make_progress_bar(info.duration, audio_path.name)
        last_end = 0.0
        last_reported = 0.0

        try:
            with temp_file.open("w", encoding="utf-8") as handle:
                for segment in segments:
                    if should_cancel is not None and should_cancel():
                        raise JobCanceledError(audio_path.name)
                    current_end = max(last_end, float(segment.end))
                    if progress_bar is not None:
                        progress_bar.update(max(0.0, current_end - last_end))
                    last_end = current_end

                    if info.duration > 0:
                        current_progress = min(1.0, current_end / info.duration)
                        if on_progress is not None and current_progress - last_reported >= 0.01:
                            on_progress(current_progress)
                            last_reported = current_progress

                    text = segment.text.strip()
                    if text:
                        handle.write(text + "\n")

            temp_file.replace(out_file)
        except BaseException:
            if temp_file.exists():
                temp_file.unlink()
            raise
        finally:
            if progress_bar is not None:
                progress_bar.close()

        if on_progress is not None:
            on_progress(1.0)
        return out_file, float(info.duration)

    @staticmethod
    def _make_progress_bar(total: float, desc: str) -> Any | None:
        try:
            from tqdm import tqdm
        except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
            return None
        return tqdm(total=total, unit="sec", desc=desc)
