"""
Generic grid-search optimizer for the IFR2 / RSI mean-reversion strategy (TA-Lib).

Parameter grid
--------------
Each grid entry can be:
    (start, stop, step)   -> inclusive numeric range, e.g. "rsi_entry": (10, 40, 5)
    [v1, v2, ...]         -> explicit list (also use for categorical values)
    scalar                -> fixed value

Built-in parameters
-------------------
    rsi_period       int    RSI length                         (default 2)
    rsi_entry        float  buy when RSI <= this               (default 30)
    rsi_exit         float  RSI exit level (rsi modes)         (default 70)
    exit_mode        str    "target" | "rsi" | "target_or_rsi" (default "target")
    target_lookback  int    N days for the high-target exit    (default 2)
    max_days         int    time stop (None = no stop)         (default None)

Custom parameters
-----------------
Pass your own `strategy_fn(df, **params) -> DataFrame` that returns the frame with
"Buy Price" and "Sell Price" columns. Any name you put in the grid is forwarded to it,
so you can optimize anything (e.g. an SMA filter length, ATR multiple, ...).
`max_days` is always handled by the backtester.
"""
import itertools
import math
from typing import Callable, Dict, Optional, Union

import numpy as np
import pandas as pd
import talib

DEFAULTS = dict(
    rsi_period=2,
    rsi_entry=30,
    rsi_exit=70,
    exit_mode="target",
    target_lookback=2,
    max_days=None,
)


# --------------------------------------------------------------------------- grid
def frange(start, stop, step):
    """Inclusive float/int range without float drift."""
    n = int(round((stop - start) / step)) + 1
    vals = [start + i * step for i in range(n)]
    return [int(v) if float(v).is_integer() and isinstance(step, int) else round(v, 10) for v in vals]


def expand(spec):
    if isinstance(spec, tuple) and len(spec) == 3 and all(isinstance(x, (int, float)) for x in spec):
        return frange(*spec)
    if isinstance(spec, (list, set)):
        return list(spec)
    return [spec]


def build_combos(grid: Dict, fixed: Optional[Dict] = None, drop_irrelevant=True):
    base = {**DEFAULTS, **(fixed or {})}
    keys = list(grid)
    combos, seen = [], set()
    for vals in itertools.product(*(expand(grid[k]) for k in keys)):
        p = {**base, **dict(zip(keys, vals))}
        if drop_irrelevant:
            if p["exit_mode"] == "target":
                p["rsi_exit"] = None                     # unused -> avoid duplicate runs
            if p["exit_mode"] == "rsi":
                p["target_lookback"] = None
            if p["rsi_exit"] is not None and p["rsi_entry"] >= p["rsi_exit"]:
                continue                                  # nonsensical
        sig = tuple(sorted(p.items(), key=lambda kv: kv[0]))
        if sig in seen:
            continue
        seen.add(sig)
        combos.append(p)
    return combos


# --------------------------------------------------------------------------- strategy
class _Cache:
    """Indicators are recomputed only when their own inputs change."""
    def __init__(self, df):
        self.df, self.rsi, self.target = df, {}, {}

    def get_rsi(self, n):
        if n not in self.rsi:
            self.rsi[n] = talib.RSI(self.df["Adj Close"].values.astype(float), timeperiod=n)
        return self.rsi[n]

    def get_target(self, n):
        if n not in self.target:
            t = pd.Series(talib.MAX(self.df["High"].values.astype(float), timeperiod=n),
                          index=self.df.index).shift(1)
            self.target[n] = t.values
        return self.target[n]


def make_default_strategy(df):
    cache = _Cache(df)
    o, h, c = df["Open"].values, df["High"].values, df["Close"].values

    def strategy(_, **p):
        rsi = cache.get_rsi(int(p["rsi_period"]))
        buy = np.where(rsi <= p["rsi_entry"], c, np.nan)

        mode = p["exit_mode"]
        sell = np.full(len(c), np.nan)
        if mode in ("target", "target_or_rsi"):
            tgt = cache.get_target(int(p["target_lookback"]))
            with np.errstate(invalid="ignore"):
                hit = h > tgt
                sell = np.where(hit, np.where(o > tgt, o, tgt), np.nan)
        if mode in ("rsi", "target_or_rsi"):
            with np.errstate(invalid="ignore"):
                rsi_sell = np.where(rsi >= p["rsi_exit"], c, np.nan)
            sell = np.where(np.isnan(sell), rsi_sell, sell)
        return pd.DataFrame({"Buy Price": buy, "Sell Price": sell, "Close": c}, index=df.index)

    return strategy


# --------------------------------------------------------------------------- backtest / stats
def _lot(x, lot=100):
    lot = max(int(lot), 1)
    return int(math.floor(x / lot)) * lot


def run_backtest(sig: pd.DataFrame, initial_capital=10_000, max_days=None,
                 reinvest=False, cost_per_trade=0.0, lot=100, cost_pct=0.0):
    buy, sell, close = sig["Buy Price"].values, sig["Sell Price"].values, sig["Close"].values
    cap, profits, durations = [initial_capital], [], []
    equity = np.empty(len(sig))                          # balance + floating PnL, marked at each close
    ongoing, days, entry, shares = False, 0, 0.0, 0
    for i in range(len(sig)):
        if ongoing:
            days += 1
            hit = not np.isnan(sell[i])
            if hit or (max_days is not None and days >= max_days):
                px = sell[i] if hit else close[i]
                pnl = (shares * (px - entry) - 2 * cost_per_trade
                       - cost_pct / 100.0 * shares * (entry + px))
                profits.append(pnl); durations.append(days)
                cap.append(cap[-1] + pnl)
                ongoing = False
        elif not np.isnan(buy[i]):
            base = cap[-1] if reinvest else initial_capital
            shares = _lot(base / buy[i], lot)
            entry, days, ongoing = buy[i], 0, shares > 0
        floating = (shares * (close[i] - entry) - cost_per_trade
                    - cost_pct / 100.0 * shares * entry) if ongoing else 0.0
        equity[i] = cap[-1] + floating
    return profits, cap, durations, equity


def _max_drawdown_pct(curve, start):
    peak = np.maximum.accumulate(np.r_[start, curve])
    return float((100 * (peak - np.r_[start, curve]) / peak).max())


def compute_stats(profits, cap, durations, equity, years):
    """
    max_dd_balance : drawdown of the closed-trade balance (what MT5 calls balance drawdown)
    max_dd         : drawdown of the daily equity curve, open trades marked at the close
                     (MT5 equity drawdown) - the real risk, and the one `calmar` uses
    cagr_pct       : annualised return over `years`; calmar = cagr_pct / max_dd
    """
    n = len(profits)
    if n == 0:
        return dict(trades=0, win_rate=np.nan, profit=0.0, profit_pct=0.0, cagr_pct=0.0,
                    max_dd=np.nan, max_dd_balance=np.nan, profit_factor=np.nan, calmar=np.nan,
                    avg_days=np.nan, expectancy=np.nan)
    p = np.array(profits)
    dd_balance = _max_drawdown_pct(cap[1:], cap[0])
    dd = _max_drawdown_pct(equity, cap[0])
    gross_win, gross_loss = p[p > 0].sum(), -p[p < 0].sum()
    pct = 100 * p.sum() / cap[0]
    final = cap[0] + p.sum()
    cagr = 100 * ((final / cap[0]) ** (1 / years) - 1) if final > 0 else -100.0
    return dict(
        trades=n,
        win_rate=round(100 * (p > 0).mean(), 2),
        profit=round(p.sum(), 2),
        profit_pct=round(pct, 2),
        cagr_pct=round(cagr, 2),
        max_dd=round(dd, 2),
        max_dd_balance=round(dd_balance, 2),
        profit_factor=round(gross_win / gross_loss, 2) if gross_loss > 0 else np.inf,
        calmar=round(cagr / dd, 2) if dd > 0 else np.inf,
        avg_days=round(np.mean(durations), 2),
        expectancy=round(p.mean(), 2),
    )


# objective name -> (stats key, maximize?)
OBJECTIVES = {
    "profit_pct": ("profit_pct", True),
    "profit": ("profit", True),
    "win_rate": ("win_rate", True),
    "max_dd": ("max_dd", False),
    "profit_factor": ("profit_factor", True),
    "calmar": ("calmar", True),          # profit % / max drawdown %
    "expectancy": ("expectancy", True),
}


# --------------------------------------------------------------------------- optimizer
def optimize(
    df: pd.DataFrame,
    grid: Dict,
    fixed: Optional[Dict] = None,
    objective: Union[str, Callable[[dict], float]] = "calmar",
    maximize: Optional[bool] = None,
    min_trades: int = 20,
    strategy_fn: Optional[Callable] = None,
    initial_capital: float = 10_000,
    reinvest: bool = False,
    cost_per_trade: float = 0.0,
    oos_frac: float = 0.0,
    top: Optional[int] = None,
    verbose: bool = True,
    lot: int = 100,
    oos_start=None,
    cost_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Grid-search `grid` and return a DataFrame sorted by `objective` (best first).

    objective   : name in OBJECTIVES, or callable(stats_dict)->float
    min_trades  : combos with fewer trades are discarded (guards against lucky tiny samples)
    cost_pct    : proportional cost PER SIDE in percent of traded value (0.03 = 0.03 %);
                  adds to the fixed `cost_per_trade`, both default to 0
    lot         : share lot size (100 = B3 standard lot, 1 = fractional market)
    oos_start   : explicit date where the out-of-sample period begins (overrides oos_frac);
                  use the same date for every ticker when optimizing a universe
    oos_frac    : e.g. 0.3 -> optimize on the first 70 %, then re-test every combo on the
                  last 30 % and add `oos_*` columns so you can see if the edge survives.
    strategy_fn : custom `fn(df, **params)` returning Buy Price / Sell Price / Close columns
    """
    if callable(objective):
        key_fn, maximize = objective, True if maximize is None else maximize
    else:
        key, default_max = OBJECTIVES[objective]
        key_fn, maximize = (lambda s, k=key: s[k]), default_max if maximize is None else maximize

    df = df.dropna(subset=["Open", "High", "Close", "Adj Close"]).copy()
    if oos_start is not None:
        cut = int(df.index.searchsorted(pd.Timestamp(oos_start)))
        df_is, df_oos = df.iloc[:cut], df.iloc[cut:]
    elif oos_frac > 0:
        cut = int(len(df) * (1 - oos_frac))
        df_is, df_oos = df.iloc[:cut], df.iloc[cut:]
    else:
        df_is, df_oos = df, None

    combos = build_combos(grid, fixed)
    if verbose:
        print(f"{len(combos)} combinations | objective={objective} | min_trades={min_trades}"
              + (f" | OOS={oos_frac:.0%}" if oos_frac else ""))

    def evaluate(frame, combo_list):
        fn = strategy_fn or make_default_strategy(frame)
        out = []
        for p in combo_list:
            sig_params = {k: v for k, v in p.items() if k != "max_days"}
            sig = fn(frame, **sig_params)
            if "Close" not in sig:
                sig = sig.assign(Close=frame["Close"].values)
            years = max((frame.index[-1] - frame.index[0]).days / 365.25, 1e-9)
            st = compute_stats(*run_backtest(sig, initial_capital, p["max_days"],
                                             reinvest, cost_per_trade, lot, cost_pct), years=years)
            out.append(st)
        return out

    is_stats = evaluate(df_is, combos)
    rows, kept_params = [], {}
    for idx, (p, st) in enumerate(zip(combos, is_stats)):
        if st["trades"] < min_trades:
            continue
        rows.append({**p, **st, "_score": key_fn(st), "_i": idx})
    if not rows:
        raise ValueError("No combination reached min_trades; lower it or widen the grid.")

    res = pd.DataFrame(rows).sort_values("_score", ascending=not maximize)

    if df_oos is not None:
        kept = [combos[i] for i in res["_i"]]      # original param dicts (keep None, not NaN)
        oos = pd.DataFrame(evaluate(df_oos, kept), index=res.index).add_prefix("oos_")
        res = pd.concat([res, oos], axis=1)

    res = res.drop(columns=["_score", "_i"]).reset_index(drop=True)
    res["max_days"] = res["max_days"].astype(object).where(res["max_days"].notna(), None)
    return res.head(top) if top else res


def sensitivity(results: pd.DataFrame, param: str, metric: str = "profit_pct") -> pd.DataFrame:
    """Average / median / worst of `metric` per value of `param` - favours plateaus over spikes."""
    g = results.groupby(results[param].astype(str))[metric]
    return pd.DataFrame({"mean": g.mean(), "median": g.median(), "min": g.min(), "n": g.size()})


# --------------------------------------------------------------------------- example
if __name__ == "__main__":
    from ifr2_talib import load

    df = load("LREN3.SA", "2015-01-01", "2020-12-30")

    grid = {
        "rsi_period": (2, 4, 1),                              # start, stop, step
        "rsi_entry": (10, 40, 5),
        "exit_mode": ["target", "rsi", "target_or_rsi"],      # variants
        "rsi_exit": (50, 80, 10),
        "max_days": [None, 3, 5, 7, 9],                       # stop
    }
    res = optimize(df, grid, objective="calmar", min_trades=30, oos_frac=0.3, top=15)
    print(res.to_string())

    # which values of one parameter are robust (not just the single best)?
    full = optimize(df, grid, objective="calmar", min_trades=30, verbose=False)
    print(sensitivity(full, "rsi_entry", "profit_pct"))
