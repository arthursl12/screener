"""Property-based tests: invariants of the Turtle engine over generated candle series (brief 8)."""

import pandas as pd
import pytest
from helpers import make_candles
from hypothesis import given, settings
from hypothesis import strategies as st

from b3core.turtle import TurtleConfig, run_turtle

# Random series add several units on one candle or skip tiny ones, which warns by design.
pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


@st.composite
def candle_series(draw: st.DrawFn) -> pd.DataFrame:
    """A random walk on a 0.01 tick grid; every candle satisfies low <= open, close <= high."""
    n = draw(st.integers(min_value=3, max_value=70))
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
def configs(draw: st.DrawFn) -> TurtleConfig:
    return TurtleConfig(
        entry_period=draw(st.integers(1, 6)),
        exit_period=draw(st.integers(1, 6)),
        atr_period=draw(st.integers(1, 5)),
        add_atr_mult=draw(st.sampled_from([0.5, 1.0, 2.0])),
        max_units=draw(st.integers(1, 5)),
        use_last_fill=draw(st.booleans()),
        capital_brl=draw(st.sampled_from([5_000.0, 25_000.0, 100_000.0])),
        risk_pct=draw(st.sampled_from([0.5, 2.0, 5.0])),
        lot_size=draw(st.sampled_from([1, 100])),
        fill_at=draw(st.sampled_from(["signal_close", "next_open"])),
    )


PROPERTY = settings(max_examples=150, deadline=None)


@PROPERTY
@given(candles=candle_series(), config=configs(), data=st.data())
def test_prefix_invariance_no_look_ahead(
    candles: pd.DataFrame, config: TurtleConfig, data: st.DataObject
) -> None:
    cut = data.draw(st.integers(min_value=1, max_value=len(candles)))

    full = run_turtle(candles, config).trades
    prefix = run_turtle(candles.iloc[:cut].reset_index(drop=True), config).trades

    assert prefix == [t for t in full if t.exit_index < cut]


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_trades_are_ordered_never_overlap_and_respect_the_limits(
    candles: pd.DataFrame, config: TurtleConfig
) -> None:
    trades = run_turtle(candles, config).trades

    previous_exit = -1
    for trade in trades:
        assert trade.entry_index > previous_exit or previous_exit == -1
        assert trade.exit_index > trade.entry_index
        assert 1 <= trade.units <= config.max_units
        assert trade.qty > 0 and trade.qty % config.lot_size == 0
        previous_exit = trade.exit_index


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_equity_has_one_value_per_candle_and_ends_at_the_realized_pnl_when_flat(
    candles: pd.DataFrame, config: TurtleConfig
) -> None:
    result = run_turtle(candles, config)

    assert len(result.equity) == len(candles)
    if result.open_units == 0:
        closed = sum(t.pnl for t in result.trades)
        assert result.equity[-1] == pytest.approx(config.capital_brl + closed)


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_peak_money_covers_every_trade(candles: pd.DataFrame, config: TurtleConfig) -> None:
    result = run_turtle(candles, config)

    for trade in result.trades:
        assert result.peak_cost >= trade.qty * trade.entry - 1e-6


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_costs_never_change_the_trades_only_lower_their_pnl(
    candles: pd.DataFrame, config: TurtleConfig
) -> None:
    free = run_turtle(candles, config).trades
    costly = run_turtle(candles, TurtleConfig(**{**config.to_dict(), "cost_pct": 0.03})).trades

    assert [(t.entry_index, t.exit_index, t.qty) for t in free] == [
        (t.entry_index, t.exit_index, t.qty) for t in costly
    ]
    assert all(c.pnl <= f.pnl for f, c in zip(free, costly, strict=True))


@PROPERTY
@given(candles=candle_series(), config=configs())
def test_same_input_same_output(candles: pd.DataFrame, config: TurtleConfig) -> None:
    first = run_turtle(candles, config)
    second = run_turtle(candles, config)

    assert first.trades == second.trades
    assert list(first.equity) == list(second.equity)
