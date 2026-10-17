"""score_v1: an original 0 to 100 score (docs/score.md). Pure, no I/O.

It combines profit factor, drawdown and expectancy, then shrinks the result for small samples,
so a lucky run of a few winning trades cannot outrank a long, solid one. `inf` profit factor and
a zero drawdown are valid inputs. Any change to a weight or constant needs a new version.
"""

import math

from b3core.metrics import Metrics

SCORE_VERSION = 1

_PF_SPAN = 1.5  # profit factor 1.0 scores 0, 2.5 or more scores 1
_DD_LIMIT = 0.30  # a drawdown of 30% or more scores 0
_EV_FULL = 0.005  # an expectancy of 0.5% of capital per trade or more scores 1
_WEIGHTS = (0.35, 0.35, 0.30)  # profit factor, drawdown, expectancy
_HALF_CREDIT_TRADES = 30  # confidence is 0.5 at this many trades


def _clip(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def score_v1(metrics: Metrics) -> float:
    """Score of one run, 0 to 100. Uses the equity drawdown, or the balance drawdown without one."""
    drawdown = (
        metrics.max_equity_drawdown
        if metrics.max_equity_drawdown is not None
        else metrics.max_drawdown
    )
    profit_factor = (
        _clip((metrics.profit_factor - 1) / _PF_SPAN)
        if not math.isnan(metrics.profit_factor)
        else 0.0
    )
    base = 100 * (
        _WEIGHTS[0] * profit_factor
        + _WEIGHTS[1] * _clip(1 - drawdown / _DD_LIMIT)
        + _WEIGHTS[2] * _clip(metrics.ev / _EV_FULL)
    )
    confidence = metrics.n_trades / (metrics.n_trades + _HALF_CREDIT_TRADES)
    return base * confidence
