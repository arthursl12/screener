"""Fail when a committed notebook output looks like raw market data (CLAUDE.md rule 7).

Notebooks listed as published in `.gitattributes` (their `filter` is unset) may keep outputs, but
only derived results: tables of metrics, charts, counts. An output that holds a table with the
`open`, `high`, `low` and `close` columns is a dump of vendor candles, and is refused.

Usage: python tools/check_notebook_outputs.py [notebook ...]
With no argument it checks every notebook whose `filter` attribute is unset, that is the published
ones. The others are stripped by nbstripout when committed, so their local outputs never leave
the machine. Standard library only.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CANDLE_COLUMNS = ("open", "high", "low", "close")


def output_texts(output: dict) -> list[str]:
    """Every text a notebook output carries: stream text, plain text and html representations."""
    texts = []
    if output.get("output_type") == "stream":
        texts.append("".join(output.get("text", [])))
    for key in ("text/plain", "text/html"):
        value = output.get("data", {}).get(key)
        if value:
            texts.append("".join(value) if isinstance(value, list) else value)
    return texts


def looks_like_candles(text: str) -> bool:
    return all(re.search(rf"(?<![\w]){column}(?![\w])", text) for column in CANDLE_COLUMNS)


def problems(path: Path) -> list[str]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    found = []
    for number, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue
        for output in cell.get("outputs", []):
            if any(looks_like_candles(text) for text in output_texts(output)):
                found.append(
                    f"{path}: cell {number} prints a table with open/high/low/close columns"
                )
    return found


def published_notebooks() -> list[Path]:
    """The notebooks in `notebooks/` whose nbstripout filter is switched off in .gitattributes."""
    candidates = sorted((ROOT / "notebooks").glob("*.ipynb"))
    if not candidates:
        return []
    result = subprocess.run(
        ["git", "-C", str(ROOT), "check-attr", "filter", "--", *[str(p) for p in candidates]],
        capture_output=True,
        text=True,
        check=True,
    )
    unset = {
        line.rsplit(": filter: ", 1)[0]
        for line in result.stdout.splitlines()
        if line.endswith(": filter: unset")
    }
    return [p for p in candidates if str(p.relative_to(ROOT)) in unset or str(p) in unset]


def main(arguments: list[str]) -> int:
    paths = [Path(a) for a in arguments] or published_notebooks()
    found = [line for path in paths for line in problems(path)]
    for line in found:
        print(line, file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
