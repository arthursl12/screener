"""Parameter optimizer (brief section 12). Pure: seeded randomness, no clock, no queue or web code.

Every algorithm implements `Optimizer.search(space, evaluate)`. `evaluate` takes a batch of
combination indices and returns their trials, so the cache, the process pool and the evaluation
budget live in one place. Grid and random search call it once; an adaptive algorithm such as a
genetic search calls it once per generation.
"""

import hashlib
import json
import math
import multiprocessing
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from typing import Any, Protocol, cast

import numpy as np
import pandas as pd

from b3core.data import Timeframe
from b3core.metrics import Metrics, compute_metrics
from b3core.score import score_v1
from b3core.strategy import STRATEGY_123, Strategy
from b3core.trialstore import SqliteTrialStore, TrialInfo

ENGINE_VERSION = "0.1.0"
COST_MODEL_VERSION = 0  # costs are not implemented yet: all default to zero

OBJECTIVES = ("result", "profit_factor", "ev", "min_drawdown", "score_v1")

# Brief section 12: ~180 combinations is cheap; ~11,500 is where a genetic search pays off.
GRID_RECOMMENDED_LIMIT = 5_000

Number = int | float


# --- parameter space -------------------------------------------------------------------------


@dataclass(frozen=True)
class ParamRange:
    """Values `start + i * step` for i in 0..size-1, built from the integer index (no drift)."""

    start: Number
    stop: Number
    step: Number

    def __post_init__(self) -> None:
        if self.step <= 0:
            raise ValueError("step must be positive")
        if self.stop < self.start:
            raise ValueError("stop must be at least start")

    @property
    def size(self) -> int:
        return math.floor((self.stop - self.start) / self.step + 1e-9) + 1

    def values(self) -> list[Number]:
        if all(isinstance(v, int) for v in (self.start, self.stop, self.step)):
            return [int(self.start + i * self.step) for i in range(self.size)]
        return [round(self.start + i * self.step, 10) for i in range(self.size)]


ParamSpec = ParamRange | Sequence[Any] | int | float | str | bool | None


class ParamSpace:
    """Named axes: a fixed value, a ParamRange, or a list of options. Combinations are indexed."""

    def __init__(self, params: Mapping[str, ParamSpec], strategy: Strategy = STRATEGY_123) -> None:
        self.strategy = strategy
        self._fields = {f.name: f for f in fields(strategy.config_type)}
        self._axes: dict[str, list[Any]] = {}
        self._valid: list[int] | None = None  # raw indices that survive `restricted`
        for name, spec in params.items():
            if name not in self._fields:
                raise ValueError(f"unknown parameter {name!r}")
            if isinstance(spec, ParamRange):
                axis: list[Any] = list(spec.values())
            elif isinstance(spec, list | tuple):
                axis = list(spec)
            else:
                axis = [spec]
            if not axis:
                raise ValueError(f"parameter {name!r} has no values")
            self._axes[name] = axis

    @property
    def names(self) -> list[str]:
        return list(self._axes)

    def to_dict(self) -> dict[str, list[Any]]:
        return {name: list(axis) for name, axis in self._axes.items()}

    @property
    def _raw_size(self) -> int:
        return math.prod(len(axis) for axis in self._axes.values())

    @property
    def size(self) -> int:
        return self._raw_size if self._valid is None else len(self._valid)

    def decode(self, index: int) -> dict[str, Any]:
        """The index-th combination, last parameter varying fastest."""
        if not 0 <= index < self.size:
            raise IndexError(f"index {index} outside a space of {self.size} combinations")
        return self._decode_raw(index if self._valid is None else self._valid[index])

    def _decode_raw(self, index: int) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for name in reversed(self.names):
            axis = self._axes[name]
            index, position = divmod(index, len(axis))
            params[name] = axis[position]
        return dict(reversed(params.items()))

    def build_config(self, base: Any, params: Mapping[str, Any]) -> Any:
        merged = base.to_dict()
        for name, value in params.items():
            merged[name] = self._cast(name, value)
        return self.strategy.config_type(**merged)

    def _cast(self, name: str, value: Any) -> Any:
        kind = self._fields[name].type
        if kind is int:
            if isinstance(value, bool) or not float(value).is_integer():
                raise ValueError(f"{name} must be an integer, got {value!r}")
            return int(value)
        if kind is float:
            return float(value)
        return value

    def restricted(self, base: Any) -> "ParamSpace":
        """A copy without the combinations the strategy rejects (its `combination_is_valid`).

        Such combinations are relations between parameters, so they are dropped before
        evaluation (brief section 12, rule 1) and not rejected one value at a time.
        """
        constrained = [n for n in self.strategy.constrained_params if n in self._axes]
        if not constrained:
            return self
        valid = [
            raw
            for raw in range(self._raw_size)
            if self.strategy.combination_is_valid(
                base, {k: v for k, v in self._decode_raw(raw).items() if k in constrained}
            )
        ]
        if not valid:
            raise ValueError(f"no combination has a valid {self.strategy.restriction}")
        copy = ParamSpace({name: list(axis) for name, axis in self._axes.items()}, self.strategy)
        copy._valid = valid
        return copy

    def validate(self, base: Any) -> None:
        """Build a config for every axis value, so bad ranges fail before any backtest runs.

        The constrained parameters are checked together by `restricted`, not one at a time.
        """
        for name, axis in self._axes.items():
            if name in self.strategy.constrained_params:
                continue
            for value in axis:
                self.build_config(base, {name: value})


@dataclass(frozen=True)
class SpaceInfo:
    size: int
    recommendation: str  # "grid" or "genetic"


def describe_space(space: ParamSpace, base: Any = None) -> SpaceInfo:
    """Report the search-space size before running, and which algorithm suits it.

    Pass `base` to count only the combinations with a valid entry window.
    """
    if base is not None:
        space = space.restricted(base)
    return SpaceInfo(
        size=space.size,
        recommendation="grid" if space.size <= GRID_RECOMMENDED_LIMIT else "genetic",
    )


# --- objectives, constraints, hashing --------------------------------------------------------


def objective_value(metrics: Metrics, objective: str) -> float:
    """Every objective is maximised, so minimum drawdown is returned negated."""
    if objective == "result":
        return metrics.result
    if objective == "profit_factor":
        return metrics.profit_factor
    if objective == "ev":
        return metrics.ev
    if objective == "min_drawdown":
        return -metrics.max_drawdown
    if objective == "score_v1":
        return score_v1(metrics)
    raise ValueError(f"unknown objective {objective!r}, expected one of {OBJECTIVES}")


@dataclass(frozen=True)
class Constraints:
    min_trades: int = 0
    max_drawdown: float | None = None

    def satisfied(self, metrics: Metrics) -> bool:
        if metrics.n_trades < self.min_trades:
            return False
        return self.max_drawdown is None or metrics.max_drawdown <= self.max_drawdown


def _hash_candles(digest: "hashlib._Hash", candles: pd.DataFrame) -> None:
    utc_ns = candles["ts"].dt.tz_convert("UTC").dt.tz_localize(None).astype("datetime64[ns]")
    digest.update(utc_ns.to_numpy().astype(np.int64).tobytes())
    for column in ("open", "high", "low", "close", "volume"):
        digest.update(candles[column].to_numpy(dtype=np.float64).tobytes())


def data_fingerprint(
    candles: pd.DataFrame,
    intraday: pd.DataFrame | None = None,
    timeframe: Timeframe | None = None,
) -> str:
    """SHA-256 over the candle values, the timeframe and the finer candles, never over indexes."""
    digest = hashlib.sha256()
    _hash_candles(digest, candles)
    digest.update(b"|timeframe:" + (timeframe.value.encode() if timeframe else b"none"))
    digest.update(b"|intraday:")
    if intraday is not None:
        _hash_candles(digest, intraday)
    return digest.hexdigest()


def run_hash(config: Any, data_version: str, strategy: Strategy = STRATEGY_123) -> str:
    """SHA-256 over everything that determines a result (brief section 9)."""
    payload = {
        "strategy": strategy.id,
        "strategy_version": strategy.version,
        "params": config.to_dict(),
        "data_version": data_version,
        "cost_model_version": COST_MODEL_VERSION,
        "engine_version": ENGINE_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


# --- evaluation ------------------------------------------------------------------------------


class BudgetExceeded(RuntimeError):
    """The search asked for more backtests than the evaluation budget allows."""


@dataclass(frozen=True)
class Trial:
    index: int
    params: dict[str, Any]
    run_hash: str
    metrics: Metrics
    objective: float
    feasible: bool


class TrialCache:
    """Map from run_hash to metrics. Repeated individuals and re-runs cost nothing.

    In memory by default. With a `store` it also reads through to it and writes new results to
    it, so a later session starts warm.
    """

    def __init__(self, store: SqliteTrialStore | None = None) -> None:
        self._metrics: dict[str, Metrics] = {}
        self.store = store
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Metrics | None:
        found = self._metrics.get(key)
        if found is None and self.store is not None:
            found = self.store.get(key)
            if found is not None:
                self._metrics[key] = found
        if found is not None:
            self.hits += 1
        return found

    def put(self, key: str, metrics: Metrics, info: TrialInfo | None = None) -> None:
        self._metrics[key] = metrics
        if self.store is not None and info is not None:
            self.store.put(key, metrics, info)
        self.misses += 1

    def flush(self) -> None:
        if self.store is not None:
            self.store.flush()


Evaluate = Callable[[Sequence[int]], list[Trial]]

_pool_data: tuple[Strategy, pd.DataFrame, Timeframe | None, pd.DataFrame | None] | None = None


def _init_pool(
    strategy: Strategy,
    candles: pd.DataFrame,
    timeframe: Timeframe | None,
    intraday: pd.DataFrame | None,
) -> None:
    global _pool_data
    _pool_data = (strategy, candles, timeframe, intraday)


def _pool_task(config: Any) -> Metrics:
    assert _pool_data is not None
    strategy, candles, timeframe, intraday = _pool_data
    return strategy.run(candles, config, timeframe=timeframe, intraday=intraday)


class _Evaluator:
    def __init__(
        self,
        candles: pd.DataFrame,
        base: Any,
        space: ParamSpace,
        objective: str,
        constraints: Constraints,
        workers: int,
        cache: TrialCache,
        max_evaluations: int | None,
        timeframe: Timeframe | None = None,
        intraday: pd.DataFrame | None = None,
    ) -> None:
        self._strategy = space.strategy
        self._candles = candles
        self._timeframe = timeframe
        self._intraday = intraday
        self._base = base
        self._space = space
        self._objective = objective
        self._constraints = constraints
        self._workers = workers
        self._cache = cache
        self._budget = max_evaluations
        self._used = 0
        self._fingerprint = data_fingerprint(candles, intraday, timeframe)

    def __call__(self, indices: Sequence[int]) -> list[Trial]:
        params = [self._space.decode(i) for i in indices]
        configs = [self._space.build_config(self._base, p) for p in params]
        hashes = [run_hash(c, self._fingerprint, self._strategy) for c in configs]

        found: dict[str, Metrics] = {}
        missing: dict[str, Any] = {}
        for key, config in zip(hashes, configs, strict=True):
            if key in found or key in missing:
                continue
            cached = self._cache.get(key)
            if cached is not None:
                found[key] = cached
            else:
                missing[key] = config

        if self._budget is not None and self._used + len(missing) > self._budget:
            raise BudgetExceeded(
                f"{self._used + len(missing)} evaluations needed, budget is {self._budget}"
            )
        self._used += len(missing)

        for key, metrics in zip(missing, self._run(list(missing.values())), strict=True):
            info = TrialInfo(self._strategy.id, missing[key].to_dict(), self._fingerprint)
            self._cache.put(key, metrics, info)
            found[key] = metrics
        self._cache.flush()

        return [
            Trial(
                index=index,
                params=p,
                run_hash=key,
                metrics=found[key],
                objective=objective_value(found[key], self._objective),
                feasible=self._constraints.satisfied(found[key]),
            )
            for index, p, key in zip(indices, params, hashes, strict=True)
        ]

    def _run(self, configs: list[Any]) -> list[Metrics]:
        if self._workers <= 1 or len(configs) < 2:
            return [
                self._strategy.run(
                    self._candles, c, timeframe=self._timeframe, intraday=self._intraday
                )
                for c in configs
            ]
        with ProcessPoolExecutor(
            max_workers=self._workers,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_init_pool,
            initargs=(self._strategy, self._candles, self._timeframe, self._intraday),
        ) as pool:
            return list(pool.map(_pool_task, configs))


# --- algorithms ------------------------------------------------------------------------------


class Optimizer(Protocol):
    def search(self, space: ParamSpace, evaluate: Evaluate) -> list[Trial]: ...


class GridSearch:
    """Evaluate every combination: slow on big spaces, but it gives the full map of results."""

    def search(self, space: ParamSpace, evaluate: Evaluate) -> list[Trial]:
        return evaluate(range(space.size))


@dataclass(frozen=True)
class RandomSearch:
    """Sample combinations without repeats from a seeded generator."""

    seed: int
    n_samples: int

    def search(self, space: ParamSpace, evaluate: Evaluate) -> list[Trial]:
        rng = np.random.default_rng(self.seed)
        count = min(self.n_samples, space.size)
        chosen = rng.choice(space.size, size=count, replace=False)
        return evaluate(sorted(int(i) for i in chosen))


# --- split, validation and results -----------------------------------------------------------


def split_candles(candles: pd.DataFrame, oos_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split: the first part is in-sample, the last `oos_fraction` out-of-sample."""
    if not 0 <= oos_fraction < 1:
        raise ValueError("oos_fraction must be in [0, 1)")
    cut = len(candles) - round(len(candles) * oos_fraction)
    return (
        candles.iloc[:cut].reset_index(drop=True),
        candles.iloc[cut:].reset_index(drop=True),
    )


def flag_drop(in_sample: float, out_of_sample: float, threshold: float = 0.5) -> bool:
    """True when the out-of-sample objective lost more than (1 - threshold) of the in-sample one.

    Written with an absolute value so it also works for negative objectives (negated drawdown).
    """
    if math.isinf(in_sample):
        return out_of_sample < in_sample
    return out_of_sample < in_sample - (1 - threshold) * abs(in_sample)


@dataclass(frozen=True)
class ValidationRow:
    rank: int
    index: int
    params: dict[str, Any]
    in_sample: Trial
    out_of_sample: Trial
    dropped: bool


_METRIC_COLUMNS = ("n_trades", "win_rate", "result", "profit_factor", "ev", "max_drawdown")


@dataclass(frozen=True)
class OptimizationResult:
    objective: str
    names: list[str]
    trials: list[Trial]  # in-sample trials, in evaluation order
    validation: list[ValidationRow] = field(default_factory=list)
    run_id: int | None = None  # set when the cache has a store: the run's id in its history

    @property
    def n_trials(self) -> int:
        """Report this next to the best result: the best of many trials is partly luck."""
        return len(self.trials)

    def ranked_trials(self) -> list[Trial]:
        return sorted(self.trials, key=lambda t: (not t.feasible, -t.objective, t.index))

    @property
    def best(self) -> Trial:
        return self.ranked_trials()[0]

    def trials_table(self) -> pd.DataFrame:
        rows = [
            {
                "index": t.index,
                **{name: t.params[name] for name in self.names},
                "objective": t.objective,
                "feasible": t.feasible,
                **{m: getattr(t.metrics, m) for m in _METRIC_COLUMNS},
                "run_hash": t.run_hash,
                "phase": "in_sample",
            }
            for t in self.trials
        ]
        return pd.DataFrame(rows)

    def validation_table(self) -> pd.DataFrame:
        rows = [
            {
                "rank": v.rank,
                "index": v.index,
                **{name: v.params[name] for name in self.names},
                "is_objective": v.in_sample.objective,
                "oos_objective": v.out_of_sample.objective,
                "is_trades": v.in_sample.metrics.n_trades,
                "oos_trades": v.out_of_sample.metrics.n_trades,
                "is_result": v.in_sample.metrics.result,
                "oos_result": v.out_of_sample.metrics.result,
                "dropped": v.dropped,
            }
            for v in self.validation
        ]
        return pd.DataFrame(rows)


def optimize(
    candles: pd.DataFrame,
    base_config: Any,
    space: ParamSpace,
    *,
    objective: str = "result",
    constraints: Constraints | None = None,
    algorithm: Optimizer | None = None,
    oos_fraction: float = 0.3,
    top_n: int = 5,
    workers: int = 1,
    max_evaluations: int | None = None,
    cache: TrialCache | None = None,
    timeframe: Timeframe | None = None,
    intraday: pd.DataFrame | None = None,
    run_label: str = "",
    created_at: str | None = None,
) -> OptimizationResult:
    """Search in-sample, then re-run the best `top_n` feasible results out-of-sample.

    With `oos_fraction=0` the search uses all candles and nothing is validated. Day-trade runs
    need the candles' `timeframe`; `intraday` (finer candles) is split at the same cut in time.
    When `cache` has a store, the run and its trials are also written to its history, labelled
    with `run_label` and `created_at` (the caller supplies the date: core never reads the clock).
    """
    objective_value(compute_metrics([], 1.0), objective)  # fail fast on an unknown objective
    if not isinstance(base_config, space.strategy.config_type):
        raise TypeError(
            f"base_config is a {type(base_config).__name__}, "
            f"but the space belongs to strategy {space.strategy.id!r}"
        )
    space = space.restricted(base_config)
    space.validate(base_config)

    constraints = constraints or Constraints()
    algorithm = algorithm or GridSearch()
    cache = cache if cache is not None else TrialCache()
    in_sample, out_of_sample = split_candles(candles, oos_fraction)
    in_intraday, out_intraday = intraday, intraday
    if intraday is not None and len(out_of_sample):
        cut = out_of_sample["ts"].iloc[0]
        in_intraday = intraday[intraday["ts"] < cut].reset_index(drop=True)
        out_intraday = intraday[intraday["ts"] >= cut].reset_index(drop=True)

    search = _Evaluator(
        in_sample,
        base_config,
        space,
        objective,
        constraints,
        workers,
        cache,
        max_evaluations,
        timeframe,
        in_intraday,
    )
    trials = algorithm.search(space, search)
    result = OptimizationResult(objective=objective, names=space.names, trials=trials)

    def record(final: OptimizationResult) -> OptimizationResult:
        if cache.store is None:
            return final
        run_id = cache.store.start_run(
            strategy=space.strategy.id,
            objective=objective,
            label=run_label,
            algorithm=type(algorithm).__name__,
            config={
                "base": cast(Any, base_config).to_dict(),
                "space": space.to_dict(),
                "constraints": asdict(constraints),
                "algorithm": asdict(algorithm) if is_dataclass(algorithm) else {},
                "oos_fraction": oos_fraction,
                "top_n": top_n,
            },
            created_at=created_at,
        )
        cache.store.record_trials(
            run_id, "in_sample", [(t.index, t.run_hash, t.objective) for t in final.trials]
        )
        cache.store.record_trials(
            run_id,
            "out_of_sample",
            [
                (v.index, v.out_of_sample.run_hash, v.out_of_sample.objective)
                for v in final.validation
            ],
        )
        return replace(final, run_id=run_id)

    if oos_fraction == 0:
        return record(result)

    validate = _Evaluator(
        out_of_sample,
        base_config,
        space,
        objective,
        constraints,
        workers,
        cache,
        None,
        timeframe,
        out_intraday,
    )
    top = [t for t in result.ranked_trials() if t.feasible][:top_n]
    out_trials = validate([t.index for t in top])
    rows = [
        ValidationRow(
            rank=rank,
            index=ins.index,
            params=ins.params,
            in_sample=ins,
            out_of_sample=oos,
            dropped=flag_drop(ins.objective, oos.objective),
        )
        for rank, (ins, oos) in enumerate(zip(top, out_trials, strict=True), start=1)
    ]
    return record(
        OptimizationResult(objective=objective, names=space.names, trials=trials, validation=rows)
    )
