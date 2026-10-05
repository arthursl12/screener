"""Day-trade mode, brief section 7. Every number is hand computed.

Base timeline on H2 candles (São Paulo time), worked-example setup (`make_config`): entry 10.41,
stop 10.24, target 10.75, 1100 shares. The 16:00 candle contains the 16:30 exit time.
"""

import pytest
from helpers import C1, C2, C3, C4_ENTRY, Row, make_candles_at, make_config

from b3core.data import Timeframe
from b3core.engine import BacktestConfig, run_backtest

DAY = make_config(day_trade=True)  # exit 16:30, window from start of day, exit at the close

QUIET: Row = (10.42, 10.60, 10.36, 10.50)  # stays between the stop and the target
K_NO_TARGET: Row = (10.52, 10.70, 10.45, 10.62)  # opens 10.52, closes 10.62, touches neither level
NEXT_DAY_TARGET: Row = (10.60, 10.90, 10.55, 10.85)  # reaches the 10.75 target

# c1 and c2 on Jan 2; the signal c3 and the fill are on Jan 3; the 16:00 candle is the exit candle.
TIMES_A = [
    "2024-01-02 14:00",
    "2024-01-02 16:00",
    "2024-01-03 10:00",
    "2024-01-03 12:00",
    "2024-01-03 14:00",
    "2024-01-03 16:00",
    "2024-01-04 10:00",
]
ROWS_A = [C1, C2, C3, C4_ENTRY, QUIET, K_NO_TARGET, NEXT_DAY_TARGET]


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


def test_the_default_forced_exit_is_the_close_of_the_exit_candle() -> None:
    (t,) = run(ROWS_A, TIMES_A)

    assert (t.entry_index, t.exit_index) == (3, 5)
    assert t.exit == pytest.approx(10.62)
    assert t.exit_reason == "time"
    assert t.pnl == pytest.approx(231.00)  # 1100 * (10.62 - 10.41)


def test_the_same_candles_in_swing_mode_wait_for_the_target_on_the_next_day() -> None:
    (t,) = run(ROWS_A, TIMES_A, make_config())

    assert (t.exit_index, t.exit_reason) == (6, "target")
    assert t.pnl == pytest.approx(374.00)


def test_the_exit_candle_is_evaluated_like_any_other_under_the_close_policy() -> None:
    hits_target = (10.52, 10.80, 10.45, 10.62)
    hits_stop = (10.52, 10.70, 10.20, 10.62)
    gaps_past_target = (10.80, 10.90, 10.78, 10.85)

    (a,) = run([*ROWS_A[:5], hits_target, ROWS_A[6]], TIMES_A)
    (b,) = run([*ROWS_A[:5], hits_stop, ROWS_A[6]], TIMES_A)
    (c,) = run([*ROWS_A[:5], gaps_past_target, ROWS_A[6]], TIMES_A)

    assert (a.exit, a.exit_reason, a.pnl) == (pytest.approx(10.75), "target", pytest.approx(374.0))
    assert (b.exit, b.exit_reason, b.pnl) == (pytest.approx(10.24), "stop", pytest.approx(-187.0))
    assert (c.exit, c.exit_reason, c.pnl) == (pytest.approx(10.75), "target", pytest.approx(374.0))


def test_the_open_policy_exits_before_looking_at_the_exit_candle() -> None:
    config = make_config(day_trade=True, day_exit_policy="last_candle_open")
    hits_target = (10.52, 10.80, 10.45, 10.62)  # would reach the target later in the candle
    (t,) = run([*ROWS_A[:5], hits_target, ROWS_A[6]], TIMES_A, config)

    assert t.exit == pytest.approx(10.52)
    assert t.exit_reason == "time"
    assert t.pnl == pytest.approx(121.00)  # 1100 * (10.52 - 10.41)


def test_stop_still_works_during_the_day() -> None:
    rows = [C1, C2, C3, (10.38, 10.45, 10.20, 10.30), QUIET, K_NO_TARGET, NEXT_DAY_TARGET]
    (t,) = run(rows, TIMES_A)

    assert t.exit_reason == "stop"
    assert t.exit == pytest.approx(10.24)
    assert t.pnl == pytest.approx(-187.00)


def test_an_order_is_carried_overnight_but_the_position_is_not() -> None:
    times = [
        "2024-01-02 12:00",
        "2024-01-02 14:00",
        "2024-01-02 16:00",  # c3, the last candle of the day
        "2024-01-03 10:00",  # fills the order the next morning
        "2024-01-03 12:00",
        "2024-01-03 14:00",
        "2024-01-03 16:00",  # exit candle
    ]
    rows = [C1, C2, C3, C4_ENTRY, QUIET, QUIET, K_NO_TARGET]
    (t,) = run(rows, times)

    assert (t.entry_index, t.exit_index) == (3, 6)
    assert t.exit == pytest.approx(10.62)
    assert t.pnl == pytest.approx(231.00)


def test_the_candle_containing_the_exit_time_is_never_an_entry_candle() -> None:
    times = [
        "2024-01-03 10:00",
        "2024-01-03 12:00",
        "2024-01-03 14:00",  # c3
        "2024-01-03 16:00",  # would fill, but it contains 16:30
        "2024-01-04 10:00",
    ]
    rows = [C1, C2, C3, C4_ENTRY, NEXT_DAY_TARGET]

    assert len(run(rows, times, make_config())) == 1
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
    config = make_config(day_trade=True, min_entry_time=min_time, max_entry_time=max_time)

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
    assert t.exit == pytest.approx(10.44)  # close of the 12:00 candle
    assert t.exit_reason == "time"
    assert t.pnl == pytest.approx(33.00)  # 1100 * (10.44 - 10.41)


def test_day_trade_needs_an_intraday_timeframe() -> None:
    candles = make_candles_at(ROWS_A, TIMES_A)

    with pytest.raises(ValueError, match="timeframe"):
        run_backtest(candles, DAY)
    with pytest.raises(ValueError, match="intraday"):
        run_backtest(candles, DAY, timeframe=Timeframe.D1)


# --- finer candles pinpoint the exit (policy auto) ---------------------------------------------

AUTO = make_config(day_trade=True, day_exit_policy="auto")
M30_TIMES = ["2024-01-03 16:00", "2024-01-03 16:30", "2024-01-03 17:00"]


def m30(first: Row, second: Row):  # type: ignore[no-untyped-def]
    # the 16:00 candle belongs to the exit candle's hour; the 16:30 candle opens at the exit time
    return make_candles_at([first, second, (10.70, 10.72, 10.60, 10.65)], M30_TIMES)


def test_a_finer_candle_at_the_exit_time_gives_its_open_as_the_price() -> None:
    intraday = m30((10.54, 10.60, 10.50, 10.58), (10.66, 11.30, 10.60, 11.25))
    (t,) = run(ROWS_A, TIMES_A, AUTO, intraday)

    assert t.exit == pytest.approx(10.66)  # open of the 16:30 candle; its later range is ignored
    assert t.exit_reason == "time"
    assert t.exit_index == 5
    assert t.pnl == pytest.approx(275.00)  # 1100 * (10.66 - 10.41)


def test_finer_candles_before_the_exit_time_can_hit_the_stop() -> None:
    intraday = m30((10.54, 10.60, 10.15, 10.30), (10.66, 11.30, 10.60, 11.25))
    (t,) = run(ROWS_A, TIMES_A, AUTO, intraday)

    assert t.exit == pytest.approx(10.24)
    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-187.00)


def test_finer_candles_before_the_exit_time_can_hit_the_target() -> None:
    intraday = m30((10.54, 10.80, 10.50, 10.78), (10.66, 11.30, 10.60, 11.25))
    (t,) = run(ROWS_A, TIMES_A, AUTO, intraday)

    assert t.exit == pytest.approx(10.75)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(374.00)


def test_without_a_finer_candle_at_the_exit_time_the_last_one_before_it_is_used() -> None:
    intraday = make_candles_at([(10.54, 10.60, 10.50, 10.58)], ["2024-01-03 16:00"])
    (t,) = run(ROWS_A, TIMES_A, AUTO, intraday)

    assert t.exit == pytest.approx(
        10.54
    )  # open of the last finer candle starting at or before 16:30
    assert t.pnl == pytest.approx(143.00)  # 1100 * (10.54 - 10.41)


def test_finer_candles_of_other_days_do_not_matter() -> None:
    intraday = make_candles_at([(10.54, 10.60, 10.50, 10.58)], ["2024-01-02 16:00"])
    (t,) = run(ROWS_A, TIMES_A, AUTO, intraday)

    assert t.exit == pytest.approx(10.52)  # falls back to the exit candle's open
    assert t.pnl == pytest.approx(121.00)


@pytest.mark.parametrize(
    ("policy", "exit_price"), [("last_candle_close", 10.62), ("last_candle_open", 10.52)]
)
def test_other_policies_ignore_finer_candles(policy: str, exit_price: float) -> None:
    intraday = m30((10.54, 10.60, 10.50, 10.58), (10.66, 11.30, 10.60, 11.25))
    config = make_config(day_trade=True, day_exit_policy=policy)
    (t,) = run(ROWS_A, TIMES_A, config, intraday)

    assert t.exit == pytest.approx(exit_price)


# --- configuration ----------------------------------------------------------------------------


def test_day_trade_defaults() -> None:
    config = BacktestConfig()

    assert config.day_trade is False
    assert (config.min_entry_time, config.max_entry_time, config.exit_time) == (
        "00:00",
        None,
        "16:30",
    )
    assert config.day_exit_policy == "last_candle_close"


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
