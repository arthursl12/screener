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

FILL_AT = ("signal_close", "next_open")

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
    fill_at: str = "signal_close"  # "signal_close" (the script) or "next_open"

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
        if self.fill_at not in FILL_AT:
            raise ValueError(f"fill_at must be one of {FILL_AT}, got {self.fill_at!r}")

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
    """Simulate Turtle de compra on closed daily candles (brief section 7c).

    Orders fill at the signal close (`fill_at` signal_close) or at the next open (next_open).

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

    open_ = candles["open"].to_numpy(dtype=np.float64)
    cost_rate = config.cost_pct / 100.0
    last = len(close) - 1
    trades: list[TurtleTrade] = []
    equity = np.empty(len(close))
    realized = 0.0
    peak_cost = 0.0
    skipped_units = 0
    multi_add_candles = 0
    units: list[tuple[int, float]] = []  # (quantity, fill price)
    entry_bar = 0
    pending: tuple[str, int, str] | None = None  # (kind, quantity, reason), fills at the next open

    def fill(kind: str, size: int, reason: str, price: float, t: int) -> None:
        """Apply an order at `price`: open a position, add a unit, or leave with every unit."""
        nonlocal units, realized, entry_bar
        if kind == "exit":
            qty = sum(q for q, _ in units)
            cost_in = sum(q * p for q, p in units)
            pnl = qty * price - cost_in - cost_rate * (cost_in + qty * price)
            trades.append(
                TurtleTrade(
                    n=len(trades) + 1,
                    entry_index=entry_bar,
                    exit_index=t,
                    entry_ts=ts.iloc[entry_bar],
                    exit_ts=ts.iloc[t],
                    entry=cost_in / qty,
                    exit=price,
                    qty=qty,
                    units=len(units),
                    pnl=pnl,
                    days=t - entry_bar,
                    exit_reason=reason,
                )
            )
            realized += pnl
            units = []
        elif kind == "buy":
            units = [(size, price)]
            entry_bar = t
        else:
            units.append((size, price))

    for t in range(len(close)):
        if pending is not None:  # fill_at next_open: the order from the previous close
            kind, size, reason = pending
            pending = None
            fill(kind, size, reason, float(open_[t]), t)

        order: tuple[str, int, str] | None = None
        if units:
            qty = sum(q for q, _ in units)
            average = sum(q * p for q, p in units) / qty
            previous_atr = atr_values[t - 1] if t > 0 else np.nan
            sell = close[t] < exit_level[t]  # False while the level is NaN
            stop = close[t] < average - previous_atr  # False while the ATR is NaN
            if sell or stop:  # a sell wins over a stop, and an exit candle takes no add
                order = ("exit", qty, "sell" if sell else "stop")
            else:
                reference = units[-1][1] if config.use_last_fill else average
                level = reference + config.add_atr_mult * previous_atr  # NaN while no ATR
                if len(units) < config.max_units and close[t] > level:
                    size = _quantity(float(atr_values[t]), config)  # the current ATR
                    if size > 0:
                        order = ("add", size, "")
                        # Would the same close still pass the level after this add? Then more
                        # than one add was due; only one is made per candle.
                        after = [*units, (size, float(close[t]))]
                        after_qty = sum(q for q, _ in after)
                        after_average = sum(q * p for q, p in after) / after_qty
                        after_reference = after[-1][1] if config.use_last_fill else after_average
                        if (
                            len(after) < config.max_units
                            and close[t] > after_reference + config.add_atr_mult * previous_atr
                        ):
                            multi_add_candles += 1
                    else:
                        skipped_units += 1
        elif close[t] > entry_level[t]:  # False while the level is NaN
            size = _quantity(float(atr_values[t]), config)
            if size > 0:
                order = ("buy", size, "")
            elif math.isfinite(atr_values[t]):  # a missing ATR is warm-up, not a skipped signal
                skipped_units += 1

        if order is not None:
            if config.fill_at == "signal_close":
                fill(*order, float(close[t]), t)
            elif t < last:  # a signal on the last candle has no next open
                pending = order

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
