.PHONY: test lint fmt notebook

BACKEND := backend

test:
	cd $(BACKEND) && uv run pytest

lint:
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check . && uv run mypy core/src

fmt:
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .

notebook:
	cd $(BACKEND) && uv run jupyter lab --notebook-dir=../notebooks
