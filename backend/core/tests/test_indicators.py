"""EMA and trend context, brief section 7. Expected values are worked out by hand."""

import numpy as np
import pytest

from b3core.indicators import ema, trend_context

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
