"""CDI benchmark (docs/cdi.md). Pure: the caller downloads the series, this only does the maths."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

LOCAL_TIMEZONE = "America/Sao_Paulo"


@dataclass(frozen=True)
class CdiComparison:
    factor: float  # what 1 real became in the CDI over the window
    cdi_cagr: float
    excess: float  # strategy CAGR minus CDI CAGR, as a fraction (0.01 is one point)
    beats_cdi: bool


def _local_dates(
    values: "pd.DatetimeIndex | pd.Series | Sequence[pd.Timestamp]",
) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex(pd.to_datetime(list(values)))
    if index.tz is not None:
        index = index.tz_convert(LOCAL_TIMEZONE).tz_localize(None)
    return index.normalize()


def compare_with_cdi(
    cagr: float,
    years: float,
    rates: pd.Series,
    trading_days: "pd.DatetimeIndex | pd.Series | Sequence[pd.Timestamp]",
) -> CdiComparison:
    """Compound the CDI over the window of `trading_days` and compare it with `cagr`.

    `rates` holds the daily CDI in percent, indexed by date. The money is invested at the close
    of the first trading day, so the CDI accrues from the next day to the last one. Every
    trading day in that range needs a rate; CDI dates that are not trading days still count.
    """
    if years <= 0:
        raise ValueError("years must be positive")
    days = _local_dates(trading_days)
    if len(days) < 2:
        raise ValueError("the window needs at least two trading days")
    start, end = days.min(), days.max()

    rate_index = pd.DatetimeIndex(rates.index).normalize()
    daily = pd.Series(rates.to_numpy(dtype=np.float64), index=rate_index)
    accruing = daily[(daily.index > start) & (daily.index <= end)]

    expected = days[(days > start) & (days <= end)]
    missing = expected.difference(pd.DatetimeIndex(accruing.index))
    if len(missing):
        shown = ", ".join(d.strftime("%Y-%m-%d") for d in missing[:5])
        raise ValueError(f"no CDI rate for {len(missing)} trading days, first: {shown}")

    factor = float(np.prod(1.0 + accruing.to_numpy() / 100.0))
    cdi_cagr = factor ** (1.0 / years) - 1.0
    excess = cagr - cdi_cagr
    return CdiComparison(factor=factor, cdi_cagr=cdi_cagr, excess=excess, beats_cdi=excess > 0)


@dataclass(frozen=True)
class PriceComparison:
    """The strategy against a buy-and-hold position (docs/ibov.md)."""

    factor: float  # what 1 real became between the first and the last close
    cagr: float  # the buy-and-hold CAGR
    excess: float  # strategy CAGR minus buy-and-hold CAGR, as a fraction
    beats: bool


def compare_with_prices(
    cagr: float, years: float, first_close: float, last_close: float
) -> PriceComparison:
    """Compare `cagr` with holding from `first_close` to `last_close` over `years`."""
    if years <= 0:
        raise ValueError("years must be positive")
    if first_close <= 0 or last_close <= 0:
        raise ValueError("closes must be positive")
    factor = last_close / first_close
    held = factor ** (1.0 / years) - 1.0
    excess = cagr - held
    return PriceComparison(factor=factor, cagr=held, excess=excess, beats=excess > 0)


def _window_closes(
    closes: pd.Series,
    trading_days: "pd.DatetimeIndex | pd.Series | Sequence[pd.Timestamp]",
) -> pd.Series:
    """The index closes from the first to the last trading day, both of which must exist."""
    days = _local_dates(trading_days)
    start, end = days.min(), days.max()
    series = pd.Series(
        closes.to_numpy(dtype=np.float64), index=pd.DatetimeIndex(closes.index).normalize()
    ).sort_index()
    for day in (start, end):
        if day not in series.index:
            raise ValueError(f"no index close for {day.strftime('%Y-%m-%d')}")
    window = series[(series.index >= start) & (series.index <= end)]
    if (window <= 0).any():
        raise ValueError("index closes must be positive")
    return window


def compare_with_index(
    cagr: float,
    years: float,
    closes: pd.Series,
    trading_days: "pd.DatetimeIndex | pd.Series | Sequence[pd.Timestamp]",
) -> PriceComparison:
    """Compare `cagr` with holding the index from the first to the last trading day.

    `closes` holds the index close, indexed by date. The window is the first and last date of
    `trading_days` (read in São Paulo), and the index needs a close on both.
    """
    window = _window_closes(closes, trading_days)
    return compare_with_prices(cagr, years, float(window.iloc[0]), float(window.iloc[-1]))


def index_equity(
    closes: pd.Series,
    trading_days: "pd.DatetimeIndex | pd.Series | Sequence[pd.Timestamp]",
    capital: float,
) -> pd.Series:
    """The index held with `capital` over the window: capital times the close over the first one."""
    window = _window_closes(closes, trading_days)
    return capital * window / window.iloc[0]
