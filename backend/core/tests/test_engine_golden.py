"""Golden cases for 123 de compra. Every number is hand computed from brief section 7.

Base setup: tick 0.01, lot 100, capital 100000, max risk 200, risk factor 2, c2_low stop,
offset 1, validity 1. Risk per share 0.36, risk-based quantity floor(200/0.36) = 555 -> 500.
"""

import pytest
from helpers import C1, C2, C3, C4_ENTRY, C5_TARGET, Row, make_candles

from b3core.engine import BacktestConfig, round_to_tick, run_backtest

BASE = BacktestConfig(max_risk_brl=200)


def run(rows: list[Row], config: BacktestConfig = BASE):  # type: ignore[no-untyped-def]
    return run_backtest(make_candles(rows), config).trades


def test_worked_example() -> None:
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET])

    assert t.entry == pytest.approx(10.56)
    assert t.stop == pytest.approx(10.20)
    assert t.target == pytest.approx(11.28)
    assert t.qty == 500
    assert t.exit == pytest.approx(11.28)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(360.00)
    assert t.r_multiple == pytest.approx(2.0)
    assert (t.entry_index, t.exit_index) == (3, 4)


def test_stop_wins_when_the_entry_candle_also_reaches_the_stop() -> None:
    c4 = (10.40, 10.58, 10.19, 10.25)  # fills at 10.56 and trades down through 10.20
    (t,) = run([C1, C2, C3, c4, C5_TARGET])

    assert t.entry == pytest.approx(10.56)
    assert t.exit == pytest.approx(10.20)
    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-180.00)  # 500 * (10.20 - 10.56)
    assert t.exit_index == 3


def test_gap_up_open_fills_at_the_open_and_target_follows_the_fill() -> None:
    c4 = (10.62, 10.70, 10.60, 10.65)  # opens above the 10.56 trigger
    c5 = (10.65, 11.50, 10.60, 11.40)
    (t,) = run([C1, C2, C3, c4, c5])

    # risk 0.42, qty floor(200/0.42) = 476 -> 400, target 10.62 + 2 * 0.42 = 11.46
    assert t.entry == pytest.approx(10.62)
    assert t.qty == 400
    assert t.target == pytest.approx(11.46)
    assert t.pnl == pytest.approx(336.00)  # 400 * 0.84


def test_stop_and_target_in_the_same_candle_stop_is_hit_first() -> None:
    c5 = (10.55, 11.30, 10.15, 10.80)  # reaches both 10.20 and 11.28
    (t,) = run([C1, C2, C3, C4_ENTRY, c5])

    assert t.exit_reason == "stop"
    assert t.exit == pytest.approx(10.20)
    assert t.pnl == pytest.approx(-180.00)


def test_gap_down_through_the_stop_fills_at_the_open() -> None:
    c5 = (10.10, 10.30, 10.05, 10.20)  # opens below the 10.20 stop
    (t,) = run([C1, C2, C3, C4_ENTRY, c5])

    assert t.exit == pytest.approx(10.10)
    assert t.exit_reason == "stop"
    assert t.pnl == pytest.approx(-230.00)  # 500 * (10.10 - 10.56)


def test_gap_up_through_the_target_fills_at_the_target_price() -> None:
    c5 = (11.40, 11.50, 11.30, 11.45)  # opens above the 11.28 target
    (t,) = run([C1, C2, C3, C4_ENTRY, c5])

    assert t.exit == pytest.approx(11.28)
    assert t.exit_reason == "target"
    assert t.pnl == pytest.approx(360.00)


def test_trigger_not_reached_inside_the_validity_window_gives_no_trade() -> None:
    c4 = (10.40, 10.50, 10.38, 10.45)  # high 10.50 < trigger 10.56
    c5 = (10.45, 10.70, 10.40, 10.60)  # would reach it, but the order expired after c4
    c6 = (10.60, 11.30, 10.50, 11.25)

    assert run([C1, C2, C3, c4, c5, c6]) == []


def test_trigger_reached_on_the_second_candle_with_validity_two() -> None:
    c4 = (10.40, 10.50, 10.38, 10.45)
    c5 = (10.45, 10.70, 10.40, 10.60)  # fills at 10.56
    c6 = (10.60, 11.30, 10.50, 11.25)  # target
    (t,) = run([C1, C2, C3, c4, c5, c6], BacktestConfig(max_risk_brl=200, entry_validity_candles=2))

    assert (t.entry_index, t.exit_index) == (4, 5)
    assert t.pnl == pytest.approx(360.00)


def test_c3_low_stop() -> None:
    config = BacktestConfig(max_risk_brl=200, stop_mode="c3_low")
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)

    # stop 10.35, risk 0.21, qty floor(200/0.21) = 952 -> 900, target 10.56 + 0.42 = 10.98
    assert t.stop == pytest.approx(10.35)
    assert t.qty == 900
    assert t.target == pytest.approx(10.98)
    assert t.pnl == pytest.approx(378.00)


def test_amplitude_target() -> None:
    config = BacktestConfig(max_risk_brl=200, target_mode="amplitude")
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)

    # amplitude = highest high 10.60 - lowest low 10.10 = 0.50, target 10.56 + 0.50 = 11.06
    assert t.target == pytest.approx(11.06)
    assert t.pnl == pytest.approx(250.00)  # 500 * 0.50
    assert t.r_multiple == pytest.approx(250.0 / 180.0)


def test_inside_bar_filter_rejects_the_worked_example() -> None:
    config = BacktestConfig(max_risk_brl=200, inside_bar=True)

    # c3 low 10.35 is above c2 low 10.20, so c3 is not an inside bar of c2
    assert run([C1, C2, C3, C4_ENTRY, C5_TARGET], config) == []


def test_inside_bar_filter_accepts_a_lower_c3_low() -> None:
    c3 = (10.50, 10.55, 10.15, 10.40)  # lower high and lower low than c2
    config = BacktestConfig(max_risk_brl=200, inside_bar=True)
    (t,) = run([C1, C2, c3, C4_ENTRY, C5_TARGET], config)

    assert t.pnl == pytest.approx(360.00)


def test_signal_with_stop_above_the_trigger_is_discarded() -> None:
    c2 = (10.30, 10.90, 10.70, 10.85)
    c3 = (10.85, 10.60, 10.50, 10.55)  # trigger 10.61 is below the c2 low 10.70
    c4 = (10.55, 10.65, 10.52, 10.60)
    c5 = (10.60, 10.90, 10.55, 10.85)

    assert run([C1, c2, c3, c4, c5]) == []

    # With the c3 low as stop the same signal is valid: risk 0.11, qty 1800, target 10.83
    (t,) = run([C1, c2, c3, c4, c5], BacktestConfig(max_risk_brl=200, stop_mode="c3_low"))
    assert t.pnl == pytest.approx(396.00)  # 1800 * 0.22


def test_quantity_below_one_lot_gives_no_trade() -> None:
    config = BacktestConfig(max_risk_brl=10)  # floor(10 / 0.36) = 27 shares, below one lot

    assert run([C1, C2, C3, C4_ENTRY, C5_TARGET], config) == []


def test_quantity_is_capped_by_capital() -> None:
    config = BacktestConfig(capital_brl=3000, max_risk_brl=200)
    (t,) = run([C1, C2, C3, C4_ENTRY, C5_TARGET], config)

    # capital cap floor(3000 / 10.56) = 284 -> 200 shares, below the risk-based 500
    assert t.qty == 200
    assert t.pnl == pytest.approx(144.00)


def test_open_position_at_the_end_of_the_data_is_not_a_trade() -> None:
    assert run([C1, C2, C3, C4_ENTRY]) == []


def test_equal_highs_do_not_form_the_pattern() -> None:
    c2 = (10.30, 10.40, 10.20, 10.35)  # same high as c1: strict comparison fails
    assert run([C1, c2, C3, C4_ENTRY, C5_TARGET]) == []


def test_round_to_tick() -> None:
    assert round_to_tick(10.404, 0.01) == pytest.approx(10.40)
    assert round_to_tick(10.406, 0.01) == pytest.approx(10.41)
    assert round_to_tick(0.1 + 0.2, 0.1) == pytest.approx(0.3)


def test_config_rejects_invalid_values_and_roundtrips_through_json() -> None:
    with pytest.raises(ValueError, match="risk_factor"):
        BacktestConfig(risk_factor=0.5)
    with pytest.raises(ValueError, match="stop_mode"):
        BacktestConfig(stop_mode="c1_low")
    with pytest.raises(ValueError, match="entry_validity_candles"):
        BacktestConfig(entry_validity_candles=0)

    config = BacktestConfig(risk_factor=3.5, stop_mode="c3_low", inside_bar=True)
    assert BacktestConfig.from_dict(config.to_dict()) == config
