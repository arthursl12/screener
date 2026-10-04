"""Property-based tests: invariants of the engine over generated candle series (brief section 8)."""

import pandas as pd
from helpers import make_candles
from hypothesis import given, settings
from hypothesis import strategies as st

from b3core.engine import BacktestConfig, run_backtest


@st.composite
def candle_series(draw: st.DrawFn) -> pd.DataFrame:
    """A random walk on a 0.01 tick grid; every candle satisfies low <= open, close <= high."""
    n = draw(st.integers(min_value=3, max_value=60))
    price = draw(st.integers(min_value=500, max_value=3000))  # in ticks (cents)
    rows = []
    for _ in range(n):
        open_ = max(price + draw(st.integers(-40, 40)), 100)
        close = max(open_ + draw(st.integers(-60, 60)), 100)
        high = max(open_, close) + draw(st.integers(0, 50))
        low = max(min(open_, close) - draw(st.integers(0, 50)), 1)
        rows.append((open_ / 100, high / 100, low / 100, close / 100))
        price = close
    return make_candles(rows)


@st.composite
def configs(draw: st.DrawFn) -> BacktestConfig:
    return BacktestConfig(
        capital_brl=draw(st.sampled_from([5_000.0, 20_000.0, 100_000.0])),
        max_risk_brl=draw(st.sampled_from([50.0, 200.0, 2_000.0])),
        lot_size=draw(st.sampled_from([1, 100])),
        stop_mode=draw(st.sampled_from(["c2_low", "c3_low"])),
        target_mode=draw(st.sampled_from(["risk_fixed", "amplitude"])),
        risk_factor=draw(st.sampled_from([1.0, 1.5, 2.0, 5.0])),
        entry_offset_ticks=draw(st.integers(0, 3)),
        entry_validity_candles=draw(st.integers(1, 4)),
        inside_bar=draw(st.booleans()),
    )


PROPERTY = settings(max_examples=150, deadline=None)


@PROPERTY
@given(candles=candle_series(), config=configs(), data=st.data())
def test_prefix_invariance_no_look_ahead(
    candles: pd.DataFrame, config: BacktestConfig, data: st.DataObject
) -> None:
    cut = data.draw(st.integers(min_value=1, max_value=len(candles)))

    full = run_backtest(candles, config).trades
    prefix = run_backtest(candles.iloc[:cut].reset_index(drop=True), config).trades

    closed_before_cut = [t for t in full if t.exit_index < cut]
    assert prefix == closed_before_cut


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_trades_are_ordered_and_never_overlap(
    candles: pd.DataFrame, config: BacktestConfig
) -> None:
    trades = run_backtest(candles, config).trades

    for t in trades:
        assert t.exit_index >= t.entry_index
        assert t.exit_ts >= t.entry_ts
    for previous, current in zip(trades, trades[1:], strict=False):
        assert current.entry_index > previous.exit_index
        assert current.n == previous.n + 1


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_stop_is_below_entry_and_target_above(
    candles: pd.DataFrame, config: BacktestConfig
) -> None:
    for t in run_backtest(candles, config).trades:
        assert t.stop < t.entry < t.target


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_quantity_respects_lot_capital_and_risk(
    candles: pd.DataFrame, config: BacktestConfig
) -> None:
    for t in run_backtest(candles, config).trades:
        assert t.qty > 0
        assert t.qty % config.lot_size == 0
        assert t.qty * t.entry <= config.capital_brl + 1e-6
        assert t.qty * (t.entry - t.stop) <= config.max_risk_brl + 1e-6


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_exit_price_is_a_stop_or_target_fill(candles: pd.DataFrame, config: BacktestConfig) -> None:
    for t in run_backtest(candles, config).trades:
        if t.exit_reason == "target":
            assert t.exit == t.target
            assert t.pnl > 0
        else:
            assert t.exit <= t.stop  # at the stop, or below it after a gap
            assert t.pnl < 0


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_same_inputs_give_identical_results(candles: pd.DataFrame, config: BacktestConfig) -> None:
    assert run_backtest(candles, config) == run_backtest(candles.copy(), config)


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_sum_of_pnl_equals_final_equity_minus_capital(
    candles: pd.DataFrame, config: BacktestConfig
) -> None:
    result = run_backtest(candles, config)
    curve = result.equity_curve()

    total = sum(t.pnl for t in result.trades)
    final = curve["equity"].iloc[-1] if len(curve) else config.capital_brl
    assert abs(final - config.capital_brl - total) < 1e-6
