"""Intraday momentum on WINFUT (brief section 10): VWAP, bands, signal, exposure, sizing, backtest.

The rules are those of the authors' notebook (Zarattini, Aziz and Barbon, "Beat the Market").
"""

import numpy as np
import pandas as pd
import pytest

from b3core.intraday_momentum import (
    breakout_signal,
    intraday_exposure,
    noise_bands,
    session_vwap,
)

NAN = float("nan")


def minute_bars(day: str, closes: list[float], start: str = "09:00", volume: float = 1.0):
    """One bar per minute with high, low and open equal to the close."""
    index = pd.date_range(f"{day} {start}", periods=len(closes), freq="min")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": volume},
        index=index,
    )


# --- VWAP --------------------------------------------------------------------------------------


def test_vwap_is_the_volume_weighted_typical_price_since_the_open_of_the_day() -> None:
    index = pd.to_datetime(["2024-01-02 09:00", "2024-01-02 09:01", "2024-01-03 09:00"])
    bars = pd.DataFrame(
        {
            "open": [10.0, 12.0, 19.0],
            "high": [11.0, 13.0, 20.0],
            "low": [9.0, 11.0, 18.0],
            "close": [10.0, 12.0, 19.0],
            "volume": [100.0, 300.0, 50.0],
        },
        index=index,
    )

    vwap = session_vwap(bars)

    assert vwap.iloc[0] == pytest.approx(10.0)  # typical price (11 + 9 + 10) / 3
    assert vwap.iloc[1] == pytest.approx((100 * 10 + 300 * 12) / 400)
    assert vwap.iloc[2] == pytest.approx(19.0)  # a new day starts again


def test_vwap_is_nan_until_something_has_traded() -> None:
    bars = minute_bars("2024-01-02", [10.0, 11.0, 12.0])
    bars["volume"] = [0.0, 0.0, 5.0]

    vwap = session_vwap(bars)

    assert vwap.iloc[:2].isna().all()
    assert vwap.iloc[2] == pytest.approx(12.0)


# --- bands -------------------------------------------------------------------------------------


def two_days(second_open: float) -> tuple[pd.DataFrame, pd.Series]:
    first = minute_bars("2024-01-02", [100.0, 102.0])  # opens at 100, closes at 102
    second = minute_bars("2024-01-03", [second_open, 105.0])
    bars = pd.concat([first, second])
    return bars, pd.Series(0.01, index=bars.index)


def test_the_bands_widen_by_the_overnight_gap_when_the_open_is_below_the_previous_close() -> None:
    bars, sigma = two_days(101.0)  # gap down from 102 to 101

    bands = noise_bands(bars, sigma)

    day2 = bands.loc["2024-01-03"]
    assert day2["ub"].to_numpy() == pytest.approx(102.0 * 1.01)  # max(open, previous close)
    assert day2["lb"].to_numpy() == pytest.approx(101.0 * 0.99)  # min(open, previous close)


def test_the_bands_use_the_open_on_both_sides_after_a_gap_up() -> None:
    bars, sigma = two_days(103.0)  # gap up from 102 to 103

    day2 = noise_bands(bars, sigma).loc["2024-01-03"]

    assert day2["ub"].to_numpy() == pytest.approx(103.0 * 1.01)
    assert day2["lb"].to_numpy() == pytest.approx(102.0 * 0.99)  # min is the previous close


def test_the_band_multiplier_scales_sigma() -> None:
    bars, sigma = two_days(101.0)

    day2 = noise_bands(bars, sigma, band_mult=2.0).loc["2024-01-03"]

    assert day2["ub"].to_numpy() == pytest.approx(102.0 * 1.02)
    assert day2["lb"].to_numpy() == pytest.approx(101.0 * 0.98)


def test_the_first_day_has_no_bands_and_a_missing_sigma_gives_none() -> None:
    bars, sigma = two_days(101.0)
    sigma.iloc[-1] = NAN

    bands = noise_bands(bars, sigma)

    assert bands.loc["2024-01-02"].isna().all().all()  # no previous close
    assert bands.iloc[-1].isna().all()
    assert bands.iloc[-2].notna().all()


def test_the_previous_close_is_the_last_bar_of_the_previous_day() -> None:
    first = minute_bars("2024-01-02", [100.0, 120.0, 90.0])  # the high of the day is not used
    second = minute_bars("2024-01-03", [95.0, 96.0])
    bars = pd.concat([first, second])

    day2 = noise_bands(bars, pd.Series(0.0, index=bars.index)).loc["2024-01-03"]

    assert day2["ub"].to_numpy() == pytest.approx(95.0)  # max(95, 90)
    assert day2["lb"].to_numpy() == pytest.approx(90.0)  # min(95, 90)


# --- signal ------------------------------------------------------------------------------------


def test_the_signal_needs_the_close_beyond_a_band_and_beyond_the_vwap() -> None:
    index = pd.date_range("2024-01-03 09:00", periods=6, freq="min")
    close = pd.Series([106.0, 106.0, 98.0, 98.0, 100.0, 106.0], index=index)
    bands = pd.DataFrame({"ub": 105.0, "lb": 99.0}, index=index)
    vwap = pd.Series([100.0, 107.0, 100.0, 97.0, 100.0, NAN], index=index)

    signal = breakout_signal(close, bands, vwap)

    # long, above the band but below the VWAP, short, below the band but above the VWAP,
    # inside the bands, and a missing VWAP
    assert list(signal) == [1, 0, -1, 0, 0, 0]


def test_a_close_on_the_band_is_not_a_signal_and_missing_bands_give_none() -> None:
    index = pd.date_range("2024-01-03 09:00", periods=3, freq="min")
    close = pd.Series([105.0, 99.0, 110.0], index=index)
    bands = pd.DataFrame({"ub": [105.0, 99.0, NAN], "lb": [99.0, 99.0, NAN]}, index=index)
    vwap = pd.Series(100.0, index=index)

    assert list(breakout_signal(close, bands, vwap)) == [0, 0, 0]


# --- exposure ----------------------------------------------------------------------------------

OPEN = 9 * 60  # the session opens at 09:00
EXIT = 17 * 60 + 30


def exposure_for(decisions: dict[str, int], **overrides: int) -> pd.Series:
    """Exposure of one day from 09:00 to 10:59, given the signal on chosen bars."""
    index = pd.date_range("2024-01-03 09:00", periods=120, freq="min")
    signal = pd.Series(0, index=index, dtype="int64")
    for stamp, value in decisions.items():
        signal[pd.Timestamp(f"2024-01-03 {stamp}")] = value
    settings = {
        "session_open": OPEN,
        "trade_freq": 30,
        "first_decision": OPEN,
        "exit_minute": EXIT,
        **overrides,
    }
    return intraday_exposure(signal, **settings)


def held(exposure: pd.Series) -> dict[int, tuple[str, str]]:
    """The first and last bar of each run of equal non-zero exposure, keyed by the sign."""
    runs = {}
    for sign in (1, -1):
        bars = exposure.index[exposure == sign]
        if len(bars):
            runs[sign] = (bars[0].strftime("%H:%M"), bars[-1].strftime("%H:%M"))
    return runs


def test_a_decision_on_the_half_hour_holds_from_the_next_bar_to_the_next_decision() -> None:
    exposure = exposure_for({"09:29": 1})

    # decided on the close of the 09:29 bar (09:30), flat from the 09:59 decision onward
    assert held(exposure) == {1: ("09:30", "09:59")}


def test_a_signal_on_a_bar_that_is_not_a_decision_bar_is_ignored() -> None:
    assert held(exposure_for({"09:30": 1, "09:45": -1})) == {}


def test_a_signal_that_repeats_at_the_next_decision_keeps_the_position() -> None:
    assert held(exposure_for({"09:29": 1, "09:59": 1})) == {1: ("09:30", "10:29")}


def test_a_reversal_goes_from_long_to_short_without_a_flat_bar() -> None:
    exposure = exposure_for({"09:29": 1, "09:59": -1})

    assert held(exposure) == {1: ("09:30", "09:59"), -1: ("10:00", "10:29")}


def test_nothing_is_held_after_the_exit_minute() -> None:
    exposure = exposure_for({"09:29": 1, "09:59": 1, "10:29": 1}, exit_minute=10 * 60 + 15)

    assert held(exposure) == {1: ("09:30", "10:14")}
    assert (exposure[exposure.index >= pd.Timestamp("2024-01-03 10:15")] == 0).all()


def test_decisions_before_the_first_decision_time_are_ignored() -> None:
    # 09:29 closes at 09:30, before 10:00; 09:59 closes at 10:00 and is allowed
    exposure = exposure_for({"09:29": 1, "09:59": -1}, first_decision=10 * 60)

    assert held(exposure) == {-1: ("10:00", "10:29")}


def test_each_day_starts_flat_and_the_last_position_is_not_carried_over() -> None:
    first = pd.date_range("2024-01-03 09:00", periods=60, freq="min")
    second = pd.date_range("2024-01-04 09:00", periods=60, freq="min")
    signal = pd.Series(0, index=first.append(second), dtype="int64")
    signal[pd.Timestamp("2024-01-03 09:59")] = 1  # decided on the last bar of day one

    exposure = intraday_exposure(
        signal, session_open=OPEN, trade_freq=30, first_decision=OPEN, exit_minute=EXIT
    )

    assert (exposure == 0).all()  # shifted within the day, so it never reaches the next one


def test_the_exposure_has_the_signals_index_and_no_missing_values() -> None:
    exposure = exposure_for({"09:29": 1})

    assert len(exposure) == 120
    assert not exposure.isna().any()
    assert set(np.unique(exposure)) <= {-1.0, 0.0, 1.0}
