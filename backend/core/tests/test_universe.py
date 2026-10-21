"""Scan one IFR2 config over many tickers (layer A of the universe notebook)."""

import pandas as pd
import pytest

from b3core.benchmark import compare_with_cdi, compare_with_index
from b3core.ifr2 import Ifr2Config, run_ifr2
from b3core.score import score_v1
from b3core.turtle import TurtleConfig, run_turtle
from b3core.universe import scan_universe

WORKED = [  # the worked example of brief section 7: one trade, +R$ 46.50
    (10.00, 10.10, 9.90, 10.00),
    (10.00, 10.60, 10.00, 10.50),
    (10.50, 10.60, 10.10, 10.20),
    (10.20, 10.30, 9.70, 9.80),
    (9.80, 9.90, 9.40, 9.50),
    (9.60, 10.00, 9.50, 9.90),
    (9.90, 10.10, 9.80, 10.00),
]
CONFIG = Ifr2Config(atr_period=2, max_risk_brl=100, capital_brl=10_000, lot_size=1)


def candles(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    # midnight in São Paulo is 03:00 UTC
    ts = pd.bdate_range("2024-01-02", periods=len(rows)).tz_localize("UTC") + pd.Timedelta(hours=3)
    return pd.DataFrame(
        {
            "ts": ts,
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": 1000.0,
        }
    )


RISING = [(10.0 + i, 10.5 + i, 9.5 + i, 10.2 + i) for i in range(7)]  # never oversold: no trade
DATA = {"WORK3": candles(WORKED), "UP3": candles(RISING)}
CDI = pd.Series(0.04, index=pd.bdate_range("2023-12-01", "2024-02-29"))


def scan(data=DATA, config=CONFIG, cdi=CDI, **kwargs):  # type: ignore[no-untyped-def]
    return scan_universe(data, config, cdi, **{"min_candles": 1, **kwargs})


def test_one_row_per_ticker_with_the_metrics_and_the_cdi_comparison() -> None:
    table = scan()

    assert list(table.index) == ["WORK3", "UP3"]
    work = table.loc["WORK3"]
    direct = run_ifr2(DATA["WORK3"], CONFIG)
    assert work["n_trades"] == 1
    assert work["result"] == pytest.approx(46.50 / 10_000)
    assert work["cagr"] == pytest.approx(direct.metrics.cagr)
    assert work["max_equity_drawdown"] == pytest.approx(direct.metrics.max_equity_drawdown)
    assert work["score_v1"] == pytest.approx(score_v1(direct.metrics))
    assert direct.metrics.cagr is not None and direct.years is not None
    expected = compare_with_cdi(direct.metrics.cagr, direct.years, CDI, DATA["WORK3"]["ts"])
    assert work["cdi_cagr"] == pytest.approx(expected.cdi_cagr)
    assert work["excess"] == pytest.approx(expected.excess)
    assert bool(work["beats_cdi"]) is expected.beats_cdi
    assert work["years"] == pytest.approx(direct.years)


def test_a_ticker_without_trades_loses_to_the_cdi() -> None:
    row = scan().loc["UP3"]

    assert row["n_trades"] == 0
    assert row["cagr"] == 0
    assert bool(row["beats_cdi"]) is False


def test_tickers_with_too_little_history_are_skipped_and_named() -> None:
    table = scan(min_candles=7)  # both have exactly 7
    assert len(table) == 2

    short = scan({**DATA, "NEW3": candles(WORKED[:4])}, min_candles=7)

    assert list(short.index) == ["WORK3", "UP3"]
    assert short.attrs["skipped"] == ["NEW3"]


def test_the_config_is_applied_to_every_ticker() -> None:
    zero_cost = scan().loc["WORK3", "net_pnl"]
    costly = scan(config=Ifr2Config(**{**CONFIG.to_dict(), "cost_pct": 1.0}))

    assert costly.loc["WORK3", "net_pnl"] < zero_cost


def test_a_missing_cdi_day_is_an_error() -> None:
    gap = CDI.drop(pd.Timestamp("2024-01-04"))

    with pytest.raises(ValueError, match="2024-01-04"):
        scan(cdi=gap)


# --- the benchmarks next to the CDI (docs/ibov.md) --------------------------------------------

INDEX = pd.Series(
    [100.0, 98.0, 103.0, 101.0, 99.0, 105.0, 110.0], index=pd.bdate_range("2024-01-02", periods=7)
)


def test_every_ticker_is_compared_with_buying_and_holding_it() -> None:
    table = scan()

    work, up = table.loc["WORK3"], table.loc["UP3"]
    assert work["bh_cagr"] == pytest.approx(0.0)  # the worked example starts and ends at 10.00
    assert work["bh_excess"] == pytest.approx(work["cagr"])
    assert bool(work["beats_bh"]) is True  # +R$ 46.50 against holding flat
    years = work["years"]
    assert up["bh_cagr"] == pytest.approx((16.2 / 10.2) ** (1 / years) - 1)
    assert up["bh_max_equity_drawdown"] == 0.0  # it never fell
    assert bool(up["beats_bh"]) is False  # no trades against a rising stock


def flat_candles(closes: list[float]) -> pd.DataFrame:
    return candles([(c, c, c, c) for c in closes])


def test_a_tie_with_buy_and_hold_is_not_a_win() -> None:
    row = scan({"FLAT3": flat_candles([10.0] * 7)}).loc["FLAT3"]  # no trades, price unchanged

    assert row["cagr"] == 0 and row["bh_cagr"] == 0
    assert bool(row["beats_bh"]) is False


def test_the_buy_and_hold_calmar_is_its_cagr_over_its_drawdown() -> None:
    row = scan({"DIP3": flat_candles([10.0, 12.0, 9.0, 13.0, 13.0, 13.0, 13.0])}).loc["DIP3"]

    assert row["bh_max_equity_drawdown"] == pytest.approx(3 / 12)
    assert row["bh_calmar"] == pytest.approx(row["bh_cagr"] / 0.25)
    assert row["bh_calmar"] > 0


def test_the_buy_and_hold_drawdown_is_the_falling_part_of_the_close() -> None:
    table = scan()

    # WORK3 closes 10.0, 10.5, 10.2, 9.8, 9.5, 9.9, 10.0 on a capital of 10_000:
    # the peak is the capital's 10.5/10.0 = 10_500 and the trough 9_500, a fall of 1_000/10_500
    assert table.loc["WORK3", "bh_max_equity_drawdown"] == pytest.approx(1_000 / 10_500)


def test_the_index_columns_appear_only_when_the_index_is_given() -> None:
    assert not any(c.startswith("ibov") for c in scan().columns)

    row = scan(index_closes=INDEX).loc["WORK3"]

    direct = run_ifr2(DATA["WORK3"], CONFIG)
    assert direct.metrics.cagr is not None and direct.years is not None
    expected = compare_with_index(direct.metrics.cagr, direct.years, INDEX, DATA["WORK3"]["ts"])
    assert row["ibov_cagr"] == pytest.approx(expected.cagr)
    assert row["ibov_excess"] == pytest.approx(expected.excess)
    assert expected.beats is False  # the index rose 10% in a week: the strategy made 0.47%
    assert bool(row["beats_ibov"]) is expected.beats
    # the index held with the capital: 10_000, 9_800, 10_300, 10_100, 9_900, 10_500, 11_000
    assert row["ibov_max_equity_drawdown"] == pytest.approx(400 / 10_300)


# --- ranking combinations across tickers -------------------------------------------------------


def trials(rows: list[tuple[float, str, float, float, int]]) -> pd.DataFrame:
    """(rsi_entry, exit_mode, objective, result, n_trades), the columns of `trials_table`."""
    return pd.DataFrame(
        rows, columns=["rsi_entry", "exit_mode", "objective", "result", "n_trades"]
    ).assign(max_days=None)


def test_combinations_are_ranked_by_how_they_do_across_tickers() -> None:
    from b3core.universe import rank_across_tickers

    tables = {
        "AAA3": trials([(10, "target", 60, 0.30, 50), (20, "target", 40, 0.10, 60),
                        (30, "rsi", 20, -0.05, 30)]),
        "BBB3": trials([(10, "target", 30, -0.02, 55), (20, "target", 50, 0.0, 65)]),
        "CCC3": trials([(10, "target", 120, 0.50, 80), (20, "target", 10, 0.01, 10)]),
    }  # fmt: skip
    params = ["rsi_entry", "exit_mode", "max_days"]

    ranked = rank_across_tickers(tables, params, min_trades=30)

    # (20, target) on CCC3 has 10 trades: below the gate, so only two tickers count for it
    first, second, third = ranked.iloc[0], ranked.iloc[1], ranked.iloc[2]
    assert (first["rsi_entry"], first["exit_mode"]) == (10, "target")
    assert first["n_tickers"] == 3
    assert first["median_objective"] == 60  # median of 60, 30, 120 (the mean would be 70)
    assert first["pos_share"] == pytest.approx(2 / 3)  # BBB3 lost money
    assert first["worst_result"] == pytest.approx(-0.02)
    assert (second["rsi_entry"], second["exit_mode"]) == (20, "target")
    assert second["n_tickers"] == 2
    assert second["median_objective"] == 45  # median of 40 and 50
    assert second["pos_share"] == 0.5  # a result of exactly zero is not a gain
    assert third["n_tickers"] == 1  # (30, rsi) only passed the gate on AAA3


def test_a_combination_must_work_on_enough_tickers_to_be_ranked() -> None:
    from b3core.universe import rank_across_tickers

    tables = {
        "AAA3": trials([(10, "target", 60, 0.30, 50), (30, "rsi", 99, 0.90, 70)]),
        "BBB3": trials([(10, "target", 30, 0.10, 55)]),
    }

    ranked = rank_across_tickers(tables, ["rsi_entry", "exit_mode", "max_days"],
                                 min_trades=30, min_tickers=2)  # fmt: skip

    assert len(ranked) == 1  # the 99-point combination exists on one ticker only
    assert ranked.iloc[0]["rsi_entry"] == 10


def test_a_missing_value_in_a_parameter_is_kept_not_dropped() -> None:
    from b3core.universe import rank_across_tickers

    table = trials([(10, "target", 60, 0.3, 50)]).assign(max_days=[5.0])
    other = trials([(10, "target", 40, 0.1, 50)])  # max_days None: a different combination

    ranked = rank_across_tickers({"A": table, "B": other}, ["rsi_entry", "exit_mode", "max_days"])

    assert len(ranked) == 2


def test_a_turtle_config_scans_with_the_turtle_runner() -> None:
    turtle_rows = [  # the worked example of brief section 7c: one trade, +R$ 92.25
        (10.00, 10.20, 9.90, 10.10),
        (10.10, 10.30, 10.00, 10.20),
        (10.20, 10.40, 10.10, 10.30),
        (10.30, 10.60, 10.25, 10.55),
        (10.85, 11.20, 10.80, 11.10),
        (11.10, 11.30, 11.00, 11.20),
        (11.00, 11.05, 10.60, 10.70),
    ]
    turtle = TurtleConfig(
        entry_period=2, exit_period=2, atr_period=2, max_units=1, capital_brl=10_000, risk_pct=2.0
    )

    table = scan_universe(
        {"TURT3": candles(turtle_rows)}, turtle, CDI, min_candles=1, runner=run_turtle
    )

    row = table.loc["TURT3"]
    direct = run_turtle(candles(turtle_rows), turtle)
    assert row["n_trades"] == 1
    assert row["result"] == pytest.approx(92.25 / 10_000)
    assert row["cagr"] == pytest.approx(direct.metrics.cagr)
    assert "beats_cdi" in table.columns and "bh_cagr" in table.columns
