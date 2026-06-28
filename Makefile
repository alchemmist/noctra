UV ?= uv
NPM ?= npm
COMPOSE ?= docker compose
CUDA_COMPOSE ?= $(COMPOSE) -f compose.cuda.yaml
MODEL ?= large-v3
LANGUAGE ?= ru
DEVICE ?= cpu
COMPUTE_TYPE ?= int8
HOST ?= 127.0.0.1
PORT ?= 8787
FILES ?=

RUN = $(UV) run python -m noctra

.PHONY: serve run model test lint fmt typecheck check install install-cli up down logs \
        up-cuda down-cuda frontend-install frontend-build frontend-dev

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
