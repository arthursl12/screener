"""WINFUT minute bars with a guard on the final test period (brief section 10)."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from b3core.data import EXPORT_TIMEZONE, CsvProvider, Timeframe

SYMBOL = "WIN$N"
# The owner's split (Nov 16, 2026): development before it, the final test from it on. The final
# bars are returned only when `final=True`, which the owner asks for once the spec and code are
# frozen.
FINAL_START = datetime(2025, 1, 1, tzinfo=ZoneInfo(EXPORT_TIMEZONE))
_FAR_PAST = datetime(1990, 1, 1, tzinfo=ZoneInfo(EXPORT_TIMEZONE))
_FAR_FUTURE = datetime(2100, 1, 1, tzinfo=ZoneInfo(EXPORT_TIMEZONE))


def load_bars(folder: Path | str, *, final: bool = False, symbol: str = SYMBOL) -> pd.DataFrame:
    """Minute bars on a tz-naive São Paulo wall-clock index, with the real volume.

    By default only the development period (before `FINAL_START`). With `final=True` only the
    final test period. Problems found by ingest validation are in `bars.attrs["issues"]`.
    """
    start, end = (FINAL_START, _FAR_FUTURE) if final else (_FAR_PAST, FINAL_START)
    candles = CsvProvider(folder).get_candles(symbol, Timeframe.M1, start, end)
    local = candles["ts"].dt.tz_convert(EXPORT_TIMEZONE).dt.tz_localize(None)
    bars = candles[["open", "high", "low", "close", "volume"]].copy()
    bars.index = pd.DatetimeIndex(local, name="ts")
    bars.attrs["issues"] = candles.attrs.get("issues", [])
    return bars
