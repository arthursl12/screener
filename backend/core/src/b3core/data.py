"""Candle data: the DataProvider interface, the MT5 CSV provider and ingest validation."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

import pandas as pd

CANDLE_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]

# Working assumption (brief section 10): MT5 export times are B3 wall-clock time.
EXPORT_TIMEZONE = "America/Sao_Paulo"


class Timeframe(Enum):
    """Supported timeframes. The value is the token MT5 puts in exported file names."""

    D1 = "Daily"
    H1 = "H1"
    H2 = "H2"
    H4 = "H4"


class DataProvider(Protocol):
    def get_candles(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Columns: ts (UTC, candle open), open, high, low, close, volume.

        `start` is inclusive and `end` is exclusive. Both must be timezone-aware.
        """
        ...


def validate_candles(df: pd.DataFrame) -> list[str]:
    """Return one message per problem found. Never fixes, fills or drops anything."""
    issues: list[str] = []

    duplicated = df["ts"].duplicated(keep=False)
    if duplicated.any():
        issues.append(f"duplicate timestamps in {int(duplicated.sum())} rows")

    steps = df["ts"].diff().dropna()
    going_back = int((steps < pd.Timedelta(0)).sum())
    if going_back:
        issues.append(f"timestamps not strictly increasing at {going_back} rows")

    high_low = df["high"] < df[["open", "close"]].max(axis=1)
    if high_low.any():
        issues.append(f"high below max(open, close) in {int(high_low.sum())} rows")

    low_high = df["low"] > df[["open", "close"]].min(axis=1)
    if low_high.any():
        issues.append(f"low above min(open, close) in {int(low_high.sum())} rows")

    negative = df["volume"] < 0
    if negative.any():
        issues.append(f"negative volume in {int(negative.sum())} rows")

    return issues


class CsvProvider:
    """Reads MT5 "export bars" files named `<SYMBOL>_<TIMEFRAME>_<from>_<to>.csv` from a folder.

    The files are tab separated and CRLF terminated. Daily files have no `<TIME>` column.
    `<VOL>` (real volume) becomes `volume`; `<TICKVOL>` and `<SPREAD>` are ignored.
    Problems found by `validate_candles` are listed in `df.attrs["issues"]`.
    """

    def __init__(self, folder: Path | str) -> None:
        self._folder = Path(folder)

    def get_candles(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")

        df = self._read(self._find_file(symbol, timeframe))
        in_range = (df["ts"] >= pd.Timestamp(start)) & (df["ts"] < pd.Timestamp(end))
        out = df.loc[in_range].reset_index(drop=True)
        out.attrs["issues"] = validate_candles(out)
        return out

    def _find_file(self, symbol: str, timeframe: Timeframe) -> Path:
        pattern = f"{symbol}_{timeframe.value}_*.csv"
        matches = sorted(self._folder.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"no file matching {pattern} in {self._folder}")
        if len(matches) > 1:
            names = ", ".join(m.name for m in matches)
            raise ValueError(f"more than one file for {symbol} {timeframe.value}: {names}")
        return matches[0]

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        raw = pd.read_csv(path, sep="\t")
        raw.columns = [c.strip("<>").lower() for c in raw.columns]

        if "time" in raw.columns:
            local = pd.to_datetime(raw["date"] + " " + raw["time"], format="%Y.%m.%d %H:%M:%S")
        else:
            local = pd.to_datetime(raw["date"], format="%Y.%m.%d")

        # Fail loudly on a nonexistent or ambiguous local time (DST changes) instead of guessing.
        ts = local.dt.tz_localize(EXPORT_TIMEZONE, ambiguous="raise", nonexistent="raise")

        df = pd.DataFrame(
            {
                "ts": ts.dt.tz_convert("UTC"),
                "open": raw["open"].astype("float64"),
                "high": raw["high"].astype("float64"),
                "low": raw["low"].astype("float64"),
                "close": raw["close"].astype("float64"),
                "volume": raw["vol"].astype("float64"),
            }
        )
        return df[CANDLE_COLUMNS]
