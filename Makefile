.PHONY: test lint fmt notebook check-notebooks

BACKEND := backend

test:
	cd $(BACKEND) && uv run pytest

lint: check-notebooks
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check . && uv run mypy core/src

# Published notebooks keep their outputs, but never a table of raw candles (CLAUDE.md rule 7).
check-notebooks:
	cd $(BACKEND) && uv run python ../tools/check_notebook_outputs.py

fmt:
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .

notebook:
	cd $(BACKEND) && uv run jupyter lab --notebook-dir=../notebooks
