#!/usr/bin/env python3
"""Cut the next **minor** release automatically.

Bumps the version to ``X.(Y+1).0``, regenerates the CHANGELOG section from the
commit subjects since the previous tag, runs the checks, then commits, tags and
pushes — which triggers CI to build the image and publish the GitHub Release.

Usage:
    python3 scripts/release.py            # do the release
    python3 scripts/release.py --dry-run  # just show the next version + notes
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "alchemmist/noctra"


def out(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def current_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"', text, re.M)
    if match is None:
        fail("Could not read version from pyproject.toml")
    return match.group(1)  # type: ignore[union-attr]


def next_minor(version: str) -> str:
    major, minor, *_ = version.split(".")
    return f"{major}.{int(minor) + 1}.0"


def last_tag() -> str:
    try:
        return out("git", "describe", "--tags", "--abbrev=0")
    except subprocess.CalledProcessError:
        return ""


def commit_notes() -> str:
    """Bullet list of commit subjects since the previous tag (release commits skipped)."""
    tag = last_tag()
    rng = f"{tag}..HEAD" if tag else "HEAD"
    log = out("git", "log", "--no-merges", "--pretty=- %s", rng)
    lines = [line for line in log.splitlines() if line and not line.startswith("- Release v")]
    return "\n".join(lines) if lines else "- Maintenance release."


def bump_file(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(re.sub(pattern, replacement, text, count=1, flags=re.M), encoding="utf-8")


def update_changelog(version: str, notes: str) -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    date = datetime.date.today().isoformat()
    section = f"## [{version}] — {date}\n\n### Changes\n\n{notes}\n\n"

    index = text.find("\n## [")
    if index == -1:
        text = text.rstrip() + "\n\n" + section
    else:
        text = text[: index + 1] + section + text[index + 1 :]

    link = f"[{version}]: https://github.com/{REPO}/releases/tag/v{version}\n"
    if f"[{version}]:" not in text:
        text = text.rstrip() + "\n" + link
    path.write_text(text, encoding="utf-8")


def main() -> None:
    dry_run = "--dry-run" in sys.argv[1:]

    if not dry_run:
        if out("git", "status", "--porcelain"):
            fail("Working tree is dirty — commit first.")
        if out("git", "rev-parse", "--abbrev-ref", "HEAD") != "main":
            fail("Not on main.")

    version = next_minor(current_version())
    tag = f"v{version}"
    if tag in out("git", "tag").split():
        fail(f"Tag {tag} already exists.")

    notes = commit_notes()

    if dry_run:
        print(f"Next version: {version}\n\nCHANGELOG section:\n")
        print(f"## [{version}]\n\n### Changes\n\n{notes}")
        return

    print(f"Releasing {current_version()} -> {version}")
    run("make", "check")

    bump_file(ROOT / "pyproject.toml", r'^version = "[^"]+"', f'version = "{version}"')
    bump_file(ROOT / "src/noctra/__init__.py", r'^__version__ = "[^"]+"', f'__version__ = "{version}"')
    update_changelog(version, notes)
    run("uv", "lock", "--quiet")

    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", f"Release {tag}")
    run("git", "tag", "-a", tag, "-m", f"Noctra {tag}")
    run("git", "push", "origin", "main")
    run("git", "push", "origin", tag)
    print(f"Pushed {tag}. CI will build the image and publish the GitHub Release.")


if __name__ == "__main__":
    main()
