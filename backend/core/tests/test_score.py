"""score_v1 (docs/score.md). The two rows of the worked example are the first tests."""

import math
from dataclasses import replace

import pytest

from b3core.metrics import Metrics, compute_metrics
from b3core.score import SCORE_VERSION, score_v1

EMPTY = compute_metrics([], capital=1.0)


def metrics(
    n: int = 300,
    pf: float = 2.0,
    dd: float | None = 0.10,
    ev: float = 0.003,
    balance_dd: float = 0.0,
) -> Metrics:
    return replace(
        EMPTY,
        n_trades=n,
        profit_factor=pf,
        max_equity_drawdown=dd,
        max_drawdown=balance_dd,
        ev=ev,
    )


def test_version_tag() -> None:
    assert SCORE_VERSION == 1


def test_worked_example_all_wins_with_a_small_sample() -> None:
    # every component is 1 (base 100), confidence 21 / 51
    assert score_v1(metrics(n=21, pf=math.inf, dd=0.0, ev=0.010)) == pytest.approx(41.2, abs=0.05)


def test_worked_example_normal_combo() -> None:
    # s_pf = 1 / 1.5, s_dd = 1 - 0.10 / 0.30, s_ev = 0.003 / 0.005 = 0.6 -> base 64.67,
    # confidence 300 / 330
    assert score_v1(metrics()) == pytest.approx(58.8, abs=0.05)


def test_the_normal_combo_outranks_the_all_wins_small_sample() -> None:
    small = metrics(n=21, pf=math.inf, dd=0.0, ev=0.010)

    assert score_v1(metrics()) > score_v1(small)


def test_infinite_profit_factor_and_zero_drawdown_give_a_finite_score() -> None:
    score = score_v1(metrics(pf=math.inf, dd=0.0))

    assert math.isfinite(score)
    assert score <= 100


def test_components_are_clipped() -> None:
    perfect = score_v1(metrics(n=10**9, pf=100.0, dd=0.0, ev=1.0))
    worst = score_v1(metrics(pf=0.5, dd=0.9, ev=-0.01))

    assert perfect == pytest.approx(100.0, abs=0.01)
    assert worst == 0.0


def test_score_rises_with_profit_factor_and_expectancy_and_falls_with_drawdown() -> None:
    assert score_v1(metrics(pf=1.5)) < score_v1(metrics(pf=2.0))
    assert score_v1(metrics(ev=0.002)) < score_v1(metrics(ev=0.003))
    assert score_v1(metrics(dd=0.20)) < score_v1(metrics(dd=0.10))


def test_more_trades_never_score_lower() -> None:
    assert score_v1(metrics(n=30)) < score_v1(metrics(n=300)) < score_v1(metrics(n=3_000))


def test_no_trades_scores_zero() -> None:
    assert score_v1(EMPTY) == 0.0


def test_the_balance_drawdown_stands_in_when_there_is_no_equity_curve() -> None:
    assert score_v1(metrics(dd=None, balance_dd=0.10)) == pytest.approx(score_v1(metrics()))
