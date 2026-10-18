"""A SQLite registry of optimization results (brief section 12).

Two jobs: a cache that survives the session (`results`, keyed by `run_hash`), and a history of
runs (`optimization_runs` and `optimization_trials`, the tables the brief plans for Postgres), so
runs from different days can be compared. Standard library only; the optimizer never sees SQL.
"""

import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from b3core.metrics import Metrics

PHASES = ("in_sample", "out_of_sample")
_COMMIT_EVERY = 500  # one commit per trial would dominate a long search

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    run_hash TEXT PRIMARY KEY,
    strategy TEXT NOT NULL,
    data_version TEXT NOT NULL,
    params TEXT NOT NULL,
    metrics TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS optimization_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    strategy TEXT NOT NULL,
    objective TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    config TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS optimization_trials (
    run_id INTEGER NOT NULL REFERENCES optimization_runs(id),
    phase TEXT NOT NULL,
    trial_index INTEGER NOT NULL,
    run_hash TEXT NOT NULL REFERENCES results(run_hash),
    objective_value REAL,
    PRIMARY KEY (run_id, phase, trial_index)
);
"""


@dataclass(frozen=True)
class TrialInfo:
    """What a result belongs to. The metrics are the cache value; this is the bookkeeping."""

    strategy: str
    params: Mapping[str, Any]  # the full config, so a stored result can be reproduced
    data_version: str


class SqliteTrialStore:
    """`path` is a file, or ":memory:" for a throwaway store."""

    def __init__(self, path: str | Path) -> None:
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)
        self._pending = 0

    def get(self, key: str) -> Metrics | None:
        row = self._db.execute("SELECT metrics FROM results WHERE run_hash = ?", (key,)).fetchone()
        return None if row is None else Metrics(**json.loads(row[0]))

    def put(self, key: str, metrics: Metrics, info: TrialInfo) -> None:
        self._db.execute(
            "INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?)",
            (
                key,
                info.strategy,
                info.data_version,
                json.dumps(dict(info.params), sort_keys=True, default=str),
                json.dumps(metrics.to_dict()),  # inf is written as Infinity and read back
            ),
        )
        self._pending += 1
        if self._pending >= _COMMIT_EVERY:
            self.flush()

    def start_run(
        self,
        *,
        strategy: str,
        objective: str,
        label: str = "",
        algorithm: str = "",
        config: Mapping[str, Any] | None = None,
        created_at: str | None = None,
    ) -> int:
        """`created_at` comes from the caller: core never reads the clock."""
        cursor = self._db.execute(
            "INSERT INTO optimization_runs (label, strategy, objective, algorithm, config,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                label,
                strategy,
                objective,
                algorithm,
                json.dumps(dict(config or {}), sort_keys=True, default=str),
                created_at,
            ),
        )
        self.flush()
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    def record_trials(
        self, run_id: int, phase: str, trials: Iterable[tuple[int, str, float]]
    ) -> None:
        """`trials` are (index, run_hash, objective value); the hashes must already be stored."""
        if phase not in PHASES:
            raise ValueError(f"phase must be one of {PHASES}, got {phase!r}")
        self._db.executemany(
            "INSERT INTO optimization_trials VALUES (?, ?, ?, ?, ?)",
            [(run_id, phase, index, key, value) for index, key, value in trials],
        )
        self.flush()

    def flush(self) -> None:
        self._db.commit()
        self._pending = 0

    def close(self) -> None:
        self.flush()
        self._db.close()

    # --- reading back, for comparing runs ---------------------------------------------------

    def results(self) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT run_hash, strategy, data_version FROM results ORDER BY rowid", self._db
        )

    def runs(self) -> pd.DataFrame:
        """One row per run, with its in-sample trial count (report it next to the best)."""
        return pd.read_sql_query(
            "SELECT r.id, r.label, r.strategy, r.objective, r.algorithm, r.created_at,"
            " (SELECT COUNT(*) FROM optimization_trials t"
            "  WHERE t.run_id = r.id AND t.phase = 'in_sample') AS n_trials"
            " FROM optimization_runs r ORDER BY r.id",
            self._db,
        )

    def trials(self, run_id: int) -> pd.DataFrame:
        """A run's trials with their parameters and metrics as columns."""
        rows = self._db.execute(
            "SELECT t.phase, t.trial_index, t.run_hash, t.objective_value, r.params, r.metrics"
            " FROM optimization_trials t JOIN results r USING (run_hash)"
            " WHERE t.run_id = ? ORDER BY t.phase DESC, t.trial_index",
            (run_id,),
        ).fetchall()
        return pd.DataFrame(
            [
                {
                    "phase": phase,
                    "trial_index": index,
                    "run_hash": key,
                    "objective_value": value,
                    **json.loads(params),
                    **json.loads(metrics),
                }
                for phase, index, key, value, params, metrics in rows
            ]
        )
