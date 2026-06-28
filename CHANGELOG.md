# Changelog

All notable changes to Noctra are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/).

## [0.4.0] — 2026-06-28

UI-focused release: results access, a tabbed layout, in-app settings and polish.

### Added
- **Tabbed layout** — Queue / History / Settings.
- **Download transcripts** from the UI — `.txt` / `.srt` / `.vtt` pills on finished
  jobs (`GET /api/job/{id}/download`).
- **History tab** listing finished jobs (newest first) with download links.
- **Settings tab** — edit the default model / language / output formats, persisted
  to `.noctra/settings.json` (`GET` / `PUT /api/settings`); device and compute type
  are shown read-only.
- Toast notifications (success / error) and subtle fade-up animations.

### Changed
- Published Docker images are now multi-arch (`linux/amd64` + `linux/arm64`).

## [0.3.0] — 2026-06-28

Feature-complete release: the full roadmap (modular core → FastAPI → SQLite →
React/Gravity UI → features → deploy) is done.

### Added
- **Audio & video formats** — `.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.opus`,
  plus video containers (`.webm`, `.mp4`, `.m4v`, `.mov`, `.mkv`, `.avi`) whose
  audio track is transcribed.
- **Subtitle export** — optional `.srt` / `.vtt` output with timestamps,
  selectable per queue; written atomically alongside the `.txt`.
- **Drag & drop upload** — drop or pick audio in the UI (`POST /api/upload`),
  stored under `.noctra/uploads`.
- **Per-queue model selection** — pick the Whisper model (`tiny` … `large-v3`)
  from the UI; the engine caches models by name.
- **Per-queue transcription language** — choose a language or `auto`-detect.
- **In-UI job control** — cancel, retry failed, delete, and reorder pending
  jobs (move up/down) via `POST /api/job`.
- **UI localization** — English (default) and Russian, toggled in the header.
- **GPU image** — `Dockerfile.cuda` + `compose.cuda.yaml` (CUDA, `float16`).
- **CLI packaging** — `noctra` entry point; `make install-cli`.
- **macOS autostart** — `deploy/com.noctra.plist` launchd template.

### Changed
- Dark theme repainted to a cool, neutral slate (Gravity's stock dark surfaces
  had a warm cast).

### Fixed
- Thin dark fringe on the running status chip (opaque border instead of
  `transparent`).

## [0.2.0]

Reliability and modern stack (roadmap phases 0–4 + early Docker).

### Added
- `src/noctra/` package split from the monolithic `main.py`, with `JobStatus`
  enum, typed config (pydantic-settings), and a pytest suite (90%+ core).
- **FastAPI** HTTP layer with a WebSocket `/ws` push (replacing polling) and
  OpenAPI docs at `/docs`.
- **SQLite persistence** — the queue and history survive restarts; in-flight
  jobs are re-queued on startup.
- **React + Vite + Gravity UI** frontend (dark-first redesign), served as a
  built SPA from the backend.
- One-command **Docker / Podman** launch (`compose.yaml`).

## [0.1.0]

Initial prototype — a single-file `http.server` backend with vanilla-JS UI and
in-memory queue.

[0.4.0]: https://github.com/alchemmist/noctra/releases/tag/v0.4.0
[0.3.0]: https://github.com/alchemmist/noctra/releases/tag/v0.3.0
