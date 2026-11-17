"""WINFUT bars loader with the guard on the final test period (brief section 10)."""

from pathlib import Path

import pandas as pd

from b3core.winfut import FINAL_START, load_bars

HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\r\n"


def write_file(folder: Path) -> None:
    rows = [
        ("2024.12.30", "17:54:00", 100),
        ("2024.12.30", "18:24:00", 101),
        ("2025.01.02", "09:00:00", 102),
        ("2026.10.30", "18:24:00", 103),
    ]
    body = "".join(f"{d}\t{t}\t{p}\t{p + 1}\t{p - 1}\t{p}\t10\t{p * 2}\t5\r\n" for d, t, p in rows)
    (folder / "WIN$N_M1_202412300900_202610301824.csv").write_text(HEADER + body, newline="")


def test_the_development_bars_stop_before_the_final_period(tmp_path: Path) -> None:
    write_file(tmp_path)

    bars = load_bars(tmp_path)

    assert list(bars["close"]) == [100.0, 101.0]
    assert bars.index.max() < pd.Timestamp("2025-01-01")


def test_the_final_period_is_returned_only_when_asked_for(tmp_path: Path) -> None:
    write_file(tmp_path)

    bars = load_bars(tmp_path, final=True)

    assert list(bars["close"]) == [102.0, 103.0]
    assert bars.index.min() >= pd.Timestamp("2025-01-01")


def test_the_bars_are_on_a_naive_local_time_index_with_real_volume(tmp_path: Path) -> None:
    write_file(tmp_path)

    bars = load_bars(tmp_path)

    assert bars.index.tz is None
    assert bars.index[0] == pd.Timestamp("2024-12-30 17:54")  # São Paulo wall-clock time
    assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
    assert bars["volume"].iloc[0] == 200.0  # <VOL>, not <TICKVOL>


def test_the_split_date_is_the_owners_choice() -> None:
    assert FINAL_START.date().isoformat() == "2025-01-01"
