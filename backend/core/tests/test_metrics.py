import math

import pytest
from helpers import C1, C2, C3, C4_ENTRY, C5_TARGET, make_candles
from hypothesis import given, settings
from hypothesis import strategies as st

from b3core.engine import BacktestConfig, run_backtest
from b3core.metrics import compute_metrics


def test_reference_screenshot_numbers_from_the_brief() -> None:
    # 173 trades, 102 wins at R$ 613.75, 71 losses at R$ 427.72, capital R$ 100,000.
    pnls = [613.75] * 102 + [-427.72] * 71

    m = compute_metrics(pnls, capital=100_000)

    assert m.n_trades == 173
    assert m.n_wins == 102
    assert m.result == pytest.approx(0.322, abs=0.0005)  # 32.2%
    assert m.profit_factor == pytest.approx(2.06, abs=0.005)
    assert m.avg_gain == pytest.approx(613.75)
    assert m.avg_loss == pytest.approx(427.72)


def test_ev_equals_result_per_trade() -> None:
    pnls = [613.75] * 102 + [-427.72] * 71
    m = compute_metrics(pnls, capital=100_000)

    w = 102 / 173
    assert m.win_rate == pytest.approx(w)
    assert m.ev == pytest.approx((w * 613.75 - (1 - w) * 427.72) / 100_000)
    assert m.ev == pytest.approx(m.result / m.n_trades)


def test_streaks_count_consecutive_wins_and_losses() -> None:
    #         W    W    L    W    0    L    L    L    W
    pnls = [10, 20, -5, 10, 0.0, -1, -2, -3, 7]

    m = compute_metrics(pnls, capital=1_000)

    assert m.best_streak == 2
    assert m.worst_streak == 3  # a zero PnL trade is neither a win nor a loss


def test_max_drawdown_is_the_largest_peak_to_trough_fall_over_capital() -> None:
    # cumulative PnL: 100, 50, 20, 220, -80, -30 -> worst fall is 220 down to -80 = 300
    m = compute_metrics([100, -50, -30, 200, -300, 50], capital=1_000)

    assert m.max_drawdown == pytest.approx(0.30)


def test_drawdown_counts_from_the_initial_capital() -> None:
    m = compute_metrics([-100, -50], capital=1_000)

    assert m.max_drawdown == pytest.approx(0.15)


def test_no_trades_gives_zeros() -> None:
    m = compute_metrics([], capital=100_000)

    assert (m.n_trades, m.n_wins, m.result) == (0, 0, 0.0)
    assert (m.profit_factor, m.max_drawdown) == (0.0, 0.0)
    assert (m.win_rate, m.ev, m.best_streak, m.worst_streak) == (0.0, 0.0, 0, 0)


def test_only_winning_trades_give_infinite_profit_factor() -> None:
    m = compute_metrics([10, 20], capital=1_000)

    assert math.isinf(m.profit_factor)
    assert m.avg_loss == 0.0


def test_result_exposes_metrics_and_an_equity_curve() -> None:
    result = run_backtest(
        make_candles([C1, C2, C3, C4_ENTRY, C5_TARGET]), BacktestConfig(max_risk_brl=200)
    )

    assert result.metrics.n_trades == 1
    assert result.metrics.result == pytest.approx(360.0 / 100_000)

    curve = result.equity_curve()
    assert list(curve.columns) == ["ts", "equity"]
    assert curve["equity"].tolist() == pytest.approx([100_000.0, 100_360.0])


@settings(max_examples=200, deadline=None)
@given(
    pnls=st.lists(st.floats(-5_000, 5_000, allow_nan=False), max_size=80),
    capital=st.floats(1_000, 1_000_000),
)
def test_metric_invariants(pnls: list[float], capital: float) -> None:
    m = compute_metrics(pnls, capital)

    assert m.n_trades == len(pnls)
    assert m.result == pytest.approx(sum(pnls) / capital)
    assert m.max_drawdown >= 0
    assert m.n_wins + m.n_losses <= m.n_trades
    assert 0 <= m.best_streak <= m.n_wins
    assert 0 <= m.worst_streak <= m.n_losses
