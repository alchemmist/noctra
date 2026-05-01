UV ?= uv
PY ?= main.py
MODEL ?= large-v3
LANGUAGE ?= ru
DEVICE ?= cpu
COMPUTE_TYPE ?= int8
HOST ?= 127.0.0.1
PORT ?= 8787
FILES ?=

.PHONY: serve run model

serve:
	$(UV) run $(PY) --serve --model $(MODEL) --language $(LANGUAGE) --device $(DEVICE) --compute-type $(COMPUTE_TYPE) --host $(HOST) --port $(PORT)

run:
	$(UV) run $(PY) --model $(MODEL) --language $(LANGUAGE) --device $(DEVICE) --compute-type $(COMPUTE_TYPE) $(FILES)

model:
	$(UV) run $(PY) --download-model --model $(MODEL) --language $(LANGUAGE) --device $(DEVICE) --compute-type $(COMPUTE_TYPE)
