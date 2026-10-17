"""Backtest metrics (brief section 6). Denominator is the initial capital, never compounded."""

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class Metrics:
    """Fractions (result, ev, max_drawdown) are of initial capital: 0.322 means 32.2%."""

    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    net_pnl: float
    result: float
    avg_gain: float  # mean PnL of winning trades
    avg_loss: float  # mean absolute PnL of losing trades
    ev: float
    profit_factor: float  # inf when there are gains and no losses, 0 with no trades
    best_streak: int  # longest run of consecutive wins
    worst_streak: int  # longest run of consecutive losses
    max_drawdown: float  # positive fraction of initial capital, on closed trades (balance)
    # The three fields below need an equity curve and a period (docs/score.md); None without.
    max_equity_drawdown: float | None = None  # positive fraction of the equity peak
    cagr: float | None = None  # annualised result of the closed trades; -1.0 on a total loss

    @property
    def calmar(self) -> float | None:
        """CAGR over the equity drawdown; inf with a gain and no drawdown."""
        if self.cagr is None or self.max_equity_drawdown is None:
            return None
        if self.max_equity_drawdown == 0:
            return math.inf if self.cagr > 0 else 0.0
        return self.cagr / self.max_equity_drawdown

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _longest_run(flags: Sequence[bool]) -> int:
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best


def _equity_drawdown(equity: Sequence[float] | NDArray[np.float64], capital: float) -> float:
    """Largest fall of the equity curve over its running peak. The curve starts at the capital."""
    curve = np.concatenate(([capital], np.asarray(equity, dtype=np.float64)))
    peak = np.maximum.accumulate(curve)
    return float(((peak - curve) / peak).max())


def _cagr(net_pnl: float, capital: float, years: float) -> float:
    final = capital + net_pnl
    return (final / capital) ** (1 / years) - 1 if final > 0 else -1.0


def compute_metrics(
    pnls: Sequence[float],
    capital: float,
    *,
    equity: Sequence[float] | NDArray[np.float64] | None = None,
    years: float | None = None,
) -> Metrics:
    """A win has PnL above zero and a loss below zero; a zero PnL trade is neither.

    `equity` is the equity curve in currency, one value per bar (closed PnL plus the open
    position marked at the close); it adds `max_equity_drawdown`. `years` is the length of
    the period; it adds `cagr`.
    """
    if years is not None and years <= 0:
        raise ValueError("years must be positive")
    max_equity_drawdown = None if equity is None else _equity_drawdown(equity, capital)
    n = len(pnls)
    if n == 0:
        return Metrics(
            0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0,
            max_equity_drawdown=max_equity_drawdown,
            cagr=None if years is None else 0.0,
        )  # fmt: skip

    values = np.asarray(pnls, dtype=np.float64)
    gains = values[values > 0]
    losses = -values[values < 0]
    net = float(values.sum())

    win_rate = len(gains) / n
    avg_gain = float(gains.mean()) if len(gains) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0

    if losses.sum() > 0:
        with np.errstate(over="ignore"):  # a tiny loss total overflows to inf, the true limit
            profit_factor = float(gains.sum() / losses.sum())
    else:
        profit_factor = math.inf if gains.sum() > 0 else 0.0

    # Equity path starts at zero PnL, so a losing start counts as drawdown from the capital.
    path = np.concatenate(([0.0], np.cumsum(values)))
    drawdown = np.maximum.accumulate(path) - path

    return Metrics(
        n_trades=n,
        n_wins=len(gains),
        n_losses=len(losses),
        win_rate=win_rate,
        net_pnl=net,
        result=net / capital,
        avg_gain=avg_gain,
        avg_loss=avg_loss,
        ev=(win_rate * avg_gain - (1 - win_rate) * avg_loss) / capital,
        profit_factor=profit_factor,
        best_streak=_longest_run([bool(v > 0) for v in values]),
        worst_streak=_longest_run([bool(v < 0) for v in values]),
        max_drawdown=float(drawdown.max()) / capital,
        max_equity_drawdown=max_equity_drawdown,
        cagr=None if years is None else _cagr(net, capital, years),
    )
