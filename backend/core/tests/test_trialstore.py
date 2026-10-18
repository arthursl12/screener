"""SQLite registry of optimization results (brief section 12): cache across sessions and history."""

import math
from pathlib import Path

import pytest
from helpers import make_config, random_walk_candles

from b3core.ifr2 import Ifr2Config
from b3core.metrics import compute_metrics
from b3core.optimizer import ParamRange, ParamSpace, TrialCache, optimize
from b3core.strategy import Ifr2Strategy
from b3core.trialstore import SqliteTrialStore, TrialInfo

INFO = TrialInfo(strategy="toy", params={"a": 1}, data_version="d1")
METRICS = compute_metrics([100, -50, 200], capital=1_000)


def test_metrics_round_trip_through_the_store() -> None:
    store = SqliteTrialStore(":memory:")

    store.put("k1", METRICS, INFO)

    assert store.get("k1") == METRICS
    assert store.get("missing") is None


def test_infinite_profit_factor_and_missing_fields_survive_the_round_trip() -> None:
    store = SqliteTrialStore(":memory:")
    all_wins = compute_metrics([10, 20], capital=1_000)  # profit factor is inf
    assert math.isinf(all_wins.profit_factor) and all_wins.cagr is None

    store.put("k", all_wins, INFO)

    assert store.get("k") == all_wins


def test_results_persist_in_the_file_across_sessions(tmp_path: Path) -> None:
    path = tmp_path / "trials.db"
    first = SqliteTrialStore(path)
    first.put("k1", METRICS, INFO)
    first.close()

    second = SqliteTrialStore(path)

    assert second.get("k1") == METRICS


def test_putting_the_same_hash_twice_keeps_one_row() -> None:
    store = SqliteTrialStore(":memory:")

    store.put("k1", METRICS, INFO)
    store.put("k1", METRICS, INFO)

    assert len(store.results()) == 1


def test_the_cache_reads_through_to_the_store_and_counts_hits() -> None:
    store = SqliteTrialStore(":memory:")
    store.put("k1", METRICS, INFO)
    cache = TrialCache(store)

    assert cache.get("k1") == METRICS
    assert cache.get("k1") == METRICS  # now from memory
    assert (cache.hits, cache.misses) == (2, 0)
    assert cache.get("nope") is None


def test_the_cache_writes_new_results_through_to_the_store() -> None:
    store = SqliteTrialStore(":memory:")
    cache = TrialCache(store)

    cache.put("k2", METRICS, INFO)

    assert store.get("k2") == METRICS
    assert cache.misses == 1


# --- through optimize ------------------------------------------------------------------------

CANDLES = random_walk_candles(600, seed=2)
BASE = Ifr2Config.preset()
SPACE = ParamSpace({"rsi_entry": ParamRange(10, 30, 10), "exit_mode": ["target", "rsi"]},
                   Ifr2Strategy())  # fmt: skip


def run(store: SqliteTrialStore, **kwargs):  # type: ignore[no-untyped-def]
    return optimize(
        CANDLES, BASE, SPACE, objective="score_v1", oos_fraction=0.3, top_n=2,
        cache=TrialCache(store), run_label="demo", **kwargs
    )  # fmt: skip


def test_a_second_session_recomputes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "t.db"
    first = SqliteTrialStore(path)
    a = run(first)
    first.close()

    cache = TrialCache(SqliteTrialStore(path))
    b = optimize(CANDLES, BASE, SPACE, objective="score_v1", oos_fraction=0.3, top_n=2, cache=cache)

    assert cache.misses == 0
    assert cache.hits > 0
    assert a.trials == b.trials


def test_a_cached_search_is_free_even_under_a_tiny_budget(tmp_path: Path) -> None:
    store = SqliteTrialStore(tmp_path / "t.db")
    run(store)

    again = optimize(
        CANDLES, BASE, SPACE, objective="score_v1", oos_fraction=0.3, top_n=2,
        cache=TrialCache(store), max_evaluations=0,
    )  # fmt: skip

    assert again.n_trials == 6


def test_every_run_is_recorded_with_its_trials_and_phases() -> None:
    store = SqliteTrialStore(":memory:")

    first = run(store, created_at="2026-10-18")
    second = run(store, created_at="2026-10-19")

    runs = store.runs()
    assert list(runs["label"]) == ["demo", "demo"]
    assert list(runs["created_at"]) == ["2026-10-18", "2026-10-19"]
    assert (runs["strategy"] == "ifr2_compra").all()
    assert runs["n_trials"].tolist() == [6, 6]
    assert (first.run_id, second.run_id) == (1, 2)

    trials = store.trials(first.run_id)
    assert (trials["phase"] == "in_sample").sum() == 6
    assert (trials["phase"] == "out_of_sample").sum() == 2
    assert {"rsi_entry", "exit_mode", "objective_value", "n_trades", "run_hash"} <= set(
        trials.columns
    )
    # the same combinations in the two runs share their results rows
    assert len(store.results()) == 6 + 2  # six in-sample, two distinct out-of-sample
    assert set(store.trials(first.run_id)["run_hash"]) == set(
        store.trials(second.run_id)["run_hash"]
    )


def test_without_a_store_nothing_is_recorded() -> None:
    result = optimize(CANDLES, BASE, SPACE, oos_fraction=0.0)

    assert result.run_id is None


def test_a_123_run_can_use_the_same_store() -> None:
    store = SqliteTrialStore(":memory:")
    space = ParamSpace({"target_mult": ParamRange(1, 2, 1)})

    result = optimize(CANDLES, make_config(), space, oos_fraction=0.0, cache=TrialCache(store))

    assert store.runs()["strategy"].tolist() == ["123_compra"]
    assert result.run_id == 1


def test_the_store_rejects_a_phase_it_does_not_know() -> None:
    store = SqliteTrialStore(":memory:")
    run_id = store.start_run(strategy="toy", objective="result")

    with pytest.raises(ValueError, match="phase"):
        store.record_trials(run_id, "training", [])


def test_results_are_committed_after_each_batch_so_a_crash_loses_nothing(tmp_path: Path) -> None:
    class Crashing:
        def search(self, space, evaluate):  # type: ignore[no-untyped-def]
            evaluate([0, 1])
            raise RuntimeError("the machine died")

    path = tmp_path / "t.db"
    store = SqliteTrialStore(path)  # never closed: a crash does not close it

    with pytest.raises(RuntimeError):
        optimize(CANDLES, BASE, SPACE, algorithm=Crashing(), oos_fraction=0.0,
                 cache=TrialCache(store))  # fmt: skip

    assert len(SqliteTrialStore(path).results()) == 2
