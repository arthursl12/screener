"""Extra statistics on daily returns: profit factor, Sortino, Calmar and the calendar CAGR."""

import math

import numpy as np
import pandas as pd
import pytest

from b3core.intraday_momentum import extended_performance


def series(values: list[float], start: str = "2022-01-03") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_profit_factor_is_the_gains_over_the_losses() -> None:
    stats = extended_performance(series([0.02, -0.01, 0.03, -0.01, 0.0]))
    assert stats["profit_factor"] == pytest.approx(0.05 / 0.02)


def test_profit_factor_without_a_losing_day_is_infinite() -> None:
    assert extended_performance(series([0.01, 0.02]))["profit_factor"] == math.inf


def test_sortino_uses_the_downside_deviation_around_zero() -> None:
    values = [0.02, -0.01, 0.03, -0.03]
    stats = extended_performance(series(values))
    r = np.array(values)
    downside = math.sqrt(np.mean(np.minimum(r, 0.0) ** 2))
    assert stats["sortino"] == pytest.approx(r.mean() / downside * math.sqrt(252))


def test_cagr_uses_the_calendar_years_of_the_window() -> None:
    returns = series([0.001] * 200)
    stats = extended_performance(returns)
    years = (returns.index[-1] - returns.index[0]).days / 365.25
    assert stats["cagr"] == pytest.approx((1.001**200) ** (1 / years) - 1)
    assert stats["years"] == pytest.approx(years)


def test_calmar_is_the_cagr_over_the_worst_drawdown() -> None:
    stats = extended_performance(series([0.10, -0.20, 0.05] + [0.001] * 100))
    assert stats["calmar"] == pytest.approx(stats["cagr"] / stats["max_drawdown"])
    assert stats["max_drawdown"] == pytest.approx(0.20)


def test_missing_days_are_left_out() -> None:
    with_gap = extended_performance(series([0.01, float("nan"), -0.01]))
    assert with_gap["profit_factor"] == pytest.approx(1.0)
