"""
Multi-ticker optimization for the IFR2 / RSI strategy.

Idea: instead of asking "which parameters were best on ONE stock", ask
"which parameters work across MANY stocks". A combo that is only good on one
ticker is probably luck; one that is good on most of them is probably an edge.

Three layers of validation are built in
---------------------------------------
    time split    : every ticker shares the same out-of-sample start date
    ticker split  : a random share of tickers (`holdout`) is never used for ranking
    both          : held-out tickers in the out-of-sample period = strictest test

Result columns (one row per parameter combo)
    is_*    fit tickers, in-sample period        <- combos are RANKED on this
    oos_*   fit tickers, out-of-sample period
    held_*  held-out tickers, out-of-sample period  <- the number to trust most
    n = tickers used | med_pct = median profit % | med_calmar | pos_% = % of tickers profitable
    worst = worst ticker's profit %

Clusters
--------
`ticker_features` + `cluster_tickers` group tickers by behaviour measured ONLY on the
in-sample period (volatility, mean reversion, trend, ...). `optimize_by_cluster` then
optimizes each group separately. Compare the cluster-specific winners against the global
winner on the `held_*` columns: if they don't beat it there, the clusters add nothing.
"""
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Optional

import numpy as np
import pandas as pd
import talib

from ifr2_optimizer import optimize

# Example list only - supply your own. Today's constituents carry SURVIVORSHIP BIAS
# (delisted / merged names are missing), which flatters mean-reversion results.
B3_LIQUID = [
    "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "BBAS3.SA", "ABEV3.SA", "WEGE3.SA",
    "RENT3.SA", "LREN3.SA", "MGLU3.SA", "SUZB3.SA", "GGBR4.SA", "CSNA3.SA", "USIM5.SA",
    "JBSS3.SA", "RADL3.SA", "RAIL3.SA", "EQTL3.SA", "CMIG4.SA", "ELET3.SA", "TOTS3.SA",
    "PRIO3.SA", "CSAN3.SA", "BBSE3.SA", "SBSP3.SA", "VIVT3.SA", "B3SA3.SA", "BRAP4.SA",
    "GOAU4.SA", "CYRE3.SA",
]


# --------------------------------------------------------------------------- data
def load_universe(tickers, start, end, min_rows=750, loader=None) -> Dict[str, pd.DataFrame]:
    """Download each ticker; silently skip failures / too-short histories (and say so)."""
    if loader is None:
        from ifr2_talib import load as loader
    data = {}
    for t in tickers:
        try:
            d = loader(t, start, end).dropna(subset=["Open", "High", "Close", "Adj Close"])
            if len(d) >= min_rows:
                data[t] = d
            else:
                print(f"skip {t}: only {len(d)} rows")
        except Exception as e:                      # noqa: BLE001
            print(f"skip {t}: {e}")
    return data


# --------------------------------------------------------------------------- core
def _run_one(args):
    t, df, grid, fixed, kw = args
    res = optimize(df, grid, fixed=fixed, min_trades=0, verbose=False, **kw)
    res.insert(0, "ticker", t)
    return res


def _agg(d: pd.DataFrame, pre: str, min_trades: int) -> pd.DataFrame:
    d = d[d[pre + "trades"] >= min_trades].copy()
    d[pre + "calmar"] = d[pre + "calmar"].replace([np.inf, -np.inf], np.nan)
    g = d.groupby("combo")
    return pd.DataFrame({
        "n": g["ticker"].nunique(),
        "med_pct": g[pre + "profit_pct"].median(),
        "med_calmar": g[pre + "calmar"].median(),
        "pos_%": g[pre + "profit_pct"].apply(lambda s: (s > 0).mean() * 100),
        "worst": g[pre + "profit_pct"].min(),
    })


def optimize_universe(
    data: Dict[str, pd.DataFrame],
    grid: Dict,
    fixed: Optional[Dict] = None,
    oos_start=None,
    oos_frac: float = 0.4,
    holdout: float = 0.3,
    seed: int = 0,
    rank_by: str = "is_med_calmar",
    min_trades_is: int = 15,
    min_trades_oos: int = 8,
    min_tickers_frac: float = 0.6,
    top: Optional[int] = 25,
    n_jobs: int = 1,
    verbose: bool = True,
    **opt_kw,                      # forwarded to optimize(): cost_per_trade, lot, strategy_fn, ...
) -> pd.DataFrame:
    """
    Evaluate every combo on every ticker, aggregate across tickers, rank on the
    fit-ticker in-sample period and report out-of-sample / held-out-ticker results.

    oos_start : common date where out-of-sample begins (default: the date that leaves
                `oos_frac` of the pooled calendar out-of-sample)
    holdout   : share of tickers never used for ranking (0 disables the ticker split)
    """
    opt_kw.setdefault("lot", 1)    # fractional lots: avoids penalising high-priced stocks
    tickers = list(data)
    if oos_start is None:
        allidx = pd.DatetimeIndex(sorted(set().union(*[d.index for d in data.values()])))
        oos_start = allidx[int(len(allidx) * (1 - oos_frac))]
    oos_start = pd.Timestamp(oos_start)

    rng = np.random.default_rng(seed)
    n_hold = int(round(len(tickers) * holdout))
    held = set(rng.choice(tickers, n_hold, replace=False)) if n_hold else set()
    fit = [t for t in tickers if t not in held]
    if verbose:
        print(f"{len(tickers)} tickers ({len(fit)} fit / {len(held)} held-out) | "
              f"OOS starts {oos_start.date()} | ranking on {rank_by}")

    jobs = [(t, data[t], grid, fixed, {**opt_kw, "oos_start": oos_start}) for t in tickers
            if data[t].index[0] < oos_start - pd.Timedelta(days=365)]   # need real IS history
    if n_jobs > 1:
        with ProcessPoolExecutor(n_jobs) as ex:
            parts = list(ex.map(_run_one, jobs))
    else:
        parts = []
        for i, j in enumerate(jobs, 1):
            parts.append(_run_one(j))
            if verbose:
                print(f"  [{i}/{len(jobs)}] {j[0]}", end="\r")
    long = pd.concat(parts, ignore_index=True)

    param_cols = list(long.columns[1:list(long.columns).index("trades")])
    P = long[param_cols].astype(object).where(long[param_cols].notna(), "-")
    long["combo"] = P.astype(str).agg("|".join, axis=1)
    params = long.drop_duplicates("combo").set_index("combo")[param_cols]

    is_fit = long["ticker"].isin(fit)
    parts = [
        _agg(long[is_fit], "", min_trades_is).add_prefix("is_"),
        _agg(long[is_fit], "oos_", min_trades_oos).add_prefix("oos_"),
    ]
    if held:
        parts.append(_agg(long[~is_fit], "oos_", min_trades_oos).add_prefix("held_"))
    out = params.join(pd.concat(parts, axis=1), how="inner")

    out = out[out["is_n"] >= max(3, min_tickers_frac * len(fit))]
    if out.empty:
        raise ValueError("No combo has enough tickers with min_trades; lower min_trades_is / min_tickers_frac.")
    out = out.sort_values(rank_by, ascending=False).reset_index(drop=True)
    return out.head(top) if top else out


# --------------------------------------------------------------------------- clustering
def ticker_features(data: Dict[str, pd.DataFrame], until=None) -> pd.DataFrame:
    """Behavioural features per ticker, measured only BEFORE `until` (no look-ahead)."""
    rows = {}
    for t, d in data.items():
        if until is not None:
            d = d[d.index < pd.Timestamp(until)]
        px = d["Adj Close"].astype(float)
        r = px.pct_change().dropna()
        rsi2 = talib.RSI(px.values, timeperiod=2)
        rows[t] = dict(
            vol=r.std() * np.sqrt(252),                                   # annualised volatility
            autocorr1=r.autocorr(1),                                      # <0 = mean-reverting
            trend=np.log(px.iloc[-1] / px.iloc[0]) / (len(px) / 252),     # annualised log drift
            range_pct=((d["High"] - d["Low"]) / d["Close"]).mean(),       # average daily range
            dip_freq=np.nanmean(rsi2 < 10),                               # how often RSI(2) < 10
        )
    return pd.DataFrame(rows).T


def cluster_tickers(features: pd.DataFrame, k: int = 3, seed: int = 0) -> pd.Series:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    X = StandardScaler().fit_transform(features.fillna(features.median()))
    lab = KMeans(n_clusters=k, n_init=20, random_state=seed).fit_predict(X)
    return pd.Series(lab, index=features.index, name="cluster")


def optimize_by_cluster(data, grid, labels: pd.Series, min_cluster_size: int = 6, **kw):
    """Run optimize_universe separately inside each cluster -> {cluster: table}."""
    out = {}
    for c, members in labels.groupby(labels):
        names = [t for t in members.index if t in data]
        if len(names) < min_cluster_size:
            print(f"cluster {c}: only {len(names)} tickers, skipped")
            continue
        print(f"\ncluster {c}: {names}")
        out[c] = optimize_universe({t: data[t] for t in names}, grid, **kw)
    return out


# --------------------------------------------------------------------------- example
if __name__ == "__main__":
    data = load_universe(B3_LIQUID, "2015-01-01", "2026-09-30")

    grid = {
        "rsi_period": (2, 4, 1),
        "rsi_entry": (10, 40, 5),
        "exit_mode": ["target", "rsi", "target_or_rsi"],
        "rsi_exit": (50, 80, 10),
        "max_days": [None, 3, 5, 7, 9],
    }
    cols = ["rsi_period", "rsi_entry", "exit_mode", "rsi_exit", "max_days",
            "is_med_pct", "is_pos_%", "oos_med_pct", "oos_pos_%", "held_n", "held_med_pct", "held_pos_%", "held_worst"]

    # 1) one set of parameters for the whole universe
    res = optimize_universe(data, grid, oos_start="2021-01-01", holdout=0.3,
                            cost_per_trade=5.0, n_jobs=4)
    print(res[cols].to_string())

    # 2) behavioural clusters (features use only pre-OOS data), optimized separately
    labels = cluster_tickers(ticker_features(data, until="2021-01-01"), k=3)
    print(labels.sort_values().to_string())
    by_cluster = optimize_by_cluster(data, grid, labels, oos_start="2021-01-01",
                                     holdout=0.3, cost_per_trade=5.0, n_jobs=4)
    for c, r in by_cluster.items():
        print(f"\n=== cluster {c} ===")
        print(r[cols].head(10).to_string())
