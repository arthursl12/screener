"""Scan one IFR2 config over many tickers (layer A of the universe notebook)."""

import pandas as pd
import pytest

from b3core.benchmark import compare_with_cdi
from b3core.ifr2 import Ifr2Config, run_ifr2
from b3core.score import score_v1
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
