"""Equal-split portfolio of independent IFR2 slots. Pure: candles and CDI rates in, numbers out.

Each ticker runs on its own slot of capital and never touches another slot. The portfolio is the
sum of the slot equity curves. There is no shared-cash rule and no position limit.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from b3core.benchmark import compare_with_cdi
from b3core.ifr2 import Ifr2Config, run_ifr2


@dataclass(frozen=True)
class PortfolioSummary:
    years: float
    cagr: float  # -1.0 on a total loss
    max_equity_drawdown: float  # positive fraction of the equity peak
    calmar: float  # CAGR over the equity drawdown; inf with a gain and no drawdown
    cdi_cagr: float
    excess: float
    beats_cdi: bool


def slot_equity(candles: pd.DataFrame, config: Ifr2Config) -> pd.Series:
    """The equity curve of one slot, indexed by the candle timestamps."""
    equity = run_ifr2(candles, config).equity
    return pd.Series(equity, index=pd.DatetimeIndex(candles["ts"]))


def combine_equity(curves: Mapping[str, pd.Series]) -> pd.Series:
    """Sum the slot curves on the union of their dates.

    A slot holds its last value after its data ends and its first value before it starts, so a
    ticker that is missing on a date neither gains nor loses on it.
    """
    if not curves:
        raise ValueError("a portfolio needs at least one slot")
    table = pd.DataFrame(dict(curves)).sort_index().ffill().bfill()
    return table.sum(axis=1)


def buy_and_hold_equity(candles: Mapping[str, pd.DataFrame], capital: float) -> pd.Series:
    """Equal-weight buy and hold of the same tickers (docs/ibov.md), on the raw close.

    Each ticker gets `capital / N`, buys at its first close and holds to its last, without
    rebalancing. The curves are combined with the same edge rule as the strategy slots.
    """
    if not candles:
        raise ValueError("buy and hold needs at least one ticker")
    share = capital / len(candles)
    curves = {}
    for ticker, frame in candles.items():
        close = frame["close"].to_numpy(dtype=np.float64)
        curves[ticker] = pd.Series(share * close / close[0], index=pd.DatetimeIndex(frame["ts"]))
    return combine_equity(curves)


def equity_drawdown(equity: pd.Series, capital: float) -> float:
    """Largest fall over the running peak, as a fraction. The curve starts at `capital`."""
    curve = np.concatenate(([capital], equity.to_numpy(dtype=np.float64)))
    peak = np.maximum.accumulate(curve)
    return float(((peak - curve) / peak).max())


def summarize_portfolio(
    equity: pd.Series, capital: float, cdi_rates: pd.Series
) -> PortfolioSummary:
    """CAGR, equity drawdown, Calmar and the CDI comparison of a combined equity curve.

    `capital` is the total starting capital. The CAGR is the final equity over the capital, the
    drawdown starts from the capital (as in `b3core.metrics`), and the CDI is compounded over
    the dates of the curve.
    """
    if len(equity) < 2:
        raise ValueError("the equity curve needs at least two dates")
    span_days = (equity.index[-1] - equity.index[0]).days
    if span_days <= 0:
        raise ValueError("the equity curve must span more than one day")
    years = span_days / 365.25

    final = float(equity.iloc[-1])
    cagr = (final / capital) ** (1 / years) - 1 if final > 0 else -1.0
    drawdown = equity_drawdown(equity, capital)
    calmar = (math.inf if cagr > 0 else 0.0) if drawdown == 0 else cagr / drawdown
    cdi = compare_with_cdi(cagr, years, cdi_rates, pd.DatetimeIndex(equity.index))
    return PortfolioSummary(years, cagr, drawdown, calmar, cdi.cdi_cagr, cdi.excess, cdi.beats_cdi)
