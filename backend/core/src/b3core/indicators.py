"""Moving averages, the trend context of 123 de compra and RSI (brief section 7). Pure numpy."""

import numpy as np
import pandas as pd
from numpy.typing import NDArray


def ema(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Exponential moving average: factor 2 / (period + 1), seeded with the first value."""
    smoothed: NDArray[np.float64] = (
        pd.Series(values).ewm(span=period, adjust=False).mean().to_numpy(dtype=np.float64)
    )
    return smoothed


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return float("nan") if avg_gain == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def rsi(values: NDArray[np.float64], period: int) -> NDArray[np.float64]:
    """Wilder's RSI. The first value is on bar `period`; earlier bars are NaN.

    The first average gain and loss are simple means of the first `period` changes, then
    `avg = (avg * (period - 1) + change) / period`. This matches TA-Lib. A window with no
    gains and no losses (0 / 0) is NaN, so a flat start never reads as oversold.
    """
    if period < 1:
        raise ValueError("period must be at least 1")
    result = np.full(len(values), np.nan)
    if len(values) <= period:
        return result
    change = np.diff(values)
    gains = np.maximum(change, 0.0)
    losses = np.maximum(-change, 0.0)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())
    result[period] = _rsi_value(avg_gain, avg_loss)
    for bar in range(period + 1, len(values)):
        avg_gain = (avg_gain * (period - 1) + gains[bar - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[bar - 1]) / period
        result[bar] = _rsi_value(avg_gain, avg_loss)
    return result


def _shifted(previous_and_current: NDArray[np.bool_], lag: int) -> NDArray[np.bool_]:
    """Put False on the first `lag` bars, where the comparison has no earlier bars to use."""
    result = np.zeros(len(previous_and_current) + lag, dtype=bool)
    result[lag:] = previous_and_current
    return result


def trend_context(
    close: NDArray[np.float64],
    *,
    fast_period: int,
    slow_period: int,
    use_ma_order: bool,
    use_fast_slope: bool,
    use_slow_slope: bool,
    use_price_above_fast: bool,
) -> NDArray[np.bool_]:
    """True on every bar where all the enabled trend checks hold; no enabled check means True."""
    fast = ema(close, fast_period)
    slow = ema(close, slow_period)
    passes = np.ones(len(close), dtype=bool)

    if use_ma_order:
        passes &= fast > slow
    if use_fast_slope:
        passes &= _shifted(fast[1:] > fast[:-1], 1)
    if use_slow_slope:
        passes &= _shifted(slow[1:] > slow[:-1], 1)
    if use_price_above_fast:
        above = close > fast
        passes &= _shifted(above[2:] & above[1:-1] & above[:-2], 2)
    return passes
