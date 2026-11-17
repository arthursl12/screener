"""Stop variants of the paper, long and short legs, leverage and the trade list (brief section 10).

The paper's base model, the current-band stop and the VWAP-only stop have no reference code: the
readings tested here are the owner-visible assumptions listed in the brief.
"""

import numpy as np
import pandas as pd
import pytest

from b3core.intraday_momentum import (
    IntradayConfig,
    contracts_for,
    run_intraday_momentum,
    strategy_exposure,
    trade_list,
)

SMALL = IntradayConfig(
    lookback=1,
    min_days=1,
    capital=1000.0,
    max_leverage=1.0,
    point_value=1.0,
    fee_per_side=0.0,
    margin_per_contract=0.0,
    exit_minute=24 * 60,
)


def day_bars(day: str, closes: list[float]) -> pd.DataFrame:
    index = pd.date_range(f"{day} 09:00", periods=len(closes), freq="min")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1.0},
        index=index,
    )


def two_days(day2_by_bar: dict[int, float], base: float = 100.0) -> pd.DataFrame:
    """Day one opens at 100 and closes at 101 everywhere else, so sigma is 1% from the second bar
    and day two has the bands 99 and 102.01. Day two is 120 bars (09:00 to 10:59), flat at 100
    except from the given bar on, where the close is the given value until the next given bar."""
    day1 = [100.0] + [101.0] * 119
    day2 = []
    level = base
    for bar in range(120):
        level = day2_by_bar.get(bar, level)
        day2.append(level)
    return pd.concat([day_bars("2024-01-02", day1), day_bars("2024-01-03", day2)])


def held(exposure: pd.Series, day: str = "2024-01-03") -> list[str]:
    """The labels of the bars held, as a first and last bar, or an empty list."""
    sel = exposure.loc[day]
    bars = sel.index[sel != 0]
    return [bars[0].strftime("%H:%M"), bars[-1].strftime("%H:%M")] if len(bars) else []


def exposure_of(bars: pd.DataFrame, **changes: object) -> pd.Series:
    config = IntradayConfig(**{**SMALL.__dict__, **changes})
    return strategy_exposure(bars, config)


# --- the stops ---------------------------------------------------------------------------------

# bars 29, 59 and 89 are 09:29, 09:59 and 10:29, the decision bars of the first hour and a half


def test_the_final_model_goes_flat_unless_beyond_both_the_band_and_the_vwap() -> None:
    # 110 at 09:29, then 104 at 09:59: above the upper band (102.01) but below the VWAP (105.07)
    bars = two_days({29: 110.0, 59: 104.0})

    assert held(exposure_of(bars, stop="vwap_band")) == ["09:30", "09:59"]


def test_the_current_band_stop_ignores_the_vwap() -> None:
    bars = two_days({29: 110.0, 59: 104.0})

    assert held(exposure_of(bars, stop="current_band")) == ["09:30", "10:59"]


def test_the_current_band_stop_goes_flat_when_the_price_is_back_inside_the_band() -> None:
    bars = two_days({29: 103.0, 59: 101.0})  # inside the bands 99 to 102.01 at 09:59

    assert held(exposure_of(bars, stop="current_band")) == ["09:30", "09:59"]


def test_the_opposite_band_stop_holds_until_the_opposite_band_or_the_end_of_the_day() -> None:
    bars = two_days({29: 103.0, 59: 101.0})

    assert held(exposure_of(bars, stop="opposite_band")) == ["09:30", "10:59"]


def test_the_opposite_band_stop_reverses_on_a_breach_of_the_other_band() -> None:
    bars = two_days({29: 103.0, 59: 97.0, 119: 95.0})

    exposure = exposure_of(bars, stop="opposite_band").loc["2024-01-03"]

    assert exposure.iloc[30] == 1.0 and exposure.iloc[59] == 1.0  # long until the 09:59 decision
    assert (exposure.iloc[60:] == -1.0).all()  # short from the bar after it, to the end of the day


def test_the_vwap_only_stop_holds_while_the_price_stays_above_the_vwap() -> None:
    # long on 103 (above 102.01); at 09:59 the price is 102, inside the band but above the VWAP
    # (101.53); at 10:29 it is 100, below the VWAP (101.67), so the position ends there
    bars = two_days({29: 103.0, 59: 102.0, 89: 100.0})

    assert held(exposure_of(bars, stop="vwap_only")) == ["09:30", "10:29"]
    assert held(exposure_of(bars, stop="vwap_band")) == ["09:30", "09:59"]  # for contrast


def test_the_vwap_only_stop_trades_the_short_side_too() -> None:
    bars = two_days({29: 97.0, 59: 98.0, 89: 100.0})  # below 99, still below the VWAP, then above

    exposure = exposure_of(bars, stop="vwap_only").loc["2024-01-03"]

    assert (exposure.iloc[30:90] == -1.0).all()
    assert (exposure.iloc[90:] == 0.0).all()


def test_the_vwap_only_stop_flips_when_it_leaves_and_the_other_band_is_breached() -> None:
    bars = two_days({29: 103.0, 59: 97.0})  # below the VWAP and below the lower band 99

    exposure = exposure_of(bars, stop="vwap_only").loc["2024-01-03"]

    assert exposure.iloc[59] == 1.0
    assert (exposure.iloc[60:] == -1.0).all()


def test_an_unknown_stop_is_refused() -> None:
    with pytest.raises(ValueError, match="stop"):
        IntradayConfig(stop="trailing")


# --- when the stop is checked ------------------------------------------------------------------


def test_the_stop_is_checked_on_the_half_hour_by_default_as_in_the_paper() -> None:
    assert IntradayConfig().stop_check == "grid"
    bars = two_days({29: 103.0, 40: 101.0})  # long on 103, back inside the band at 09:40

    assert held(exposure_of(bars, stop="vwap_band")) == ["09:30", "09:59"]
    assert held(exposure_of(bars, stop="current_band")) == ["09:30", "09:59"]


def test_checked_on_every_bar_the_final_model_leaves_as_soon_as_the_close_fails_the_stop() -> None:
    bars = two_days({29: 103.0, 40: 101.0})

    # held through the 09:40 bar, which closes at 101: out at that close, not at 10:00
    assert held(exposure_of(bars, stop="vwap_band", stop_check="every_bar")) == ["09:30", "09:40"]


def test_checked_on_every_bar_the_current_band_stop_leaves_when_back_inside_the_band() -> None:
    bars = two_days({29: 103.0, 40: 101.0})

    every_bar = exposure_of(bars, stop="current_band", stop_check="every_bar")

    assert held(every_bar) == ["09:30", "09:40"]


def test_checked_on_every_bar_the_opposite_band_leaves_on_the_cross_then_reverses() -> None:
    bars = two_days({29: 103.0, 40: 98.0})  # below the lower band (99) from 09:40

    grid = exposure_of(bars, stop="opposite_band").loc["2024-01-03"]
    every = exposure_of(bars, stop="opposite_band", stop_check="every_bar").loc["2024-01-03"]

    assert (grid.iloc[30:60] == 1.0).all() and (grid.iloc[60:] == -1.0).all()
    assert (every.iloc[30:41] == 1.0).all()  # long through the 09:40 bar
    assert (every.iloc[41:60] == 0.0).all()  # flat until the next decision
    assert (every.iloc[60:] == -1.0).all()  # the reversal still waits for 09:59


def test_checked_on_every_bar_the_vwap_only_stop_leaves_when_the_price_crosses_the_vwap() -> None:
    # long on 103; above the VWAP at 09:59 (102 over 101.5), below it at 10:10 (100 under 101.6)
    bars = two_days({29: 103.0, 59: 102.0, 70: 100.0})

    assert held(exposure_of(bars, stop="vwap_only")) == ["09:30", "10:29"]
    assert held(exposure_of(bars, stop="vwap_only", stop_check="every_bar")) == ["09:30", "10:10"]


def test_entries_stay_on_the_half_hour_even_when_the_stop_is_checked_on_every_bar() -> None:
    bars = two_days({35: 103.0})  # breaks out at 09:35, which is not a decision bar

    for stop_check in ("grid", "every_bar"):
        exposure = exposure_of(bars, stop="vwap_band", stop_check=stop_check)
        assert held(exposure) == ["10:00", "10:59"]


def test_an_unknown_stop_check_is_refused() -> None:
    with pytest.raises(ValueError, match="stop_check"):
        IntradayConfig(stop_check="always")


# --- long and short legs, leverage ---------------------------------------------------------------


def test_a_long_only_run_never_goes_short_and_a_short_only_run_never_goes_long() -> None:
    up = two_days({29: 110.0})
    down = two_days({29: 90.0})

    assert held(exposure_of(up, sides="long")) != []
    assert held(exposure_of(up, sides="short")) == []
    assert held(exposure_of(down, sides="short")) != []
    assert held(exposure_of(down, sides="long")) == []


def test_the_two_legs_add_up_to_the_combined_exposure() -> None:
    bars = two_days({29: 103.0, 59: 97.0, 119: 95.0})

    both = exposure_of(bars, stop="opposite_band", sides="both")
    long = exposure_of(bars, stop="opposite_band", sides="long")
    short = exposure_of(bars, stop="opposite_band", sides="short")

    assert (long + short).equals(both)


def test_an_unknown_side_is_refused() -> None:
    with pytest.raises(ValueError, match="sides"):
        IntradayConfig(sides="neither")


def test_a_fixed_leverage_replaces_the_volatility_target() -> None:
    full = IntradayConfig(leverage=1.0)

    # R$ 100,000 over a contract of R$ 20,000 is 5 contracts at 1x, whatever the volatility
    assert contracts_for(100_000.0, 100_000.0, 0.001, full) == 5
    assert contracts_for(100_000.0, 100_000.0, 0.05, full) == 5
    assert contracts_for(100_000.0, 100_000.0, float("nan"), full) == 5


# --- trade list --------------------------------------------------------------------------------


def test_a_trade_runs_from_the_decision_close_to_the_last_held_close() -> None:
    bars = two_days({29: 110.0, 59: 104.0})
    config = IntradayConfig(**{**SMALL.__dict__, "fee_per_side": 0.25})
    result = run_intraday_momentum(bars, config)

    trades = trade_list(bars, config, result)

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["side"] == 1
    assert trade["entry_time"] == pd.Timestamp("2024-01-03 09:30")  # the close of the 09:29 bar
    assert trade["exit_time"] == pd.Timestamp("2024-01-03 10:00")  # the close of the 09:59 bar
    assert (trade["entry_price"], trade["exit_price"]) == (110.0, 104.0)
    assert trade["points"] == -6.0
    assert trade["contracts"] == 10
    assert trade["gross"] == pytest.approx(-60.0)
    assert trade["cost"] == pytest.approx(5.0)  # 10 contracts, two sides at 0.25
    assert trade["net"] == pytest.approx(-65.0)


def test_a_reversal_is_two_trades_at_the_same_price() -> None:
    bars = two_days({29: 103.0, 59: 97.0, 119: 95.0})
    config = IntradayConfig(**{**SMALL.__dict__, "stop": "opposite_band"})
    result = run_intraday_momentum(bars, config)

    trades = trade_list(bars, config, result)

    assert list(trades["side"]) == [1, -1]
    assert trades["exit_price"].iloc[0] == trades["entry_price"].iloc[1] == 97.0
    assert list(trades["points"]) == [-6.0, 2.0]


def test_the_trades_add_up_to_the_backtest_days_and_sides() -> None:
    rng = np.random.default_rng(3)
    frames = []
    for day in pd.bdate_range("2024-01-02", periods=25):
        closes = 100.0 + np.cumsum(rng.normal(0, 0.2, 120))
        frame = day_bars(day.strftime("%Y-%m-%d"), list(closes))
        frame["volume"] = rng.integers(1, 40, 120).astype(float)
        frames.append(frame)
    bars = pd.concat(frames)
    config = IntradayConfig(**{**SMALL.__dict__, "lookback": 3, "min_days": 2, "fee_per_side": 0.1})
    result = run_intraday_momentum(bars, config)

    trades = trade_list(bars, config, result)

    assert len(trades) > 0
    assert 2 * len(trades) == pytest.approx(result["trades"].sum())
    per_day = trades.groupby(trades["entry_time"].dt.normalize())["net"].sum()
    assert per_day.to_numpy() == pytest.approx(result.loc[per_day.index, "net"].to_numpy())
