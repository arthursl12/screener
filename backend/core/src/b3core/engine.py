"""Backtest engine for 123 de compra. Rules: brief sections 6 and 7. Pure: no I/O, no clock."""

import math
import re
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from b3core.data import Timeframe
from b3core.metrics import Metrics, compute_metrics

STOP_MODES = ("c2_low", "c3_low")
TARGET_MODES = ("risk_fixed", "amplitude")
DAY_EXIT_POLICIES = ("auto", "last_candle_open")

# Trading rules are evaluated in São Paulo wall-clock time (CLAUDE.md, rule 5).
TRADING_TIMEZONE = "America/Sao_Paulo"
_TIME_FORMAT = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# Guards float noise in floor(): 199.99999999999997 must count as 200.
_EPS = 1e-9


def parse_hhmm(value: str, name: str) -> int:
    """Minutes since midnight for an "HH:MM" string."""
    match = _TIME_FORMAT.match(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f"{name} must be HH:MM, got {value!r}")
    return int(match[1]) * 60 + int(match[2])


def window_is_valid(min_entry_time: str, max_entry_time: str | None, exit_time: str) -> bool:
    """min_entry_time < max_entry_time <= exit_time; no maximum means the exit time."""
    exit_minute = parse_hhmm(exit_time, "exit_time")
    low = parse_hhmm(min_entry_time, "min_entry_time")
    high = exit_minute if max_entry_time is None else parse_hhmm(max_entry_time, "max_entry_time")
    return low < high <= exit_minute


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
    day_trade: bool = False
    min_entry_time: str = "00:00"  # day trade only: earliest candle open for a fill
    max_entry_time: str | None = None  # day trade only: None means exit_time
    exit_time: str = "16:30"  # day trade only: forced exit time
    day_exit_policy: str = "auto"  # day trade only: how the forced exit is priced

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
        if self.day_exit_policy not in DAY_EXIT_POLICIES:
            raise ValueError(
                f"day_exit_policy must be one of {DAY_EXIT_POLICIES}, got {self.day_exit_policy!r}"
            )
        if not window_is_valid(self.min_entry_time, self.max_entry_time, self.exit_time):
            raise ValueError(
                "entry window must satisfy min_entry_time < max_entry_time <= exit_time"
            )

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
    exit_reason: str  # "stop", "target" or "time" (day-trade forced exit)


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    trades: list[Trade]

    @property
    def metrics(self) -> Metrics:
        return compute_metrics([t.pnl for t in self.trades], self.config.capital_brl)

    def equity_curve(self) -> pd.DataFrame:
        """Initial capital plus cumulative PnL, one row per closed trade after a start row."""
        equity = self.config.capital_brl + np.cumsum([t.pnl for t in self.trades])
        start_ts = [self.trades[0].entry_ts] if self.trades else []
        return pd.DataFrame(
            {
                "ts": start_ts + [t.exit_ts for t in self.trades],
                "equity": np.concatenate(([self.config.capital_brl], equity))
                if self.trades
                else [],
            }
        )


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


def _scan(
    open_: NDArray[np.float64],
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    start: int,
    end: int,
    stop: float,
    target: float,
    gaps_on_first: bool,
) -> tuple[int, float, str] | None:
    """Look for a stop or target fill on candles start..end-1. The stop is checked first.

    The position is assumed open before `start`; `gaps_on_first` says whether the open of the
    first candle can already gap through the stop or target (False on the entry candle).
    """
    for j in range(start, end):
        if j > start or gaps_on_first:
            if open_[j] <= stop:
                return j, float(open_[j]), "stop"  # gap through the stop fills at the open
            if open_[j] >= target:
                return j, target, "target"  # gap through the target fills at the target
        if low[j] <= stop:
            return j, stop, "stop"
        if high[j] >= target:
            return j, target, "target"
    return None


@dataclass(frozen=True)
class _Intraday:
    """Finer candles, sorted by time, with a key (local day * 2000 + minute) for searching."""

    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    key: NDArray[np.int64]


@dataclass(frozen=True)
class _DayContext:
    """Per-candle local day and minute, plus the day-trade parameters (brief section 7)."""

    day: NDArray[np.int64]  # local date as yyyymmdd
    minute: NDArray[np.int64]  # minutes since local midnight, at the candle open
    period: int  # candle length in minutes, from the timeframe
    exit_minute: int
    min_entry: int
    max_entry: int
    intraday: _Intraday | None

    def can_fill(self, k: int) -> bool:
        """The fill candle opens inside the window and ends no later than the exit time."""
        return bool(
            self.min_entry <= self.minute[k] < self.max_entry
            and self.minute[k] + self.period <= self.exit_minute
        )

    def is_exit_candle(self, k: int) -> bool:
        """A candle that ends after the exit time: it contains the exit time or follows it."""
        return bool(self.minute[k] + self.period > self.exit_minute)

    def last_of_day(self, k: int) -> int:
        return int(np.searchsorted(self.day, self.day[k], side="right")) - 1


def _local_clock(ts: pd.Series) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    local = ts.dt.tz_convert(TRADING_TIMEZONE)
    day = (local.dt.year * 10_000 + local.dt.month * 100 + local.dt.day).to_numpy(dtype=np.int64)
    minute = (local.dt.hour * 60 + local.dt.minute).to_numpy(dtype=np.int64)
    return day, minute


def _day_context(
    candles: pd.DataFrame,
    config: BacktestConfig,
    timeframe: Timeframe | None,
    intraday: pd.DataFrame | None,
) -> _DayContext:
    if timeframe is None:
        raise ValueError("timeframe is required when day_trade is on")
    if timeframe.minutes >= 1440:
        raise ValueError("day trade needs an intraday timeframe, not the daily one")

    day, minute = _local_clock(candles["ts"])
    exit_minute = parse_hhmm(config.exit_time, "exit_time")
    max_entry = (
        exit_minute
        if config.max_entry_time is None
        else parse_hhmm(config.max_entry_time, "max_entry_time")
    )

    fine: _Intraday | None = None
    if intraday is not None and len(intraday) and config.day_exit_policy == "auto":
        fine_day, fine_minute = _local_clock(intraday["ts"])
        fine = _Intraday(
            open=intraday["open"].to_numpy(dtype=np.float64),
            high=intraday["high"].to_numpy(dtype=np.float64),
            low=intraday["low"].to_numpy(dtype=np.float64),
            key=fine_day * 2000 + fine_minute,
        )

    return _DayContext(
        day=day,
        minute=minute,
        period=timeframe.minutes,
        exit_minute=exit_minute,
        min_entry=parse_hhmm(config.min_entry_time, "min_entry_time"),
        max_entry=max_entry,
        intraday=fine,
    )


def _forced_exit(
    ctx: _DayContext, open_: NDArray[np.float64], j: int, stop: float, target: float
) -> tuple[float, str]:
    """Price and reason of the forced exit on exit candle j, with the position open at its start.

    Policy `auto` with finer candles pinpoints the exit time; otherwise the exit candle's open.
    """
    fine = ctx.intraday
    if fine is not None:
        base = int(ctx.day[j]) * 2000
        first = int(np.searchsorted(fine.key, base + ctx.minute[j], side="left"))
        after = int(np.searchsorted(fine.key, base + ctx.exit_minute, side="right"))
        if after > first:
            # Finer candles from the exit candle's open up to the last one starting at or before
            # the exit time are checked for the stop and target; that last candle prices the exit.
            hit = _scan(fine.open, fine.high, fine.low, first, after - 1, stop, target, True)
            if hit is not None:
                return hit[1], hit[2]
            return float(fine.open[after - 1]), "time"
    return float(open_[j]), "time"


def _find_exit_day(
    open_: NDArray[np.float64],
    high: NDArray[np.float64],
    low: NDArray[np.float64],
    close: NDArray[np.float64],
    first: int,
    stop: float,
    target: float,
    ctx: _DayContext,
) -> tuple[int, float, str] | None:
    """Like the swing scan, but a position never survives its day."""
    for j in range(first, len(open_)):
        if j > first and ctx.day[j] != ctx.day[first]:
            # The day ended with no exit candle (a short day): leave at its last close.
            return j - 1, float(close[j - 1]), "time"
        if j > first:
            if open_[j] <= stop:
                return j, float(open_[j]), "stop"
            if open_[j] >= target:
                return j, target, "target"
        if ctx.is_exit_candle(j):  # never the fill candle: fills must end by the exit time
            price, reason = _forced_exit(ctx, open_, j, stop, target)
            return j, price, reason
        if low[j] <= stop:
            return j, stop, "stop"
        if high[j] >= target:
            return j, target, "target"
    return None


def run_backtest(
    candles: pd.DataFrame,
    config: BacktestConfig,
    *,
    timeframe: Timeframe | None = None,
    intraday: pd.DataFrame | None = None,
) -> BacktestResult:
    """Simulate 123 de compra on closed candles. A signal at c3 can fill from c3 + 1 on.

    Day-trade mode needs the candle `timeframe`. `intraday` optionally holds finer candles
    (same columns, UTC) that pinpoint the forced exit time.
    """
    open_ = candles["open"].to_numpy(dtype=np.float64)
    high = candles["high"].to_numpy(dtype=np.float64)
    low = candles["low"].to_numpy(dtype=np.float64)
    close = candles["close"].to_numpy(dtype=np.float64)
    ts = candles["ts"]
    n_candles = len(candles)
    tick = config.tick_size
    ctx = _day_context(candles, config, timeframe, intraday) if config.day_trade else None

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

        expiry = c3 + config.entry_validity_candles
        last_live = min(expiry, n_candles - 1)
        fill = None
        for k in range(c3 + 1, last_live + 1):
            if ctx is not None and ctx.day[k] != ctx.day[c3]:
                break  # an order never lives past the day of its signal in day-trade mode
            if (ctx is None or ctx.can_fill(k)) and high[k] >= trigger:
                fill = k
                break
        if fill is None:
            # The order expired unfilled (in day-trade mode, at the latest at the end of the day).
            free_from = expiry if ctx is None else min(expiry, ctx.last_of_day(c3))
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

        if ctx is None:
            found = _scan(open_, high, low, fill, n_candles, stop, target, False)
        else:
            found = _find_exit_day(open_, high, low, close, fill, stop, target, ctx)
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
