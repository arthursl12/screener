"""EMA, trend context, RSI and ATR, brief section 7. Expected values are worked out by hand."""

import numpy as np
import pytest

from b3core.indicators import atr, ema, rsi, trend_context

ALL_OFF = {
    "use_ma_order": False,
    "use_fast_slope": False,
    "use_slow_slope": False,
    "use_price_above_fast": False,
}


def context(close: list[float], fast: int, slow: int, **flags: bool) -> list[bool]:
    merged = {**ALL_OFF, **flags}
    result = trend_context(np.array(close), fast_period=fast, slow_period=slow, **merged)
    return [bool(v) for v in result]


def test_ema_is_the_standard_recursion_seeded_with_the_first_value() -> None:
    # period 3 -> factor 2 / (3 + 1) = 0.5: 10, 0.5*11 + 0.5*10, 0.5*12 + 0.5*10.5
    assert ema(np.array([10.0, 11.0, 12.0]), 3) == pytest.approx([10.0, 10.5, 11.25])
    # period 2 -> factor 2/3
    assert ema(np.array([10.0, 12.0, 14.0]), 2) == pytest.approx([10.0, 11.0 + 1 / 3, 13.111111])


def test_ema_of_period_one_is_the_input() -> None:
    values = np.array([10.0, 12.5, 9.0])

    assert ema(values, 1) == pytest.approx(values)


def test_no_enabled_check_means_every_bar_passes() -> None:
    assert context([10, 12, 14], 2, 3) == [True, True, True]


def test_ma_order_needs_fast_above_slow() -> None:
    # fast 10, 11.33, 13.11 against slow 10, 11, 12.5: equal on the first bar, above after
    assert context([10, 12, 14], 2, 3, use_ma_order=True) == [False, True, True]
    # falling closes: fast 14, 12.67, 10.89 against slow 14, 13, 11.5
    assert context([14, 12, 10], 2, 3, use_ma_order=True) == [False, False, False]


def test_slopes_need_the_previous_bar_and_are_strict() -> None:
    assert context([10, 12, 14], 2, 3, use_fast_slope=True) == [False, True, True]
    assert context([10, 12, 14], 2, 3, use_slow_slope=True) == [False, True, True]
    assert context([14, 12, 10], 2, 3, use_fast_slope=True) == [False, False, False]
    # [10, 14, 12]: fast 10, 12.67, 12.22 (falls on the last bar); slow 10, 12, 12 (flat)
    assert context([10, 14, 12], 2, 3, use_fast_slope=True) == [False, True, False]
    assert context([10, 14, 12], 2, 3, use_slow_slope=True) == [False, True, False]
    assert context([10, 14, 12], 2, 3, use_ma_order=True)[2] is True  # order alone still holds


def test_price_above_fast_needs_three_closes_above() -> None:
    # fast 10, 11.33, 13.11, 15.04: the first close equals its average, so bar 2 fails
    assert context([10, 12, 14, 16], 2, 3, use_price_above_fast=True) == [
        False,
        False,
        False,
        True,
    ]


def test_all_enabled_checks_must_pass_together() -> None:
    flags = {"use_ma_order": True, "use_fast_slope": True, "use_slow_slope": True}

    assert context([10, 12, 14], 2, 3, **flags) == [False, True, True]
    # bar 1 passes every check (fast 12.67 > slow 12, both rising); bar 2 fails the fast slope
    assert context([10, 14, 12], 2, 3, **flags) == [False, True, False]


def test_rsi_uses_wilder_smoothing_seeded_with_a_simple_average() -> None:
    # period 2, changes +1 -1 +2 -1. Seed (bar 2): gain 0.5, loss 0.5 -> RSI 50.
    # bar 3: gain (0.5 + 2) / 2 = 1.25, loss 0.5 / 2 = 0.25 -> RS 5 -> 100 - 100 / 6.
    # bar 4: gain 1.25 / 2 = 0.625, loss (0.25 + 1) / 2 = 0.625 -> RSI 50.
    result = rsi(np.array([10.0, 11.0, 10.0, 12.0, 11.0]), 2)

    assert np.isnan(result[:2]).all()
    assert result[2:] == pytest.approx([50.0, 100 - 100 / 6, 50.0])


def test_rsi_is_100_when_there_are_only_gains() -> None:
    result = rsi(np.array([10.0, 11.0, 12.0, 13.0]), 2)

    assert result[2:] == pytest.approx([100.0, 100.0])


def test_rsi_is_0_when_there_are_only_losses() -> None:
    result = rsi(np.array([13.0, 12.0, 11.0, 10.0]), 2)

    assert result[2:] == pytest.approx([0.0, 0.0])


def test_rsi_is_undefined_when_the_seed_window_is_flat() -> None:
    # no gains and no losses: 0 / 0, so no value (and no signal) rather than a made-up one
    result = rsi(np.array([10.0, 10.0, 10.0, 11.0]), 2)

    assert np.isnan(result[:3]).all()
    assert result[3] == pytest.approx(100.0)


def test_rsi_with_fewer_bars_than_needed_is_all_undefined() -> None:
    assert np.isnan(rsi(np.array([10.0, 11.0]), 2)).all()


def test_rsi_rejects_a_period_below_one() -> None:
    with pytest.raises(ValueError, match="period"):
        rsi(np.array([10.0, 11.0, 12.0]), 0)


def test_rsi_matches_ta_lib_on_a_seeded_random_walk() -> None:
    talib = pytest.importorskip("talib")
    close = 20 * np.exp(np.cumsum(np.random.default_rng(7).normal(0, 0.02, 500)))

    for period in (2, 3, 14):
        expected = talib.RSI(close, timeperiod=period)
        assert rsi(close, period) == pytest.approx(expected, nan_ok=True)


HIGH = np.array([10.0, 12.0, 11.0, 13.0, 13.0])
LOW = np.array([8.0, 10.0, 9.0, 12.0, 11.0])
CLOSE = np.array([9.0, 11.0, 10.0, 13.0, 12.0])


def test_atr_uses_true_range_and_wilder_smoothing() -> None:
    # true range = max(high - low, |high - prev close|, |low - prev close|), from bar 1:
    # 3 (gap up from 9), 2, 3 (gap up from 10), 2. Period 2: seed (3 + 2) / 2 = 2.5 on bar 2,
    # then (2.5 + 3) / 2 = 2.75, then (2.75 + 2) / 2 = 2.375.
    result = atr(HIGH, LOW, CLOSE, 2)

    assert np.isnan(result[:2]).all()
    assert result[2:] == pytest.approx([2.5, 2.75, 2.375])


def test_atr_of_period_one_is_the_true_range() -> None:
    assert atr(HIGH, LOW, CLOSE, 1)[1:] == pytest.approx([3.0, 2.0, 3.0, 2.0])


def test_atr_with_too_few_bars_is_all_undefined() -> None:
    assert np.isnan(atr(HIGH[:2], LOW[:2], CLOSE[:2], 2)).all()


def test_atr_rejects_a_period_below_one() -> None:
    with pytest.raises(ValueError, match="period"):
        atr(HIGH, LOW, CLOSE, 0)


def test_atr_rejects_series_of_different_lengths() -> None:
    with pytest.raises(ValueError, match="length"):
        atr(HIGH, LOW[:-1], CLOSE, 2)


def test_atr_matches_ta_lib_on_a_seeded_random_walk() -> None:
    talib = pytest.importorskip("talib")
    rng = np.random.default_rng(11)
    close = 20 * np.exp(np.cumsum(rng.normal(0, 0.02, 500)))
    high = close * (1 + np.abs(rng.normal(0, 0.01, 500)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, 500)))

    for period in (2, 5, 14):
        expected = talib.ATR(high, low, close, timeperiod=period)
        assert atr(high, low, close, period) == pytest.approx(expected, nan_ok=True)
