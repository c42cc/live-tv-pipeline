.PHONY: install build smoke verify clean

VENV := .venv
PY := $(VENV)/bin/python

install:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip >/dev/null
	$(PY) -m pip install -r requirements.txt

# Full build: fetch + resolve + validate every declared stream + publish artifacts.
build:
	$(PY) -m pipeline.run --min-emitted 20

# Fast smoke test: cap candidates so it finishes in well under a minute.
smoke:
	$(PY) -m pipeline.run --limit 120 --min-emitted 5

# Acceptance: prove the artifacts are real (valid M3U, sampled streams truly play).
verify:
	$(PY) scripts/verify_artifacts.py

clean:
	rm -rf dist/*.tmp __pycache__ pipeline/__pycache__
