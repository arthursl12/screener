"""Noise Area sigma (brief section 10, WINFUT intraday momentum): the time-of-day move band."""

import pandas as pd
import pytest

from b3core.noise_area import noise_sigma

Bar = tuple[str, float, float]  # clock time, open, close


def bars(days: dict[str, list[Bar]]) -> pd.DataFrame:
    rows = [
        (pd.Timestamp(f"{day} {time}"), open_, close)
        for day, items in days.items()
        for time, open_, close in items
    ]
    return pd.DataFrame(rows, columns=["ts", "open", "close"]).set_index("ts")


def day(open_: float, close_0930: float, close_1000: float) -> list[Bar]:
    """Three bars; the day's open is the first bar's open, the moves are measured against it."""
    return [
        ("09:00", open_, open_),
        ("09:30", open_, close_0930),
        ("10:00", open_, close_1000),
    ]


FOUR_DAYS = {
    "2024-01-02": day(100.0, 101.0, 98.0),  # moves 0.01, 0.02
    "2024-01-03": day(200.0, 210.0, 190.0),  # moves 0.05, 0.05
    "2024-01-04": day(50.0, 49.0, 52.0),  # moves 0.02, 0.04
    "2024-01-05": day(80.0, 80.0, 80.0),
}


def at(sigma: pd.Series, stamp: str) -> float:
    return float(sigma[pd.Timestamp(stamp)])


def test_sigma_is_the_mean_move_from_the_open_at_that_time_over_the_previous_days() -> None:
    sigma = noise_sigma(bars(FOUR_DAYS), lookback=2, min_days=2)

    assert at(sigma, "2024-01-04 09:30") == pytest.approx((0.01 + 0.05) / 2)
    assert at(sigma, "2024-01-04 10:00") == pytest.approx((0.02 + 0.05) / 2)
    assert at(sigma, "2024-01-05 09:30") == pytest.approx((0.05 + 0.02) / 2)
    assert at(sigma, "2024-01-05 10:00") == pytest.approx((0.05 + 0.04) / 2)


def test_the_move_is_absolute_so_a_fall_counts_like_a_rise() -> None:
    falling = {
        "2024-01-02": day(100.0, 97.0, 97.0),
        "2024-01-03": day(100.0, 103.0, 103.0),
        "2024-01-04": day(100.0, 100.0, 100.0),
    }

    sigma = noise_sigma(bars(falling), lookback=2, min_days=2)

    assert at(sigma, "2024-01-04 09:30") == pytest.approx(0.03)


def test_there_is_no_sigma_until_enough_previous_days_exist() -> None:
    sigma = noise_sigma(bars(FOUR_DAYS), lookback=2, min_days=2)

    assert sigma[sigma.index.normalize() <= pd.Timestamp("2024-01-03")].isna().all()
    assert sigma[sigma.index.normalize() >= pd.Timestamp("2024-01-04")].notna().all()


def test_nothing_from_the_current_day_reaches_its_sigma() -> None:
    base = noise_sigma(bars(FOUR_DAYS), lookback=2, min_days=2)
    changed_days = dict(FOUR_DAYS)
    changed_days["2024-01-05"] = day(8000.0, 1.0, 99999.0)

    changed = noise_sigma(bars(changed_days), lookback=2, min_days=2)

    today = base.index.normalize() == pd.Timestamp("2024-01-05")
    assert changed[today].equals(base[today])
    assert changed[~today].equals(base[~today])


def test_a_days_move_does_feed_the_sigma_of_the_following_days() -> None:
    longer = {**FOUR_DAYS, "2024-01-08": day(80.0, 80.0, 80.0)}
    base = noise_sigma(bars(longer), lookback=2, min_days=2)
    changed_days = dict(longer)
    changed_days["2024-01-05"] = day(80.0, 88.0, 72.0)

    changed = noise_sigma(bars(changed_days), lookback=2, min_days=2)

    assert at(changed, "2024-01-08 09:30") != at(base, "2024-01-08 09:30")


def test_a_missing_bar_pulls_an_older_day_into_the_window_as_in_the_authors_notebook() -> None:
    # the notebook rolls over the last observations of each minute, not over calendar rows
    gappy = {"2023-12-29": day(100.0, 110.0, 100.0), **FOUR_DAYS}  # moves 0.10 and 0.0
    gappy["2024-01-02"] = [bar for bar in gappy["2024-01-02"] if bar[0] != "09:30"]

    sigma = noise_sigma(bars(gappy), lookback=3, min_days=2)

    # 09:30 on Jan 5: the last three observations are Dec 29, Jan 3 and Jan 4 (Jan 2 has none)
    assert at(sigma, "2024-01-05 09:30") == pytest.approx((0.10 + 0.05 + 0.02) / 3)
    # 10:00 on Jan 5: Jan 2, 3 and 4
    assert at(sigma, "2024-01-05 10:00") == pytest.approx((0.02 + 0.05 + 0.04) / 3)


def test_fewer_observations_than_min_days_still_average_over_what_exists() -> None:
    gappy = dict(FOUR_DAYS)
    gappy["2024-01-02"] = [bar for bar in gappy["2024-01-02"] if bar[0] != "09:30"]

    sigma = noise_sigma(bars(gappy), lookback=3, min_days=2)

    assert at(sigma, "2024-01-05 09:30") == pytest.approx((0.05 + 0.02) / 2)


def test_too_few_observations_of_that_time_give_no_sigma() -> None:
    gappy = dict(FOUR_DAYS)
    gappy["2024-01-02"] = [bar for bar in gappy["2024-01-02"] if bar[0] != "09:30"]

    sigma = noise_sigma(bars(gappy), lookback=3, min_days=3)

    assert pd.isna(at(sigma, "2024-01-05 09:30"))
    assert at(sigma, "2024-01-05 10:00") == pytest.approx((0.02 + 0.05 + 0.04) / 3)


def test_a_late_open_measures_moves_from_the_first_bar_that_exists() -> None:
    late = {
        "2024-01-02": [("09:03", 100.0, 100.0), ("09:30", 100.0, 102.0)],
        "2024-01-03": [("09:00", 100.0, 100.0), ("09:30", 100.0, 104.0)],
        "2024-01-04": [("09:00", 100.0, 100.0), ("09:30", 100.0, 100.0)],
    }

    sigma = noise_sigma(bars(late), lookback=2, min_days=2)

    assert at(sigma, "2024-01-04 09:30") == pytest.approx((0.02 + 0.04) / 2)
    assert pd.isna(at(sigma, "2024-01-04 09:00"))  # only one previous day has a 09:00 bar


def test_the_defaults_are_the_papers_fourteen_days_with_at_least_thirteen() -> None:
    days = {
        f"2024-01-{d:02d}": day(100.0, 101.0, 99.0) for d in range(1, 31) if d % 7 not in (0, 6)
    }
    frame = bars(days)

    sigma = noise_sigma(frame)

    first_valid = sigma.dropna().index[0]
    assert first_valid.normalize() == pd.Timestamp(sorted(days)[13])  # 13 days exist before it
    assert at(sigma, first_valid.strftime("%Y-%m-%d") + " 09:30") == pytest.approx(0.01)


def test_unsorted_or_duplicated_timestamps_are_refused() -> None:
    frame = bars(FOUR_DAYS)

    with pytest.raises(ValueError, match="sorted"):
        noise_sigma(frame.iloc[::-1], lookback=2, min_days=2)
    with pytest.raises(ValueError, match="unique"):
        noise_sigma(pd.concat([frame, frame.iloc[:1]]).sort_index(), lookback=2, min_days=2)


def test_the_window_settings_must_make_sense() -> None:
    with pytest.raises(ValueError, match="min_days"):
        noise_sigma(bars(FOUR_DAYS), lookback=2, min_days=3)
    with pytest.raises(ValueError, match="lookback"):
        noise_sigma(bars(FOUR_DAYS), lookback=0, min_days=1)
