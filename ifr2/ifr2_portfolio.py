"""
Portfolio simulation for the IFR2 / RSI strategy (a NEW module - nothing existing changed).

Per-ticker aggregation asks "does this rule work on each stock?". The portfolio asks
"could I actually trade it with one pot of money?":

    * one shared capital, at most `max_positions` open positions at a time
    * when more signals than free slots appear on the same day, the most oversold
      (lowest RSI) are taken first
    * equity is marked to market EVERY day, so drawdown includes open losers
    * same entry/exit rules and fill assumptions as the single-ticker backtester
      (buy at the signal day's close; target/RSI/time exits), so with max_positions=1,
      one ticker and reinvest=False it reproduces `run_backtest` exactly

Sizing: each new position gets (equity or initial capital) / max_positions, limited by
the cash available. Costs: `cost_pct` (percent per side) and `cost_per_trade` (fixed per side).
"""
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ifr2_optimizer import DEFAULTS, _Cache, build_combos, make_default_strategy


# --------------------------------------------------------------------------- result object
class PortfolioResult:
    def __init__(self, equity: pd.Series, trades: pd.DataFrame, stats: dict, params: dict,
                 n_open_end: int):
        self.equity, self.trades, self.stats, self.params, self.n_open_end = (
            equity, trades, stats, params, n_open_end)

    def yearly(self) -> pd.DataFrame:
        """Return per calendar year (%), plus the worst drawdown inside that year."""
        eq = self.equity
        out = {}
        prev = float(eq.iloc[0]) if len(eq) else np.nan
        for y, g in eq.groupby(eq.index.year):
            dd = (100 * (g.cummax() - g) / g.cummax()).max()
            out[y] = dict(return_pct=100 * (g.iloc[-1] / prev - 1), max_dd_pct=dd)
            prev = float(g.iloc[-1])
        return pd.DataFrame(out).T.round(2).rename_axis("year")

    def __repr__(self):
        return "PortfolioResult(" + ", ".join(f"{k}={v}" for k, v in self.stats.items()) + ")"


# --------------------------------------------------------------------------- data preparation
class Universe:
    """Aligns every ticker on one calendar and caches indicators. Build once, reuse per combo."""

    def __init__(self, data: Dict[str, pd.DataFrame], strategy_fn=None):
        self.tickers = list(data)
        self.data = data
        self.index = pd.DatetimeIndex(sorted(set().union(*[d.index for d in data.values()])))
        T, N = len(self.index), len(self.tickers)
        self.H = np.zeros((T, N), bool)                     # ticker has a bar that day
        self.C = np.full((T, N), np.nan)                    # close, forward-filled (for mark-to-market)
        self.pos = []
        for j, t in enumerate(self.tickers):
            d = data[t]
            p = self.index.get_indexer(d.index)
            self.pos.append(p)
            self.H[p, j] = True
            col = np.full(T, np.nan)
            col[p] = d["Close"].values
            self.C[:, j] = pd.Series(col).ffill().values
        self.strategy_fn = strategy_fn
        self._strat = {t: make_default_strategy(d) for t, d in data.items()} if strategy_fn is None else None
        self._cache = {t: _Cache(d) for t, d in data.items()}

    def signals(self, p: dict):
        """Matrices Buy / Sell / Rank (lower rank = taken first), shape (T, N)."""
        T, N = len(self.index), len(self.tickers)
        B, S = np.full((T, N), np.nan), np.full((T, N), np.nan)
        K = np.zeros((T, N))
        sig_p = {k: v for k, v in p.items() if k not in ("max_days", "max_positions")}
        for j, t in enumerate(self.tickers):
            d, pos = self.data[t], self.pos[j]
            if self.strategy_fn is None:
                sig = self._strat[t](d, **sig_p)
                rank = self._cache[t].get_rsi(int(p["rsi_period"]))
            else:
                sig = self.strategy_fn(d, **sig_p)
                rank = sig["Rank"].values if "Rank" in sig else np.zeros(len(d))
            B[pos, j] = sig["Buy Price"].values
            S[pos, j] = sig["Sell Price"].values
            K[pos, j] = np.where(np.isnan(rank), np.inf, rank)
        return B, S, K


# --------------------------------------------------------------------------- simulation core
def _simulate(B, S, K, C, H, index, max_days, max_pos, cap0, reinvest, cost_pct, cost_fix, lot, names):
    T, N = B.shape
    cash, pos, trades = float(cap0), {}, []
    equity, npos, invested = np.empty(T), np.zeros(T), np.zeros(T)
    lot = max(int(lot), 1)
    for t in range(T):
        exited = set()
        for j in list(pos):
            if not H[t, j]:
                continue
            sh, ent, days, et, efee = pos[j]
            days += 1
            hit = not np.isnan(S[t, j])
            if hit or (max_days is not None and days >= max_days):
                px = S[t, j] if hit else C[t, j]
                fee = cost_pct / 100.0 * sh * px + cost_fix
                cash += sh * px - fee
                trades.append((names[j], index[et], index[t], sh, ent, px,
                               sh * (px - ent) - fee - efee, days, "target/rsi" if hit else "time"))
                del pos[j]
                exited.add(j)
            else:
                pos[j][2] = days
        free = max_pos - len(pos)
        if free > 0:
            cand = [j for j in np.flatnonzero(~np.isnan(B[t])) if H[t, j] and j not in pos and j not in exited]
            if cand:
                cand.sort(key=lambda j: (K[t, j], j))
                eq_now = cash + sum(v[0] * C[t, j] for j, v in pos.items())
                for j in cand[:free]:
                    px = B[t, j]
                    slot = (eq_now if reinvest else cap0) / max_pos
                    budget = min(slot, cash) - cost_fix
                    sh = int(np.floor(budget / (px * (1 + cost_pct / 100.0)) / lot)) * lot if budget > 0 else 0
                    if sh > 0:
                        fee = cost_pct / 100.0 * sh * px + cost_fix
                        cash -= sh * px + fee
                        pos[j] = [sh, px, 0, t, fee]            # [shares, entry, days, entry_idx, entry fee]
        val = sum(v[0] * C[t, j] for j, v in pos.items())
        equity[t], npos[t], invested[t] = cash + val, len(pos), val
    cols = ["ticker", "entry_date", "exit_date", "shares", "entry", "exit", "pnl", "days", "reason"]
    return equity, npos, invested, pd.DataFrame(trades, columns=cols), len(pos)


def _stats(equity, npos, invested, trades, index, cap0):
    eq = pd.Series(equity, index=index)
    peak = np.maximum.accumulate(np.r_[cap0, equity])[1:]
    dd = (100 * (peak - equity) / peak).max() if len(equity) else np.nan
    years = max((index[-1] - index[0]).days / 365.25, 1e-9)
    final = equity[-1]
    cagr = 100 * ((final / cap0) ** (1 / years) - 1) if final > 0 else -100.0
    r = eq.pct_change().dropna()
    sharpe = r.mean() / r.std() * np.sqrt(252) if len(r) > 2 and r.std() > 0 else np.nan
    n = len(trades)
    out = dict(
        trades=n,
        ret_pct=round(100 * (final / cap0 - 1), 2),
        cagr_pct=round(cagr, 2),
        max_dd_pct=round(dd, 2),
        calmar=round(cagr / dd, 2) if dd > 0 else np.inf,
        sharpe=round(sharpe, 2) if sharpe == sharpe else np.nan,
        win_rate=round(100 * (trades["pnl"] > 0).mean(), 1) if n else np.nan,
        avg_days=round(trades["days"].mean(), 2) if n else np.nan,
        exposure_pct=round(100 * (npos > 0).mean(), 1),
        avg_positions=round(npos.mean(), 2),
        avg_invested_pct=round(100 * np.nanmean(invested / np.where(equity > 0, equity, np.nan)), 1),
    )
    return {k: (float(x) if isinstance(x, (np.floating, np.integer)) else x) for k, x in out.items()}


def _slice(arrs, a, b):
    return [x[a:b] for x in arrs]


def portfolio_backtest(data, params: Optional[dict] = None, max_positions: int = 10,
                       initial_capital: float = 100_000, reinvest: bool = False,
                       cost_pct: float = 0.0, cost_per_trade: float = 0.0, lot: int = 1,
                       start=None, end=None, strategy_fn=None, universe: Optional[Universe] = None
                       ) -> PortfolioResult:
    """
    Simulate ONE parameter set as a portfolio.

    params        : same names as the optimizer (rsi_period, rsi_entry, exit_mode, rsi_exit,
                    target_lookback, max_days); missing ones take DEFAULTS
    max_positions : slots (also accepted inside `params`)
    reinvest      : True  -> each new slot = current equity / max_positions (compounding)
                    False -> each slot = initial_capital / max_positions
    start / end   : restrict the calendar (inclusive start, exclusive end)
    """
    p = {**DEFAULTS, **(params or {})}
    max_pos = int(p.pop("max_positions", max_positions))
    uni = universe or Universe(data, strategy_fn)
    B, S, K = uni.signals(p)
    a = uni.index.searchsorted(pd.Timestamp(start)) if start is not None else 0
    b = uni.index.searchsorted(pd.Timestamp(end)) if end is not None else len(uni.index)
    Bs, Ss, Ks, Cs, Hs = _slice((B, S, K, uni.C, uni.H), a, b)
    idx = uni.index[a:b]
    eq, npos, inv, trades, n_open = _simulate(Bs, Ss, Ks, Cs, Hs, idx, p["max_days"], max_pos,
                                              initial_capital, reinvest, cost_pct, cost_per_trade,
                                              lot, uni.tickers)
    st = _stats(eq, npos, inv, trades, idx, initial_capital)
    return PortfolioResult(pd.Series(eq, index=idx, name="equity"), trades, st,
                           {**p, "max_positions": max_pos}, n_open)


# --------------------------------------------------------------------------- optimizer
def optimize_portfolio(data, grid: Dict, fixed: Optional[Dict] = None, oos_start="2021-01-01",
                       max_positions: int = 10, objective: str = "calmar",
                       initial_capital: float = 100_000, reinvest: bool = False,
                       cost_pct: float = 0.0, cost_per_trade: float = 0.0, lot: int = 1,
                       min_trades: int = 30, strategy_fn=None, top: Optional[int] = 25,
                       dedupe_results: bool = True, verbose: bool = True) -> pd.DataFrame:
    """
    Grid search where every combo is a full portfolio simulation, run separately on the
    in-sample period (before `oos_start`) and the out-of-sample period (from `oos_start`),
    each starting with fresh capital. Ranked on the in-sample `objective`
    (calmar | sharpe | cagr_pct | ret_pct | max_dd_pct[min]).

    `max_positions` may be put in the grid like any other parameter, e.g. [5, 10, 20].
    """
    uni = Universe(data, strategy_fn)
    cut = uni.index.searchsorted(pd.Timestamp(oos_start))
    sub = {"calmar": "calmar", "sharpe": "sharpe", "cagr": "cagr_pct", "cagr_pct": "cagr_pct",
           "ret_pct": "ret_pct", "max_dd": "max_dd_pct", "max_dd_pct": "max_dd_pct"}[objective]
    maximize = sub != "max_dd_pct"

    combos = build_combos(grid, fixed)
    if verbose:
        print(f"{len(combos)} combinations | {len(uni.tickers)} tickers | OOS from {pd.Timestamp(oos_start).date()} "
              f"| objective={objective} | slots={max_positions if 'max_positions' not in grid else grid['max_positions']}")
    rows, seen_cache = [], {}
    for n, p in enumerate(combos, 1):
        mp = int(p.get("max_positions", max_positions))
        sp = {k: v for k, v in p.items() if k != "max_positions"}
        key = tuple(sorted((k, v) for k, v in sp.items() if k != "max_days"))
        if key not in seen_cache:                          # signals do not depend on stop / slots
            seen_cache.clear()
            seen_cache[key] = uni.signals(sp)
        B, S, K = seen_cache[key]
        out = {**p, "max_positions": mp}
        for tag, (a, b) in (("is", (0, cut)), ("oos", (cut, len(uni.index)))):
            if b - a < 30:
                continue
            Bs, Ss, Ks, Cs, Hs = _slice((B, S, K, uni.C, uni.H), a, b)
            idx = uni.index[a:b]
            eq, npos, inv, tr, _ = _simulate(Bs, Ss, Ks, Cs, Hs, idx, sp["max_days"], mp, initial_capital,
                                             reinvest, cost_pct, cost_per_trade, lot, uni.tickers)
            for k, v in _stats(eq, npos, inv, tr, idx, initial_capital).items():
                out[f"{tag}_{k}"] = v
        rows.append(out)
        if verbose and n % 25 == 0:
            print(f"  {n}/{len(combos)}", end="\r")
    res = pd.DataFrame(rows)
    res = res[res["is_trades"] >= min_trades]
    if res.empty:
        raise ValueError("No combo reached min_trades; lower it or widen the grid.")
    res["_s"] = res[f"is_{sub}"].replace([np.inf, -np.inf], np.nan)
    res = res.sort_values("_s", ascending=not maximize).drop(columns="_s").reset_index(drop=True)
    if dedupe_results:
        pcols = list(DEFAULTS) + ["max_positions"]
        metrics = [c for c in res.columns if c not in pcols]
        res = res.drop_duplicates(subset=metrics, keep="first").reset_index(drop=True)
    return res.head(top) if top else res


# --------------------------------------------------------------------------- example
if __name__ == "__main__":
    from ifr2_universe import B3_LIQUID, load_universe

    data = load_universe(B3_LIQUID, "2015-01-01", "2026-09-30")

    # one parameter set as a portfolio, with 0.03 % per side
    cfg = dict(rsi_period=2, rsi_entry=15, exit_mode="rsi", rsi_exit=80, max_days=9)
    r = portfolio_backtest(data, cfg, max_positions=10, cost_pct=0.03, start="2021-01-01")
    print(r.stats); print(r.yearly())

    # grid search with slots as a parameter
    grid = {
        "rsi_period": [2, 3],
        "rsi_entry": (10, 30, 5),
        "exit_mode": ["target", "rsi"],
        "rsi_exit": [70, 80],
        "max_days": [None, 5, 9],
        "max_positions": [5, 10, 20],
    }
    res = optimize_portfolio(data, grid, oos_start="2021-01-01", cost_pct=0.03)
    cols = ["rsi_period", "rsi_entry", "exit_mode", "rsi_exit", "max_days", "max_positions",
            "is_cagr_pct", "is_max_dd_pct", "is_calmar", "oos_cagr_pct", "oos_max_dd_pct", "oos_calmar", "oos_trades"]
    print(res[cols].to_string())
