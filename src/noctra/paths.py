"""Filesystem helpers for discovering audio files and naming outputs.

Pure functions only — no shared state, so they are easy to test in isolation.
"""

from __future__ import annotations

from pathlib import Path

#: Audio extensions Noctra will pick up when expanding files and directories.
AUDIO_EXTENSIONS = {
    ".m4a",
    ".mp3",
}


def output_path_for(audio_path: Path) -> Path:
    """Return the ``.txt`` transcript path that sits next to ``audio_path``."""
    return audio_path.with_suffix(".txt")


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def expand_directory(directory: Path) -> list[Path]:
    """Recursively collect audio files inside ``directory`` (sorted, resolved)."""
    return [child.resolve() for child in sorted(directory.rglob("*")) if is_audio_file(child)]


def expand_paths(raw_paths: list[str]) -> tuple[list[tuple[Path, str]], list[str]]:
    """Expand user-supplied paths into ``(audio_file, source_dir)`` pairs.

    Directories are expanded recursively. Returns the discovered files together
    with a list of paths that do not exist (``missing``).
    """
    expanded: list[tuple[Path, str]] = []
    missing: list[str] = []
    for raw in raw_paths:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.is_dir():
            directory = path.resolve()
            for audio in expand_directory(directory):
                expanded.append((audio, str(directory)))
            continue
        if path.exists():
            resolved = path.resolve()
            expanded.append((resolved, str(resolved.parent)))
        else:
            missing.append(str(path))
    return expanded, missing
