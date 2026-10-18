import sys
from pathlib import Path

import pandas as pd
import pytest

# Reuse the synthetic candle helpers from the core tests.
sys.path.insert(0, str(Path(__file__).parents[2] / "core" / "tests"))
from helpers import (  # noqa: E402
    C1,
    C2,
    C3,
    C4_ENTRY,
    C5_TARGET,
    make_candles,
    make_config,
    random_walk_candles,
)

from b3core.engine import run_backtest  # noqa: E402
from b3core.ifr2 import Ifr2Config, run_ifr2  # noqa: E402
from b3core.optimizer import ParamRange, ParamSpace, optimize  # noqa: E402
from b3report.charts import (  # noqa: E402
    DISCLAIMER,
    equity_curve_figure,
    heatmap_figure,
    ifr2_equity_figure,
    monthly_returns,
    monthly_returns_figure,
    trade_chart,
)

CANDLES = make_candles([C1, C2, C3, C4_ENTRY, C5_TARGET])
RESULT = run_backtest(CANDLES, make_config())  # one trade, +R$ 374


def test_disclaimer_says_educational_and_not_investment_advice() -> None:
    assert "educational" in DISCLAIMER.lower()
    assert "not investment advice" in DISCLAIMER.lower()


def test_equity_curve_plots_capital_then_capital_plus_pnl() -> None:
    fig = equity_curve_figure(RESULT)

    assert list(fig.data[0].y) == pytest.approx([100_000.0, 100_374.0])


def test_equity_curve_of_a_run_without_trades_is_an_empty_chart() -> None:
    empty = run_backtest(make_candles([C1, C2, C3]), make_config())

    assert len(equity_curve_figure(empty).data[0].y) == 0


def test_monthly_returns_groups_pnl_by_exit_month_over_capital() -> None:
    table = monthly_returns(RESULT)

    assert list(table.columns) == ["year", "month", "pnl", "return"]
    assert len(table) == 1
    assert (table.loc[0, "year"], table.loc[0, "month"]) == (2024, 1)
    assert table.loc[0, "pnl"] == pytest.approx(374.0)
    assert table.loc[0, "return"] == pytest.approx(0.00374)


def test_monthly_returns_figure_has_one_bar_per_month() -> None:
    fig = monthly_returns_figure(RESULT)

    assert list(fig.data[0].y) == pytest.approx([0.00374])


def test_trade_chart_shows_candles_entry_exit_stop_and_target() -> None:
    (trade,) = RESULT.trades
    fig = trade_chart(CANDLES, trade, context=2)

    candlestick = fig.data[0]
    assert candlestick.type == "candlestick"
    assert len(candlestick.x) == 4  # candles 1..4: entry_index 3 - 2 up to the last candle
    markers = [t for t in fig.data if t.type == "scatter"]
    assert sorted(m.name for m in markers) == ["entry", "exit"]
    assert len(fig.layout.shapes) == 2  # stop and target lines


def test_heatmap_pivots_two_parameters_and_averages_the_rest() -> None:
    space = ParamSpace(
        {
            "target_mult": ParamRange(1, 3, 1),
            "entry_offset_ticks": ParamRange(0, 2, 1),
            "stop_mode": ["C3", "C2"],
        }
    )
    result = optimize(random_walk_candles(400, seed=2), make_config(), space, oos_fraction=0)
    table = result.trials_table()

    fig = heatmap_figure(table, x="entry_offset_ticks", y="target_mult")

    z = fig.data[0].z
    assert (len(z), len(z[0])) == (3, 3)
    assert list(fig.data[0].x) == [0, 1, 2]
    assert list(fig.data[0].y) == [1, 2, 3]
    expected = table[(table.target_mult == 2) & (table.entry_offset_ticks == 1)].objective.mean()
    assert z[1][1] == pytest.approx(expected)


def test_heatmap_rejects_unknown_columns() -> None:
    with pytest.raises(ValueError, match="nope"):
        heatmap_figure(pd.DataFrame({"a": [1], "objective": [1.0]}), x="a", y="nope")


# --- IFR2 ------------------------------------------------------------------------------------

IFR2_ROWS = [
    (10.00, 10.10, 9.90, 10.00),
    (10.00, 10.60, 10.00, 10.50),
    (10.50, 10.60, 10.10, 10.20),
    (10.20, 10.30, 9.70, 9.80),
    (9.80, 9.90, 9.40, 9.50),  # signal: buy 93 at the close, 9.50
    (9.60, 10.00, 9.00, 9.00),  # equity 10,000 + 93 * (9.00 - 9.50) = 9,953.50
    (9.00, 9.20, 8.90, 9.10),  # equity 10,000 + 93 * (9.10 - 9.50) = 9,962.80
]
IFR2_CONFIG = Ifr2Config(atr_period=2, max_risk_brl=100, capital_brl=10_000, lot_size=1)
IFR2_CANDLES = make_candles(IFR2_ROWS)
IFR2_RESULT = run_ifr2(IFR2_CANDLES, IFR2_CONFIG)  # still open at the end: no closed trade


def test_ifr2_equity_figure_plots_the_daily_equity_and_its_drawdown() -> None:
    fig = ifr2_equity_figure(IFR2_RESULT, IFR2_CANDLES)

    equity, drawdown = fig.data
    # plotly keeps the instants but drops the time zone
    assert list(pd.DatetimeIndex(equity.x).tz_localize("UTC")) == list(IFR2_CANDLES["ts"])
    assert list(equity.y) == pytest.approx([10_000] * 5 + [9_953.5, 9_962.8])
    # (equity - peak) / peak, with the peak starting at the initial capital
    assert list(drawdown.y) == pytest.approx([0, 0, 0, 0, 0, -0.00465, -0.00372])


def test_ifr2_equity_figure_rejects_candles_of_another_length() -> None:
    with pytest.raises(ValueError, match="candles"):
        ifr2_equity_figure(IFR2_RESULT, IFR2_CANDLES.iloc[:3])


def test_monthly_returns_accepts_an_ifr2_result() -> None:
    rows = [*IFR2_ROWS[:5], (9.60, 10.00, 9.50, 9.90), (9.90, 10.10, 9.80, 10.00)]
    result = run_ifr2(make_candles(rows), IFR2_CONFIG)  # the worked example: +R$ 46.50

    table = monthly_returns(result)

    assert table["pnl"].tolist() == pytest.approx([46.50])
    assert table["return"].tolist() == pytest.approx([46.50 / 10_000])
