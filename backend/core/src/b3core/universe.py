"""Run one strategy config over many tickers. Pure: candles and CDI rates in, a table out."""

from collections.abc import Callable, Mapping
from typing import Any, Protocol

import pandas as pd

from b3core.benchmark import compare_with_cdi, compare_with_index, index_equity
from b3core.ifr2 import Ifr2Config, run_ifr2
from b3core.metrics import Metrics
from b3core.portfolio import buy_and_hold_equity, equity_drawdown, summarize_portfolio
from b3core.score import score_v1
from b3core.turtle import TurtleConfig


class _Run(Protocol):
    """What a strategy result offers the scan: its metrics and the length of the data."""

    @property
    def metrics(self) -> Metrics: ...

    @property
    def years(self) -> float | None: ...


def scan_universe(
    data: Mapping[str, pd.DataFrame],
    config: Ifr2Config | TurtleConfig,
    cdi_rates: pd.Series,
    *,
    min_candles: int = 250,
    index_closes: pd.Series | None = None,
    runner: Callable[[pd.DataFrame, Any], _Run] = run_ifr2,
) -> pd.DataFrame:
    """One row per ticker, in the order given: the metrics, `score_v1` and the benchmarks.

    Each ticker is compared, over its own window, with the CDI and with buying and holding the
    ticker (docs/cdi.md, docs/ibov.md). With `index_closes` (the IBOV close by date) it is also
    compared with holding the index. Tickers with fewer than `min_candles` candles are left out
    and named in `table.attrs["skipped"]`. `runner` runs the strategy: `run_ifr2` for an
    `Ifr2Config` (the default), `run_turtle` for a `TurtleConfig`.
    """
    rows: dict[str, dict[str, float | int | bool]] = {}
    skipped: list[str] = []
    for ticker, candles in data.items():
        if len(candles) < min_candles:
            skipped.append(ticker)
            continue
        result = runner(candles, config)
        m = result.metrics
        row: dict[str, float | int | bool] = {
            "n_trades": m.n_trades,
            "win_rate": m.win_rate,
            "net_pnl": m.net_pnl,
            "result": m.result,
            "profit_factor": m.profit_factor,
            "ev": m.ev,
            "max_drawdown": m.max_drawdown,
            "score_v1": score_v1(m),
        }
        if m.cagr is not None and result.years is not None:
            cdi = compare_with_cdi(m.cagr, result.years, cdi_rates, candles["ts"])
            row |= {
                "years": result.years,
                "cagr": m.cagr,
                "max_equity_drawdown": m.max_equity_drawdown or 0.0,
                "calmar": m.calmar if m.calmar is not None else float("nan"),
                "cdi_cagr": cdi.cdi_cagr,
                "excess": cdi.excess,
                "beats_cdi": cdi.beats_cdi,
            }
            capital = config.capital_brl
            held = summarize_portfolio(
                buy_and_hold_equity({ticker: candles}, capital), capital, cdi_rates
            )
            row |= {
                "bh_cagr": held.cagr,
                "bh_excess": m.cagr - held.cagr,
                "beats_bh": m.cagr > held.cagr,
                "bh_max_equity_drawdown": held.max_equity_drawdown,
                "bh_calmar": held.calmar,
            }
            if index_closes is not None:
                ibov = compare_with_index(m.cagr, result.years, index_closes, candles["ts"])
                curve = index_equity(index_closes, candles["ts"], capital)
                row |= {
                    "ibov_cagr": ibov.cagr,
                    "ibov_excess": ibov.excess,
                    "beats_ibov": ibov.beats,
                    "ibov_max_equity_drawdown": equity_drawdown(curve, capital),
                }
        rows[ticker] = row
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.attrs["skipped"] = skipped
    return table


def rank_across_tickers(
    tables: Mapping[str, pd.DataFrame],
    params: list[str],
    *,
    min_trades: int = 0,
    min_tickers: int = 1,
) -> pd.DataFrame:
    """Rank parameter combinations by how they do across tickers, best first.

    `tables` maps a ticker to its trials (`OptimizationResult.trials_table()`: the parameter
    columns plus `objective`, `result` and `n_trades`). A ticker counts for a combination only
    with at least `min_trades` trades. A combination needs `min_tickers` tickers to be ranked.
    The key is the median objective, so one lucky ticker cannot carry a combination.
    """
    frames = []
    for ticker, table in tables.items():
        kept = table[table["n_trades"] >= min_trades]
        frames.append(kept.assign(ticker=ticker))
    long = pd.concat(frames, ignore_index=True)
    # None and NaN are values (max_days off), and groupby would silently drop them
    keys = long[params].astype(object).where(long[params].notna(), "none")
    long["_combo"] = keys.astype(str).agg("|".join, axis=1)
    grouped = long.groupby("_combo", sort=False)
    ranked = grouped.agg(
        n_tickers=("ticker", "nunique"),
        median_objective=("objective", "median"),
        mean_objective=("objective", "mean"),
        pos_share=("result", lambda r: float((r > 0).mean())),
        median_result=("result", "median"),
        worst_result=("result", "min"),
    )
    first = long.drop_duplicates("_combo").set_index("_combo")[params]
    ranked = first.join(ranked)
    ranked = ranked[ranked["n_tickers"] >= min_tickers]
    return ranked.sort_values(
        ["median_objective", "n_tickers"], ascending=[False, False], kind="stable"
    ).reset_index(drop=True)
