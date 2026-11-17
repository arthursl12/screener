"""Parameter search for the intraday momentum strategy on WIN and WDO (brief section 10).

Pure and seeded: the same seed gives the same sample of combinations and the same scores. The
clock, the process pool and the progress bar live in the notebook that runs it, never here.

A trial is one combination of the eight searched parameters, run on each instrument with that
instrument's point value and costs. Its daily returns and sides are kept, and everything else
(the Sharpe ratio of the whole period, of a year, the worse of the two instruments) is computed
from them, so the same trials serve every mode and every fold.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from b3core.intraday_momentum import IntradayConfig, run_intraday_momentum

# The owner's grid (brief section 10). `exit_minute` 1440 is "no exit time": the last bar.
SPACE: dict[str, list[object]] = {
    "lookback": [5, 10, 14, 20, 30, 45, 60, 90],
    "band_mult": [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0],
    "trade_freq": [15, 30, 60],
    "first_decision": [540, 570, 600, 630, 660, 720],
    "exit_minute": [960, 990, 1020, 1050, 1080, 1100, 1440],
    "stop": ["vwap_band", "current_band", "opposite_band", "vwap_only"],
    "stop_check": ["grid", "every_bar"],
    "sides": ["both", "long", "short"],
}


@dataclass(frozen=True)
class Instrument:
    symbol: str
    point_value: float  # reais per index point
    fee_per_side: float  # B3 fee per contract and side, reais
    tick_reais: float  # one tick, reais per contract


INSTRUMENTS = {
    "WIN": Instrument("WIN$N", point_value=0.20, fee_per_side=0.25, tick_reais=1.00),
    "WDO": Instrument("WDO$N", point_value=10.0, fee_per_side=1.20, tick_reais=5.00),
}


def space_size() -> int:
    return math.prod(len(values) for values in SPACE.values())


def _digits(index: int) -> list[int]:
    digits = []
    for values in reversed(SPACE.values()):
        index, digit = divmod(index, len(values))
        digits.append(digit)
    return digits[::-1]


def decode(index: int) -> dict[str, object]:
    """The index-th combination, the last parameter varying fastest."""
    if not 0 <= index < space_size():
        raise IndexError(f"index {index} outside a space of {space_size()} combinations")
    return {name: SPACE[name][digit] for name, digit in zip(SPACE, _digits(index), strict=True)}


def encode(params: Mapping[str, object]) -> int:
    index = 0
    for name, values in SPACE.items():
        index = index * len(values) + values.index(params[name])
    return index


def sample_indices(count: int, seed: int) -> list[int]:
    """`count` different combinations, drawn with a seeded generator."""
    drawn = np.random.default_rng(seed).choice(space_size(), size=count, replace=False)
    return [int(i) for i in drawn]


def neighbours(index: int) -> list[int]:
    """The combinations one step away on one parameter (no wrap-around), for a plateau view."""
    digits = _digits(index)
    out = []
    for position, values in enumerate(SPACE.values()):
        for step in (-1, 1):
            moved = digits[position] + step
            if 0 <= moved < len(values):
                changed = list(digits)
                changed[position] = moved
                out.append(encode({n: SPACE[n][d] for n, d in zip(SPACE, changed, strict=True)}))
    return out


def make_config(
    params: Mapping[str, object],
    instrument: str,
    *,
    slippage_ticks: float,
    capital: float = 100_000.0,
    margin: float = 1_000.0,
) -> IntradayConfig:
    """The strategy's settings for one instrument. The sizing is fixed at the paper's values
    (2% volatility target, leverage cap 4) and the cost is the B3 fee plus the slippage."""
    inst = INSTRUMENTS[instrument]
    lookback = int(params["lookback"])  # type: ignore[call-overload]
    return IntradayConfig(
        lookback=lookback,
        min_days=max(1, lookback - 1),
        band_mult=float(params["band_mult"]),  # type: ignore[arg-type]
        trade_freq=int(params["trade_freq"]),  # type: ignore[call-overload]
        first_decision=int(params["first_decision"]),  # type: ignore[call-overload]
        exit_minute=int(params["exit_minute"]),  # type: ignore[call-overload]
        stop=str(params["stop"]),
        stop_check=str(params["stop_check"]),
        sides=str(params["sides"]),
        capital=capital,
        target_vol=0.02,
        max_leverage=4.0,
        point_value=inst.point_value,
        fee_per_side=inst.fee_per_side + slippage_ticks * inst.tick_reais,
        margin_per_contract=margin,
    )


def run_trial(
    bars: Mapping[str, pd.DataFrame],
    params: Mapping[str, object],
    days: pd.DatetimeIndex,
    *,
    slippage_ticks: float,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Daily net returns (NaN without a sigma) and sides traded, per instrument, on `days`."""
    returns: dict[str, np.ndarray] = {}
    sides: dict[str, np.ndarray] = {}
    for name, frame in bars.items():
        result = run_intraday_momentum(
            frame, make_config(params, name, slippage_ticks=slippage_ticks)
        )
        returns[name] = result["ret"].reindex(days).to_numpy(dtype=np.float64)
        sides[name] = result["trades"].reindex(days).to_numpy(dtype=np.float64)
    return returns, sides


@dataclass(frozen=True)
class TrialSet:
    """Many trials of one search: rows are trials, columns are days."""

    indices: np.ndarray  # the combination index of each trial
    days: pd.DatetimeIndex
    ret: dict[str, np.ndarray]  # instrument -> (trials, days), NaN where nothing was traded
    sides: dict[str, np.ndarray]  # instrument -> (trials, days)


def sharpe_by_trial(returns: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Annualised Sharpe ratio (daily mean over standard deviation with n - 1, times the root of
    252) of each row, over the days in `mask`; NaN for a flat row."""
    x = returns[:, mask]
    spread = x.std(axis=1, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = x.mean(axis=1) / spread * math.sqrt(252)
    return np.where(spread > 1e-12, out, np.nan)


def fold_of(days: pd.DatetimeIndex) -> np.ndarray:
    """The calendar-year fold of each day; the days of 2021 (December) join 2022."""
    return np.maximum(np.asarray(days.year), 2022)


def _flat(values: np.ndarray) -> np.ndarray:
    return np.nan_to_num(values, nan=0.0)  # a day without a sigma is a flat day


def scores(trials: TrialSet, mask: np.ndarray, mode: str, min_trades: int) -> np.ndarray:
    """The objective of every trial over the days in `mask`: the Sharpe ratio of one instrument,
    or, for `joint`, the worse of the two. A trial with fewer than `min_trades` round trips in
    the mask (in any instrument it is scored on) gets NaN."""
    names = ["WIN", "WDO"] if mode == "joint" else [mode]
    ok = np.ones(len(trials.indices), dtype=bool)
    per_instrument = []
    for name in names:
        per_instrument.append(sharpe_by_trial(_flat(trials.ret[name]), mask))
        ok &= trials.sides[name][:, mask].sum(axis=1) / 2.0 >= min_trades
    combined = per_instrument[0]
    for other in per_instrument[1:]:
        combined = np.minimum(combined, other)
    return np.where(ok, combined, np.nan)


def portfolio_sharpe(trials: TrialSet, mask: np.ndarray) -> np.ndarray:
    """Sharpe ratio of the 50/50 average of the two instruments' daily returns."""
    average = (_flat(trials.ret["WIN"]) + _flat(trials.ret["WDO"])) / 2.0
    return sharpe_by_trial(average, mask)


def leave_one_year_out(trials: TrialSet, mode: str, min_trades: int) -> pd.DataFrame:
    """For each calendar year: pick the best trial on the other years, then score it on the year.

    Columns: the held-out year, the winner (its position in the trial set, NaN when none passes
    the trade minimum), its training and test scores, the median test score of all trials (what a
    random pick would get) and the percentile of the winner's test score among them.
    """
    folds = fold_of(trials.days)
    rows = []
    for year in sorted(set(folds)):
        test = folds == year
        train_scores = scores(trials, ~test, mode, min_trades)
        test_scores = scores(trials, test, mode, 0)
        finite = test_scores[np.isfinite(test_scores)]
        if not np.isfinite(train_scores).any():
            median = float(np.median(finite)) if finite.size else math.nan
            rows.append((year, math.nan, math.nan, math.nan, median, math.nan))
            continue
        winner = int(np.nanargmax(train_scores))
        value = test_scores[winner]
        percentile = float((finite <= value).mean() * 100) if np.isfinite(value) else math.nan
        median_test = float(np.median(finite)) if finite.size else math.nan
        rows.append((year, float(winner), train_scores[winner], value, median_test, percentile))
    return pd.DataFrame(
        rows, columns=["held out", "winner", "train", "test", "median test", "percentile"]
    )


def scramble_bars(bars: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The bars with the order of each day's moves shuffled: a baseline with no edge.

    Each bar is kept as a step from the previous close (and the shape of its high and low), and the
    steps of a day are put in a random order. A day keeps its open, its last close, its volume and
    the set of its moves, but any dependence between one move and the next, and the time-of-day
    profile of the volatility, is gone. Opens are set to the previous close.
    """
    rng = np.random.default_rng(seed)
    day = pd.DatetimeIndex(bars.index).normalize()
    o, h, low, c = (bars[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close"))
    new_open, new_high, new_low, new_close = (np.empty_like(o) for _ in range(4))
    for where in bars.groupby(day).indices.values():
        first_open = o[where][0]
        previous = np.concatenate(([first_open], c[where][:-1]))
        step = c[where] - previous
        up = h[where] - previous
        down = low[where] - previous
        order = rng.permutation(len(where))
        closes = first_open + np.cumsum(step[order])
        starts = np.concatenate(([first_open], closes[:-1]))
        new_open[where] = starts
        new_close[where] = closes
        new_high[where] = np.maximum(starts + up[order], np.maximum(starts, closes))
        new_low[where] = np.minimum(starts + down[order], np.minimum(starts, closes))
    out = bars.copy()
    out["open"], out["high"], out["low"], out["close"] = new_open, new_high, new_low, new_close
    return out


def stack_trials(
    results: Sequence[tuple[int, dict[str, np.ndarray], dict[str, np.ndarray]]],
    days: pd.DatetimeIndex,
) -> TrialSet:
    """Assemble `(index, returns, sides)` results into a `TrialSet`, ordered as given."""
    names = list(results[0][1])
    return TrialSet(
        indices=np.array([r[0] for r in results]),
        days=days,
        ret={n: np.vstack([r[1][n] for r in results]) for n in names},
        sides={n: np.vstack([r[2][n] for r in results]) for n in names},
    )
