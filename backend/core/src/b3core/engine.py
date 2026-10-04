"""Backtest engine for 123 de compra. Rules: brief sections 6 and 7. Pure: no I/O, no clock."""

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

STOP_MODES = ("c2_low", "c3_low")
TARGET_MODES = ("risk_fixed", "amplitude")

# Guards float noise in floor(): 199.99999999999997 must count as 200.
_EPS = 1e-9


@dataclass(frozen=True)
class BacktestConfig:
    """Parameters of one backtest (brief section 7). JSON-serializable via to_dict."""

    capital_brl: float = 100_000.0
    max_risk_brl: float = 2_000.0
    tick_size: float = 0.01
    lot_size: int = 100
    stop_mode: str = "c2_low"
    target_mode: str = "risk_fixed"
    risk_factor: float = 2.0
    entry_offset_ticks: int = 1
    entry_validity_candles: int = 1
    inside_bar: bool = False

    def __post_init__(self) -> None:
        if self.capital_brl <= 0:
            raise ValueError("capital_brl must be positive")
        if self.max_risk_brl <= 0:
            raise ValueError("max_risk_brl must be positive")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if self.lot_size < 1:
            raise ValueError("lot_size must be at least 1")
        if self.stop_mode not in STOP_MODES:
            raise ValueError(f"stop_mode must be one of {STOP_MODES}, got {self.stop_mode!r}")
        if self.target_mode not in TARGET_MODES:
            raise ValueError(f"target_mode must be one of {TARGET_MODES}, got {self.target_mode!r}")
        if not 1 <= self.risk_factor <= 5:
            raise ValueError("risk_factor must be between 1 and 5")
        if self.entry_offset_ticks < 0:
            raise ValueError("entry_offset_ticks must be 0 or more")
        if self.entry_validity_candles < 1:
            raise ValueError("entry_validity_candles must be at least 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BacktestConfig":
        return cls(**data)


@dataclass(frozen=True)
class Trade:
    """One closed long trade. Timestamps are the open time of the fill and exit candles."""

    n: int
    entry_index: int
    exit_index: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry: float
    exit: float
    stop: float
    target: float
    qty: int
    pnl: float
    r_multiple: float
    exit_reason: str  # "stop" or "target"


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]


def round_to_tick(price: float, tick: float) -> float:
    """Round to the nearest tick, immune to float noise such as 0.1 + 0.2."""
    return round(math.floor(price / tick + 0.5) * tick, 10)


def _round_to_tick_array(prices: NDArray[np.float64], tick: float) -> NDArray[np.float64]:
    result: NDArray[np.float64] = np.round(np.floor(prices / tick + 0.5) * tick, 10)
    return result


def find_signals(candles: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    """Vectorized 123 de compra signals, evaluated on the close of c3.

    Columns: c3_index (position of c3), trigger, stop, amplitude. Signals whose stop is at or
    above the trigger are dropped because the risk cannot be sized.
    """
    high = candles["high"].to_numpy(dtype=np.float64)
    low = candles["low"].to_numpy(dtype=np.float64)
    tick = config.tick_size

    h1, h2, h3 = high[:-2], high[1:-1], high[2:]
    l1, l2, l3 = low[:-2], low[1:-1], low[2:]

    valid = (h2 > h1) & (h2 > h3)
    if config.inside_bar:
        valid &= l3 < l2

    trigger = _round_to_tick_array(h3 + config.entry_offset_ticks * tick, tick)
    stop = _round_to_tick_array(l2 if config.stop_mode == "c2_low" else l3, tick)
    valid &= stop < trigger

    # c2 has the highest high of the three, so the pattern range is c2.high - lowest low.
    amplitude = h2 - np.minimum(np.minimum(l1, l2), l3)

    return pd.DataFrame(
        {
            "c3_index": np.flatnonzero(valid) + 2,
            "trigger": trigger[valid],
            "stop": stop[valid],
            "amplitude": amplitude[valid],
        }
    )


def _quantity(entry: float, stop: float, config: BacktestConfig) -> int:
    by_risk = math.floor(config.max_risk_brl / (entry - stop) + _EPS)
    by_capital = math.floor(config.capital_brl / entry + _EPS)
    return int(min(by_risk, by_capital) // config.lot_size * config.lot_size)


def _find_exit(
    open_: NDArray[np.float64],
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    first: int,
    stop: float,
    target: float,
) -> tuple[int, float, str] | None:
    """Scan from the entry candle. Stop is checked before target (pessimistic)."""
    for j in range(first, len(open_)):
        if j > first:
            if open_[j] <= stop:
                return j, float(open_[j]), "stop"  # gap through the stop fills at the open
            if open_[j] >= target:
                return j, target, "target"  # gap through the target fills at the target
        if low[j] <= stop:
            return j, stop, "stop"
        if high[j] >= target:
            return j, target, "target"
    return None


def run_backtest(candles: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
    """Simulate 123 de compra on closed candles. A signal at c3 can fill from c3 + 1 on."""
    open_ = candles["open"].to_numpy(dtype=np.float64)
    high = candles["high"].to_numpy(dtype=np.float64)
    low = candles["low"].to_numpy(dtype=np.float64)
    ts = candles["ts"]
    n_candles = len(candles)
    tick = config.tick_size

    signals = find_signals(candles, config)
    trades: list[Trade] = []
    free_from = 0  # a signal is considered only if its c3 index is at least this

    for c3, trigger, signal_stop, amplitude in zip(
        signals["c3_index"].to_numpy(),
        signals["trigger"].to_numpy(),
        signals["stop"].to_numpy(),
        signals["amplitude"].to_numpy(),
        strict=True,
    ):
        c3 = int(c3)
        if c3 < free_from:
            continue

        last_live = min(c3 + config.entry_validity_candles, n_candles - 1)
        fill = next((k for k in range(c3 + 1, last_live + 1) if high[k] >= trigger), None)
        if fill is None:
            free_from = c3 + config.entry_validity_candles  # the order expired unfilled
            continue

        entry = max(float(open_[fill]), float(trigger))  # a gap above the trigger fills at the open
        stop = float(signal_stop)
        qty = _quantity(entry, stop, config)
        if qty == 0:
            free_from = fill
            continue

        risk = entry - stop
        distance = config.risk_factor * risk if config.target_mode == "risk_fixed" else amplitude
        target = round_to_tick(entry + float(distance), tick)

        found = _find_exit(open_, high, low, fill, stop, target)
        if found is None:
            break  # still open at the end of the data: not a closed trade
        exit_index, exit_price, reason = found

        pnl = qty * (exit_price - entry)
        trades.append(
            Trade(
                n=len(trades) + 1,
                entry_index=fill,
                exit_index=exit_index,
                entry_ts=ts.iloc[fill],
                exit_ts=ts.iloc[exit_index],
                entry=entry,
                exit=exit_price,
                stop=stop,
                target=target,
                qty=qty,
                pnl=pnl,
                r_multiple=pnl / (qty * risk),
                exit_reason=reason,
            )
        )
        free_from = exit_index

    return BacktestResult(config=config, trades=trades)
