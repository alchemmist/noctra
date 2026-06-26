# Noctra container image — CPU transcription with the web UI.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    NOCTRA_HOST=0.0.0.0 \
    NOCTRA_PORT=8787

# ffmpeg is required by faster-whisper to decode audio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# uv provides fast, reproducible (locked) dependency installs.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached layer) using only the lockfile manifests.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then install the project itself.
COPY src ./src
COPY web ./web
RUN uv sync --frozen --no-dev

EXPOSE 8787

CMD ["uv", "run", "--no-dev", "python", "-m", "noctra", "--serve"]
