"""Intraday momentum on WINFUT (brief section 10): volatility target, sizing, daily backtest."""

import math

import numpy as np
import pandas as pd
import pytest

from b3core.intraday_momentum import (
    IntradayConfig,
    contracts_for,
    daily_volatility,
    drawdown_summary,
    intraday_equity,
    performance,
    run_intraday_momentum,
    trade_list,
)

NAN = float("nan")


# --- daily volatility --------------------------------------------------------------------------


def closes_from_returns(returns: list[float]) -> pd.Series:
    """Daily closes whose first return is missing, then the given returns."""
    levels = [100.0]
    for r in returns:
        levels.append(levels[-1] * (1 + r))
    return pd.Series(levels, index=pd.bdate_range("2024-01-01", periods=len(levels)))


def test_the_volatility_is_the_sample_deviation_of_the_14_returns_before_the_previous_day() -> None:
    # returns alternate +1% and -1%; the notebook's window for day d is returns d-15 .. d-2
    closes = closes_from_returns([0.01, -0.01] * 12)

    vol = daily_volatility(closes)

    expected = 0.01 * math.sqrt(14 / 13)  # seven of each, mean zero, n - 1 in the divisor
    assert vol.iloc[16] == pytest.approx(expected)


def test_the_first_valid_volatility_is_on_day_16_because_day_zero_has_no_return() -> None:
    vol = daily_volatility(closes_from_returns([0.01, -0.01] * 12))

    assert vol.iloc[:16].isna().all()  # day 15's window still holds the missing first return
    assert vol.iloc[16:].notna().all()


def test_the_previous_day_is_left_out_of_the_window_as_in_the_notebook() -> None:
    quiet = [0.001, -0.001] * 12
    shock = quiet.copy()
    shock[19] = 0.20  # the return of day 20

    base = daily_volatility(closes_from_returns(quiet))
    shocked = daily_volatility(closes_from_returns(shock))

    assert shocked.iloc[21] == pytest.approx(base.iloc[21])  # day 21 leaves out day 20's return
    assert shocked.iloc[22] != pytest.approx(base.iloc[22])  # day 22 is the first to see it


# --- sizing ------------------------------------------------------------------------------------

CONFIG = IntradayConfig()  # R$ 100,000, 2% target, leverage cap 4, R$ 0.20 a point


def test_contracts_follow_the_volatility_target() -> None:
    # R$ 100,000 against a contract worth 100,000 x 0.20 = R$ 20,000; target 2% over 1% is 2x
    assert contracts_for(100_000.0, 100_000.0, 0.01, CONFIG) == 10


def test_leverage_is_capped_and_a_missing_volatility_uses_the_cap() -> None:
    assert contracts_for(100_000.0, 100_000.0, 0.002, CONFIG) == 20  # 10x asked, 4x allowed
    assert contracts_for(100_000.0, 100_000.0, NAN, CONFIG) == 20  # the notebook's warm-up
    assert contracts_for(100_000.0, 100_000.0, 0.0, CONFIG) == 20  # no division by zero


def test_contracts_are_whole_numbers_rounded_like_the_notebook() -> None:
    assert contracts_for(100_000.0, 100_000.0, 0.04, CONFIG) == 2  # 0.5x of 5 contracts is 2.5
    assert isinstance(contracts_for(100_000.0, 100_000.0, 0.01, CONFIG), int)


def test_a_fixed_number_of_contracts_ignores_equity_price_and_volatility() -> None:
    one = IntradayConfig(fixed_contracts=1)

    assert contracts_for(100_000.0, 100_000.0, 0.01, one) == 1
    assert contracts_for(500_000.0, 90_000.0, 0.001, one) == 1
    assert contracts_for(100_000.0, 100_000.0, NAN, one) == 1
    assert contracts_for(100_000.0, 100_000.0, 0.01, IntradayConfig(fixed_contracts=3)) == 3


def test_the_margin_limits_the_contracts_to_what_the_equity_can_carry() -> None:
    # R$ 1,000 of margin a contract: R$ 5,000 of equity carries 5 contracts. The leverage cap of 4
    # never gets near this on its own (it asks for 1), so a loose cap of 40 asks for 10.
    loose = IntradayConfig(max_leverage=40.0)

    assert contracts_for(5_000.0, 100_000.0, NAN, loose) == 5
    assert contracts_for(999.0, 100_000.0, NAN, loose) == 0
    assert contracts_for(2_500.0, 100_000.0, NAN, IntradayConfig(fixed_contracts=3)) == 2


def test_the_margin_does_not_bind_with_the_default_account() -> None:
    # R$ 100,000 carries 100 contracts and the leverage cap allows 20
    assert contracts_for(100_000.0, 100_000.0, 0.002, CONFIG) == 20


def test_a_margin_of_zero_switches_the_limit_off() -> None:
    no_margin = IntradayConfig(margin_per_contract=0.0, max_leverage=40.0)

    assert contracts_for(5_000.0, 100_000.0, NAN, no_margin) == 10


# --- backtest ----------------------------------------------------------------------------------

SMALL = IntradayConfig(
    lookback=1,
    min_days=1,
    capital=1000.0,
    max_leverage=1.0,
    point_value=1.0,
    fee_per_side=0.0,
    margin_per_contract=0.0,  # a R$ 1,000 account could not margin the ten contracts used below
)


def day_bars(day: str, closes: list[float]) -> pd.DataFrame:
    index = pd.date_range(f"{day} 09:00", periods=len(closes), freq="min")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": 1.0},
        index=index,
    )


FLAT = [100.0] * 60


def rising_day() -> list[float]:
    """Flat, then 101 at the 09:29 bar, 102 until 09:58, and 103 on the last bar (09:59)."""
    return [100.0] * 29 + [101.0] + [102.0] * 29 + [103.0]


def falling_day() -> list[float]:
    return [100.0] * 29 + [99.0] + [98.0] * 29 + [97.0]


def test_a_breakout_earns_from_the_decision_close_to_the_last_bar() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", rising_day())])

    result = run_intraday_momentum(bars, SMALL)

    day2 = result.loc["2024-01-03"]
    assert day2["contracts"] == 10  # R$ 1,000 over a contract of 100 points at R$ 1
    assert day2["gross"] == pytest.approx(20.0)  # long from 101 to 103 on 10 contracts
    assert day2["trades"] == 2  # in and out
    assert day2["ret"] == pytest.approx(0.02)
    assert day2["aum"] == pytest.approx(1020.0)


def test_a_breakdown_is_traded_short() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", falling_day())])

    day2 = run_intraday_momentum(bars, SMALL).loc["2024-01-03"]

    assert day2["gross"] == pytest.approx(20.0)  # short from 99 to 97 on 10 contracts
    assert day2["ret"] == pytest.approx(0.02)


def test_the_cost_is_charged_per_contract_and_side() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", rising_day())])
    config = IntradayConfig(**{**SMALL.__dict__, "fee_per_side": 0.25})

    day2 = run_intraday_momentum(bars, config).loc["2024-01-03"]

    assert day2["cost"] == pytest.approx(2 * 10 * 0.25)  # in and out, ten contracts
    assert day2["net"] == pytest.approx(20.0 - 5.0)
    assert day2["aum"] == pytest.approx(1015.0)


def test_the_next_day_is_sized_on_the_new_equity_and_a_quiet_day_earns_nothing() -> None:
    bars = pd.concat(
        [
            day_bars("2024-01-02", FLAT),
            day_bars("2024-01-03", rising_day()),
            day_bars("2024-01-04", FLAT),
        ]
    )

    day3 = run_intraday_momentum(bars, SMALL).loc["2024-01-04"]

    assert day3["contracts"] == 10  # round(1020 / 100) = 10
    assert day3["gross"] == 0.0
    assert day3["ret"] == 0.0
    assert day3["aum"] == pytest.approx(1020.0)


def test_days_before_there_is_a_sigma_do_not_trade_and_keep_the_capital() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", rising_day())])

    result = run_intraday_momentum(bars, SMALL)

    first = result.loc["2024-01-02"]
    assert math.isnan(first["ret"])
    assert first["aum"] == 1000.0


def test_the_exit_time_ends_the_position_early() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", rising_day())])
    config = IntradayConfig(**{**SMALL.__dict__, "exit_minute": 9 * 60 + 45})

    day2 = run_intraday_momentum(bars, config).loc["2024-01-03"]

    assert day2["gross"] == pytest.approx(10.0)  # out at the 09:44 close, 102 - 101 on 10 contracts


# --- performance -------------------------------------------------------------------------------


def test_performance_follows_the_notebooks_statistics() -> None:
    returns = pd.Series([0.10, -0.05, 0.02, NAN])

    stats = performance(returns)

    clean = np.array([0.10, -0.05, 0.02])
    assert stats["total_return"] == pytest.approx(1.10 * 0.95 * 1.02 - 1)
    assert stats["annualized_return"] == pytest.approx((1.10 * 0.95 * 1.02) ** (252 / 3) - 1)
    assert stats["annualized_vol"] == pytest.approx(clean.std(ddof=1) * math.sqrt(252))
    assert stats["sharpe"] == pytest.approx(clean.mean() / clean.std(ddof=1) * math.sqrt(252))
    assert stats["hit_ratio"] == pytest.approx(2 / 3)
    assert stats["max_drawdown"] == pytest.approx(0.05)  # from 1.10 down to 1.045
    assert stats["t_stat"] == pytest.approx(clean.mean() / (clean.std(ddof=1) / math.sqrt(3)))
    assert stats["days"] == 3


def test_a_flat_day_is_not_a_miss_in_the_hit_ratio() -> None:
    stats = performance(pd.Series([0.01, 0.0, -0.01, 0.0]))

    assert stats["hit_ratio"] == pytest.approx(0.5)  # one winner out of two days that traded


def test_a_single_contract_version_trades_one_contract_every_day() -> None:
    bars = pd.concat(
        [
            day_bars("2024-01-02", FLAT),
            day_bars("2024-01-03", rising_day()),
            day_bars("2024-01-04", rising_day()),
        ]
    )
    config = IntradayConfig(**{**SMALL.__dict__, "fixed_contracts": 1})

    result = run_intraday_momentum(bars, config)

    traded = result[result["ret"].notna()]
    assert list(traded["contracts"]) == [1, 1]
    assert traded["gross"].iloc[0] == pytest.approx(2.0)  # 101 to 103, one contract at R$ 1 a point


def test_the_margin_used_is_reported_each_day() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", rising_day())])
    config = IntradayConfig(**{**SMALL.__dict__, "margin_per_contract": 20.0})

    day2 = run_intraday_momentum(bars, config).loc["2024-01-03"]

    assert day2["margin"] == pytest.approx(10 * 20.0)  # ten contracts at R$ 20 each


# --- intraday equity and drawdowns -------------------------------------------------------------

WITH_FEE = IntradayConfig(**{**SMALL.__dict__, "fee_per_side": 0.25})


def three_days() -> pd.DataFrame:
    return pd.concat(
        [
            day_bars("2024-01-02", FLAT),
            day_bars("2024-01-03", rising_day()),
            day_bars("2024-01-04", FLAT),
        ]
    )


def at_time(series: pd.Series, stamp: str) -> float:
    return float(series[pd.Timestamp(stamp)])


def test_the_equity_is_marked_at_every_bar_close_with_the_cost_when_the_side_is_paid() -> None:
    bars = three_days()
    result = run_intraday_momentum(bars, WITH_FEE)

    curve = intraday_equity(bars, WITH_FEE, result)

    equity = curve["equity"]
    assert at_time(equity, "2024-01-03 09:28") == pytest.approx(1000.0)  # nothing held yet
    assert at_time(equity, "2024-01-03 09:29") == pytest.approx(997.5)  # entry cost, 10 x 0.25
    assert at_time(equity, "2024-01-03 09:30") == pytest.approx(1007.5)  # 102 against 101
    assert at_time(equity, "2024-01-03 09:59") == pytest.approx(1015.0)  # 103, less the exit cost


def test_each_days_last_equity_is_the_end_of_day_equity_of_the_backtest() -> None:
    bars = three_days()
    result = run_intraday_momentum(bars, WITH_FEE)

    curve = intraday_equity(bars, WITH_FEE, result)

    last = curve["equity"].groupby(curve.index.normalize()).last()
    assert list(last.index) == list(result.index)
    assert last.to_numpy() == pytest.approx(result["aum"].to_numpy())


def test_the_adverse_equity_takes_the_low_of_a_long_and_the_high_of_a_short() -> None:
    long_bars = three_days()
    long_bars.loc[pd.Timestamp("2024-01-03 09:40"), "low"] = 98.0  # a dip inside a bar, close 102
    short_bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", falling_day())])
    short_bars.loc[pd.Timestamp("2024-01-03 09:40"), "high"] = 106.0  # a spike, close 98

    long_result = run_intraday_momentum(long_bars, WITH_FEE)
    short_result = run_intraday_momentum(short_bars, WITH_FEE)
    long_curve = intraday_equity(long_bars, WITH_FEE, long_result)
    short_curve = intraday_equity(short_bars, WITH_FEE, short_result)

    # long: 10 contracts from 102 down to 98 is -40 against the 1007.5 of the bar before
    assert at_time(long_curve["adverse"], "2024-01-03 09:40") == pytest.approx(1007.5 - 40.0)
    assert at_time(long_curve["equity"], "2024-01-03 09:40") == pytest.approx(1007.5)
    # short: 10 contracts from 98 up to 106 is -80 against the 1007.5 of the bar before
    assert at_time(short_curve["adverse"], "2024-01-03 09:40") == pytest.approx(1007.5 - 80.0)


def test_the_adverse_equity_is_never_above_the_equity_and_equal_when_flat() -> None:
    bars = three_days()
    curve = intraday_equity(bars, WITH_FEE, run_intraday_momentum(bars, WITH_FEE))

    assert (curve["adverse"] <= curve["equity"] + 1e-9).all()
    day1 = curve.loc["2024-01-02"]
    assert (day1["adverse"] == day1["equity"]).all()


def test_the_curve_closes_every_day_at_the_backtest_equity_on_random_bars() -> None:
    rng = np.random.default_rng(7)
    frames = []
    for day in pd.bdate_range("2024-01-02", periods=30):
        closes = 100.0 + np.cumsum(rng.normal(0, 0.15, 120))
        frame = day_bars(day.strftime("%Y-%m-%d"), list(closes))
        frame["high"] = frame["close"] + rng.uniform(0, 0.1, 120)
        frame["low"] = frame["close"] - rng.uniform(0, 0.1, 120)
        frame["volume"] = rng.integers(1, 50, 120).astype(float)
        frames.append(frame)
    bars = pd.concat(frames)
    config = IntradayConfig(**{**SMALL.__dict__, "lookback": 3, "min_days": 2, "fee_per_side": 0.1})

    result = run_intraday_momentum(bars, config)
    curve = intraday_equity(bars, config, result)

    assert (result["contracts"] > 0).any() and (result["trades"] > 0).any()
    last = curve["equity"].groupby(curve.index.normalize()).last()
    assert last.to_numpy() == pytest.approx(result["aum"].to_numpy())
    assert (curve["adverse"] <= curve["equity"] + 1e-9).all()
    assert curve.index.equals(bars.index)


def test_the_drawdown_summary_separates_balance_equity_and_adverse_drawdowns() -> None:
    days = pd.to_datetime(["2024-01-02", "2024-01-03"])
    result = pd.DataFrame(
        {"aum": [1100.0, 1050.0], "net": [100.0, -50.0], "ret": [0.1, -0.045]}, index=days
    )
    index = pd.to_datetime(
        ["2024-01-02 09:00", "2024-01-02 09:01", "2024-01-02 09:02"]
        + ["2024-01-03 09:00", "2024-01-03 09:01", "2024-01-03 09:02"]
    )
    curve = pd.DataFrame(
        {
            "equity": [1000.0, 1150.0, 1100.0, 1100.0, 1000.0, 1050.0],
            "adverse": [980.0, 1120.0, 1090.0, 1050.0, 900.0, 1040.0],
        },
        index=index,
    )

    summary = drawdown_summary(result, curve, capital=1000.0)

    assert summary["balance_drawdown"] == pytest.approx(50.0)  # 1100 to 1050 at the closes
    assert summary["equity_drawdown"] == pytest.approx(150.0)  # 1150 to 1000 on the bar closes
    assert summary["adverse_drawdown"] == pytest.approx(250.0)  # 1150 to the 900 low
    assert summary["worst_day"] == pytest.approx(50.0)  # the end-of-day result
    assert summary["worst_intraday_loss"] == pytest.approx(200.0)  # 1100 at the open to 900


# --- the bridge between the paper's shares and WIN contracts -------------------------------------


def test_the_daily_result_reports_the_exposure_and_the_leverage_it_took() -> None:
    bars = pd.concat([day_bars("2024-01-02", FLAT), day_bars("2024-01-03", rising_day())])

    result = run_intraday_momentum(bars, SMALL)

    day2 = result.loc["2024-01-03"]
    assert day2["exposure"] == pytest.approx(10 * 100.0 * 1.0)  # 10 contracts of 100 points at R$ 1
    assert day2["leverage"] == pytest.approx(1.0)  # R$ 1,000 of exposure on R$ 1,000 of equity
    first = result.loc["2024-01-02"]
    assert first["exposure"] == 0.0 and first["leverage"] == 0.0


def random_days(count: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for day in pd.bdate_range("2024-01-02", periods=count):
        closes = 100.0 + np.cumsum(rng.normal(0, 0.3, 120))
        frame = day_bars(day.strftime("%Y-%m-%d"), list(closes))
        frame["volume"] = rng.integers(1, 40, 120).astype(float)
        frames.append(frame)
    return pd.concat(frames)


def test_the_profit_of_a_day_is_the_leverage_times_the_index_move_on_the_equity() -> None:
    """The same law for shares and for contracts: gain / equity = leverage x (points / open)."""
    bars = random_days(40, 5)
    settings = {**SMALL.__dict__, "lookback": 3, "min_days": 2, "capital": 100_000.0}
    config = IntradayConfig(**settings)
    result = run_intraday_momentum(bars, config)
    trades = trade_list(bars, config, result)

    points = trades.groupby("day")["points"].sum()
    opens = bars["open"].groupby(bars.index.normalize()).first()
    aum_before = result["aum"].shift(1).fillna(config.capital)
    days = points.index
    gain = result.loc[days, "gross"] / aum_before[days]
    law = result.loc[days, "leverage"] * points / opens[days]

    assert len(days) > 5
    assert gain.to_numpy() == pytest.approx(law.to_numpy(), rel=1e-9, abs=1e-12)


def test_the_leverage_taken_is_the_papers_target_up_to_the_rounding_of_whole_contracts() -> None:
    bars = random_days(45, 11)
    config = IntradayConfig(
        **{
            **SMALL.__dict__,
            "lookback": 3,
            "min_days": 2,
            "capital": 100_000.0,
            "target_vol": 0.004,
            "max_leverage": 4.0,
        }
    )
    result = run_intraday_momentum(bars, config)
    daily = daily_volatility(bars["close"].groupby(bars.index.normalize()).last())
    opens = bars["open"].groupby(bars.index.normalize()).first()
    aum_before = result["aum"].shift(1).fillna(config.capital)

    traded = result[result["ret"].notna()]
    assert len(traded) > 20 and daily.notna().sum() > 10
    for day in traded.index:
        vol = daily[day]
        asked = config.max_leverage if np.isnan(vol) else config.target_vol / vol
        target = min(asked, config.max_leverage)
        half_contract = 0.5 * opens[day] * config.point_value / aum_before[day]
        assert abs(traded.loc[day, "leverage"] - target) <= half_contract + 1e-9
