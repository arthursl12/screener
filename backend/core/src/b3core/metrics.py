"""Backtest metrics (brief section 6). Denominator is the initial capital, never compounded."""

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


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
    max_drawdown: float  # positive fraction

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _longest_run(flags: Sequence[bool]) -> int:
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0
        best = max(best, current)
    return best


def compute_metrics(pnls: Sequence[float], capital: float) -> Metrics:
    """A win has PnL above zero and a loss below zero; a zero PnL trade is neither."""
    n = len(pnls)
    if n == 0:
        return Metrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0.0)

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
    )
