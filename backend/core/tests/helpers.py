"""Test helpers: build small synthetic candle series by hand."""

import pandas as pd

Row = tuple[float, float, float, float]  # open, high, low, close


def make_candles(rows: list[Row]) -> pd.DataFrame:
    ts = pd.date_range("2024-01-02 13:00", periods=len(rows), freq="2h", tz="UTC")
    return pd.DataFrame(
        {
            "ts": ts,
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [1000.0] * len(rows),
        }
    )


# The worked example from brief section 7. c1..c3 form the signal; trigger 10.56,
# stop (c2 low) 10.20, target (risk factor 2) 11.28.
C1: Row = (10.20, 10.40, 10.10, 10.30)
C2: Row = (10.30, 10.60, 10.20, 10.50)
C3: Row = (10.50, 10.55, 10.35, 10.40)
C4_ENTRY: Row = (10.40, 10.58, 10.38, 10.55)  # high reaches 10.56: fills at 10.56
C5_TARGET: Row = (10.55, 11.30, 10.50, 11.25)  # high reaches 11.28
