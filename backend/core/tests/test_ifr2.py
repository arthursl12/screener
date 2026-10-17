"""Golden cases for IFR2 (RSI 2) de compra. Every number is hand computed from brief section 7.

Base setup (`config`): rsi_period 2, rsi_entry 30, target mode with lookback 2, no time stop,
atr_period 2, atr_mult 2, max risk 100, capital 10000, lot 1, no costs.

Worked example (SERIES), RSI(2) and ATR(2) by hand:
  bar   close  RSI     TR    ATR
  2     10.20  62.50   0.5   0.5500
  3      9.80  31.25   0.6   0.5750
  4      9.50  17.86   0.5   0.5375   <- signal, buy at 9.50
Quantity floor(100 / (2 * 0.5375)) = floor(93.02) = 93.
"""

import pandas as pd
import pytest

from b3core.data import Timeframe
from b3core.ifr2 import Ifr2Config, run_ifr2

Row = tuple[float, float, float, float]  # open, high, low, close

R0: Row = (10.00, 10.10, 9.90, 10.00)
R1: Row = (10.00, 10.60, 10.00, 10.50)
R2: Row = (10.50, 10.60, 10.10, 10.20)
R3: Row = (10.20, 10.30, 9.70, 9.80)
R4: Row = (9.80, 9.90, 9.40, 9.50)  # signal: buy at the close, 9.50
R5: Row = (9.60, 10.00, 9.50, 9.90)  # target max(10.30, 9.90) = 10.30 not reached
R6: Row = (9.90, 10.10, 9.80, 10.00)  # target max(9.90, 10.00) = 10.00 reached
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


def config(**overrides: object) -> Ifr2Config:
    base: dict[str, object] = {
        "rsi_period": 2,
        "rsi_entry": 30,
        "target_lookback": 2,
        "atr_period": 2,
        "atr_mult": 2,
        "max_risk_brl": 100,
        "capital_brl": 10_000,
        "lot_size": 1,
    }
    return Ifr2Config(**{**base, **overrides})  # type: ignore[arg-type]


def run(rows: list[Row], **overrides: object):  # type: ignore[no-untyped-def]
    return run_ifr2(candles(rows), config(**overrides)).trades


def test_worked_example() -> None:
    (t,) = run(SERIES)

    assert t.entry == pytest.approx(9.50)
    assert t.qty == 93
    assert t.exit == pytest.approx(10.00)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(46.50)
    assert (t.entry_index, t.exit_index, t.days) == (4, 6, 2)


def test_result_metrics_use_the_configured_capital() -> None:
    result = run_ifr2(candles(SERIES), config())

    assert result.metrics.n_trades == 1
    assert result.metrics.result == pytest.approx(46.50 / 10_000)


def test_rsi_exactly_at_the_threshold_is_a_signal() -> None:
    # closes 10, 11, 10 -> RSI(2) on bar 2 is exactly 50. ATR(2) = 1, quantity 100 / 2 = 50.
    # Bar 3 high 12 passes the target max(11, 10) = 11, opens at 10 (below it): fills at 11.
    rows: list[Row] = [
        (10, 10, 10, 10),
        (11, 11, 11, 11),
        (10, 10, 10, 10),
        (10, 12, 10, 11),
    ]

    (t,) = run(rows, rsi_entry=50)

    assert (t.entry, t.qty, t.exit, t.pnl) == (10.0, 50, 11.0, 50.0)
    assert run(rows, rsi_entry=49.99) == []


def test_target_uses_the_previous_candles_only_and_the_configured_lookback() -> None:
    # lookback 3: the target on bar 6 is max(10.30, 9.90, 10.00) = 10.30, high 10.10 misses it,
    # and the position is still open at the end of the data.
    assert run(SERIES, target_lookback=3) == []


def test_gap_above_the_target_fills_at_the_open() -> None:
    # bar 6 opens at 10.20, above the target 10.00: exit at 10.20, pnl 93 * 0.70 = 65.10
    gap: Row = (10.20, 10.30, 10.10, 10.25)

    (t,) = run([*SERIES[:6], gap])

    assert t.exit == pytest.approx(10.20)
    assert t.pnl == pytest.approx(65.10)


def test_rsi_exit_fills_at_the_close() -> None:
    # RSI(2) on bar 5: gain 0.4 -> avg gain 0.23125, avg loss 0.14375 -> 61.67, above 60.
    (t,) = run(SERIES, exit_mode="rsi", rsi_exit=60)

    assert (t.exit_index, t.exit, t.exit_reason) == (5, pytest.approx(9.90), "rsi")
    assert t.pnl == pytest.approx(93 * 0.40)


def test_target_wins_when_the_target_and_the_rsi_exit_fire_together() -> None:
    # bar 6 closes at 10.05: RSI(2) 72.6 is above 65 (bar 5 is 61.67, below it) and the target
    # 10.00 is reached. The target fills at 10.00, not at the 10.05 close.
    r6: Row = (9.90, 10.10, 9.80, 10.05)

    (t,) = run([*SERIES[:6], r6], exit_mode="target_or_rsi", rsi_exit=65)

    assert (t.exit_reason, t.exit) == ("target", pytest.approx(10.00))
    assert t.pnl == pytest.approx(46.50)


def test_time_stop_exits_at_the_close_and_counts_the_entry_candle_as_day_zero() -> None:
    (one_day,) = run(SERIES, max_days=1)
    assert (one_day.exit_index, one_day.days, one_day.exit_reason) == (5, 1, "time")
    assert one_day.pnl == pytest.approx(93 * 0.40)

    # lookback 3 keeps the target out of reach, so day 2 is the time stop on bar 6
    (two_days,) = run(SERIES, max_days=2, target_lookback=3)
    assert (two_days.exit_index, two_days.days, two_days.exit_reason) == (6, 2, "time")
    assert two_days.pnl == pytest.approx(46.50)


def test_time_stop_comes_before_the_rsi_exit_when_both_fire() -> None:
    # rsi mode, exit level 65: bar 5 is 61.67 (no), bar 6 is 69.74 (yes) and day 2 is the stop.
    (t,) = run(SERIES, exit_mode="rsi", rsi_exit=65, max_days=2)

    assert (t.exit_index, t.exit_reason, t.exit) == (6, "time", pytest.approx(10.00))


def test_exits_are_not_checked_on_the_entry_candle() -> None:
    # bar 4 has a high of 10.70, above its own target 10.60: an exit on the entry candle would
    # close at once. ATR(2) on bar 4 is (0.575 + 1.30) / 2 = 0.9375 -> quantity floor(53.3) = 53.
    # The real exit is bar 7: target max(10.00, 10.10) = 10.10, opens at 10.00 -> fills 10.10.
    r4: Row = (9.80, 10.70, 9.40, 9.50)
    r7: Row = (10.00, 10.90, 9.90, 10.80)

    (t,) = run([R0, R1, R2, R3, r4, R5, R6, r7])

    assert (t.entry_index, t.exit_index, t.qty) == (4, 7, 53)
    assert t.pnl == pytest.approx(53 * 0.60)


def test_no_new_entry_while_a_position_is_open() -> None:
    # bar 5 closes at 9.30: RSI(2) 11.4 is a signal, but the bar 4 position is still open.
    # It exits on bar 6: target max(9.90, 9.60) = 9.90, opens at 9.30 -> fills at 9.90.
    r5: Row = (9.50, 9.60, 9.20, 9.30)
    r6: Row = (9.30, 10.40, 9.30, 10.30)

    (t,) = run([R0, R1, R2, R3, R4, r5, r6])

    assert (t.entry, t.qty, t.exit_index) == (9.50, 93, 6)
    assert t.pnl == pytest.approx(93 * 0.40)


def test_the_equity_curve_marks_the_open_position_at_each_close() -> None:
    # same series as above: bar 5 closes at 9.30, so the open 93 shares are 18.60 under water
    # (equity 9981.40) before the bar 6 exit books +37.20.
    r5: Row = (9.50, 9.60, 9.20, 9.30)
    r6: Row = (9.30, 10.40, 9.30, 10.30)

    result = run_ifr2(candles([R0, R1, R2, R3, R4, r5, r6]), config())

    assert list(result.equity) == pytest.approx(
        [10_000, 10_000, 10_000, 10_000, 10_000, 9_981.40, 10_037.20]
    )
    assert result.metrics.max_equity_drawdown == pytest.approx(18.60 / 10_000)
    assert result.metrics.max_drawdown == 0  # the closed trade is a winner: no balance dip
    assert result.metrics.cagr is not None


REENTRY_ROWS: list[Row] = [
    R0,
    R1,
    R2,
    R3,
    R4,
    # bar 5: high 10.50 passes the target 10.30 (exit at 10.30), and the 9.10 close is a new
    # signal (RSI 8.3). ATR(2) = (0.5375 + 1.50) / 2 = 1.01875 -> quantity floor(49.07) = 49.
    (9.60, 10.50, 9.00, 9.10),
    (9.20, 9.60, 9.10, 9.50),  # RSI 55.6: no signal
    # bar 7: target max(10.50, 9.60) = 10.50, opens at 9.50 -> fills at 10.50
    (9.50, 10.80, 9.40, 10.60),
]


def test_same_candle_reentry_is_off_by_default() -> None:
    (t,) = run(REENTRY_ROWS)

    assert (t.exit_index, t.exit) == (5, pytest.approx(10.30))
    assert t.pnl == pytest.approx(93 * 0.80)


def test_same_candle_reentry_when_allowed() -> None:
    first, second = run(REENTRY_ROWS, allow_same_day_reentry=True)

    assert (first.exit_index, second.entry_index) == (5, 5)
    assert (second.entry, second.qty, second.exit) == (9.10, 49, pytest.approx(10.50))
    assert second.pnl == pytest.approx(49 * 1.40)


def test_signals_wait_for_the_atr_warm_up() -> None:
    # ATR(5) exists from bar 5 on, so the bar 4 signal is skipped (and none follows)
    assert run(SERIES, atr_period=5) == []


def test_quantity_rounding_to_zero_takes_no_trade() -> None:
    # 1 / 1.075 = 0.93 shares
    assert run(SERIES, max_risk_brl=1) == []


def test_quantity_is_capped_by_the_capital() -> None:
    # floor(500 / 9.50) = 52 shares instead of 93
    (t,) = run(SERIES, capital_brl=500)

    assert t.qty == 52
    assert t.pnl == pytest.approx(52 * 0.50)


def test_quantity_is_rounded_down_to_the_lot() -> None:
    (t,) = run(SERIES, lot_size=10)

    assert t.qty == 90


def test_costs_are_charged_on_both_sides() -> None:
    # 0.03 % of 93 * 9.50 on the way in and of 93 * 10.00 on the way out
    (t,) = run(SERIES, cost_pct=0.03)

    assert t.pnl == pytest.approx(46.50 - 0.0003 * 93 * (9.50 + 10.00))


def test_an_open_position_at_the_end_of_the_data_is_left_out() -> None:
    assert run(SERIES[:6]) == []


def test_a_flat_start_gives_no_signal() -> None:
    # the RSI of a window with no gains and no losses is undefined. With a time stop of one
    # day, a signal on a flat series would show up as a trade.
    flat: list[Row] = [(10, 10.5, 9.5, 10)] * 6

    assert run(flat, rsi_entry=100, max_days=1) == []


def test_only_the_daily_timeframe_is_accepted() -> None:
    with pytest.raises(ValueError, match="daily"):
        run_ifr2(candles(SERIES), config(), timeframe=Timeframe.H2)


def test_the_preset_charges_the_b3_fee() -> None:
    assert Ifr2Config().cost_pct == 0
    assert Ifr2Config.preset().cost_pct == pytest.approx(0.03)
    assert Ifr2Config.preset(cost_pct=0.0).cost_pct == 0


def test_config_round_trips_through_a_dict() -> None:
    original = config(exit_mode="target_or_rsi", rsi_exit=60, max_days=5)

    assert Ifr2Config.from_dict(original.to_dict()) == original


@pytest.mark.parametrize(
    "overrides",
    [
        {"rsi_period": 0},
        {"atr_period": 0},
        {"atr_mult": 0},
        {"exit_mode": "stop"},
        {"target_lookback": 0},
        {"max_days": 0},
        {"capital_brl": 0},
        {"max_risk_brl": 0},
        {"lot_size": 0},
        {"cost_pct": -0.1},
        {"rsi_entry": 101},
        {"exit_mode": "rsi", "rsi_entry": 30, "rsi_exit": 30},
    ],
)
def test_invalid_config_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        config(**overrides)


def test_rsi_exit_is_ignored_when_the_mode_has_no_rsi_exit() -> None:
    assert config(exit_mode="target", rsi_entry=30, rsi_exit=20).rsi_exit == 20
