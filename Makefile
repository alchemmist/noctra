UV ?= uv
MODEL ?= large-v3
LANGUAGE ?= ru
DEVICE ?= cpu
COMPUTE_TYPE ?= int8
HOST ?= 127.0.0.1
PORT ?= 8787
FILES ?=

RUN = $(UV) run python -m noctra

.PHONY: serve run model test lint fmt typecheck check install

install:
	$(UV) sync --extra dev

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
