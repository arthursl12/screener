"""Intraday momentum on WINFUT (brief section 10). Pure: bars in, numbers out.

The rules are those of the authors' notebook (Zarattini, Aziz and Barbon, "Beat the Market").
Bars are a DataFrame on a sorted, unique, tz-naive local-time index with `open`, `high`, `low`,
`close` and `volume` columns; each bar is labelled by its open time, so the bar labelled 09:29
closes at 09:30.
"""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from b3core.noise_area import noise_sigma


def session_vwap(bars: pd.DataFrame) -> pd.Series:
    """Volume-weighted average of the typical price (high + low + close) / 3 since the day's
    open; NaN until something has traded."""
    typical = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    day = pd.DatetimeIndex(bars.index).normalize()
    cum_value = (bars["volume"] * typical).groupby(day).cumsum()
    cum_volume = bars["volume"].groupby(day).cumsum()
    return cum_value / cum_volume.where(cum_volume > 0)


def noise_bands(bars: pd.DataFrame, sigma: pd.Series, band_mult: float = 1.0) -> pd.DataFrame:
    """The Noise Area of each bar: columns `ub` and `lb`.

    `ub = max(open, previous close) * (1 + band_mult * sigma)` and
    `lb = min(open, previous close) * (1 - band_mult * sigma)`, where `open` is the open of the
    day's first bar and the previous close is the close of the previous day's last bar, so an
    overnight gap widens the band on the side it opened away from. The first day has no
    previous close and so no bands.
    """
    day = pd.DatetimeIndex(bars.index).normalize()
    day_open = bars["open"].groupby(day).transform("first").to_numpy(dtype=np.float64)
    previous_close = (
        bars["close"].groupby(day).last().shift(1).reindex(day).to_numpy(dtype=np.float64)
    )
    width = band_mult * sigma.to_numpy(dtype=np.float64)
    return pd.DataFrame(
        {
            "ub": np.maximum(day_open, previous_close) * (1.0 + width),
            "lb": np.minimum(day_open, previous_close) * (1.0 - width),
        },
        index=bars.index,
    )


def breakout_signal(close: pd.Series, bands: pd.DataFrame, vwap: pd.Series) -> pd.Series:
    """+1 above the upper band and the VWAP, -1 below the lower band and the VWAP, else 0.

    The comparisons are strict, and a missing band or VWAP gives no signal.
    """
    long = (close > bands["ub"]) & (close > vwap)
    short = (close < bands["lb"]) & (close < vwap)
    return long.astype("int64") - short.astype("int64")


def intraday_exposure(
    signal: pd.Series,
    *,
    session_open: int,
    trade_freq: int,
    first_decision: int,
    exit_minute: int,
) -> pd.Series:
    """The position (-1, 0 or +1) held during each bar, flat at each day's start and end.

    A decision is taken on the bars that close `trade_freq` minutes apart counting from the
    session open (the 09:29 and 09:59 bars for a 09:00 open and 30 minutes), and only when the
    bar closes at or after `first_decision`. The position stays at the last decision until the
    next one, and a decision of 0 goes flat. It starts on the next bar, so the price it earns
    from is the close of the decision bar. Nothing is held in the bars from `exit_minute` on.
    All times are minutes since midnight; `exit_minute` is the label of the first bar that is
    flat, so an exit at 17:30 is at the close of the 17:29 bar.
    """
    index = pd.DatetimeIndex(signal.index)
    minute = index.hour * 60 + index.minute
    day = index.normalize()
    is_decision = ((minute - session_open + 1) % trade_freq == 0) & (minute + 1 >= first_decision)

    decided = signal.astype("float64").where(is_decision)
    current = decided.groupby(day).ffill().fillna(0.0)
    started = current.groupby(day).shift(1).fillna(0.0)
    return started.where(minute < exit_minute, 0.0)


@dataclass(frozen=True)
class IntradayConfig:
    """The strategy's settings. Defaults are the paper's, with the owner's WIN choices (brief
    section 10): a R$ 100,000 account, R$ 0.20 a point, R$ 0.25 per contract and side (B3's
    R$ 0.50 round trip, no brokerage, no slippage), a 09:00 session open and an exit at 17:30.
    Times are minutes since midnight; `first_decision` and `exit_minute` are the two the owner
    wants searched. `fixed_contracts` trades that many contracts every day instead of the volatility
    target (1 is the single-contract version). `margin_per_contract` is what the broker asks for a
    WIN mini contract (R$ 1,000, the owner's figure; 0 switches the limit off): the contracts are
    capped at what the equity can margin, which the default R$ 100,000 account never reaches."""

    lookback: int = 14
    min_days: int = 13
    band_mult: float = 1.0
    trade_freq: int = 30
    session_open: int = 9 * 60
    first_decision: int = 9 * 60
    exit_minute: int = 17 * 60 + 30
    capital: float = 100_000.0
    target_vol: float = 0.02
    max_leverage: float = 4.0
    point_value: float = 0.20
    fee_per_side: float = 0.25
    fixed_contracts: int | None = None
    margin_per_contract: float = 1_000.0


def daily_volatility(daily_close: pd.Series, days: int = 14) -> pd.Series:
    """The authors' notebook volatility target input: for day d, the sample standard deviation
    of the `days` close-to-close returns of days d-15 .. d-2.

    The previous day, d-1, is left out, as in the notebook (the paper and the replication repo
    include it). A window that holds a missing return gives NaN, so the first value is on day
    16, because day 0 has no return.
    """
    returns = daily_close.pct_change()
    return returns.shift(2).rolling(days).std()


def contracts_for(aum: float, open_price: float, volatility: float, config: IntradayConfig) -> int:
    """Whole contracts of the WIN mini: `fixed_contracts` when set, else the equity over the
    contract's value times the leverage that targets the daily volatility, capped at
    `max_leverage`. A missing or zero volatility uses the cap, as the notebook does while its
    window is not full. Rounded with Python's `round`. Never more than the equity can margin."""
    if config.fixed_contracts is not None:
        wanted = config.fixed_contracts
    else:
        if math.isnan(volatility) or volatility <= 0:
            leverage = config.max_leverage
        else:
            leverage = min(config.target_vol / volatility, config.max_leverage)
        wanted = int(round(aum / (open_price * config.point_value) * leverage))
    if config.margin_per_contract > 0:
        wanted = min(wanted, int(aum // config.margin_per_contract))
    return wanted


def _sigma_and_exposure(bars: pd.DataFrame, config: IntradayConfig) -> tuple[pd.Series, pd.Series]:
    sigma = noise_sigma(bars[["open", "close"]], config.lookback, config.min_days)
    bands = noise_bands(bars, sigma, config.band_mult)
    signal = breakout_signal(bars["close"], bands, session_vwap(bars))
    exposure = intraday_exposure(
        signal,
        session_open=config.session_open,
        trade_freq=config.trade_freq,
        first_decision=config.first_decision,
        exit_minute=config.exit_minute,
    )
    return sigma, exposure


def strategy_exposure(bars: pd.DataFrame, config: IntradayConfig) -> pd.Series:
    """The position (-1, 0, +1) held during each bar, from the bars and the settings alone."""
    return _sigma_and_exposure(bars, config)[1]


def run_intraday_momentum(bars: pd.DataFrame, config: IntradayConfig) -> pd.DataFrame:
    """The daily backtest of the authors' notebook, one row per day.

    Columns: `contracts`, `trades` (sides, in and out), `gross`, `cost`, `net` (reais), `ret`
    (net over the equity of the day before), `aum` and `margin` (what the contracts of the day
    tie up at the broker). The first day, and days without any
    sigma, do not trade: their `ret` is NaN and the equity carries over. Each day is sized on the
    equity at the end of the day before, at the open of the day.
    """
    sigma, exposure = _sigma_and_exposure(bars, config)

    day = pd.DatetimeIndex(bars.index).normalize()
    volatility = daily_volatility(bars["close"].groupby(day).last())
    day_open = bars["open"].groupby(day).first()
    has_sigma = sigma.notna().groupby(day).any()
    positions = bars.groupby(day).indices
    close = bars["close"].to_numpy(dtype=np.float64)
    held = exposure.to_numpy(dtype=np.float64)

    aum = config.capital
    rows = []
    for number, current in enumerate(day.unique()):
        if number == 0 or not has_sigma[current]:
            rows.append((0, 0.0, 0.0, 0.0, 0.0, math.nan, aum, 0.0))
            continue
        where = positions[current]
        exposed = held[where]
        points = float(np.nansum(exposed * np.diff(close[where], prepend=np.nan)))
        trades = float(np.abs(np.diff(np.append(exposed, 0.0))).sum())
        size = contracts_for(aum, float(day_open[current]), float(volatility[current]), config)
        gross = points * size * config.point_value
        cost = trades * size * config.fee_per_side
        net = gross - cost
        previous, aum = aum, aum + net
        rows.append(
            (size, trades, gross, cost, net, net / previous, aum, size * config.margin_per_contract)
        )
    return pd.DataFrame(
        rows,
        index=day.unique(),
        columns=["contracts", "trades", "gross", "cost", "net", "ret", "aum", "margin"],
    )


def performance(returns: pd.Series) -> dict[str, float]:
    """The notebook's statistics on daily returns (missing days left out), plus the t-statistic
    of the mean. `max_drawdown` is a positive fraction of the running peak; `hit_ratio` counts
    winners among the days that traded."""
    clean = returns.dropna()
    if clean.empty:
        raise ValueError("no returns")
    equity = np.concatenate(([1.0], np.cumprod(1.0 + clean.to_numpy(dtype=np.float64))))
    peak = np.maximum.accumulate(equity)
    mean, spread, count = float(clean.mean()), float(clean.std()), len(clean)
    traded = int((clean.abs() > 0).sum())
    return {
        "total_return": float(equity[-1] - 1.0),
        "annualized_return": float(equity[-1] ** (252 / count) - 1.0),
        "annualized_vol": spread * math.sqrt(252),
        "sharpe": mean / spread * math.sqrt(252) if spread > 0 else math.nan,
        "hit_ratio": int((clean > 0).sum()) / traded if traded else math.nan,
        "max_drawdown": float(((peak - equity) / peak).max()),
        "t_stat": mean / (spread / math.sqrt(count)) if spread > 0 else math.nan,
        "days": float(count),
    }


def intraday_equity(
    bars: pd.DataFrame, config: IntradayConfig, result: pd.DataFrame
) -> pd.DataFrame:
    """The account equity at every bar, from the daily `result` of `run_intraday_momentum`.

    `equity` marks the open position at each bar's close and charges each side's cost on the bar
    where the price of that fill is the close, so the last bar of a day equals the day's `aum`.
    `adverse` is the worst the equity could have been inside the bar: a long is marked at the
    bar's low and a short at its high, against the close before. It is never above `equity`.
    The day's contracts and starting equity come from `result`; days without trading stay flat.
    """
    day = pd.DatetimeIndex(bars.index).normalize()
    exposure = strategy_exposure(bars, config)
    contracts = result["contracts"].reindex(day).to_numpy(dtype=np.float64)
    start_of_day = result["aum"].shift(1).fillna(config.capital)
    day_start = start_of_day.reindex(day).to_numpy(dtype=np.float64)

    previous_close = bars["close"].groupby(day).shift(1)
    move = (bars["close"] - previous_close).fillna(0.0)
    next_exposure = exposure.groupby(day).shift(-1).fillna(0.0)
    scale = contracts * config.point_value
    pnl = exposure.to_numpy() * move.to_numpy() * scale
    cost = np.abs(next_exposure.to_numpy() - exposure.to_numpy()) * contracts * config.fee_per_side
    net = pd.Series(pnl - cost, index=bars.index)
    equity = pd.Series(day_start + net.groupby(day).cumsum(), index=bars.index)

    before = equity.groupby(day).shift(1).fillna(pd.Series(day_start, index=bars.index))
    held = exposure.to_numpy()
    extreme = np.where(held > 0, bars["low"], np.where(held < 0, bars["high"], previous_close))
    worst = (pd.Series(extreme, index=bars.index) - previous_close).fillna(0.0)
    adverse = np.minimum(equity.to_numpy(), before.to_numpy() + held * worst.to_numpy() * scale)
    return pd.DataFrame({"equity": equity, "adverse": adverse}, index=bars.index)


def drawdown_summary(result: pd.DataFrame, curve: pd.DataFrame, capital: float) -> dict[str, float]:
    """Drawdowns and worst losses in reais, all positive, three ways.

    `balance_drawdown`: from the running peak of the end-of-day equity, which is the closed
    result because the strategy is flat each night. `equity_drawdown`: from the running peak of
    the bar-close equity. `adverse_drawdown`: from that same peak to the worst intrabar equity.
    `worst_day` is the worst end-of-day result; `worst_intraday_loss` the largest fall from a
    day's starting equity to its worst intrabar equity.
    """
    balance = np.concatenate(([capital], result["aum"].to_numpy(dtype=np.float64)))
    equity = np.concatenate(([capital], curve["equity"].to_numpy(dtype=np.float64)))
    peak = np.maximum.accumulate(equity)
    adverse = curve["adverse"].to_numpy(dtype=np.float64)
    day = pd.DatetimeIndex(curve.index).normalize()
    start = result["aum"].shift(1).fillna(capital).reindex(day).to_numpy(dtype=np.float64)
    day_drop = pd.Series(start - adverse, index=curve.index).groupby(day).max()
    return {
        "balance_drawdown": float((np.maximum.accumulate(balance) - balance).max()),
        "equity_drawdown": float((peak - equity).max()),
        "adverse_drawdown": float((peak[1:] - adverse).max()),
        "worst_day": float(max(0.0, -result["net"].min())),
        "worst_intraday_loss": float(max(0.0, day_drop.max())),
    }
