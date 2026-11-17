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


def band_signal(close: pd.Series, bands: pd.DataFrame) -> pd.Series:
    """+1 above the upper band, -1 below the lower band, else 0 (strict, no VWAP)."""
    return (close > bands["ub"]).astype("int64") - (close < bands["lb"]).astype("int64")


def _decision_mask(
    index: pd.DatetimeIndex, session_open: int, trade_freq: int, first_decision: int
) -> np.ndarray:
    minute = np.asarray(index.hour * 60 + index.minute)
    on_grid = (minute - session_open + 1) % trade_freq == 0
    return np.asarray(on_grid & (minute + 1 >= first_decision))


def _hold_and_delay(decided: pd.Series, exit_minute: int) -> pd.Series:
    """From the position decided on some bars (NaN elsewhere): hold it within the day, start it
    on the next bar, and keep nothing from `exit_minute` on."""
    index = pd.DatetimeIndex(decided.index)
    day = index.normalize()
    minute = index.hour * 60 + index.minute
    current = decided.groupby(day).ffill().fillna(0.0)
    started = current.groupby(day).shift(1).fillna(0.0)
    return started.where(minute < exit_minute, 0.0)


def intraday_exposure(
    signal: pd.Series,
    *,
    session_open: int,
    trade_freq: int,
    first_decision: int,
    exit_minute: int,
    hold_zero: bool = False,
) -> pd.Series:
    """The position (-1, 0 or +1) held during each bar, flat at each day's start and end.

    A decision is taken on the bars that close `trade_freq` minutes apart counting from the
    session open (the 09:29 and 09:59 bars for a 09:00 open and 30 minutes), and only when the
    bar closes at or after `first_decision`. The position stays at the last decision until the
    next one, and a decision of 0 goes flat, unless `hold_zero` is set: then a 0 changes nothing
    and a position is kept until the opposite signal or the end of the day. It starts on the next
    bar, so the price it earns from is the close of the decision bar. Nothing is held in the bars
    from `exit_minute` on. All times are minutes since midnight; `exit_minute` is the label of
    the first bar that is flat, so an exit at 17:30 is at the close of the 17:29 bar.
    """
    index = pd.DatetimeIndex(signal.index)
    is_decision = _decision_mask(index, session_open, trade_freq, first_decision)
    decided = signal.astype("float64").where(is_decision)
    if hold_zero:
        decided = decided.where(decided != 0)
    return _hold_and_delay(decided, exit_minute)


def _decide(stop: str, position: float, c: float, ub: float, lb: float, vw: float) -> float:
    """The position after a decision bar, for each way of exiting (see `STOPS`)."""
    if stop == "vwap_band":
        return 1.0 if (c > ub and c > vw) else -1.0 if (c < lb and c < vw) else 0.0
    if stop == "current_band":
        return 1.0 if c > ub else -1.0 if c < lb else 0.0
    if stop == "opposite_band":
        return 1.0 if c > ub else -1.0 if c < lb else position
    # vwap_only: leave when the close is no longer on the position's side of the VWAP, then enter
    if (position > 0 and not c > vw) or (position < 0 and not c < vw):
        position = 0.0
    if position == 0.0:
        return 1.0 if c > ub else -1.0 if c < lb else 0.0
    return position


def _stopped(stop: str, position: float, c: float, ub: float, lb: float, vw: float) -> bool:
    """Whether a position held at a bar's close fails its stop (a missing value counts as a fail,
    except for the opposite band, which needs a real cross)."""
    if stop == "vwap_band":
        return not (c > ub and c > vw) if position > 0 else not (c < lb and c < vw)
    if stop == "current_band":
        return not c > ub if position > 0 else not c < lb
    if stop == "opposite_band":
        return c < lb if position > 0 else c > ub
    return not c > vw if position > 0 else not c < vw


def bar_by_bar_exposure(
    close: pd.Series,
    bands: pd.DataFrame,
    vwap: pd.Series,
    *,
    stop: str,
    every_bar: bool,
    session_open: int,
    trade_freq: int,
    first_decision: int,
    exit_minute: int,
) -> pd.Series:
    """The position held during each bar, built bar by bar (a state machine per day).

    Positions are opened or changed only on the decision bars. With `every_bar` False a position
    is also left only there, as in the paper ("stop losses can also be triggered only on
    semi-hourly intervals"). With `every_bar` True it is closed at the close of the first bar,
    decision bar or not, that fails the stop, and the next entry waits for the next decision.
    Needed for the VWAP-only stop, which depends on the position held, and for `every_bar`.
    """
    index = pd.DatetimeIndex(close.index)
    is_decision = _decision_mask(index, session_open, trade_freq, first_decision)
    day = index.normalize().to_numpy()
    prices, upper, lower = close.to_numpy(), bands["ub"].to_numpy(), bands["lb"].to_numpy()
    average = vwap.to_numpy()
    positions = np.zeros(len(index))
    position, current_day = 0.0, None
    for i in range(len(index)):
        if day[i] != current_day:
            position, current_day = 0.0, day[i]
        if is_decision[i]:
            position = _decide(stop, position, prices[i], upper[i], lower[i], average[i])
        elif (
            every_bar
            and position != 0.0
            and _stopped(stop, position, prices[i], upper[i], lower[i], average[i])
        ):
            position = 0.0
        positions[i] = position
    return _hold_and_delay(pd.Series(positions, index=close.index), exit_minute)


# vwap_band is the paper's final model (and the authors' notebook); the others are its earlier
# stages and FAQ Q22, read from the text (brief section 10): opposite_band holds the last breakout
# until the opposite band, current_band is flat once the price is back inside the band, vwap_only
# leaves when the price crosses the VWAP.
STOPS = ("vwap_band", "opposite_band", "current_band", "vwap_only")
# grid: a stop is only acted on at the half-hour decisions (the paper, and both codes);
# every_bar: a stop is acted on at the close of the first bar that fails it (an alternative)
STOP_CHECKS = ("grid", "every_bar")


@dataclass(frozen=True)
class IntradayConfig:
    """The strategy's settings. Defaults are the paper's, with the owner's WIN choices (brief
    section 10): a R$ 100,000 account, R$ 0.20 a point, R$ 0.25 per contract and side (B3's
    R$ 0.50 round trip, no brokerage, no slippage), a 09:00 session open and an exit at 17:30.
    Times are minutes since midnight; `first_decision` and `exit_minute` are the two the owner
    wants searched. `fixed_contracts` trades that many contracts every day instead of the volatility
    target (1 is the single-contract version). `margin_per_contract` is what the broker asks for a
    WIN mini contract (R$ 1,000, the owner's figure; 0 switches the limit off): the contracts are
    capped at what the equity can margin, which the default R$ 100,000 account never reaches.
    `stop` picks the exit rule (see `STOPS`), `sides` trades only the long or the short leg, and
    `leverage` replaces the volatility target by a constant leverage (1 is the paper's '100%').
    `stop_check` is when a stop is acted on: `grid` at the half-hour decisions (the paper's rule
    and the default), `every_bar` at the first bar close that fails it (an alternative)."""

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
    stop: str = "vwap_band"
    sides: str = "both"
    leverage: float | None = None
    stop_check: str = "grid"

    def __post_init__(self) -> None:
        if self.stop_check not in STOP_CHECKS:
            raise ValueError(f"stop_check must be one of {STOP_CHECKS}, got {self.stop_check!r}")
        if self.stop not in STOPS:
            raise ValueError(f"stop must be one of {STOPS}, got {self.stop!r}")
        if self.sides not in ("both", "long", "short"):
            raise ValueError(f"sides must be both, long or short, got {self.sides!r}")


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
        if config.leverage is not None:
            leverage = config.leverage
        elif math.isnan(volatility) or volatility <= 0:
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
    vwap = session_vwap(bars)

    def expose(signal: pd.Series, hold_zero: bool = False) -> pd.Series:
        return intraday_exposure(
            signal,
            session_open=config.session_open,
            trade_freq=config.trade_freq,
            first_decision=config.first_decision,
            exit_minute=config.exit_minute,
            hold_zero=hold_zero,
        )

    if config.stop == "vwap_only" or config.stop_check == "every_bar":
        exposure = bar_by_bar_exposure(
            bars["close"],
            bands,
            vwap,
            stop=config.stop,
            every_bar=config.stop_check == "every_bar",
            session_open=config.session_open,
            trade_freq=config.trade_freq,
            first_decision=config.first_decision,
            exit_minute=config.exit_minute,
        )
    elif config.stop == "vwap_band":
        exposure = expose(breakout_signal(bars["close"], bands, vwap))
    elif config.stop == "current_band":
        exposure = expose(band_signal(bars["close"], bands))
    else:
        exposure = expose(band_signal(bars["close"], bands), hold_zero=True)
    if config.sides == "long":
        exposure = exposure.clip(lower=0.0)
    elif config.sides == "short":
        exposure = exposure.clip(upper=0.0)
    return sigma, exposure


def strategy_exposure(bars: pd.DataFrame, config: IntradayConfig) -> pd.Series:
    """The position (-1, 0, +1) held during each bar, from the bars and the settings alone."""
    return _sigma_and_exposure(bars, config)[1]


def run_intraday_momentum(bars: pd.DataFrame, config: IntradayConfig) -> pd.DataFrame:
    """The daily backtest of the authors' notebook, one row per day.

    Columns: `contracts`, `trades` (sides, in and out), `gross`, `cost`, `net` (reais), `ret`
    (net over the equity of the day before), `aum`, `margin` (what the contracts of the day tie up
    at the broker), `exposure` (the index value the contracts control at the open, in reais) and
    `leverage` (that exposure over the equity of the day before). Exposure and leverage are what
    the paper's shares are in its formula: the day's gain over the equity is the leverage times the
    index move, for shares and contracts alike. The first day, and days without any
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
            rows.append((0, 0.0, 0.0, 0.0, 0.0, math.nan, aum, 0.0, 0.0, 0.0))
            continue
        where = positions[current]
        exposed = held[where]
        points = float(np.nansum(exposed * np.diff(close[where], prepend=np.nan)))
        trades = float(np.abs(np.diff(np.append(exposed, 0.0))).sum())
        size = contracts_for(aum, float(day_open[current]), float(volatility[current]), config)
        gross = points * size * config.point_value
        cost = trades * size * config.fee_per_side
        net = gross - cost
        notional = size * float(day_open[current]) * config.point_value
        previous, aum = aum, aum + net
        rows.append(
            (
                size,
                trades,
                gross,
                cost,
                net,
                net / previous,
                aum,
                size * config.margin_per_contract,
                notional,
                notional / previous,
            )
        )
    return pd.DataFrame(
        rows,
        index=day.unique(),
        columns=[
            "contracts",
            "trades",
            "gross",
            "cost",
            "net",
            "ret",
            "aum",
            "margin",
            "exposure",
            "leverage",
        ],
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


def extended_performance(returns: pd.Series) -> dict[str, float]:
    """Statistics beyond `performance`, on daily returns indexed by date (missing days left out).

    `profit_factor` is the sum of the winning days over the sum of the losing days (infinite
    with no losing day); `sortino` is the mean over the downside deviation around zero, times the
    root of 252; `cagr` compounds the daily returns over the calendar years between the first and
    last day (days / 365.25, as docs/cdi.md); `calmar` is `cagr` over the worst drawdown.
    """
    clean = returns.dropna()
    if len(clean) < 2:
        raise ValueError("need at least two returns")
    r = clean.to_numpy(dtype=np.float64)
    equity = np.concatenate(([1.0], np.cumprod(1.0 + r)))
    peak = np.maximum.accumulate(equity)
    drawdown = float(((peak - equity) / peak).max())
    years = (clean.index[-1] - clean.index[0]).days / 365.25
    cagr = float(equity[-1] ** (1.0 / years) - 1.0)
    losses = float(-r[r < 0].sum())
    downside = math.sqrt(float(np.mean(np.minimum(r, 0.0) ** 2)))
    return {
        "profit_factor": float(r[r > 0].sum()) / losses if losses > 0 else math.inf,
        "sortino": float(r.mean()) / downside * math.sqrt(252) if downside > 0 else math.nan,
        "cagr": cagr,
        "years": years,
        "max_drawdown": drawdown,
        "calmar": cagr / drawdown if drawdown > 0 else math.nan,
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


def trade_list(bars: pd.DataFrame, config: IntradayConfig, result: pd.DataFrame) -> pd.DataFrame:
    """One row per trade: a run of the same position inside a day.

    It is entered at the close of the decision bar (`entry_time` is that close) and left at the
    close of the last bar held (`exit_time`), which is the end of the day or the bar before a
    change of position. A reversal is two trades at the same price. `points` are per contract,
    `ret` is points over the entry price, and `gross`, `cost` (both sides) and `net` are in
    reais on the day's contracts, so the net of a day's trades adds up to the day's `net`.
    """
    exposure = strategy_exposure(bars, config).to_numpy(dtype=np.float64)
    close = bars["close"].to_numpy(dtype=np.float64)
    day = pd.DatetimeIndex(bars.index).normalize()
    one_minute = pd.Timedelta(minutes=1)
    contracts_by_day = result["contracts"].to_dict()
    rows = []
    for current, where in bars.groupby(day).indices.items():
        size = int(contracts_by_day[current])
        held = exposure[where]
        if size == 0 or not held.any():
            continue
        stamps = bars.index[where]
        prices = close[where]
        start = 0
        while start < len(held):
            if held[start] == 0:
                start += 1
                continue
            side = held[start]
            stop = start
            while stop + 1 < len(held) and held[stop + 1] == side:
                stop += 1
            entry, leave = prices[start - 1], prices[stop]
            points = side * (leave - entry)
            gross = points * size * config.point_value
            cost = 2 * size * config.fee_per_side
            rows.append(
                (
                    current,
                    int(side),
                    stamps[start - 1] + one_minute,
                    stamps[stop] + one_minute,
                    entry,
                    leave,
                    points,
                    points / entry,
                    size,
                    gross,
                    cost,
                    gross - cost,
                )
            )
            start = stop + 1
    return pd.DataFrame(
        rows,
        columns=[
            "day",
            "side",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "points",
            "ret",
            "contracts",
            "gross",
            "cost",
            "net",
        ],
    )
