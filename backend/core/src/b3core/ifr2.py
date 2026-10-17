"""IFR2 (RSI 2) de compra engine. Rules: brief section 7. Pure: no I/O, no clock."""

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from b3core.data import Timeframe
from b3core.indicators import atr, rsi
from b3core.metrics import Metrics, compute_metrics

EXIT_MODES = ("target", "rsi", "target_or_rsi")

# B3 fee per side in percent of traded value (brief section 10). The engine default is 0 so
# golden tests stay readable; the IFR2 preset uses this value.
IFR2_COST_PCT = 0.03

# Guards float noise in floor(): 92.99999999999999 must count as 93.
_EPS = 1e-9


@dataclass(frozen=True)
class Ifr2Config:
    """Parameters of one IFR2 backtest (brief section 7). JSON-serializable via to_dict."""

    rsi_period: int = 2
    rsi_entry: float = 30
    exit_mode: str = "target"
    rsi_exit: float = 70  # only used when the mode has an RSI exit
    target_lookback: int = 2  # only used when the mode has a target
    max_days: int | None = None  # time stop in candles; None means off
    allow_same_day_reentry: bool = False
    atr_period: int = 5
    atr_mult: float = 2
    max_risk_brl: float = 2_000.0
    capital_brl: float = 100_000.0
    lot_size: int = 1
    cost_pct: float = 0.0  # percent of traded value, per side

    def __post_init__(self) -> None:
        if self.rsi_period < 1:
            raise ValueError("rsi_period must be at least 1")
        if not 0 <= self.rsi_entry <= 100:
            raise ValueError("rsi_entry must be between 0 and 100")
        if self.exit_mode not in EXIT_MODES:
            raise ValueError(f"exit_mode must be one of {EXIT_MODES}, got {self.exit_mode!r}")
        if self.uses_rsi_exit and not self.rsi_entry < self.rsi_exit <= 100:
            raise ValueError("rsi_exit must be above rsi_entry and at most 100")
        if self.target_lookback < 1:
            raise ValueError("target_lookback must be at least 1")
        if self.max_days is not None and self.max_days < 1:
            raise ValueError("max_days must be at least 1 (or None for off)")
        if self.atr_period < 1:
            raise ValueError("atr_period must be at least 1")
        if self.atr_mult <= 0:
            raise ValueError("atr_mult must be above 0")
        if self.max_risk_brl <= 0:
            raise ValueError("max_risk_brl must be positive")
        if self.capital_brl <= 0:
            raise ValueError("capital_brl must be positive")
        if self.lot_size < 1:
            raise ValueError("lot_size must be at least 1")
        if self.cost_pct < 0:
            raise ValueError("cost_pct must be 0 or more")

    @property
    def uses_target(self) -> bool:
        return self.exit_mode in ("target", "target_or_rsi")

    @property
    def uses_rsi_exit(self) -> bool:
        return self.exit_mode in ("rsi", "target_or_rsi")

    @classmethod
    def preset(cls, **overrides: Any) -> "Ifr2Config":
        """The IFR2 preset: defaults plus the B3 fee of 0.03% per side."""
        return cls(**{"cost_pct": IFR2_COST_PCT, **overrides})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Ifr2Config":
        return cls(**data)


@dataclass(frozen=True)
class Ifr2Trade:
    """One closed long trade. Timestamps are the open time of the entry and exit candles."""

    n: int
    entry_index: int
    exit_index: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry: float
    exit: float
    qty: int
    pnl: float  # after costs
    days: int  # candles in the trade, the entry candle being day 0
    exit_reason: str  # "target", "time" or "rsi"


@dataclass(frozen=True)
class Ifr2Result:
    config: Ifr2Config
    trades: list[Ifr2Trade]
    # One value per candle: capital plus closed PnL plus the open position marked at the close.
    equity: NDArray[np.float64] = field(compare=False, repr=False)
    years: float | None  # length of the data in years; None below two candles apart in time

    @property
    def metrics(self) -> Metrics:
        return compute_metrics(
            [t.pnl for t in self.trades],
            self.config.capital_brl,
            equity=self.equity,
            years=self.years,
        )


def _target_levels(high: NDArray[np.float64], lookback: int) -> NDArray[np.float64]:
    """Highest high of the previous `lookback` candles, never including the current one."""
    levels = np.full(len(high), np.nan)
    if len(high) > lookback:
        windows = np.lib.stride_tricks.sliding_window_view(high, lookback).max(axis=1)
        levels[lookback:] = windows[: len(high) - lookback]
    return levels


def _quantity(entry: float, atr_value: float, config: Ifr2Config) -> int:
    """Risk budget over the ATR distance, rounded down to the lot, capped by the capital."""
    if not math.isfinite(atr_value) or atr_value <= 0:
        return 0
    lot = config.lot_size
    by_risk = math.floor(config.max_risk_brl / (config.atr_mult * atr_value) / lot + _EPS)
    by_capital = math.floor(config.capital_brl / entry / lot + _EPS)
    return max(min(by_risk, by_capital), 0) * lot


def run_ifr2(
    candles: pd.DataFrame,
    config: Ifr2Config,
    *,
    timeframe: Timeframe = Timeframe.D1,
) -> Ifr2Result:
    """Simulate IFR2 de compra on closed daily candles.

    A signal on candle t buys at that candle's close (a named exception to section 6, rule 1).
    Exits are checked from the next candle on: the target first, then the time stop, then the
    RSI exit. An open position at the end of the data is not a closed trade and is left out.
    """
    if timeframe is not Timeframe.D1:
        raise ValueError("IFR2 runs on the daily timeframe only")

    open_ = candles["open"].to_numpy(dtype=np.float64)
    high = candles["high"].to_numpy(dtype=np.float64)
    low = candles["low"].to_numpy(dtype=np.float64)
    close = candles["close"].to_numpy(dtype=np.float64)
    ts = candles["ts"]

    rsi_values = rsi(close, config.rsi_period)
    atr_values = atr(high, low, close, config.atr_period)
    target = _target_levels(high, config.target_lookback)
    cost_rate = config.cost_pct / 100.0

    trades: list[Ifr2Trade] = []
    equity = np.empty(len(close))
    realized = 0.0
    in_trade = False
    entry_bar = 0
    entry_price = 0.0
    qty = 0

    for t in range(len(close)):
        exited_now = False
        if in_trade:
            days = t - entry_bar
            exit_price: float | None = None
            reason = ""
            if config.uses_target and high[t] > target[t]:  # False while the target is NaN
                exit_price = open_[t] if open_[t] > target[t] else float(target[t])
                reason = "target"
            elif config.max_days is not None and days >= config.max_days:
                exit_price, reason = float(close[t]), "time"
            elif config.uses_rsi_exit and rsi_values[t] >= config.rsi_exit:
                exit_price, reason = float(close[t]), "rsi"
            if exit_price is not None:
                pnl = qty * (exit_price - entry_price) - cost_rate * qty * (
                    entry_price + exit_price
                )
                trades.append(
                    Ifr2Trade(
                        n=len(trades) + 1,
                        entry_index=entry_bar,
                        exit_index=t,
                        entry_ts=ts.iloc[entry_bar],
                        exit_ts=ts.iloc[t],
                        entry=entry_price,
                        exit=exit_price,
                        qty=qty,
                        pnl=pnl,
                        days=days,
                        exit_reason=reason,
                    )
                )
                realized += pnl
                in_trade = False
                exited_now = True

        can_enter = not in_trade and (not exited_now or config.allow_same_day_reentry)
        if can_enter and rsi_values[t] <= config.rsi_entry:  # False while the RSI is NaN
            size = _quantity(float(close[t]), float(atr_values[t]), config)
            if size > 0:
                in_trade, entry_bar, entry_price, qty = True, t, float(close[t]), size

        floating = (
            qty * (close[t] - entry_price) - cost_rate * qty * entry_price if in_trade else 0.0
        )
        equity[t] = config.capital_brl + realized + floating

    span_days = (ts.iloc[-1] - ts.iloc[0]).days if len(ts) > 1 else 0
    years = span_days / 365.25 if span_days > 0 else None
    return Ifr2Result(config=config, trades=trades, equity=equity, years=years)
