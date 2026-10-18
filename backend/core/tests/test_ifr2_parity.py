"""Parity of `run_ifr2` with the research prototype in `/ifr2`, used as an oracle.

The prototype sizes by capital only, so the ATR sizing is neutralised with a huge risk budget.
Run with `uv run --group ifr2 pytest` (TA-Lib and the prototype's imports are needed).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("talib")
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ifr2"))
from ifr2_optimizer import make_default_strategy  # type: ignore[import-not-found] # noqa: E402
from ifr2_validation import trade_log  # type: ignore[import-not-found] # noqa: E402

from b3core.ifr2 import Ifr2Config, run_ifr2  # noqa: E402

CAPITAL = 100_000.0
CASES = [
    {"exit_mode": "target", "rsi_entry": 30, "target_lookback": 2},
    {"exit_mode": "target", "rsi_entry": 10, "target_lookback": 5, "max_days": 5},
    {"exit_mode": "rsi", "rsi_entry": 20, "rsi_exit": 70},
    {"exit_mode": "rsi", "rsi_entry": 25, "rsi_exit": 60, "max_days": 3},
    {"exit_mode": "target_or_rsi", "rsi_entry": 15, "target_lookback": 3, "rsi_exit": 80},
    {"exit_mode": "target_or_rsi", "rsi_entry": 30, "rsi_period": 3, "max_days": 10},
]


def synthetic(seed: int, n: int = 1500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 20 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, n)))
    open_ = close * (1 + rng.normal(0, 0.006, n))  # gaps, so the open fill is exercised
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.007, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.007, n)))
    index = pd.bdate_range("2012-01-02", periods=n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Adj Close": close}, index=index
    )


def to_candles(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.DatetimeIndex(frame.index).tz_localize("America/Sao_Paulo"),
            "open": frame["Open"].to_numpy(),
            "high": frame["High"].to_numpy(),
            "low": frame["Low"].to_numpy(),
            "close": frame["Close"].to_numpy(),
            "volume": 1.0,
        }
    )


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("case", CASES, ids=lambda c: "-".join(f"{k}{v}" for k, v in c.items()))
def test_trades_match_the_prototype(seed: int, case: dict) -> None:
    frame = synthetic(seed)
    defaults = {"rsi_period": 2, "rsi_entry": 30, "rsi_exit": 70, "exit_mode": "target"}
    params = defaults | {"target_lookback": 2} | {k: v for k, v in case.items() if k != "max_days"}
    max_days = case.get("max_days")

    signals = make_default_strategy(frame)(frame, **params)
    config = Ifr2Config(
        **{**params, "max_days": max_days},
        capital_brl=CAPITAL,
        max_risk_brl=1e12,  # the prototype has no ATR sizing: let the capital cap decide
        lot_size=1,
    )
    # The one rule the prototype lacks: no signal while the ATR warms up (brief section 7).
    signals.iloc[: config.atr_period, signals.columns.get_loc("Buy Price")] = np.nan
    expected = trade_log(signals, max_days, CAPITAL, reinvest=False, lot=1)
    pos = {d: i for i, d in enumerate(frame.index)}
    expected = expected.assign(
        ei=expected["entry_date"].map(pos), xi=expected["exit_date"].map(pos)
    )
    mine = run_ifr2(to_candles(frame), config).trades

    assert len(mine) == len(expected) > 0
    assert [t.qty for t in mine] == list(expected["shares"])
    assert [t.entry_index for t in mine] == list(expected["ei"])
    assert [t.exit_index for t in mine] == list(expected["xi"])
    np.testing.assert_allclose([t.exit for t in mine], expected["exit"])
    np.testing.assert_allclose([t.pnl for t in mine], expected["pnl"])
