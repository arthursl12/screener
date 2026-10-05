"""Test helpers: build small synthetic candle series by hand."""

from typing import Any

import pandas as pd

from b3core.engine import BacktestConfig

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


# The worked example from brief section 7. c1..c3 form the signal (c2 has the lowest low);
# entry 10.41, stop (c3 low minus one tick) 10.24, target (risk times 2) 10.75.
C1: Row = (10.50, 10.60, 10.40, 10.45)
C2: Row = (10.45, 10.50, 10.20, 10.30)
C3: Row = (10.30, 10.40, 10.25, 10.38)
C4_ENTRY: Row = (10.38, 10.45, 10.35, 10.44)  # high reaches 10.41: fills at 10.41
C5_TARGET: Row = (10.44, 10.80, 10.40, 10.78)  # high reaches 10.75


def make_config(**overrides: Any) -> BacktestConfig:
    """The worked-example setup: trend checks off, C3 stop, RISK target times 2, max risk 200."""
    base: dict[str, Any] = {
        "max_risk_brl": 200,
        "use_ma_order": False,
        "use_fast_slope": False,
        "use_slow_slope": False,
        "target_mode": "RISK",
        "target_mult": 2.0,
    }
    return BacktestConfig(**{**base, **overrides})


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


def make_candles_at(rows: list[Row], local_times: list[str]) -> pd.DataFrame:
    """Candles at explicit São Paulo wall-clock times (January 2024: UTC-3, no DST)."""
    ts = pd.DatetimeIndex(pd.to_datetime(local_times)).tz_localize("America/Sao_Paulo")
    return pd.DataFrame(
        {
            "ts": ts.tz_convert("UTC"),
            "open": [r[0] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[2] for r in rows],
            "close": [r[3] for r in rows],
            "volume": [1000.0] * len(rows),
        }
    )


def random_multi_day_candles(n_days: int, seed: int) -> pd.DataFrame:
    """Seeded H2 candles at 10:00, 12:00, 14:00 and 16:00, one block per day (January 2024)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    price = 2000
    rows: list[Row] = []
    times: list[str] = []
    for day in range(n_days):
        for hhmm in ("10:00", "12:00", "14:00", "16:00"):
            times.append(f"2024-01-{2 + day:02d} {hhmm}")
            open_ = max(price + int(rng.integers(-30, 31)), 200)
            close = max(open_ + int(rng.integers(-60, 61)), 200)
            high = max(open_, close) + int(rng.integers(0, 40))
            low = max(min(open_, close) - int(rng.integers(0, 40)), 1)
            rows.append((open_ / 100, high / 100, low / 100, close / 100))
            price = close
    return make_candles_at(rows, times)


def random_m30_candles(n_days: int, seed: int) -> pd.DataFrame:
    """Seeded M30 candles from 16:00 to 17:30 for each day, to pinpoint a 16:30 exit."""
    import numpy as np

    rng = np.random.default_rng(seed)
    rows: list[Row] = []
    times: list[str] = []
    for day in range(n_days):
        for hhmm in ("16:00", "16:30", "17:00", "17:30"):
            times.append(f"2024-01-{2 + day:02d} {hhmm}")
            open_ = 2000 + int(rng.integers(-80, 81))
            close = open_ + int(rng.integers(-30, 31))
            rows.append(
                (
                    open_ / 100,
                    (max(open_, close) + int(rng.integers(0, 20))) / 100,
                    (min(open_, close) - int(rng.integers(0, 20))) / 100,
                    close / 100,
                )
            )
    return make_candles_at(rows, times)
