"""Golden cases for Turtle de compra. Every number is hand computed from brief section 7c.

Base setup (`config`): entry_period 2, exit_period 2, atr_period 2, add_atr_mult 1, max_units 1,
capital 10000 and risk_pct 2 (so the risk budget is R$ 200), lot 1, signal_close, no costs.

Worked example (SERIES). ATR(2) by hand, true range from bar 1, first ATR on bar 2:
  bar   TR     ATR      entry level  exit level
  1     0.30
  2     0.30   0.3000   10.30        9.90      close 10.30 equals the entry level: no signal
  3     0.35   0.3250   10.40        10.00     close 10.55 breaks out: buy floor(200 / 0.325) = 615
  4     0.65   0.4875   10.60        10.10
  5     0.30   0.39375  11.20        10.25
  6     0.60   0.49688  11.30        10.80     close 10.70 is below 10.80: sell
The entry level of bar 3 excludes the current candle: with its own high (10.60) the close 10.55
would not break out.
"""

import pandas as pd
import pytest

from b3core.turtle import TurtleConfig, run_turtle

Row = tuple[float, float, float, float]  # open, high, low, close

R0: Row = (10.00, 10.20, 9.90, 10.10)
R1: Row = (10.10, 10.30, 10.00, 10.20)
R2: Row = (10.20, 10.40, 10.10, 10.30)  # close equals the entry level 10.30: strict, no signal
R3: Row = (10.30, 10.60, 10.25, 10.55)  # breakout: buy at the close, 10.55
R4: Row = (10.85, 11.20, 10.80, 11.10)  # add level 10.875 is passed, but max_units is 1
R5: Row = (11.10, 11.30, 11.00, 11.20)
R6: Row = (11.00, 11.05, 10.60, 10.70)  # close below the exit level 10.80: sell at 10.70
SERIES = [R0, R1, R2, R3, R4, R5, R6]


def candles(rows: list[Row]) -> pd.DataFrame:
    ts = pd.date_range("2024-01-02", periods=len(rows), freq="B", tz="UTC")
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


def config(**overrides: object) -> TurtleConfig:
    base: dict[str, object] = {
        "entry_period": 2,
        "exit_period": 2,
        "atr_period": 2,
        "add_atr_mult": 1.0,
        "max_units": 1,
        "capital_brl": 10_000,
        "risk_pct": 2.0,
        "lot_size": 1,
    }
    return TurtleConfig(**{**base, **overrides})  # type: ignore[arg-type]


def run(rows: list[Row], **overrides: object):  # type: ignore[no-untyped-def]
    return run_turtle(candles(rows), config(**overrides))


def test_worked_example() -> None:
    (t,) = run(SERIES).trades

    assert t.qty == 615
    assert t.units == 1
    assert t.entry == pytest.approx(10.55)
    assert t.exit == pytest.approx(10.70)
    assert t.exit_reason == "sell"
    assert t.pnl == pytest.approx(92.25)
    assert (t.entry_index, t.exit_index, t.days) == (3, 6, 3)


def test_close_equal_to_the_entry_level_is_not_a_signal() -> None:
    equal: Row = (10.30, 10.60, 10.25, 10.40)  # the entry level of this bar is 10.40

    assert run([R0, R1, R2, equal]).trades == []


def test_peak_money_in_the_position() -> None:
    assert run(SERIES).peak_cost == pytest.approx(615 * 10.55)


def test_result_metrics_use_the_configured_capital() -> None:
    result = run(SERIES)

    assert result.metrics.n_trades == 1
    assert result.metrics.result == pytest.approx(92.25 / 10_000)


# Stop tests. After the buy at 10.55 on bar 3 (ATR 0.325), bar 4 has TR 0.65 and ATR 0.4875.
# The stop reads the PREVIOUS candle's ATR: 10.55 - 0.325 = 10.225. With the current ATR it would
# be 10.55 - 0.4875 = 10.0625, so a close of 10.20 tells the two apart. The exit level of bar 4
# is min(10.10, 10.25) = 10.10.
STOP_BAR: Row = (10.40, 10.45, 9.90, 10.20)  # below 10.225, above the exit level 10.10
BOTH_BAR: Row = (10.40, 10.45, 9.90, 10.05)  # below the stop and below the exit level


def test_stop_is_read_on_the_close_with_the_previous_atr() -> None:
    (t,) = run([R0, R1, R2, R3, STOP_BAR]).trades

    assert t.exit_reason == "stop"
    assert t.exit == pytest.approx(10.20)  # the close, not the stop level 10.225
    assert t.pnl == pytest.approx(615 * (10.20 - 10.55))
    assert (t.entry_index, t.exit_index, t.days) == (3, 4, 1)


def test_sell_takes_priority_over_stop_on_the_same_candle() -> None:
    (t,) = run([R0, R1, R2, R3, BOTH_BAR]).trades

    assert t.exit_reason == "sell"
    assert t.exit == pytest.approx(10.05)
