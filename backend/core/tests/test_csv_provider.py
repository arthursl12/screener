from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from b3core.data import CsvProvider, Timeframe, validate_candles

H2_HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"
D1_HEADER = "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"

EXPECTED_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]
START = datetime(2000, 1, 1, tzinfo=UTC)
END = datetime(2100, 1, 1, tzinfo=UTC)


def write_csv(folder: Path, name: str, header: str, rows: list[str]) -> None:
    # MT5 exports use tabs and CRLF line endings.
    (folder / name).write_bytes(("\r\n".join([header, *rows]) + "\r\n").encode())


def test_h2_row_is_converted_to_utc_and_vol_becomes_volume(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "TEST3_H2_201610031000_201610031000.csv",
        H2_HEADER,
        ["2016.10.03\t10:00:00\t6.66\t6.81\t6.65\t6.79\t5255\t4736800\t1"],
    )

    df = CsvProvider(tmp_path).get_candles("TEST3", Timeframe.H2, START, END)

    assert list(df.columns) == EXPECTED_COLUMNS
    # Hand computed: 2016-10-03 is before Brazil's DST (UTC-3), so 10:00 local is 13:00Z.
    assert df.loc[0, "ts"] == pd.Timestamp("2016-10-03 13:00", tz="UTC")
    assert df.loc[0, "volume"] == 4736800  # <VOL>, not <TICKVOL> (5255)
    assert df.loc[0, "open"] == 6.66


def test_timestamp_inside_brazil_dst_uses_utc_minus_2(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "TEST3_H2_201701021000_201701021000.csv",
        H2_HEADER,
        ["2017.01.02\t10:00:00\t6.66\t6.81\t6.65\t6.79\t5255\t4736800\t1"],
    )

    df = CsvProvider(tmp_path).get_candles("TEST3", Timeframe.H2, START, END)

    # Hand computed: Brazil's DST ran from 2016-10-16 to 2017-02-19, so local time was UTC-2.
    assert df.loc[0, "ts"] == pd.Timestamp("2017-01-02 12:00", tz="UTC")


def test_daily_file_has_no_time_column_and_opens_at_local_midnight(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "TEST3_Daily_201610030000_201610030000.csv",
        D1_HEADER,
        ["2016.10.03\t6.66\t6.82\t6.65\t6.78\t16491\t12644400\t1"],
    )

    df = CsvProvider(tmp_path).get_candles("TEST3", Timeframe.D1, START, END)

    assert df.loc[0, "ts"] == pd.Timestamp("2016-10-03 03:00", tz="UTC")
    assert df.loc[0, "volume"] == 12644400


def test_start_is_inclusive_and_end_is_exclusive(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "TEST3_H2_201610031000_201610031600.csv",
        H2_HEADER,
        [
            "2016.10.03\t10:00:00\t6.66\t6.81\t6.65\t6.79\t1\t100\t1",
            "2016.10.03\t12:00:00\t6.79\t6.79\t6.73\t6.79\t1\t100\t1",
            "2016.10.03\t14:00:00\t6.79\t6.80\t6.76\t6.77\t1\t100\t1",
        ],
    )

    df = CsvProvider(tmp_path).get_candles(
        "TEST3",
        Timeframe.H2,
        start=datetime(2016, 10, 3, 15, 0, tzinfo=UTC),  # 12:00 local
        end=datetime(2016, 10, 3, 17, 0, tzinfo=UTC),  # 14:00 local, excluded
    )

    assert df["ts"].tolist() == [pd.Timestamp("2016-10-03 15:00", tz="UTC")]


def test_missing_file_raises_with_a_clear_message(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="TEST3"):
        CsvProvider(tmp_path).get_candles("TEST3", Timeframe.H2, START, END)


def test_bad_rows_are_reported_and_never_dropped(tmp_path: Path) -> None:
    write_csv(
        tmp_path,
        "TEST3_H2_201610031000_201610031400.csv",
        H2_HEADER,
        [
            "2016.10.03\t10:00:00\t6.66\t6.81\t6.65\t6.79\t1\t100\t1",
            "2016.10.03\t10:00:00\t6.66\t6.81\t6.65\t6.79\t1\t100\t1",  # duplicate ts
            "2016.10.03\t12:00:00\t6.79\t6.70\t6.73\t6.79\t1\t-5\t1",  # high < open, vol < 0
        ],
    )

    df = CsvProvider(tmp_path).get_candles("TEST3", Timeframe.H2, START, END)

    assert len(df) == 3
    issues = df.attrs["issues"]
    assert any("duplicate" in i for i in issues)
    assert any("high" in i for i in issues)
    assert any("volume" in i for i in issues)


def _candles(rows: list[tuple[str, float, float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(pd.Timestamp(t, tz="UTC"), o, h, lo, c, v) for t, o, h, lo, c, v in rows],
        columns=EXPECTED_COLUMNS,
    )


def test_validate_candles_accepts_clean_data() -> None:
    df = _candles(
        [
            ("2016-10-03 13:00", 10.0, 10.5, 9.9, 10.2, 100),
            ("2016-10-03 15:00", 10.2, 10.4, 10.1, 10.3, 0),
        ]
    )
    assert validate_candles(df) == []


def test_validate_candles_flags_unsorted_timestamps() -> None:
    df = _candles(
        [
            ("2016-10-03 15:00", 10.0, 10.5, 9.9, 10.2, 100),
            ("2016-10-03 13:00", 10.2, 10.4, 10.1, 10.3, 100),
        ]
    )
    assert any("increasing" in i for i in validate_candles(df))


def test_validate_candles_flags_low_above_close() -> None:
    df = _candles([("2016-10-03 13:00", 10.0, 10.5, 10.25, 10.2, 100)])
    assert any("low" in i for i in validate_candles(df))
