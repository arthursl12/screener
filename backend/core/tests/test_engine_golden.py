"""Golden cases for 123 de compra. Every number is hand computed from brief section 7.

Base setup (`make_config`): tick 0.01, lot 100, capital 100000, max risk 200, trend checks off,
C3 stop with offset 1, RISK target times 2, entry offset 1, validity 1.
Entry 10.41, stop 10.24, risk 0.17, quantity floor(200 / 0.17) = 1176 -> 1100, target 10.75.
"""

import pytest
from helpers import C1, C2, C3, C4_ENTRY, C5_TARGET, Row, make_candles, make_config

from b3core.engine import BacktestConfig, find_signals, round_to_tick, run_backtest

BASE = make_config()


def run(rows: list[Row], config: BacktestConfig = BASE):  # type: ignore[no-untyped-def]
    return run_backtest(make_candles(rows), config).trades


def test_worked_example() -> None:
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET])

    assert t.entry == pytest.approx(10.41)
    assert t.stop == pytest.approx(10.24)
    assert t.target == pytest.approx(10.75)
    assert t.qty == 1100
    assert t.exit == pytest.approx(10.75)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(374.00)
    assert t.r_multiple == pytest.approx(2.0)
    assert (t.entry_index, t.exit_index) == (3, 4)


def test_signal_levels_are_computed_once_at_the_signal() -> None:
    signals = find_signals(make_candles([C1, C2, C3, C4_ENTRY, C5_TARGET]), BASE)

    assert signals["c3_index"].tolist() == [2]
    assert signals["trigger"].tolist() == pytest.approx([10.41])
    assert signals["stop"].tolist() == pytest.approx([10.24])
    assert signals["target"].tolist() == pytest.approx([10.75])


def test_the_entry_candle_reaching_the_stop_stops_the_trade() -> None:
    c4 = (10.38, 10.45, 10.20, 10.30)  # fills at 10.41 and trades down through 10.24
    (t,) = run([C1, C2, C3, c4, C5_TARGET])

    assert t.exit == pytest.approx(10.24)
    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-187.00)  # 1100 * (10.24 - 10.41)
    assert t.exit_index == 3


def test_gap_up_fill_keeps_the_frozen_stop_and_target_and_sizes_from_the_fill() -> None:
    c4 = (10.50, 10.55, 10.48, 10.52)  # opens above the 10.41 trigger: fills at 10.50
    c5 = (10.52, 10.80, 10.45, 10.78)
    (t,) = run([C1, C2, C3, c4, c5])

    # stop 10.24 and target 10.75 do not move; risk from the fill is 0.26, qty floor(200/0.26) = 769
    assert t.entry == pytest.approx(10.50)
    assert t.stop == pytest.approx(10.24)
    assert t.target == pytest.approx(10.75)
    assert t.qty == 700
    assert t.pnl == pytest.approx(175.00)  # 700 * (10.75 - 10.50)
    assert t.r_multiple == pytest.approx(175.0 / (700 * 0.26))


def test_a_fill_that_gaps_past_the_target_leaves_at_the_fill_price() -> None:
    c4 = (10.80, 10.90, 10.70, 10.85)  # opens above the 10.75 target itself
    (t,) = run([C1, C2, C3, c4, C5_TARGET])

    assert t.entry == pytest.approx(10.80)
    assert t.exit == pytest.approx(10.80)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(0.0)
    assert (t.entry_index, t.exit_index) == (3, 3)


def test_stop_and_target_in_the_same_candle_stop_is_hit_first() -> None:
    c5 = (10.44, 10.80, 10.20, 10.50)  # reaches both 10.24 and 10.75
    (t,) = run([C1, C2, C3, C4_ENTRY, c5])

    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-187.00)


def test_gap_down_through_the_stop_fills_at_the_open() -> None:
    c5 = (10.10, 10.30, 10.05, 10.20)  # opens below the 10.24 stop
    (t,) = run([C1, C2, C3, C4_ENTRY, c5])

    assert t.exit == pytest.approx(10.10)
    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-341.00)  # 1100 * (10.10 - 10.41)


def test_gap_up_through_the_target_fills_at_the_target_price() -> None:
    c5 = (10.90, 11.00, 10.85, 10.95)  # opens above the 10.75 target
    (t,) = run([C1, C2, C3, C4_ENTRY, c5])

    assert t.exit == pytest.approx(10.75)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(374.00)


def test_trigger_not_reached_inside_the_validity_window_gives_no_trade() -> None:
    c4 = (10.38, 10.40, 10.35, 10.39)  # high 10.40 < trigger 10.41
    c5 = (10.38, 10.80, 10.35, 10.78)  # would fill and hit the target, but the order expired

    assert run([C1, C2, C3, c4, c5]) == []


def test_trigger_reached_on_the_second_bar_with_validity_two() -> None:
    c4 = (10.38, 10.40, 10.35, 10.39)
    c5 = (10.38, 10.80, 10.35, 10.78)  # fills at 10.41 and reaches the target in the same candle
    (t,) = run([C1, C2, C3, c4, c5], make_config(entry_validity_bars=2))

    assert (t.entry_index, t.exit_index) == (4, 4)
    assert t.pnl == pytest.approx(374.00)


def test_c2_stop() -> None:
    config = make_config(stop_mode="C2", target_mult=1.5)
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)

    # stop 10.20 - 0.01 = 10.19, risk 0.22, qty floor(200/0.22) = 909 -> 900, target 10.41 + 0.33
    assert t.stop == pytest.approx(10.19)
    assert t.qty == 900
    assert t.target == pytest.approx(10.74)
    assert t.pnl == pytest.approx(297.00)


def test_stop_offset() -> None:
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], make_config(stop_offset_ticks=0))

    # stop at the c3 low 10.25, risk 0.16, qty floor(200/0.16) = 1250 -> 1200, target 10.73
    assert t.stop == pytest.approx(10.25)
    assert t.qty == 1200
    assert t.pnl == pytest.approx(384.00)  # 1200 * 0.32


def test_entry_offset() -> None:
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], make_config(entry_offset_ticks=0))

    # entry at the c3 high 10.40, risk 0.16, qty 1200, target 10.72
    assert t.entry == pytest.approx(10.40)
    assert t.qty == 1200
    assert t.pnl == pytest.approx(384.00)


def test_amplitude_target() -> None:
    config = make_config(target_mode="AMP", target_mult=0.75)
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)

    # amplitude = highest high 10.60 - lowest low 10.20 = 0.40; target 10.41 + 0.75 * 0.40 = 10.71
    assert t.target == pytest.approx(10.71)
    assert t.pnl == pytest.approx(330.00)  # 1100 * 0.30


def test_default_amplitude_multiple_is_1_61() -> None:
    c6 = (10.78, 11.10, 10.70, 11.06)
    (t,) = run(
        [C1, C2, C3, C4_ENTRY, C5_TARGET, c6], make_config(target_mode="AMP", target_mult=1.61)
    )

    # 10.41 + 1.61 * 0.40 = 11.054, rounded to the nearest tick: 11.05, reached on the sixth candle
    assert t.target == pytest.approx(11.05)
    assert (t.entry_index, t.exit_index) == (3, 5)
    assert t.pnl == pytest.approx(704.00)  # 1100 * 0.64


@pytest.mark.parametrize(("max_ticks", "trades"), [(0, 1), (15, 1), (14, 0)])
def test_size_filter_on_c3_is_inclusive_and_zero_means_off(max_ticks: int, trades: int) -> None:
    # c3 range is 10.40 - 10.25 = 0.15 = 15 ticks
    config = make_config(max_c3_ticks=max_ticks)

    assert len(run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)) == trades


def test_quantity_below_one_lot_gives_no_trade() -> None:
    config = make_config(max_risk_brl=10)  # floor(10 / 0.17) = 58 shares, below one lot

    assert run([C1, C2, C3, C4_ENTRY, C5_TARGET], config) == []


def test_quantity_is_capped_by_capital() -> None:
    config = make_config(capital_brl=3000)
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)

    # capital cap floor(3000 / 10.41) = 288 -> 200 shares, below the risk-based 1100
    assert t.qty == 200
    assert t.pnl == pytest.approx(68.00)


def test_open_position_at_the_end_of_the_data_is_not_a_trade() -> None:
    assert run([C1, C2, C3, C4_ENTRY]) == []


def test_a_signal_with_zero_risk_is_dropped() -> None:
    doji = (10.30, 10.30, 10.30, 10.30)  # high equals low: entry would equal the c3 stop
    config = make_config(entry_offset_ticks=0, stop_offset_ticks=0)

    assert run([C1, C2, doji, C4_ENTRY, C5_TARGET], config) == []
    assert (
        len(run([C1, C2, doji, C4_ENTRY, C5_TARGET])) == 1
    )  # with the default offsets it is valid


def test_equal_lows_do_not_form_the_pattern() -> None:
    c3_equal = (10.30, 10.40, 10.20, 10.38)  # same low as c2: strict comparison fails
    c2_equal = (10.45, 10.50, 10.40, 10.30)  # same low as c1: strict comparison fails

    for rows in ([C1, C2, c3_equal, C4_ENTRY, C5_TARGET], [C1, c2_equal, C3, C4_ENTRY, C5_TARGET]):
        # no signal at bar 2; a later window can still form its own pattern, so check the signals
        assert 2 not in find_signals(make_candles(rows), BASE)["c3_index"].tolist()


# --- trend checks with tiny periods (hand computed in test_indicators) -------------------------

TREND = {"use_ma_order": True, "use_fast_slope": True, "use_slow_slope": True}
FAST1_SLOW2 = {"ma_fast_period": 1, "ma_slow_period": 2}


def test_trend_checks_pass_on_the_worked_example() -> None:
    # closes 10.45, 10.30, 10.38: fast = close; slow 10.45, 10.35, 10.37
    # c3: fast 10.38 > slow 10.37, fast rising from 10.30, slow rising from 10.35
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], make_config(**FAST1_SLOW2, **TREND))

    assert t.pnl == pytest.approx(374.00)


def test_price_above_fast_fails_when_the_closes_equal_the_average() -> None:
    config = make_config(**FAST1_SLOW2, use_price_above_fast=True)  # fast period 1: close == fast

    assert run([C1, C2, C3, C4_ENTRY, C5_TARGET], config) == []


@pytest.mark.parametrize(
    ("flag", "trades"),
    [("use_ma_order", 0), ("use_fast_slope", 1), ("use_slow_slope", 0)],
)
def test_each_trend_check_on_its_own(flag: str, trades: int) -> None:
    # c3 closes at 10.33: fast 10.33 < slow 10.3367 (order fails), fast still rises from 10.30,
    # slow 10.3367 falls from 10.35
    c3 = (10.30, 10.40, 10.25, 10.33)
    config = make_config(**FAST1_SLOW2, **{flag: True})

    assert len(run([C1, C2, c3, C4_ENTRY, C5_TARGET], config)) == trades


def test_averages_need_a_warm_up_of_the_slow_period() -> None:
    warm = make_config(ma_fast_period=1, ma_slow_period=2, use_ma_order=True)
    cold = make_config(ma_fast_period=1, ma_slow_period=3, use_ma_order=True)
    rows = [C1, C2, C3, C4_ENTRY, C5_TARGET]

    assert len(run(rows, warm)) == 1  # the signal is on bar 2, the slow period is 2
    assert run(rows, cold) == []  # bar 2 is before bar number 3: still warming up
    assert len(run(rows, make_config(ma_slow_period=3))) == 1  # no average-based check, no warm-up


# --- helpers and configuration ------------------------------------------------------------------


def test_round_to_tick() -> None:
    assert round_to_tick(10.404, 0.01) == pytest.approx(10.40)
    assert round_to_tick(10.406, 0.01) == pytest.approx(10.41)
    assert round_to_tick(0.1 + 0.2, 0.1) == pytest.approx(0.3)


def test_config_defaults_follow_the_pseudocode() -> None:
    c = BacktestConfig()

    assert (c.ma_fast_period, c.ma_slow_period) == (8, 80)
    assert (c.use_ma_order, c.use_fast_slope, c.use_slow_slope) == (True, True, True)
    assert c.use_price_above_fast is False
    assert (c.max_c3_ticks, c.entry_offset_ticks, c.entry_validity_bars) == (0, 1, 1)
    assert (c.stop_mode, c.stop_offset_ticks) == ("C3", 1)
    assert (c.target_mode, c.target_mult) == ("AMP", 1.61)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"target_mult": 0}, "target_mult"),
        ({"stop_mode": "C1"}, "stop_mode"),
        ({"target_mode": "FIXED"}, "target_mode"),
        ({"entry_validity_bars": 0}, "entry_validity_bars"),
        ({"entry_offset_ticks": -1}, "entry_offset_ticks"),
        ({"stop_offset_ticks": -1}, "stop_offset_ticks"),
        ({"max_c3_ticks": -1}, "max_c3_ticks"),
        ({"ma_fast_period": 0}, "ma_fast_period"),
        ({"ma_slow_period": 0}, "ma_slow_period"),
    ],
)
def test_config_rejects_invalid_values(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BacktestConfig(**kwargs)  # type: ignore[arg-type]


def test_config_roundtrips_through_json() -> None:
    config = BacktestConfig(target_mult=1.272, stop_mode="C2", use_price_above_fast=True)

    assert BacktestConfig.from_dict(config.to_dict()) == config
