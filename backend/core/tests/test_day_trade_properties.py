"""Property-based tests of day-trade mode over generated multi-day H2 series."""

import pandas as pd
from helpers import Row, make_candles_at
from hypothesis import given, settings
from hypothesis import strategies as st

from b3core.data import Timeframe
from b3core.engine import TRADING_TIMEZONE, BacktestConfig, parse_hhmm, run_backtest

PERIOD = Timeframe.H2.minutes
SESSION = ["10:00", "12:00", "14:00", "16:00"]  # complete days: every day has an exit candle


@st.composite
def multi_day_series(draw: st.DrawFn) -> pd.DataFrame:
    n_days = draw(st.integers(min_value=2, max_value=8))
    price = draw(st.integers(min_value=500, max_value=3000))  # in ticks (cents)
    rows: list[Row] = []
    times: list[str] = []
    for day in range(n_days):
        for hhmm in SESSION:
            times.append(f"2024-01-{2 + day:02d} {hhmm}")
            open_ = max(price + draw(st.integers(-40, 40)), 100)
            close = max(open_ + draw(st.integers(-60, 60)), 100)
            high = max(open_, close) + draw(st.integers(0, 50))
            low = max(min(open_, close) - draw(st.integers(0, 50)), 1)
            rows.append((open_ / 100, high / 100, low / 100, close / 100))
            price = close
    return make_candles_at(rows, times)


@st.composite
def day_configs(draw: st.DrawFn) -> BacktestConfig:
    return BacktestConfig(
        max_risk_brl=draw(st.sampled_from([50.0, 200.0, 2_000.0])),
        lot_size=draw(st.sampled_from([1, 100])),
        ma_fast_period=draw(st.sampled_from([1, 2, 3])),
        ma_slow_period=draw(st.sampled_from([2, 4, 6])),
        use_ma_order=draw(st.booleans()),
        use_fast_slope=draw(st.booleans()),
        use_slow_slope=draw(st.booleans()),
        entry_offset_ticks=draw(st.integers(0, 2)),
        entry_validity_bars=draw(st.integers(1, 3)),
        stop_mode=draw(st.sampled_from(["C3", "C2"])),
        target_mode=draw(st.sampled_from(["AMP", "RISK"])),
        target_mult=draw(st.sampled_from([1.0, 2.0, 3.0])),
        day_trade=True,
        min_entry_time=draw(st.sampled_from(["00:00", "11:00", "13:00"])),
        max_entry_time=draw(st.sampled_from([None, "15:00"])),
        exit_time=draw(st.sampled_from(["16:30", "15:30"])),
        day_exit_policy=draw(st.sampled_from(["last_candle_close", "last_candle_open"])),
    )


PROPERTY = settings(max_examples=120, deadline=None)


def local(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.tz_convert(TRADING_TIMEZONE)


def run(candles: pd.DataFrame, config: BacktestConfig):  # type: ignore[no-untyped-def]
    return run_backtest(candles, config, timeframe=Timeframe.H2).trades


@PROPERTY
@given(candles=multi_day_series(), config=day_configs())
def test_no_position_survives_its_day(candles: pd.DataFrame, config: BacktestConfig) -> None:
    for t in run(candles, config):
        assert local(t.entry_ts).date() == local(t.exit_ts).date()


@PROPERTY
@given(candles=multi_day_series(), config=day_configs())
def test_fills_happen_inside_the_entry_window_and_end_by_the_exit_time(
    candles: pd.DataFrame, config: BacktestConfig
) -> None:
    exit_minute = parse_hhmm(config.exit_time, "exit_time")
    max_entry = (
        exit_minute
        if config.max_entry_time is None
        else parse_hhmm(config.max_entry_time, "max_entry_time")
    )
    for t in run(candles, config):
        opened = local(t.entry_ts)
        minute = opened.hour * 60 + opened.minute
        assert parse_hhmm(config.min_entry_time, "min_entry_time") <= minute < max_entry
        assert minute + PERIOD <= exit_minute


@PROPERTY
@given(candles=multi_day_series(), config=day_configs())
def test_forced_exits_happen_on_a_candle_ending_after_the_exit_time(
    candles: pd.DataFrame, config: BacktestConfig
) -> None:
    exit_minute = parse_hhmm(config.exit_time, "exit_time")
    for t in run(candles, config):
        closed = local(t.exit_ts)
        if t.exit_reason == "time":
            assert closed.hour * 60 + closed.minute + PERIOD > exit_minute


@PROPERTY
@given(candles=multi_day_series(), config=day_configs(), data=st.data())
def test_prefix_invariance_holds_in_day_trade_mode(
    candles: pd.DataFrame, config: BacktestConfig, data: st.DataObject
) -> None:
    cut = data.draw(st.integers(min_value=1, max_value=len(candles)))

    full = run(candles, config)
    prefix = run(candles.iloc[:cut].reset_index(drop=True), config)

    assert prefix == [t for t in full if t.exit_index < cut]


@PROPERTY
@given(candles=multi_day_series(), config=day_configs())
def test_trades_keep_the_basic_invariants(candles: pd.DataFrame, config: BacktestConfig) -> None:
    trades = run(candles, config)

    for t in trades:
        assert t.stop < t.entry
        assert t.qty > 0 and t.qty % config.lot_size == 0
        assert t.qty * t.entry <= config.capital_brl + 1e-6
        assert t.exit_index >= t.entry_index
    for previous, current in zip(trades, trades[1:], strict=False):
        assert current.entry_index > previous.exit_index
