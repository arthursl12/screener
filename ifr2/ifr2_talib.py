"""
IFR2 (RSI 2) mean-reversion backtest using TA-Lib.

Entry : buy at Close when RSI(2) <= rsi_entry
Exit  : (a) price hits Target = max(High[t-1], High[t-2])  [exit at max(Open, Target)]
        (b) optional: RSI(2) >= rsi_exit  -> exit at Close
        (c) optional: time stop after `max_days` days     -> exit at Close
"""
import math
import numpy as np
import pandas as pd
import talib
import yfinance as yf


def load(ticker="LREN3.SA", start="2015-01-01", end="2020-12-30"):
    df = yf.download(ticker, start=start, end=end, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df[["Open", "High", "Low", "Close", "Adj Close"]].copy()


def add_indicators(df, rsi_period=2, target_lookback=2):
    # Same as your notebook: RSI on Adj Close (TA-Lib uses Wilder smoothing seeded by SMA)
    df["IFR2"] = talib.RSI(df["Adj Close"].values.astype(float), timeperiod=rsi_period)

    # Highest high of the previous N days (shifted so today's high is NOT included)
    df["Target"] = pd.Series(
        talib.MAX(df["High"].values.astype(float), timeperiod=target_lookback),
        index=df.index,
    ).shift(1)
    return df


def add_signals(df, rsi_entry=30, rsi_exit=None):
    df["Buy Price"] = np.where(df["IFR2"] <= rsi_entry, df["Close"], np.nan)

    # Target exit: if High crosses Target, fill at Open when gapping above, else at Target
    target_fill = np.where(
        df["High"] > df["Target"],
        np.where(df["Open"] > df["Target"], df["Open"], df["Target"]),
        np.nan,
    )
    df["Target Exit"] = target_fill

    if rsi_exit is None:
        df["Sell Price"] = df["Target Exit"]
    else:
        df["Sell Price"] = np.where(df["IFR2"] >= rsi_exit, df["Close"], np.nan)
    return df


def round_down_lot(x, lot=100):
    return int(math.floor(x / lot)) * lot


def backtest(df, initial_capital=10_000, max_days=None, reinvest=False):
    buy = df["Buy Price"].values
    sell = df["Sell Price"].values
    close = df["Close"].values

    capital = [initial_capital]
    profits = []
    ongoing, days, entry, shares = False, 0, 0.0, 0

    for i in range(len(df)):
        if ongoing:
            days += 1
            hit_exit = not np.isnan(sell[i])
            hit_stop = max_days is not None and days >= max_days
            if hit_exit or hit_stop:
                exit_px = sell[i] if hit_exit else close[i]
                p = shares * (exit_px - entry)
                profits.append(p)
                capital.append(capital[-1] + p)
                ongoing = False
        elif not np.isnan(buy[i]):
            entry = buy[i]
            base = capital[-1] if reinvest else initial_capital
            shares = round_down_lot(base / entry)
            days = 0
            ongoing = shares > 0
    return profits, capital


def stats(profits, capital):
    n = len(profits)
    if n == 0:
        return {}
    cap = pd.Series(capital)
    dd = 100 * (cap.cummax() - cap) / cap.cummax()
    gains = sum(p > 0 for p in profits)
    return {
        "operations": n,
        "win_rate_%": round(100 * gains / n, 1),
        "total_profit": round(sum(profits), 2),
        "profit_%": round(100 * sum(profits) / capital[0], 2),
        "max_drawdown_%": round(dd.max(), 2),
    }


if __name__ == "__main__":
    df = add_indicators(load())

    rows = {}
    # Variant 1: target exit, no stop
    d = add_signals(df.copy(), rsi_entry=30)
    rows["RSI<=30 | target exit"] = stats(*backtest(d))

    # Variant 2: target exit + 3-day time stop
    rows["RSI<=30 | target + 3d stop"] = stats(*backtest(d, max_days=3))

    # Variant 3: RSI exit grid + time stops
    for rsi_exit in (50, 60, 70, 80):
        d = add_signals(df.copy(), rsi_entry=30, rsi_exit=rsi_exit)
        for stop in (None, 3, 5, 7, 9):
            rows[f"RSI<=30 | exit>={rsi_exit} | stop={stop}"] = stats(*backtest(d, max_days=stop))

    print(pd.DataFrame(rows).T.to_string())
