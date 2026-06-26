from __future__ import annotations

from pathlib import Path

from noctra.paths import expand_paths, is_audio_file, output_path_for


def test_output_path_for() -> None:
    assert output_path_for(Path("/a/b/clip.m4a")) == Path("/a/b/clip.txt")


def test_is_audio_file(tmp_path: Path) -> None:
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    other = tmp_path / "a.txt"
    other.write_text("x")
    assert is_audio_file(audio)
    assert not is_audio_file(other)
    assert not is_audio_file(tmp_path)  # a directory


def test_expand_paths_files_and_missing(tmp_path: Path) -> None:
    audio = tmp_path / "clip.m4a"
    audio.write_bytes(b"x")
    expanded, missing = expand_paths([str(audio), str(tmp_path / "nope.m4a"), ""])
    assert [p for p, _ in expanded] == [audio.resolve()]
    assert missing == [str(tmp_path / "nope.m4a")]


def test_expand_paths_recurses_directories(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    a = tmp_path / "a.m4a"
    b = tmp_path / "sub" / "b.mp3"
    skip = tmp_path / "notes.txt"
    for f in (a, b):
        f.write_bytes(b"x")
    skip.write_text("x")

    expanded, missing = expand_paths([str(tmp_path)])
    found = sorted(str(p) for p, _ in expanded)
    assert found == sorted([str(a.resolve()), str(b.resolve())])
    assert missing == []
    # source_dir points at the expanded directory.
    assert all(src == str(tmp_path.resolve()) for _, src in expanded)
