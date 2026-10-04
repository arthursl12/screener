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


def random_walk_candles(n: int, seed: int) -> pd.DataFrame:
    """Seeded synthetic series on a 0.01 tick grid, for optimizer tests."""
    import numpy as np

    rng = np.random.default_rng(seed)
    price = 2000  # in ticks
    rows: list[Row] = []
    for _ in range(n):
        open_ = max(price + int(rng.integers(-30, 31)), 200)
        close = max(open_ + int(rng.integers(-60, 61)), 200)
        high = max(open_, close) + int(rng.integers(0, 40))
        low = max(min(open_, close) - int(rng.integers(0, 40)), 1)
        rows.append((open_ / 100, high / 100, low / 100, close / 100))
        price = close
    return make_candles(rows)
