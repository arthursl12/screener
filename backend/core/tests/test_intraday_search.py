"""Parameter search for the intraday momentum strategy on WIN and WDO (brief section 10)."""

import math

import numpy as np
import pandas as pd
import pytest

from b3core.intraday_momentum import IntradayConfig, run_intraday_momentum
from b3core.intraday_search import (
    INSTRUMENTS,
    SPACE,
    TrialSet,
    decode,
    encode,
    fold_of,
    leave_one_year_out,
    make_config,
    neighbours,
    run_trial,
    sample_indices,
    scores,
    scramble_bars,
    sharpe_by_trial,
    space_size,
)

# --- the space ---------------------------------------------------------------------------------


def test_the_space_is_the_eight_parameters_the_owner_approved() -> None:
    assert list(SPACE) == [
        "lookback",
        "band_mult",
        "trade_freq",
        "first_decision",
        "exit_minute",
        "stop",
        "stop_check",
        "sides",
    ]
    assert space_size() == 8 * 7 * 3 * 6 * 7 * 4 * 2 * 3 == 169_344


def test_an_index_decodes_to_one_combination_and_encodes_back() -> None:
    for index in (0, 1, 12_345, space_size() - 1):
        params = decode(index)
        assert set(params) == set(SPACE)
        assert all(params[name] in SPACE[name] for name in SPACE)
        assert encode(params) == index
    assert decode(0) == {name: values[0] for name, values in SPACE.items()}
    assert decode(space_size() - 1) == {name: values[-1] for name, values in SPACE.items()}


def test_the_last_parameter_varies_fastest() -> None:
    assert decode(1)["sides"] == SPACE["sides"][1]
    assert decode(1)["lookback"] == SPACE["lookback"][0]


def test_sampling_is_seeded_unique_and_inside_the_space() -> None:
    first = sample_indices(500, seed=7)

    assert first == sample_indices(500, seed=7)
    assert first != sample_indices(500, seed=8)
    assert len(set(first)) == 500
    assert all(0 <= i < space_size() for i in first)


def test_a_neighbour_changes_one_parameter_by_one_step_and_never_wraps() -> None:
    def steps_available(index: int) -> int:
        digits = [list(SPACE[n]).index(decode(index)[n]) for n in SPACE]
        return sum((d > 0) + (d < len(SPACE[n]) - 1) for d, n in zip(digits, SPACE, strict=True))

    first = encode({name: values[0] for name, values in SPACE.items()})
    last = encode({name: values[-1] for name, values in SPACE.items()})
    middle = encode({name: values[len(values) // 2] for name, values in SPACE.items()})

    assert len(neighbours(first)) == len(SPACE)  # only the step up exists on every axis
    assert len(neighbours(last)) == len(SPACE)  # only the step down
    assert len(neighbours(middle)) == steps_available(middle)
    for index in neighbours(middle):
        moved = [n for n in SPACE if decode(index)[n] != decode(middle)[n]]
        assert len(moved) == 1
        name = moved[0]
        before = SPACE[name].index(decode(middle)[name])
        after = SPACE[name].index(decode(index)[name])
        assert abs(after - before) == 1


# --- configurations ----------------------------------------------------------------------------


def test_each_instrument_has_its_own_point_value_and_costs() -> None:
    win, wdo = INSTRUMENTS["WIN"], INSTRUMENTS["WDO"]

    assert (win.point_value, win.fee_per_side, win.tick_reais) == (0.20, 0.25, 1.00)
    assert (wdo.point_value, wdo.fee_per_side, wdo.tick_reais) == (10.0, 1.20, 5.00)


def test_a_configuration_carries_the_fee_the_slippage_and_the_fixed_parameters() -> None:
    params = decode(0) | {"lookback": 20, "exit_minute": 1100}

    win = make_config(params, "WIN", slippage_ticks=1.0)
    wdo = make_config(params, "WDO", slippage_ticks=1.0)
    plain = make_config(params, "WIN", slippage_ticks=0.0)

    assert win.fee_per_side == pytest.approx(0.25 + 1.00)
    assert wdo.fee_per_side == pytest.approx(1.20 + 5.00)
    assert plain.fee_per_side == pytest.approx(0.25)
    assert (win.point_value, wdo.point_value) == (0.20, 10.0)
    assert (win.lookback, win.min_days) == (20, 19)
    assert win.exit_minute == 1100
    assert (win.target_vol, win.max_leverage) == (0.02, 4.0)  # fixed at the paper's values
    assert (win.capital, win.margin_per_contract) == (100_000.0, 1_000.0)
    assert win.fixed_contracts is None and win.leverage is None


def test_the_end_of_the_session_is_a_value_of_the_exit() -> None:
    assert SPACE["exit_minute"][-1] == 24 * 60  # no exit time: the last bar of the session


# --- sharpe and scores -------------------------------------------------------------------------


def test_the_sharpe_ratio_follows_the_notebook_with_n_minus_one() -> None:
    r = np.array([[0.01, -0.01, 0.02, 0.0]])
    expected = r[0].mean() / r[0].std(ddof=1) * math.sqrt(252)

    assert sharpe_by_trial(r, np.ones(4, dtype=bool))[0] == pytest.approx(expected)


def test_a_flat_trial_has_no_sharpe_and_days_outside_the_mask_do_not_count() -> None:
    r = np.array([[0.0, 0.0, 0.0], [0.01, 0.50, -0.01]])

    out = sharpe_by_trial(r, np.array([True, False, True]))

    assert math.isnan(out[0])
    assert out[1] == pytest.approx(0.0)  # 0.01 and -0.01 only: the 0.50 day is masked out


def days_for_folds() -> pd.DatetimeIndex:
    return pd.to_datetime(
        ["2021-12-30", "2022-06-01", "2023-03-01", "2023-09-01", "2024-03-01", "2024-09-02"]
    )


def test_each_day_belongs_to_a_calendar_year_fold_and_december_2021_joins_2022() -> None:
    assert list(fold_of(days_for_folds())) == [2022, 2022, 2023, 2023, 2024, 2024]


def make_set(win: list[list[float]], wdo: list[list[float]], sides: float = 400.0) -> TrialSet:
    count = len(win)
    ones = np.full((count, 6), sides / 6)
    return TrialSet(
        indices=np.arange(count),
        days=days_for_folds(),
        ret={"WIN": np.array(win, dtype=float), "WDO": np.array(wdo, dtype=float)},
        sides={"WIN": ones, "WDO": ones},
    )


def test_missing_days_count_as_flat_days_in_the_scores() -> None:
    nan = float("nan")
    trials = make_set([[nan, 0.01, 0.02, -0.01, 0.01, 0.0]], [[0.01, 0.01, 0.02, -0.01, 0.01, 0.0]])
    everything = np.ones(6, dtype=bool)

    filled = np.array([[0.0, 0.01, 0.02, -0.01, 0.01, 0.0]])
    expected = sharpe_by_trial(filled, everything)[0]

    assert scores(trials, everything, "WIN", min_trades=0)[0] == pytest.approx(expected)


def test_the_joint_score_is_the_worse_of_the_two_instruments() -> None:
    win = [[0.02, -0.01, 0.03, -0.01, 0.02, 0.01]]
    wdo = [[0.01, -0.02, 0.0, 0.01, -0.01, 0.0]]
    trials = make_set(win, wdo)
    everything = np.ones(6, dtype=bool)

    s_win = scores(trials, everything, "WIN", min_trades=0)[0]
    s_wdo = scores(trials, everything, "WDO", min_trades=0)[0]

    assert scores(trials, everything, "joint", min_trades=0)[0] == pytest.approx(min(s_win, s_wdo))
    assert s_win != pytest.approx(s_wdo)


def test_a_trial_with_too_few_trades_gets_no_score() -> None:
    returns = [[0.01, 0.02, -0.01, 0.01, 0.02, 0.0]]
    busy = make_set(returns, returns, sides=400.0)  # 400 sides = 200 round trips
    quiet = make_set(returns, returns, sides=100.0)
    everything = np.ones(6, dtype=bool)

    assert not math.isnan(scores(busy, everything, "WIN", min_trades=200)[0])
    assert math.isnan(scores(quiet, everything, "WIN", min_trades=200)[0])
    assert math.isnan(scores(quiet, everything, "joint", min_trades=200)[0])


# --- leave one year out ------------------------------------------------------------------------


def test_leave_one_year_out_picks_on_the_other_years_and_scores_on_the_held_out_one() -> None:
    # trial 0 is great in 2022 and 2023 and terrible in 2024; trial 1 is mediocre everywhere
    great_then_bad = [0.03, 0.02, 0.03, 0.02, -0.04, -0.03]
    steady = [0.004, 0.002, -0.001, 0.003, 0.002, -0.001]
    trials = make_set([great_then_bad, steady], [great_then_bad, steady])

    table = leave_one_year_out(trials, "WIN", min_trades=0).set_index("held out")

    assert table.loc[2024, "winner"] == 0  # chosen on 2022 and 2023, where trial 0 shines
    assert table.loc[2024, "test"] < 0  # and it loses in 2024
    assert table.loc[2022, "winner"] == 1  # on 2023 and 2024 trial 0 is the worse one
    assert table.loc[2022, "train"] > 0
    assert set(table.index) == {2022, 2023, 2024}


def test_the_held_out_year_never_enters_its_own_selection() -> None:
    tie_breaker = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01]
    lucky_in_2024 = [0.0, 0.0, 0.0, 0.0, 0.50, 0.40]
    trials = make_set([tie_breaker, lucky_in_2024], [tie_breaker, lucky_in_2024])

    table = leave_one_year_out(trials, "WIN", min_trades=0).set_index("held out")

    # trial 1 would win on the whole period, but never when 2024 is the year held out
    assert table.loc[2024, "winner"] != 1 or table.loc[2024, "train"] <= 0


# --- the luck baseline -------------------------------------------------------------------------


def synthetic_days(count: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for day in pd.bdate_range("2024-01-02", periods=count):
        index = pd.date_range(f"{day:%Y-%m-%d} 09:00", periods=60, freq="min")
        close = 100.0 + np.cumsum(rng.normal(0, 0.2, 60))
        previous = np.concatenate(([close[0]], close[:-1]))
        frames.append(
            pd.DataFrame(
                {
                    "open": previous,
                    "high": np.maximum(previous, close) + rng.uniform(0, 0.1, 60),
                    "low": np.minimum(previous, close) - rng.uniform(0, 0.1, 60),
                    "close": close,
                    "volume": rng.integers(1, 50, 60).astype(float),
                },
                index=index,
            )
        )
    return pd.concat(frames)


def test_scrambling_is_seeded_and_changes_the_path() -> None:
    bars = synthetic_days(5, 1)

    one = scramble_bars(bars, seed=3)

    assert one.equals(scramble_bars(bars, seed=3))
    assert not one.equals(scramble_bars(bars, seed=4))
    assert not one["close"].equals(bars["close"])


def test_scrambling_keeps_each_days_open_close_volume_and_bar_shape() -> None:
    bars = synthetic_days(6, 2)

    scrambled = scramble_bars(bars, seed=5)

    day = bars.index.normalize()
    assert scrambled.index.equals(bars.index)
    assert scrambled["volume"].equals(bars["volume"])
    assert scrambled["open"].groupby(day).first().equals(bars["open"].groupby(day).first())
    assert scrambled["close"].groupby(day).last().to_numpy() == pytest.approx(
        bars["close"].groupby(day).last().to_numpy()
    )
    assert (scrambled["high"] >= scrambled[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (scrambled["low"] <= scrambled[["open", "close"]].min(axis=1) + 1e-9).all()


def test_scrambling_keeps_the_set_of_moves_of_a_day_and_only_reorders_them() -> None:
    bars = synthetic_days(4, 3)
    scrambled = scramble_bars(bars, seed=9)
    day = bars.index.normalize()

    def moves(frame: pd.DataFrame) -> np.ndarray:
        step = frame["close"].groupby(day).diff().fillna(frame["close"] - frame["open"])
        return np.sort(step[day == day[0]].to_numpy())

    assert moves(scrambled) == pytest.approx(moves(bars))
    assert not np.allclose(scrambled["close"].to_numpy(), bars["close"].to_numpy())


# --- running a trial ---------------------------------------------------------------------------


def test_a_trial_gives_the_daily_returns_and_sides_of_each_instrument_on_a_common_index() -> None:
    win = synthetic_days(30, 11)
    wdo = synthetic_days(30, 12)
    days = pd.DatetimeIndex(win.index.normalize().unique())
    params = decode(0) | {"lookback": 5, "exit_minute": 24 * 60, "first_decision": 540}

    returns, sides = run_trial({"WIN": win, "WDO": wdo}, params, days, slippage_ticks=1.0)

    assert set(returns) == set(sides) == {"WIN", "WDO"}
    assert returns["WIN"].shape == sides["WIN"].shape == (30,)
    direct = run_intraday_momentum(win, make_config(params, "WIN", slippage_ticks=1.0))
    assert np.allclose(returns["WIN"], direct["ret"].to_numpy(), equal_nan=True)
    assert np.allclose(sides["WIN"], direct["trades"].to_numpy())
    again, _ = run_trial({"WIN": win, "WDO": wdo}, params, days, slippage_ticks=1.0)
    assert np.allclose(again["WDO"], returns["WDO"], equal_nan=True)
    assert isinstance(make_config(params, "WDO", slippage_ticks=1.0), IntradayConfig)
