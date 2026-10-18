"""CDI benchmark (docs/cdi.md): compound the daily CDI over the strategy's window."""

import pandas as pd
import pytest

from b3core.benchmark import (
    compare_with_cdi,
    compare_with_index,
    compare_with_prices,
    index_equity,
)

# 366 calendar days, 252 business days at 0.04% (the worked example in docs/cdi.md)
YEARS = 366 / 365.25


def days(n: int, start: str = "2024-01-01") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def constant(index: pd.DatetimeIndex, rate: float) -> pd.Series:
    return pd.Series(rate, index=index)


def test_worked_example_where_the_strategy_beats_the_cdi() -> None:
    trading = days(253)  # the first day only starts the clock, 252 days accrue
    rates = constant(trading, 0.04)

    result = compare_with_cdi(0.12, YEARS, rates, trading)

    assert result.factor == pytest.approx(1.0004**252, rel=1e-12)
    assert result.factor == pytest.approx(1.10603, abs=1e-5)
    assert result.cdi_cagr == pytest.approx(0.10580, abs=1e-5)
    assert result.excess == pytest.approx(0.12 - result.cdi_cagr)
    assert result.excess == pytest.approx(0.0142, abs=1e-4)
    assert result.beats_cdi is True


def test_worked_example_where_the_strategy_loses_to_the_cdi() -> None:
    trading = days(253)

    result = compare_with_cdi(0.09, YEARS, constant(trading, 0.04), trading)

    assert result.excess == pytest.approx(-0.0158, abs=1e-4)
    assert result.beats_cdi is False


def test_three_days_compound_day_by_day() -> None:
    trading = days(4)  # d0 plus three accruing days
    rates = pd.Series([0.99, 0.04, 0.05, 0.06], index=trading)  # d0's rate is not used

    result = compare_with_cdi(0.0, 3 / 365.25, rates, trading)

    assert result.factor == pytest.approx(1.0004 * 1.0005 * 1.0006, abs=1e-7)
    assert result.factor == pytest.approx(1.0015007, abs=1e-7)


def test_the_window_excludes_the_first_day_and_includes_the_last() -> None:
    trading = days(4)
    rates = pd.Series([1.0, 2.0, 3.0, 4.0], index=trading)

    shorter = compare_with_cdi(0.0, 1.0, rates.iloc[:3], trading[:3])
    longer = compare_with_cdi(0.0, 1.0, rates, trading)

    assert shorter.factor == pytest.approx(1.02 * 1.03)
    assert longer.factor == pytest.approx(shorter.factor * 1.04)  # one more day, that day's rate


def test_a_missing_business_day_is_an_error_that_names_it() -> None:
    trading = days(5)
    rates = constant(trading, 0.04).drop(trading[2])

    with pytest.raises(ValueError, match="2024-01-03"):
        compare_with_cdi(0.1, 1.0, rates, trading)


def test_cdi_dates_that_are_not_candle_dates_are_still_compounded() -> None:
    trading = days(4).delete(2)  # a candle is missing, but the CDI exists that day
    rates = constant(days(4), 1.0)

    result = compare_with_cdi(0.0, 1.0, rates, trading)

    assert result.factor == pytest.approx(1.01**3)


def test_a_zero_rate_gives_zero_cdi_so_any_gain_beats_it() -> None:
    trading = days(10)

    result = compare_with_cdi(0.01, 1.0, constant(trading, 0.0), trading)

    assert result.cdi_cagr == 0.0
    assert result.beats_cdi is True
    assert compare_with_cdi(0.0, 1.0, constant(trading, 0.0), trading).beats_cdi is False


def test_a_strategy_with_no_trades_loses_to_a_positive_cdi() -> None:
    trading = days(253)

    assert compare_with_cdi(0.0, YEARS, constant(trading, 0.04), trading).beats_cdi is False


def test_timezone_aware_candle_times_are_read_as_sao_paulo_dates() -> None:
    # midnight in São Paulo is 02:00 or 03:00 UTC: still the same local date
    local = days(4)
    utc = local.tz_localize("America/Sao_Paulo").tz_convert("UTC")

    result = compare_with_cdi(0.0, 1.0, constant(local, 1.0), utc)

    assert result.factor == pytest.approx(1.01**3)


def test_bad_arguments_are_rejected() -> None:
    trading = days(3)
    with pytest.raises(ValueError, match="years"):
        compare_with_cdi(0.1, 0.0, constant(trading, 0.04), trading)
    with pytest.raises(ValueError, match="two"):
        compare_with_cdi(0.1, 1.0, constant(trading[:1], 0.04), trading[:1])


def test_a_late_evening_local_time_keeps_its_local_date() -> None:
    # 22:00 in São Paulo is 01:00 UTC the next day: converting first keeps the local date
    local = days(4)
    evening = (local + pd.Timedelta(hours=22)).tz_localize("America/Sao_Paulo").tz_convert("UTC")

    result = compare_with_cdi(0.0, 1.0, constant(local, 1.0), evening)

    assert result.factor == pytest.approx(1.01**3)


# --- IBOV (docs/ibov.md) ---------------------------------------------------------------------

YEARS_366 = 366 / 365.25


def local_days(n: int, start: str = "2024-01-02") -> pd.DatetimeIndex:
    # midnight in São Paulo is 03:00 UTC
    return pd.bdate_range(start, periods=n).tz_localize("UTC") + pd.Timedelta(hours=3)


def closes(values: list[float], start: str = "2024-01-02") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_prices_worked_example_beats_and_loses() -> None:
    won = compare_with_prices(0.12, YEARS_366, 100_000, 110_000)
    lost = compare_with_prices(0.09, YEARS_366, 100_000, 110_000)

    assert won.factor == pytest.approx(1.10)
    assert won.cagr == pytest.approx(0.099785, abs=1e-6)
    assert won.excess == pytest.approx(0.12 - 0.099785, abs=1e-6)
    assert won.beats is True
    assert lost.excess == pytest.approx(-0.009785, abs=1e-6)
    assert lost.beats is False


def test_a_falling_index_has_a_negative_cagr_and_a_flat_strategy_beats_it() -> None:
    fell = compare_with_prices(0.0, YEARS_366, 100_000, 90_000)

    assert fell.cagr == pytest.approx(-0.099806, abs=1e-6)
    assert fell.beats is True


def test_equal_prices_are_not_a_win_for_a_flat_strategy() -> None:
    assert compare_with_prices(0.0, 1.0, 100.0, 100.0).beats is False  # excess is exactly 0


def test_the_short_window_factor() -> None:
    assert compare_with_prices(0.0, 3 / 365.25, 100_000, 100_150).factor == pytest.approx(1.0015)


def test_prices_reject_bad_input() -> None:
    with pytest.raises(ValueError, match="years"):
        compare_with_prices(0.0, 0.0, 100.0, 110.0)
    with pytest.raises(ValueError, match="positive"):
        compare_with_prices(0.0, 1.0, 0.0, 110.0)
    with pytest.raises(ValueError, match="positive"):
        compare_with_prices(0.0, 1.0, 100.0, -5.0)


def test_index_uses_the_candle_window_not_the_index_dates() -> None:
    index = closes([90.0, 100.0, 105.0, 110.0, 200.0])  # Jan 2 to Jan 8
    window = local_days(3, "2024-01-03")  # candles on Jan 3, 4, 5: closes 100 -> 110

    result = compare_with_index(0.0, 2 / 365.25, index, window)

    assert result.factor == pytest.approx(1.10)


def test_index_missing_the_first_or_last_close_names_the_date() -> None:
    index = closes([100.0, 110.0, 120.0], "2024-01-03")  # Jan 3 to Jan 5
    with pytest.raises(ValueError, match="2024-01-02"):
        compare_with_index(0.0, 1.0, index, local_days(3, "2024-01-02"))
    with pytest.raises(ValueError, match="2024-01-08"):
        compare_with_index(0.0, 1.0, index, local_days(4, "2024-01-03"))


def test_index_with_a_non_positive_close_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        compare_with_index(0.0, 1.0, closes([0.0, 1.0, 2.0]), local_days(3))


def test_index_with_a_zero_close_inside_the_window_raises() -> None:
    index = closes([100.0, 0.0, 110.0])

    with pytest.raises(ValueError, match="positive"):
        compare_with_index(0.0, 1.0, index, local_days(3))
    with pytest.raises(ValueError, match="positive"):
        index_equity(index, local_days(3), 1_000.0)


def test_index_reads_candle_dates_in_sao_paulo() -> None:
    # 23:30 on Jan 2 in São Paulo is 02:30 UTC on Jan 3: still the local day of Jan 2
    late = pd.DatetimeIndex(["2024-01-03 02:30", "2024-01-04 02:30"], tz="UTC")
    index = closes([100.0, 110.0], "2024-01-02")  # Jan 2, Jan 3

    assert compare_with_index(0.0, 1.0, index, late).factor == pytest.approx(1.10)


def test_index_equity_is_the_capital_times_the_close_over_the_first_close() -> None:
    index = closes([90.0, 100.0, 105.0, 110.0, 200.0])
    window = local_days(3, "2024-01-03")

    curve = index_equity(index, window, 1_000.0)

    assert curve.tolist() == pytest.approx([1_000.0, 1_050.0, 1_100.0])
    assert list(curve.index) == list(pd.bdate_range("2024-01-03", periods=3))
