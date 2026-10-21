"""The guard that keeps raw candles out of published notebooks (CLAUDE.md rule 7)."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "check_notebook_outputs.py"
spec = importlib.util.spec_from_file_location("check_notebook_outputs", SCRIPT)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def notebook(tmp_path: Path, output: dict) -> Path:
    path = tmp_path / "n.ipynb"
    path.write_text(json.dumps({"cells": [{"cell_type": "code", "outputs": [output]}]}))
    return path


def plain(text: str) -> dict:
    return {"output_type": "execute_result", "data": {"text/plain": [text]}}


def test_a_table_of_candles_is_refused(tmp_path: Path) -> None:
    path = notebook(tmp_path, plain("        open   high    low  close\n0  10.0  10.2  9.9  10.1"))

    assert guard.problems(path)


def test_derived_columns_with_similar_names_pass(tmp_path: Path) -> None:
    path = notebook(tmp_path, plain("is_cagr  open_units  close_to  high_water  low_risk"))

    assert guard.problems(path) == []


@pytest.mark.parametrize("kind", ["candlestick", "ohlc"])
def test_a_candlestick_chart_is_refused(tmp_path: Path, kind: str) -> None:
    figure = {"data": [{"type": kind, "x": ["2024-01-02"]}], "layout": {}}
    path = notebook(
        tmp_path,
        {"output_type": "display_data", "data": {"application/vnd.plotly.v1+json": figure}},
    )

    assert guard.problems(path)


def test_a_line_chart_passes(tmp_path: Path) -> None:
    figure = {"data": [{"type": "scatter", "x": ["2024-01-02"], "y": [100.0]}], "layout": {}}
    path = notebook(
        tmp_path,
        {"output_type": "display_data", "data": {"application/vnd.plotly.v1+json": figure}},
    )

    assert guard.problems(path) == []
