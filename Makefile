PYTHON ?= python3
VENV ?= .venv

.PHONY: setup run once

setup:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip wheel setuptools && pip install -r requirements.txt

run:
	. $(VENV)/bin/activate && python assistant.py

once:
	. $(VENV)/bin/activate && python assistant.py --text "Hello from Ameego"
