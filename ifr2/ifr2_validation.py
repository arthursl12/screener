"""
Validation tools for the IFR2 optimizer (all NEW functions - nothing existing is changed).

    best_k(features)            how many clusters? silhouette + stability across seeds
    dedupe(res)                 drop rows whose results are identical (inert parameters)
    trade_log(sig, ...)         the backtester again, but returning every trade with dates
    yearly(data, configs)       profit per calendar year for fixed parameter sets
    kfold_tickers(data, grid)   pick the winner WITHOUT a ticker, test it ON that ticker
"""
from typing import Dict, Optional

import numpy as np
import pandas as pd

from ifr2_optimizer import DEFAULTS, make_default_strategy, optimize
from ifr2_universe import _agg, _run_one

PARAM_COLS = tuple(DEFAULTS)


# --------------------------------------------------------------------------- clusters
def best_k(features: pd.DataFrame, k_range=range(2, 8), n_seeds: int = 10,
           seed: int = 0, min_size: int = 4) -> pd.DataFrame:
    """
    For each k: mean silhouette (higher = cleaner groups), stability (agreement between
    runs with different random seeds, 1 = identical), and the smallest cluster size.
    `suggested_k` (in .attrs) = best silhouette among k whose smallest cluster >= min_size
    AND stability >= 0.7. With few tickers treat this as a hint, not a proof.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score, silhouette_score
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(features.fillna(features.median()))
    rows = []
    for k in k_range:
        runs = [KMeans(n_clusters=k, n_init=10, random_state=seed + s).fit(X) for s in range(n_seeds)]
        sil = np.mean([silhouette_score(X, r.labels_) for r in runs])
        stab = np.mean([adjusted_rand_score(runs[0].labels_, r.labels_) for r in runs[1:]])
        best = min(runs, key=lambda r: r.inertia_)
        rows.append(dict(k=k, silhouette=round(sil, 3), stability=round(stab, 3),
                         smallest=int(np.bincount(best.labels_).min())))
    out = pd.DataFrame(rows).set_index("k")
    ok = out[(out["smallest"] >= min_size) & (out["stability"] >= 0.7)]
    out.attrs["suggested_k"] = int(ok["silhouette"].idxmax()) if len(ok) else None
    print(f"suggested k = {out.attrs['suggested_k']}  "
          f"(needs smallest cluster >= {min_size} and stability >= 0.7)")
    return out


# --------------------------------------------------------------------------- housekeeping
def dedupe(res: pd.DataFrame, params=PARAM_COLS) -> pd.DataFrame:
    """Drop rows whose metric columns are all identical to a better-ranked row
    (e.g. the RSI exit level that never fires in target_or_rsi mode)."""
    metrics = [c for c in res.columns if c not in params]
    return res.drop_duplicates(subset=metrics, keep="first").reset_index(drop=True)


# --------------------------------------------------------------------------- trade log
def trade_log(sig: pd.DataFrame, max_days=None, initial_capital=10_000, reinvest=False,
              cost_per_trade=0.0, lot=1, cost_pct=0.0) -> pd.DataFrame:
    """Same logic as ifr2_optimizer.run_backtest, but returns one row per trade."""
    buy, sell, close = sig["Buy Price"].values, sig["Sell Price"].values, sig["Close"].values
    idx = sig.index
    cap, rows = initial_capital, []
    ongoing, days, entry, shares, ei = False, 0, 0.0, 0, 0
    for i in range(len(sig)):
        if ongoing:
            days += 1
            hit = not np.isnan(sell[i])
            if hit or (max_days is not None and days >= max_days):
                px = sell[i] if hit else close[i]
                pnl = (shares * (px - entry) - 2 * cost_per_trade
                       - cost_pct / 100.0 * shares * (entry + px))
                rows.append(dict(entry_date=idx[ei], exit_date=idx[i], shares=shares,
                                 entry=entry, exit=px, pnl=pnl, days=days,
                                 reason="target/rsi" if hit else "time"))
                cap += pnl
                ongoing = False
        elif not np.isnan(buy[i]):
            base = cap if reinvest else initial_capital
            shares = int(np.floor(base / buy[i] / max(lot, 1))) * max(lot, 1)
            entry, days, ei, ongoing = buy[i], 0, i, shares > 0
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- year by year
def yearly(data: Dict[str, pd.DataFrame], configs, initial_capital=10_000, lot=1,
           cost_per_trade=0.0, cost_pct=0.0, strategy_fn=None) -> Dict[str, pd.DataFrame]:
    """
    Calendar-year performance of fixed parameter sets across all tickers.

    configs : one params dict, or {"name": params, ...} to compare several side by side
    Returns {"median": ..., "pos": ..., "trades": ...}, each a (year x config) table:
        median = median over tickers of that year's profit as % of `initial_capital`
        pos    = % of tickers (with data that year) that made money
        trades = total trades closed in that year
    A trade belongs to the year it was CLOSED.
    """
    if not (isinstance(configs, dict) and configs
            and all(isinstance(v, dict) for v in configs.values())):
        configs = {"config": configs}              # a single params dict
    med, pos, trd = {}, {}, {}
    strategies = {t: (strategy_fn or make_default_strategy(d)) for t, d in data.items()}
    for name, params in configs.items():
        p = {**DEFAULTS, **params}
        sig_p = {k: v for k, v in p.items() if k != "max_days"}
        per = {}                                    # ticker -> Series(year -> pnl %)
        cnt = {}
        for t, d in data.items():
            sig = strategies[t](d, **sig_p)
            if "Close" not in sig:
                sig = sig.assign(Close=d["Close"].values)
            log = trade_log(sig, p["max_days"], initial_capital, False, cost_per_trade, lot, cost_pct)
            yrs = pd.Index(sorted(set(d.index.year)))
            if len(log):
                y = log.groupby(log["exit_date"].dt.year)["pnl"].sum() / initial_capital * 100
                c = log.groupby(log["exit_date"].dt.year).size()
            else:
                y, c = pd.Series(dtype=float), pd.Series(dtype=int)
            per[t] = y.reindex(yrs).fillna(0.0)        # years with data but no trades = 0 %
            cnt[t] = c.reindex(yrs).fillna(0)
        P = pd.DataFrame(per)                          # NaN where the ticker has no data that year
        med[name] = P.median(axis=1)
        pos[name] = P.apply(lambda r: (r.dropna() > 0).mean() * 100, axis=1)
        trd[name] = pd.DataFrame(cnt).sum(axis=1)
    out = {"median": pd.DataFrame(med).round(2), "pos": pd.DataFrame(pos).round(1),
           "trades": pd.DataFrame(trd).astype(int)}
    for v in out.values():
        v.index.name = "year"
    return out


# --------------------------------------------------------------------------- k-fold over tickers
def build_long(data, grid, fixed=None, oos_start=None, oos_frac=0.4, n_jobs=1,
               verbose=True, **opt_kw):
    """Every combo x every ticker, evaluated once (the expensive step). Returns (long, oos_start)."""
    opt_kw.setdefault("lot", 1)
    if oos_start is None:
        allidx = pd.DatetimeIndex(sorted(set().union(*[d.index for d in data.values()])))
        oos_start = allidx[int(len(allidx) * (1 - oos_frac))]
    oos_start = pd.Timestamp(oos_start)
    jobs = [(t, d, grid, fixed, {**opt_kw, "oos_start": oos_start}) for t, d in data.items()
            if d.index[0] < oos_start - pd.Timedelta(days=365)]
    if n_jobs > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(n_jobs) as ex:
            parts = list(ex.map(_run_one, jobs))
    else:
        parts = []
        for i, j in enumerate(jobs, 1):
            parts.append(_run_one(j))
            if verbose:
                print(f"  [{i}/{len(jobs)}] {j[0]}", end="\r")
    long = pd.concat(parts, ignore_index=True)
    pc = list(long.columns[1:list(long.columns).index("trades")])
    P = long[pc].astype(object).where(long[pc].notna(), "-")
    long["combo"] = P.astype(str).agg("|".join, axis=1)
    long.attrs["param_cols"] = pc
    return long, oos_start


def kfold_tickers(data, grid, k: int = 5, repeats: int = 1, seed: int = 0, fixed=None,
                  oos_start=None, oos_frac: float = 0.4, rank_by: str = "is_med_calmar",
                  min_trades_is: int = 15, min_trades_oos: int = 8,
                  min_tickers_frac: float = 0.6, n_jobs: int = 1, long=None,
                  verbose: bool = True, **opt_kw):
    """
    Cross-validation over TICKERS. Tickers are split into k folds; for each fold the
    winning combo is chosen on the OTHER folds (in-sample period only) and then measured
    on the held-out fold in the out-of-sample period. Every ticker is held out once per
    repeat, so each ticker gets one honest out-of-sample number.

    Returns dict:
        per_ticker : each ticker's OOS profit % using the combo chosen without it
        winners    : the combo chosen in each fold/repeat (are they the same? = stability)
        summary    : median / % profitable / worst over tickers, vs a "typical combo" baseline
        long       : the expensive per-ticker x combo table (pass back via long= to reuse)
    """
    if long is None:
        long, oos_start = build_long(data, grid, fixed, oos_start, oos_frac, n_jobs, verbose, **opt_kw)
    pc = long.attrs.get("param_cols") or list(long.columns[1:list(long.columns).index("trades")])
    params = long.drop_duplicates("combo").set_index("combo")[pc]
    tickers = sorted(long["ticker"].unique())

    recs, wins = [], []
    for rep in range(repeats):
        order = np.random.default_rng(seed + rep).permutation(tickers)
        for f, held in enumerate(np.array_split(order, k)):
            held = set(held)
            fit_rows = long[~long["ticker"].isin(held)]
            agg = _agg(fit_rows, "", min_trades_is).add_prefix("is_")
            agg = agg[agg["is_n"] >= max(3, min_tickers_frac * (len(tickers) - len(held)))]
            if agg.empty:
                continue
            win = agg[rank_by].idxmax()
            h = long[(long["combo"] == win) & (long["ticker"].isin(held))]
            for _, r in h.iterrows():
                recs.append(dict(rep=rep, fold=f, ticker=r["ticker"], combo=win,
                                 held_oos_pct=r["oos_profit_pct"] if r["oos_trades"] >= min_trades_oos else np.nan,
                                 held_oos_trades=r["oos_trades"],
                                 held_is_pct=r["profit_pct"]))
            wins.append({"rep": rep, "fold": f, "fit_is_med_pct": agg.loc[win, "is_med_pct"],
                         "fit_is_pos_%": agg.loc[win, "is_pos_%"], **params.loc[win].to_dict()})
    rec = pd.DataFrame(recs)
    per_ticker = rec.groupby("ticker")[["held_is_pct", "held_oos_pct"]].median().round(2)

    ok = long[long["oos_trades"] >= min_trades_oos]
    base = ok.groupby("ticker")["oos_profit_pct"].median()      # what a typical combo does per ticker
    s = per_ticker["held_oos_pct"].dropna()
    summary = pd.DataFrame({
        "selected combo (honest)": dict(n_tickers=len(s), median_pct=s.median(),
                                        mean_pct=s.mean(), pos_pct=(s > 0).mean() * 100, worst_pct=s.min()),
        "typical combo (baseline)": dict(n_tickers=base.size, median_pct=base.median(),
                                         mean_pct=base.mean(), pos_pct=(base > 0).mean() * 100,
                                         worst_pct=base.min()),
    }).round(2)
    winners = pd.DataFrame(wins)
    if verbose:
        print(f"\n{k}-fold x {repeats} over {len(tickers)} tickers | OOS starts {pd.Timestamp(oos_start).date() if oos_start is not None else '?'}")
        print(summary.to_string())
        if len(winners):
            W = winners[pc].astype(object).where(winners[pc].notna(), "-")
            same = W.astype(str).agg("|".join, axis=1).value_counts()
            print(f"distinct winners: {len(same)} of {len(winners)} folds (1 = very stable choice)")
    return dict(per_ticker=per_ticker, winners=winners, summary=summary, long=long)
