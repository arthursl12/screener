"""Run one IFR2 config over many tickers. Pure: candles and CDI rates in, a table out."""

from collections.abc import Mapping

import pandas as pd

from b3core.benchmark import compare_with_cdi
from b3core.ifr2 import Ifr2Config, run_ifr2
from b3core.score import score_v1


def scan_universe(
    data: Mapping[str, pd.DataFrame],
    config: Ifr2Config,
    cdi_rates: pd.Series,
    *,
    min_candles: int = 250,
) -> pd.DataFrame:
    """One row per ticker, in the order given: the metrics, `score_v1` and the CDI comparison.

    Each ticker is compared with the CDI over its own window. Tickers with fewer than
    `min_candles` candles are left out and named in `table.attrs["skipped"]`.
    """
    rows: dict[str, dict[str, float | int | bool]] = {}
    skipped: list[str] = []
    for ticker, candles in data.items():
        if len(candles) < min_candles:
            skipped.append(ticker)
            continue
        result = run_ifr2(candles, config)
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
        rows[ticker] = row
    table = pd.DataFrame.from_dict(rows, orient="index")
    table.attrs["skipped"] = skipped
    return table
