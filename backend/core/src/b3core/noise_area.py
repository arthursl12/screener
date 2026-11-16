"""Noise Area sigma (brief section 10, WINFUT intraday momentum). Pure: bars in, sigma out.

Bars are a DataFrame on a sorted, unique, tz-naive local-time index with `open` and `close`
columns. Only the clock time of each bar matters, so a day may open late or miss a bar.
"""

import numpy as np
import pandas as pd


def noise_sigma(bars: pd.DataFrame, lookback: int = 14, min_days: int = 13) -> pd.Series:
    """For each bar, the mean absolute move from the day's open at that clock time, over the
    `lookback` previous observations of that clock time.

    The move of a bar is `|close / open of its day - 1|`, where the day's open is the open of
    its first bar. This follows the authors' notebook (Zarattini, Aziz and Barbon): per clock
    time, `rolling(lookback, min_periods=min_days).mean()` shifted by one observation, so the
    bar's own day is never read and fewer than `min_days` observations give NaN. The window
    counts observations of that clock time, not trading days, so a day with no bar at that time
    pulls an older day into the window. The defaults are the paper's: 14 and 13.
    """
    if lookback < 1:
        raise ValueError("lookback must be at least 1")
    if not 1 <= min_days <= lookback:
        raise ValueError("min_days must be between 1 and lookback")
    index = pd.DatetimeIndex(bars.index)
    if not index.is_monotonic_increasing:
        raise ValueError("bars must be sorted by time")
    if index.has_duplicates:
        raise ValueError("bars must have unique timestamps")

    day_open = bars["open"].groupby(index.normalize()).transform("first")
    move = (bars["close"] / day_open - 1.0).abs()
    clock = index.hour * 60 + index.minute
    sigma = move.groupby(clock).transform(
        lambda moves: moves.rolling(lookback, min_periods=min_days).mean().shift(1)
    )
    return pd.Series(sigma.to_numpy(dtype=np.float64), index=index, name="sigma")
