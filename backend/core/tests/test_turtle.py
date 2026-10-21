"""Golden cases for Turtle de compra. Every number is hand computed from brief section 7c.

Base setup (`config`): entry_period 2, exit_period 2, atr_period 2, add_atr_mult 1, max_units 1,
capital 10000 and risk_pct 2 (so the risk budget is R$ 200), lot 1, signal_close, no costs.

Worked example (SERIES). ATR(2) by hand, true range from bar 1, first ATR on bar 2:
  bar   TR     ATR      entry level  exit level
  1     0.30
  2     0.30   0.3000   10.30        9.90      close 10.30 equals the entry level: no signal
  3     0.35   0.3250   10.40        10.00     close 10.55 breaks out: buy floor(200 / 0.325) = 615
  4     0.65   0.4875   10.60        10.10
  5     0.30   0.39375  11.20        10.25
  6     0.60   0.49688  11.30        10.80     close 10.70 is below 10.80: sell
The entry level of bar 3 excludes the current candle: with its own high (10.60) the close 10.55
would not break out.
"""

import warnings

import pandas as pd
import pytest

from b3core.turtle import TurtleConfig, run_turtle

# Longer series add several units on one candle, which warns; the tests that assert the warning
# use pytest.warns, which is not affected by this filter.
pytestmark = pytest.mark.filterwarnings("ignore:.*more than one add:UserWarning")

Row = tuple[float, float, float, float]  # open, high, low, close

R0: Row = (10.00, 10.20, 9.90, 10.10)
R1: Row = (10.10, 10.30, 10.00, 10.20)
R2: Row = (10.20, 10.40, 10.10, 10.30)  # close equals the entry level 10.30: strict, no signal
R3: Row = (10.30, 10.60, 10.25, 10.55)  # breakout: buy at the close, 10.55
R4: Row = (10.85, 11.20, 10.80, 11.10)  # add level 10.875 is passed, but max_units is 1
R5: Row = (11.10, 11.30, 11.00, 11.20)
R6: Row = (11.00, 11.05, 10.60, 10.70)  # close below the exit level 10.80: sell at 10.70
SERIES = [R0, R1, R2, R3, R4, R5, R6]


def candles(rows: list[Row]) -> pd.DataFrame:
    ts = pd.date_range("2024-01-02", periods=len(rows), freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "ts": ts,
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [1000.0] * len(rows),
        }
    )


def config(**overrides: object) -> TurtleConfig:
    base: dict[str, object] = {
        "entry_period": 2,
        "exit_period": 2,
        "atr_period": 2,
        "add_atr_mult": 1.0,
        "max_units": 1,
        "capital_brl": 10_000,
        "risk_pct": 2.0,
        "lot_size": 1,
    }
    return TurtleConfig(**{**base, **overrides})  # type: ignore[arg-type]


def run(rows: list[Row], **overrides: object):  # type: ignore[no-untyped-def]
    return run_turtle(candles(rows), config(**overrides))


def test_worked_example() -> None:
    (t,) = run(SERIES).trades

    assert t.qty == 615
    assert t.units == 1
    assert t.entry == pytest.approx(10.55)
    assert t.exit == pytest.approx(10.70)
    assert t.exit_reason == "sell"
    assert t.pnl == pytest.approx(92.25)
    assert (t.entry_index, t.exit_index, t.days) == (3, 6, 3)


def test_close_equal_to_the_entry_level_is_not_a_signal() -> None:
    equal: Row = (10.30, 10.60, 10.25, 10.40)  # the entry level of this bar is 10.40

    assert run([R0, R1, R2, equal]).trades == []


def test_peak_money_in_the_position() -> None:
    assert run(SERIES).peak_cost == pytest.approx(615 * 10.55)


def test_result_metrics_use_the_configured_capital() -> None:
    result = run(SERIES)

    assert result.metrics.n_trades == 1
    assert result.metrics.result == pytest.approx(92.25 / 10_000)


# Stop tests. After the buy at 10.55 on bar 3 (ATR 0.325), bar 4 has TR 0.65 and ATR 0.4875.
# The stop reads the PREVIOUS candle's ATR: 10.55 - 0.325 = 10.225. With the current ATR it would
# be 10.55 - 0.4875 = 10.0625, so a close of 10.20 tells the two apart. The exit level of bar 4
# is min(10.10, 10.25) = 10.10.
STOP_BAR: Row = (10.40, 10.45, 9.90, 10.20)  # below 10.225, above the exit level 10.10
BOTH_BAR: Row = (10.40, 10.45, 9.90, 10.05)  # below the stop and below the exit level


def test_stop_is_read_on_the_close_with_the_previous_atr() -> None:
    (t,) = run([R0, R1, R2, R3, STOP_BAR]).trades

    assert t.exit_reason == "stop"
    assert t.exit == pytest.approx(10.20)  # the close, not the stop level 10.225
    assert t.pnl == pytest.approx(615 * (10.20 - 10.55))
    assert (t.entry_index, t.exit_index, t.days) == (3, 4, 1)


def test_sell_takes_priority_over_stop_on_the_same_candle() -> None:
    (t,) = run([R0, R1, R2, R3, BOTH_BAR]).trades

    assert t.exit_reason == "sell"
    assert t.exit == pytest.approx(10.05)


# Pyramiding. With max_units 2, bar 4 passes the add level 10.55 + 0.325 = 10.875 and adds
# floor(200 / 0.4875) = 410 shares at 11.10, sized with the CURRENT ATR (a unit of 615 would use
# the previous one). The average becomes (615 * 10.55 + 410 * 11.10) / 1025 = 10.77024.
def test_second_worked_example_pyramiding() -> None:
    result = run(SERIES, max_units=2)
    (t,) = result.trades

    assert t.units == 2
    assert t.qty == 615 + 410
    assert t.entry == pytest.approx(11_039.25 / 1025)
    assert t.exit == pytest.approx(10.70)
    assert t.pnl == pytest.approx(615 * 0.15 + 410 * -0.40)  # -71.75
    assert result.peak_cost == pytest.approx(615 * 10.55 + 410 * 11.10)


# A rally on bar 5 to a close of 11.50. After the add on bar 4 the average is 10.77024 and the
# bar-4 ATR is 0.4875, so the next add level is 11.25774: bar 5 passes it. Bar 5 has TR 0.50 and
# ATR 0.49375, so the third unit is floor(200 / 0.49375) = 405 shares at 11.50.
R5_RALLY: Row = (11.10, 11.55, 11.05, 11.50)
RALLY = [R0, R1, R2, R3, R4, R5_RALLY, R6]


def test_max_units_is_a_ceiling() -> None:
    (t,) = run(RALLY, max_units=2).trades

    assert t.units == 2
    assert t.pnl == pytest.approx(-71.75)


def test_a_third_unit_is_added_when_the_ceiling_allows() -> None:
    (t,) = run(RALLY, max_units=3).trades

    assert t.units == 3
    assert t.qty == 615 + 410 + 405
    assert t.pnl == pytest.approx(615 * 0.15 + 410 * -0.40 + 405 * -0.80)  # -395.75


def test_add_level_can_be_measured_from_the_last_fill() -> None:
    # From the last fill (11.10) the level is 11.10 + 0.4875 = 11.5875: the close 11.50 is below it.
    (t,) = run(RALLY, max_units=3, use_last_fill=True).trades

    assert t.units == 2


# A candle that would add AND sell. After a jump to 16.00 the average (13.871) lags the price, so
# the last close 14.60 is above the add level 13.871 + 0.553 = 14.424, and below the exit level
# min(15.40, 15.35) = 15.35. The exit wins and no unit is added on that candle (brief 7c,
# assumption). The numbers come from an independent throwaway simulation, not by hand.
ADD_AND_SELL = [
    (10.0, 10.2, 9.95, 10.0),
    (10.1, 10.5, 10.05, 10.3),
    (10.2, 10.8, 10.15, 10.6),
    (10.7, 10.75, 10.4, 10.6),
    (10.7, 11.1, 10.5, 10.9),
    (10.8, 11.4, 10.6, 11.2),
    (11.1, 11.3, 10.95, 11.0),
    (10.9, 13.55, 10.85, 13.5),
    (13.5, 16.2, 13.3, 16.0),
    (15.9, 16.1, 15.6, 15.8),
    (15.8, 16.0, 15.75, 15.8),
    (15.8, 16.0, 15.4, 15.6),
    (15.7, 15.75, 15.35, 15.4),
    (15.4, 15.6, 14.4, 14.6),
]


def test_an_exit_candle_takes_no_add() -> None:
    (t,) = run(ADD_AND_SELL, max_units=10).trades

    assert t.exit_reason == "sell"
    assert t.exit == pytest.approx(14.60)
    assert t.units == 8  # a ninth unit on the exit candle would change these three
    assert t.qty == 1894
    assert t.entry == pytest.approx(13.871277719112989)


# Warnings and counts (owner, Oct 21, 2026).
def test_a_unit_below_one_lot_is_skipped_counted_and_warned() -> None:
    # risk_pct 0.001 gives a budget of R$ 0.10, so floor(0.10 / ATR) is 0 on every signal.
    # Bars 3 and 4 both break out (closes 10.55 > 10.40 and 11.10 > 10.60): two skipped units.
    with pytest.warns(UserWarning, match="2 .*skipped"):
        result = run(SERIES, risk_pct=0.001)

    assert result.trades == []
    assert result.skipped_units == 2
    assert result.open_units == 0


def test_a_skipped_add_does_not_advance_the_unit_count() -> None:
    # Lot 500: the entry is floor(200 / 0.325 / 500) = 1 lot = 500 shares. The add on bar 4 would
    # be floor(200 / 0.4875 / 500) = 0 lots: skipped, the count stays at 1. Bar 5 (ATR 0.39375)
    # is still above the level 10.55 + 0.4875 and rounds to floor(1.016) = 1 lot: added there.
    with pytest.warns(UserWarning, match="skipped"):
        result = run(SERIES, max_units=2, lot_size=500)

    (t,) = result.trades
    assert result.skipped_units == 1
    assert t.units == 2
    assert t.qty == 1000
    assert t.entry == pytest.approx((500 * 10.55 + 500 * 11.20) / 1000)  # added on bar 5, not 4


# Bar 4 jumps to 12.00. The add level is 10.55 + 0.325 = 10.875, so one unit is added:
# floor(200 / 0.9375) = 213 (TR 1.55, ATR 0.9375). The new average is 10.92301 and the next level
# 10.92301 + 0.325 = 11.248, which the same close 12.00 still passes: more than one add was due.
JUMP: Row = (10.85, 12.10, 10.80, 12.00)


def test_a_candle_that_justifies_more_than_one_add_is_counted_and_warned() -> None:
    with pytest.warns(UserWarning, match="1 .*more than one add"):
        result = run([R0, R1, R2, R3, JUMP], max_units=4)

    assert result.multi_add_candles == 1
    assert result.open_units == 2  # only one add was made on the candle


def test_no_warning_when_one_add_was_all_that_was_due() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = run(SERIES, max_units=2)  # the ceiling is reached: no second add is due

    assert result.skipped_units == 0
    assert result.multi_add_candles == 0
