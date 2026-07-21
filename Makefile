PYTHON ?= python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: setup test api

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements.txt

test:
	DATABASE_URL=sqlite:///./custody_test.db $(BIN)/python -m pytest -q

api:
	$(BIN)/uvicorn app.main:app --reload
