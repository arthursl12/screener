"""Equal-split portfolio of independent slots."""

import math

import numpy as np
import pandas as pd
import pytest

from b3core.benchmark import compare_with_cdi
from b3core.ifr2 import Ifr2Config, run_ifr2
from b3core.portfolio import (
    buy_and_hold_equity,
    combine_equity,
    slot_equity,
    summarize_portfolio,
)

CONFIG = Ifr2Config(atr_period=2, max_risk_brl=100, capital_brl=10_000, lot_size=1)
WORKED = [
    (10.00, 10.10, 9.90, 10.00),
    (10.00, 10.60, 10.00, 10.50),
    (10.50, 10.60, 10.10, 10.20),
    (10.20, 10.30, 9.70, 9.80),
    (9.80, 9.90, 9.40, 9.50),
    (9.60, 10.00, 9.50, 9.90),
    (9.90, 10.10, 9.80, 10.00),
]


def days(n: int, start: str = "2024-01-02") -> pd.DatetimeIndex:
    # midnight in São Paulo is 03:00 UTC
    return pd.bdate_range(start, periods=n).tz_localize("UTC") + pd.Timedelta(hours=3)


def candles(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": days(len(rows)),
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": 1000.0,
        }
    )


def test_slot_equity_is_the_engine_curve_on_the_candle_dates() -> None:
    data = candles(WORKED)
    curve = slot_equity(data, CONFIG)

    assert list(curve.index) == list(data["ts"])
    np.testing.assert_allclose(curve.to_numpy(), run_ifr2(data, CONFIG).equity)
    assert curve.iloc[-1] == pytest.approx(10_000 + 46.50)


def test_combine_sums_slots_and_holds_their_edges() -> None:
    a = pd.Series([100.0, 110.0, 120.0], index=days(3))
    early_end = pd.Series([50.0, 40.0], index=days(2))  # ends before A: holds 40
    late_start = pd.Series([70.0, 80.0], index=days(2, "2024-01-03"))  # starts after A: holds 70

    combined = combine_equity({"A": a, "E": early_end, "L": late_start})

    assert list(combined.index) == list(days(3))
    assert combined.tolist() == [100 + 50 + 70, 110 + 40 + 70, 120 + 40 + 80]


def test_combine_needs_a_slot() -> None:
    with pytest.raises(ValueError, match="at least one slot"):
        combine_equity({})


CDI = pd.Series(0.04, index=pd.bdate_range("2023-12-01", "2024-03-29"))


def curve(values: list[float]) -> pd.Series:
    return pd.Series(values, index=days(len(values)))


def test_summary_cagr_drawdown_calmar_and_the_cdi() -> None:
    equity = curve([110.0, 99.0, 121.0, 121.0, 121.0])  # capital 100, peak 110, trough 99

    s = summarize_portfolio(equity, 100.0, CDI)

    years = (equity.index[-1] - equity.index[0]).days / 365.25
    assert s.years == pytest.approx(years)
    assert s.cagr == pytest.approx(1.21 ** (1 / years) - 1)
    assert s.max_equity_drawdown == pytest.approx(0.10)
    assert s.calmar == pytest.approx(s.cagr / 0.10)
    cdi = compare_with_cdi(s.cagr, years, CDI, pd.DatetimeIndex(equity.index))
    assert (s.cdi_cagr, s.excess, s.beats_cdi) == (cdi.cdi_cagr, cdi.excess, cdi.beats_cdi)


def test_the_drawdown_starts_from_the_capital() -> None:
    # never above the capital: the fall is measured from the capital, not from the first value
    s = summarize_portfolio(curve([90.0, 95.0, 96.0]), 100.0, CDI)

    assert s.max_equity_drawdown == pytest.approx(0.10)


def test_a_total_loss_is_minus_one_and_no_drawdown_gives_inf_or_zero() -> None:
    assert summarize_portfolio(curve([50.0, 0.0, 0.0]), 100.0, CDI).cagr == -1.0
    assert summarize_portfolio(curve([101.0, 102.0, 103.0]), 100.0, CDI).calmar == math.inf
    assert summarize_portfolio(curve([100.0, 100.0, 100.0]), 100.0, CDI).calmar == 0.0


def test_the_curve_needs_a_span() -> None:
    with pytest.raises(ValueError, match="two dates"):
        summarize_portfolio(curve([100.0]), 100.0, CDI)
    same_day = pd.Series([100.0, 101.0], index=pd.DatetimeIndex([days(1)[0]] * 2))
    with pytest.raises(ValueError, match="more than one day"):
        summarize_portfolio(same_day, 100.0, CDI)


# --- buy and hold (docs/ibov.md) -------------------------------------------------------------


def prices(closes_: list[float], start: str = "2024-01-02") -> pd.DataFrame:
    return candles([(c, c, c, c) for c in closes_]).assign(ts=days(len(closes_), start))


def test_buy_and_hold_of_one_ticker_is_the_capital_times_the_close_ratio() -> None:
    curve = buy_and_hold_equity({"A": prices([20.0, 22.0, 18.0, 22.0])}, 1_000.0)

    assert curve.tolist() == pytest.approx([1_000.0, 1_100.0, 900.0, 1_100.0])
    s = summarize_portfolio(curve, 1_000.0, CDI)
    assert s.cagr == pytest.approx(1.1 ** (1 / s.years) - 1)
    assert s.max_equity_drawdown == pytest.approx(200 / 1_100)


def test_equal_weight_buy_and_hold_is_the_mean_of_the_ratios() -> None:
    up = prices([10.0, 12.0])
    down = prices([10.0, 8.0])

    curve = buy_and_hold_equity({"UP": up, "DOWN": down}, 100_000.0)

    assert curve.tolist() == pytest.approx([100_000.0, 100_000.0])  # 50k*1.2 + 50k*0.8


def test_a_ticker_that_starts_later_holds_its_first_value_before_it_starts() -> None:
    early = prices([10.0, 10.0, 20.0])  # Jan 2 to 4
    late = prices([5.0, 10.0], "2024-01-03")  # Jan 3 to 4: doubles

    curve = buy_and_hold_equity({"E": early, "L": late}, 100.0)

    # the late slot holds its 50 until Jan 3 and doubles on Jan 4; the early one doubles on Jan 4
    assert curve.tolist() == pytest.approx([100.0, 100.0, 200.0])


def test_buy_and_hold_needs_a_ticker() -> None:
    with pytest.raises(ValueError, match="at least one"):
        buy_and_hold_equity({}, 100.0)
