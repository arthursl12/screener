"""Turtle (channel breakout with ATR pyramiding) de compra engine. Rules: brief section 7c.

Pure: no I/O, no clock.
"""

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from b3core.indicators import atr
from b3core.metrics import Metrics, compute_metrics

# Guards float noise in floor(): 92.99999999999999 must count as 93.
_EPS = 1e-9


@dataclass(frozen=True)
class TurtleConfig:
    """Parameters of one Turtle backtest (brief section 7c). JSON-serializable via to_dict."""

    entry_period: int = 20
    exit_period: int = 20
    atr_period: int = 14
    add_atr_mult: float = 1.0
    max_units: int = 4
    use_last_fill: bool = False
    capital_brl: float = 25_000.0  # sets the risk budget only: there is no capital cap
    risk_pct: float = 2.0
    lot_size: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TurtleConfig":
        return cls(**data)

    @property
    def risk_budget(self) -> float:
        return self.capital_brl * self.risk_pct / 100.0


@dataclass(frozen=True)
class TurtleTrade:
    """One closed position, from its first unit to the exit of all units."""

    n: int
    entry_index: int
    exit_index: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry: float  # average fill price of the units
    exit: float
    qty: int  # all units together
    units: int
    pnl: float
    days: int  # candles in the trade, the entry candle being day 0
    exit_reason: str  # "sell" or "stop"


@dataclass(frozen=True)
class TurtleResult:
    config: TurtleConfig
    trades: list[TurtleTrade]
    # One value per candle: capital plus closed PnL plus the open units marked at the close.
    equity: NDArray[np.float64] = field(compare=False, repr=False)
    years: float | None  # length of the data in years; None below two candles apart in time
    peak_cost: float  # the most money the open units ever held (quantity times fill price)

    @property
    def metrics(self) -> Metrics:
        return compute_metrics(
            [t.pnl for t in self.trades],
            self.config.capital_brl,
            equity=self.equity,
            years=self.years,
        )


def _channel(values: NDArray[np.float64], period: int, use_max: bool) -> NDArray[np.float64]:
    """Highest high (or lowest low) of the previous `period` candles, never the current one."""
    levels = np.full(len(values), np.nan)
    if len(values) > period:
        windows = np.lib.stride_tricks.sliding_window_view(values, period)
        reduced = windows.max(axis=1) if use_max else windows.min(axis=1)
        levels[period:] = reduced[: len(values) - period]
    return levels


def _quantity(atr_value: float, config: TurtleConfig) -> int:
    """Risk budget over the ATR, rounded down to the lot. 0 when the ATR is not usable."""
    if not math.isfinite(atr_value) or atr_value <= 0:
        return 0
    lot = config.lot_size
    return max(math.floor(config.risk_budget / atr_value / lot + _EPS), 0) * lot


def run_turtle(candles: pd.DataFrame, config: TurtleConfig) -> TurtleResult:
    """Simulate Turtle de compra on closed daily candles, filling at the signal close."""
    high = candles["high"].to_numpy(dtype=np.float64)
    low = candles["low"].to_numpy(dtype=np.float64)
    close = candles["close"].to_numpy(dtype=np.float64)
    ts = candles["ts"]

    atr_values = atr(high, low, close, config.atr_period)
    entry_level = _channel(high, config.entry_period, use_max=True)
    exit_level = _channel(low, config.exit_period, use_max=False)

    trades: list[TurtleTrade] = []
    equity = np.empty(len(close))
    realized = 0.0
    peak_cost = 0.0
    units: list[tuple[int, float]] = []  # (quantity, fill price)
    entry_bar = 0

    for t in range(len(close)):
        if units:
            if close[t] < exit_level[t]:  # False while the level is NaN
                qty = sum(q for q, _ in units)
                pnl = sum(q * (float(close[t]) - p) for q, p in units)
                trades.append(
                    TurtleTrade(
                        n=len(trades) + 1,
                        entry_index=entry_bar,
                        exit_index=t,
                        entry_ts=ts.iloc[entry_bar],
                        exit_ts=ts.iloc[t],
                        entry=sum(q * p for q, p in units) / qty,
                        exit=float(close[t]),
                        qty=qty,
                        units=len(units),
                        pnl=pnl,
                        days=t - entry_bar,
                        exit_reason="sell",
                    )
                )
                realized += pnl
                units = []
        elif close[t] > entry_level[t]:  # False while the level is NaN
            size = _quantity(float(atr_values[t]), config)
            if size > 0:
                units = [(size, float(close[t]))]
                entry_bar = t

        floating = sum(q * (close[t] - p) for q, p in units)
        peak_cost = max(peak_cost, sum(q * p for q, p in units))
        equity[t] = config.capital_brl + realized + floating

    span_days = (ts.iloc[-1] - ts.iloc[0]).days if len(ts) > 1 else 0
    years = span_days / 365.25 if span_days > 0 else None
    return TurtleResult(
        config=config, trades=trades, equity=equity, years=years, peak_cost=peak_cost
    )
