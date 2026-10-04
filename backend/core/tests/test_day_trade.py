"""Day-trade mode, brief section 7. Every number is hand computed.

Base timeline on H2 candles (São Paulo time), worked-example prices, max risk 200:
risk per share 0.36, 500 shares, entry 10.56, stop 10.20, target 11.28.
"""

import pytest
from helpers import C1, C2, C3, C4_ENTRY, C5_TARGET, Row, make_candles_at

from b3core.data import Timeframe
from b3core.engine import BacktestConfig, run_backtest

SWING = BacktestConfig(max_risk_brl=200)
DAY = BacktestConfig(max_risk_brl=200, day_trade=True)  # exit 16:30, window from start of day

QUIET: Row = (10.55, 10.70, 10.40, 10.60)  # stays between the stop and the target
K_CANDLE: Row = (10.65, 11.30, 10.50, 11.25)  # opens at 10.65, reaches the target later on

# c1, c2 on Jan 2; the signal c3 and the fill are on Jan 3. The 16:00 candle contains 16:30.
TIMES_A = [
    "2024-01-02 14:00",
    "2024-01-02 16:00",
    "2024-01-03 10:00",
    "2024-01-03 12:00",
    "2024-01-03 14:00",
    "2024-01-03 16:00",
]
ROWS_A = [C1, C2, C3, C4_ENTRY, QUIET, K_CANDLE]


def run(rows, times, config=DAY, intraday=None, timeframe=Timeframe.H2):  # type: ignore[no-untyped-def]
    return run_backtest(
        make_candles_at(rows, times), config, timeframe=timeframe, intraday=intraday
    ).trades


@pytest.mark.parametrize(
    ("timeframe", "minutes"),
    [
        (Timeframe.M1, 1),
        (Timeframe.M5, 5),
        (Timeframe.M15, 15),
        (Timeframe.M30, 30),
        (Timeframe.H1, 60),
        (Timeframe.H2, 120),
        (Timeframe.H4, 240),
        (Timeframe.D1, 1440),
    ],
)
def test_timeframe_minutes(timeframe: Timeframe, minutes: int) -> None:
    assert timeframe.minutes == minutes


def test_forced_exit_is_the_open_of_the_candle_containing_the_exit_time() -> None:
    (t,) = run(ROWS_A, TIMES_A)

    assert (t.entry_index, t.exit_index) == (3, 5)
    assert t.exit == pytest.approx(10.65)
    assert t.exit_reason == "time"
    assert t.pnl == pytest.approx(45.00)  # 500 * (10.65 - 10.56)


def test_same_candles_in_swing_mode_reach_the_target_on_the_last_candle() -> None:
    (t,) = run(ROWS_A, TIMES_A, SWING)

    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(360.00)


def test_stop_still_works_during_the_day() -> None:
    rows = [C1, C2, C3, (10.40, 10.58, 10.19, 10.25), QUIET, K_CANDLE]
    (t,) = run(rows, TIMES_A)

    assert t.exit_reason == "stop"
    assert t.exit == pytest.approx(10.20)
    assert t.pnl == pytest.approx(-180.00)


def test_an_order_is_not_carried_overnight() -> None:
    times = [
        "2024-01-02 12:00",
        "2024-01-02 14:00",
        "2024-01-02 16:00",  # c3, the last candle of the day
        "2024-01-03 10:00",  # would fill the order in swing mode
        "2024-01-03 12:00",
    ]
    rows = [C1, C2, C3, C4_ENTRY, C5_TARGET]

    assert len(run(rows, times, SWING)) == 1
    assert run(rows, times, DAY) == []
    longer = BacktestConfig(max_risk_brl=200, day_trade=True, entry_validity_candles=2)
    assert run(rows, times, longer) == []


def test_the_candle_containing_the_exit_time_is_never_an_entry_candle() -> None:
    times = [
        "2024-01-03 10:00",
        "2024-01-03 12:00",
        "2024-01-03 14:00",  # c3
        "2024-01-03 16:00",  # would fill, but it contains 16:30
        "2024-01-04 10:00",
    ]
    rows = [C1, C2, C3, C4_ENTRY, C5_TARGET]

    assert len(run(rows, times, SWING)) == 1
    assert run(rows, times, DAY) == []


@pytest.mark.parametrize(
    ("min_time", "max_time", "expected_trades"),
    [
        ("12:00", None, 1),  # the fill candle opens at 12:00: the minimum is inclusive
        ("12:01", None, 0),
        ("00:00", "12:00", 0),  # the fill candle must open before the maximum
        ("00:00", "12:01", 1),
    ],
)
def test_entry_window_edges_apply_to_the_fill_candle(
    min_time: str, max_time: str | None, expected_trades: int
) -> None:
    config = BacktestConfig(
        max_risk_brl=200, day_trade=True, min_entry_time=min_time, max_entry_time=max_time
    )

    assert len(run(ROWS_A, TIMES_A, config)) == expected_trades


def test_a_day_that_ends_early_closes_at_the_close_of_its_last_candle() -> None:
    times = [
        "2024-01-02 14:00",
        "2024-01-02 16:00",
        "2024-01-03 10:00",
        "2024-01-03 12:00",  # fills; the day has no candle after this one
        "2024-01-04 10:00",
    ]
    rows = [C1, C2, C3, C4_ENTRY, (10.58, 10.62, 10.50, 10.60)]
    (t,) = run(rows, times)

    assert (t.entry_index, t.exit_index) == (3, 3)
    assert t.exit == pytest.approx(10.55)  # close of the 12:00 candle
    assert t.exit_reason == "time"
    assert t.pnl == pytest.approx(-5.00)  # 500 * (10.55 - 10.56)


def test_day_trade_needs_an_intraday_timeframe() -> None:
    candles = make_candles_at(ROWS_A, TIMES_A)

    with pytest.raises(ValueError, match="timeframe"):
        run_backtest(candles, DAY)
    with pytest.raises(ValueError, match="intraday"):
        run_backtest(candles, DAY, timeframe=Timeframe.D1)


# --- finer candles pinpoint the exit -------------------------------------------------------

M30_TIMES = ["2024-01-03 16:00", "2024-01-03 16:30", "2024-01-03 17:00"]


def m30(first: Row, second: Row):  # type: ignore[no-untyped-def]
    # the 16:00 candle belongs to the exit candle's hour; the 16:30 candle opens at the exit time
    return make_candles_at([first, second, (10.70, 10.72, 10.60, 10.65)], M30_TIMES)


def test_a_finer_candle_at_the_exit_time_gives_its_open_as_the_price() -> None:
    intraday = m30((10.64, 10.70, 10.60, 10.66), (10.72, 11.30, 10.70, 11.25))
    (t,) = run(ROWS_A, TIMES_A, intraday=intraday)

    assert t.exit == pytest.approx(10.72)  # open of the 16:30 candle; its later range is ignored
    assert t.exit_reason == "time"
    assert t.exit_index == 5
    assert t.pnl == pytest.approx(80.00)  # 500 * (10.72 - 10.56)


def test_finer_candles_before_the_exit_time_can_hit_the_stop() -> None:
    intraday = m30((10.64, 10.70, 10.15, 10.30), (10.72, 11.30, 10.70, 11.25))
    (t,) = run(ROWS_A, TIMES_A, intraday=intraday)

    assert t.exit == pytest.approx(10.20)
    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-180.00)


def test_finer_candles_before_the_exit_time_can_hit_the_target() -> None:
    intraday = m30((10.64, 11.30, 10.60, 11.25), (10.72, 11.30, 10.70, 11.25))
    (t,) = run(ROWS_A, TIMES_A, intraday=intraday)

    assert t.exit == pytest.approx(11.28)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(360.00)


def test_without_a_finer_candle_at_the_exit_time_the_last_one_before_it_is_used() -> None:
    intraday = make_candles_at([(10.64, 10.70, 10.60, 10.66)], ["2024-01-03 16:00"])
    (t,) = run(ROWS_A, TIMES_A, intraday=intraday)

    assert t.exit == pytest.approx(
        10.64
    )  # open of the last finer candle starting at or before 16:30
    assert t.pnl == pytest.approx(40.00)


def test_finer_candles_of_other_days_do_not_matter() -> None:
    intraday = make_candles_at([(10.64, 10.70, 10.60, 10.66)], ["2024-01-02 16:00"])
    (t,) = run(ROWS_A, TIMES_A, intraday=intraday)

    assert t.exit == pytest.approx(10.65)  # falls back to the exit candle's open
    assert t.pnl == pytest.approx(45.00)


def test_last_candle_open_policy_ignores_finer_candles() -> None:
    intraday = m30((10.64, 10.70, 10.60, 10.66), (10.72, 11.30, 10.70, 11.25))
    config = BacktestConfig(max_risk_brl=200, day_trade=True, day_exit_policy="last_candle_open")
    (t,) = run(ROWS_A, TIMES_A, config, intraday=intraday)

    assert t.exit == pytest.approx(10.65)


# --- configuration ----------------------------------------------------------------------------


def test_day_trade_defaults() -> None:
    config = BacktestConfig()

    assert config.day_trade is False
    assert (config.min_entry_time, config.max_entry_time, config.exit_time) == (
        "00:00",
        None,
        "16:30",
    )
    assert config.day_exit_policy == "auto"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"exit_time": "4pm"}, "exit_time"),
        ({"min_entry_time": "25:00"}, "min_entry_time"),
        ({"max_entry_time": "12:60"}, "max_entry_time"),
        ({"min_entry_time": "13:00", "max_entry_time": "12:00"}, "entry window"),
        ({"min_entry_time": "16:30"}, "entry window"),  # not before the default maximum 16:30
        ({"max_entry_time": "17:00"}, "entry window"),  # after the exit time
        ({"day_exit_policy": "close"}, "day_exit_policy"),
    ],
)
def test_config_rejects_invalid_day_trade_values(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BacktestConfig(**kwargs)  # type: ignore[arg-type]


def test_day_trade_config_roundtrips_through_json() -> None:
    config = BacktestConfig(day_trade=True, min_entry_time="10:30", max_entry_time="15:00")

    assert BacktestConfig.from_dict(config.to_dict()) == config
