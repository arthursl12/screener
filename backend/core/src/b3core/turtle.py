"""Turtle (channel breakout with ATR pyramiding) de compra engine. Rules: brief section 7c.

Pure: no I/O, no clock.
"""

import math
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from b3core.data import Timeframe
from b3core.indicators import atr
from b3core.metrics import Metrics, compute_metrics

# B3 fee per side in percent of traded value (brief section 10). The engine default is 0 so
# golden tests stay readable; the preset uses this value.
TURTLE_COST_PCT = 0.03

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
    cost_pct: float = 0.0  # percent of traded value, on every fill

    def __post_init__(self) -> None:
        if self.entry_period < 1:
            raise ValueError("entry_period must be at least 1")
        if self.exit_period < 1:
            raise ValueError("exit_period must be at least 1")
        if self.atr_period < 1:
            raise ValueError("atr_period must be at least 1")
        if self.add_atr_mult <= 0:
            raise ValueError("add_atr_mult must be above 0")
        if not 1 <= self.max_units <= 10:
            raise ValueError("max_units must be between 1 and 10")
        if self.capital_brl <= 0:
            raise ValueError("capital_brl must be positive")
        if self.risk_pct <= 0:
            raise ValueError("risk_pct must be above 0")
        if self.lot_size < 1:
            raise ValueError("lot_size must be at least 1")
        if self.cost_pct < 0:
            raise ValueError("cost_pct must be 0 or more")

    @classmethod
    def preset(cls, **overrides: Any) -> "TurtleConfig":
        """The Turtle preset: defaults plus the B3 fee of 0.03% per side."""
        return cls(**{"cost_pct": TURTLE_COST_PCT, **overrides})

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
    skipped_units: int  # signals whose quantity was below one lot or whose ATR was zero
    multi_add_candles: int  # candles that justified more than one add (only one is made)
    open_units: int  # units still open on the last candle

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


def run_turtle(
    candles: pd.DataFrame,
    config: TurtleConfig,
    *,
    timeframe: Timeframe = Timeframe.D1,
) -> TurtleResult:
    """Simulate Turtle de compra on closed daily candles, filling at the signal close.

    Other timeframes run (every rule counts candles) but warn: the spec is daily.
    """
    if timeframe is not Timeframe.D1:
        warnings.warn(
            f"Turtle is specified for daily candles; {timeframe.value} is outside the spec",
            stacklevel=2,
        )
    high = candles["high"].to_numpy(dtype=np.float64)
    low = candles["low"].to_numpy(dtype=np.float64)
    close = candles["close"].to_numpy(dtype=np.float64)
    ts = candles["ts"]

    atr_values = atr(high, low, close, config.atr_period)
    entry_level = _channel(high, config.entry_period, use_max=True)
    exit_level = _channel(low, config.exit_period, use_max=False)

    cost_rate = config.cost_pct / 100.0
    trades: list[TurtleTrade] = []
    equity = np.empty(len(close))
    realized = 0.0
    peak_cost = 0.0
    skipped_units = 0
    multi_add_candles = 0
    units: list[tuple[int, float]] = []  # (quantity, fill price)
    entry_bar = 0

    for t in range(len(close)):
        if units:
            qty = sum(q for q, _ in units)
            average = sum(q * p for q, p in units) / qty
            previous_atr = atr_values[t - 1] if t > 0 else np.nan
            sell = close[t] < exit_level[t]  # False while the level is NaN
            stop = close[t] < average - previous_atr  # False while the ATR is NaN
            if sell or stop:  # a sell wins over a stop on the same candle
                pnl = sum(q * (float(close[t]) - p) for q, p in units) - cost_rate * (
                    sum(q * p for q, p in units) + qty * float(close[t])
                )
                trades.append(
                    TurtleTrade(
                        n=len(trades) + 1,
                        entry_index=entry_bar,
                        exit_index=t,
                        entry_ts=ts.iloc[entry_bar],
                        exit_ts=ts.iloc[t],
                        entry=average,
                        exit=float(close[t]),
                        qty=qty,
                        units=len(units),
                        pnl=pnl,
                        days=t - entry_bar,
                        exit_reason="sell" if sell else "stop",
                    )
                )
                realized += pnl
                units = []
            else:
                reference = units[-1][1] if config.use_last_fill else average
                level = reference + config.add_atr_mult * previous_atr  # NaN while no ATR
                if len(units) < config.max_units and close[t] > level:
                    size = _quantity(float(atr_values[t]), config)  # the current ATR
                    if size > 0:
                        units.append((size, float(close[t])))
                        # Would the same close still pass the next level? Then more than one
                        # add was due; only one is made per candle.
                        qty = sum(q for q, _ in units)
                        average = sum(q * p for q, p in units) / qty
                        reference = units[-1][1] if config.use_last_fill else average
                        if (
                            len(units) < config.max_units
                            and close[t] > reference + config.add_atr_mult * previous_atr
                        ):
                            multi_add_candles += 1
                    else:
                        skipped_units += 1
        elif close[t] > entry_level[t]:  # False while the level is NaN
            size = _quantity(float(atr_values[t]), config)
            if size > 0:
                units = [(size, float(close[t]))]
                entry_bar = t
            elif math.isfinite(atr_values[t]):  # a missing ATR is warm-up, not a skipped signal
                skipped_units += 1

        floating = sum(q * (close[t] - p) for q, p in units) - cost_rate * sum(
            q * p for q, p in units
        )
        peak_cost = max(peak_cost, sum(q * p for q, p in units))
        equity[t] = config.capital_brl + realized + floating

    span_days = (ts.iloc[-1] - ts.iloc[0]).days if len(ts) > 1 else 0
    years = span_days / 365.25 if span_days > 0 else None
    if skipped_units:
        warnings.warn(
            f"{skipped_units} Turtle unit(s) skipped: the quantity was below one lot "
            "or the ATR was zero",
            stacklevel=2,
        )
    if multi_add_candles:
        warnings.warn(
            f"{multi_add_candles} candle(s) justified more than one add; only one was made",
            stacklevel=2,
        )
    return TurtleResult(
        config=config,
        trades=trades,
        equity=equity,
        years=years,
        peak_cost=peak_cost,
        skipped_units=skipped_units,
        multi_add_candles=multi_add_candles,
        open_units=len(units),
    )
