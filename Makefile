UV ?= uv
NPM ?= npm
COMPOSE ?= docker compose
CUDA_COMPOSE ?= $(COMPOSE) -f compose.cuda.yaml

# Project version, read straight from pyproject.toml.
VERSION := $(shell grep -m1 '^version' pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
MODEL ?= large-v3
LANGUAGE ?= ru
DEVICE ?= cpu
COMPUTE_TYPE ?= int8
HOST ?= 127.0.0.1
PORT ?= 8787
FILES ?=

RUN = $(UV) run python -m noctra

.PHONY: serve run model test lint fmt typecheck check install install-cli up down logs \
        up-cuda down-cuda frontend-install frontend-build frontend-dev release

install:
	$(UV) sync --extra dev

# Install Noctra as a global `noctra` CLI (uses the entry point in pyproject).
install-cli:
	$(UV) tool install --force .

serve:
	$(RUN) --serve --model $(MODEL) --language $(LANGUAGE) --device $(DEVICE) --compute-type $(COMPUTE_TYPE) --host $(HOST) --port $(PORT)

run:
	$(RUN) --model $(MODEL) --language $(LANGUAGE) --device $(DEVICE) --compute-type $(COMPUTE_TYPE) $(FILES)

model:
	$(RUN) --download-model --model $(MODEL) --language $(LANGUAGE) --device $(DEVICE) --compute-type $(COMPUTE_TYPE)

test:
	$(UV) run pytest --cov

lint:
	$(UV) run ruff check src tests

fmt:
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

typecheck:
	$(UV) run mypy

check: lint typecheck test

# Frontend (React + Vite + Gravity UI). Build output goes to web/dist, which the
# backend serves. frontend-dev runs Vite with API/WS proxied to a local backend.
frontend-install:
	cd frontend && $(NPM) install

frontend-build:
	cd frontend && $(NPM) run build

frontend-dev:
	cd frontend && $(NPM) run dev

# Containerized launch. Override the engine with: COMPOSE="podman compose" make up
up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

# GPU launch (needs the NVIDIA Container Toolkit on the host).
up-cuda:
	$(CUDA_COMPOSE) up --build

down-cuda:
	$(CUDA_COMPOSE) down

logs:
	$(COMPOSE) logs -f

# Cut a release: validate, tag v$(VERSION) and push. Pushing the tag triggers
# CI to build/push the Docker image and create the GitHub Release from the
# matching CHANGELOG section. Bump the version in pyproject.toml + __init__.py
# and update CHANGELOG.md first.
release:
	@git diff-index --quiet HEAD -- || { echo "Working tree is dirty — commit first."; exit 1; }
	@test "$$(git rev-parse --abbrev-ref HEAD)" = "main" || { echo "Not on main."; exit 1; }
	@grep -q "^## \[$(VERSION)\]" CHANGELOG.md || { echo "No CHANGELOG section for $(VERSION)."; exit 1; }
	@git rev-parse -q --verify "refs/tags/v$(VERSION)" >/dev/null && { echo "Tag v$(VERSION) already exists."; exit 1; } || true
	$(MAKE) check
	git tag -a "v$(VERSION)" -m "Noctra v$(VERSION)"
	git push origin main
	git push origin "v$(VERSION)"
	@echo "Pushed v$(VERSION). CI will build the image and publish the GitHub Release."
