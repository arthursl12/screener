"""Drawdown and Calmar on a hand-checkable series (see docs: balance vs equity)."""
import numpy as np
import pandas as pd
import pytest

from ifr2_optimizer import compute_stats, run_backtest

NAN = np.nan


def _sig(buy, sell, close, start="2020-01-01"):
    idx = pd.bdate_range(start, periods=len(close))
    return pd.DataFrame({"Buy Price": buy, "Sell Price": sell, "Close": close}, index=idx)


def _run(sig, **kw):
    kw = {"initial_capital": 10_000, "lot": 1, **kw}
    return run_backtest(sig, **kw)


def test_equity_drawdown_sees_the_open_loser_balance_drawdown_does_not():
    # buy 100 shares at 100, close falls to 80 and 90, exit at 98: closed trade = -R$ 200
    sig = _sig(buy=[100, NAN, NAN, NAN, NAN], sell=[NAN, NAN, NAN, 98, NAN],
               close=[100, 80, 90, 98, 98])
    stats = compute_stats(*_run(sig), years=1.0)
    assert stats["max_dd_balance"] == pytest.approx(2.0)    # 10_000 -> 9_800
    assert stats["max_dd"] == pytest.approx(20.0)           # 10_000 -> 8_000 on day 2


def test_equity_curve_has_one_point_per_bar_and_ends_at_balance_when_flat():
    sig = _sig(buy=[100, NAN, NAN, NAN, NAN], sell=[NAN, NAN, NAN, 98, NAN],
               close=[100, 80, 90, 98, 98])
    _, _, _, equity = _run(sig)
    assert list(equity) == pytest.approx([10_000, 8_000, 9_000, 9_800, 9_800])


def test_calmar_is_annualised_return_over_equity_drawdown():
    # same trades over twice the period -> lower annual return -> lower Calmar
    short = compute_stats(*_run(_sig([100, NAN, NAN, NAN], [NAN, NAN, 110, NAN], [100, 95, 110, 110])),
                          years=1.0)
    long_ = compute_stats(*_run(_sig([100, NAN, NAN, NAN], [NAN, NAN, 110, NAN], [100, 95, 110, 110])),
                          years=2.0)
    assert short["profit_pct"] == long_["profit_pct"] == pytest.approx(10.0)
    assert short["max_dd"] == pytest.approx(5.0)            # 10_000 -> 9_500 mid-trade
    assert short["cagr_pct"] == pytest.approx(10.0)
    assert short["calmar"] == pytest.approx(10.0 / 5.0)
    assert long_["cagr_pct"] == pytest.approx((1.1 ** 0.5 - 1) * 100, abs=0.01)
    assert long_["calmar"] < short["calmar"]
