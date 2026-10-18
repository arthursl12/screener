"""CDI benchmark (docs/cdi.md): compound the daily CDI over the strategy's window."""

import pandas as pd
import pytest

from b3core.benchmark import compare_with_cdi

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
