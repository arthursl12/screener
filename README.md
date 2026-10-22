# B3 Backtester

A notebook-first backtester for B3 stocks and BDRs, built to answer one question honestly: **is there a trading strategy here that beats leaving the money in the CDI?**

> **Disclaimer.** This project is educational and is not investment advice. Backtest and optimizer results are historical and do not predict future results.

## Status: on hold (Oct 22, 2026)

**The answer was no.** Across three strategies, about 50 liquid Brazilian stocks and BDRs, and 14 years of daily data, nothing survived all of these at once: out-of-sample testing, realistic fills, no hidden leverage, and no selection bias. A fully invested CDI had less risk than anything found here, and the one result that beat it out-of-sample (a basket of BDRs) did worse than simply holding the same BDRs, on a short sample in a bull market. The project is paused, and the money stays in the CDI.

The engineering is complete for what it set out to do, and the negative result is the result. The details are below.

## What the backtests found

All numbers come from the notebooks in `notebooks/` (published with outputs). "Out-of-sample" means the last 30% of the history, from May 2022. The CDI ran at roughly 13% a year in that window and the IBOV at about 15%. Prices are raw Yahoo Finance closes, with the 0.03% B3 fee on every fill and no taxes.

| Question | Result |
| --- | --- |
| **IFR2** (RSI 2 mean reversion), one fixed setting, 29 liquid Ibovespa names | **None** beat the CDI, in-sample or out-of-sample. Median out-of-sample excess over the CDI: −11 points. |
| IFR2 on the ten most traded BDRs, out-of-sample | 2.9% a year (7.6% with three times the risk), against 15% for the IBOV. |
| **Turtle** (20-day breakout, ATR pyramiding, from a TradingView script), 30 names | 8 of 30 beat the CDI out-of-sample. Median excess: −13 points. With the realistic next-open fill the median CAGR is −1.7%. |
| Turtle as an equal-split portfolio of the 30 names | 9.9% in-sample, **7.7% out-of-sample** against about 13% for the CDI. |
| Does pyramiding help? | In-sample yes, out-of-sample no. 4 units instead of 1 raised the median drawdown from 23% to 54% and the money needed from about 1× to 3.7× the capital, while the median CAGR fell from 2.2% to 0.3%. |
| Can past profit pick the stocks? | No. The ranking correlation between three periods is +0.02, −0.07 and −0.36, and at five rolling cuts it averages −0.11. A yearly walk-forward pick beat the average in 9 of 12 years, but only at the 62nd to 69th percentile of random picks. |
| The nine stocks that "looked promising" | 12.8% a year against 9.8% for the CDI, **but they were chosen on the same history**. Picked cleanly from earlier data, the same kind of selection landed at the 47th, 55th and 71st percentile of random picks. |
| Turtle on the ten most traded BDRs, out-of-sample | 23% a year, about 10 points over the CDI. Buy and hold made 44%, the sample is ten correlated US mega-caps in a bull run, and the positions needed at least 3.4× the capital. |

Two caveats shape every number above. First, **there is no capital cap**: Turtle's positions are several times its stated capital, so a CAGR "on capital" hides leverage, and every table shows the peak money in the position next to the return. Second, a backtest that is fully invested can be compared with the CDI, but a strategy that is in the market part of the time cannot be compared fairly without a rule for idle cash, and that rule was never specified.

Exploratory work that is not kept in the repo reached the same conclusion: changing the position size, adding a trend filter or a lower RSI entry, and re-picking tickers each year did not turn any setting into one that beat the CDI at a deployable size.

## What is built

- **`backend/core` (`b3core`)**: a pure domain package, with no web or database code. Deterministic: the same input gives the same output, and randomness only from seeded generators.
  - Engines for **123 de compra** (swing and day-trade mode), **IFR2** and **Turtle** (with pyramiding, a close-based stop, and fills at the signal close or the next open).
  - Metrics, a composite `score_v1` (`docs/score.md`), and equity-curve based drawdown and Calmar.
  - Benchmarks: the CDI, the IBOV and buy and hold, with strict checks (a missing CDI day is an error that names the date, never a silent fill).
  - Equal-split portfolios of independent slots, and a scan of one setting over many tickers.
  - A parameter optimizer: grid and random search, a content-addressed result cache (`run_hash`), a SQLite registry of runs and trials, an in-sample against out-of-sample split with an overfitting flag, and a neighbourhood heatmap.
- **`backend/report` (`b3report`)**: Plotly charts for notebooks.
- **`notebooks/`**: all analysis, with no trading logic in them.
- **`docs/`**: the specification of every trading rule (`docs/brief.md`), the benchmark specs, data notes, and a learning log.
- **`tools/check_notebook_outputs.py`**: a guard that refuses a published notebook that prints raw candles.

Not built: 123 de venda, a genetic-algorithm optimizer, the API, the database and the frontend (the brief's later phases).

## How it was built

- **Spec first.** No trading rule is implemented until it is written in `docs/brief.md`; ambiguities are listed as open questions instead of guessed. Several rules were reverse-engineered against real platform trades, and the differences are documented.
- **Tests first.** 378 tests: golden cases whose every number is worked out by hand in the spec, Hypothesis property tests (no look-ahead through prefix invariance, no overlapping trades, determinism, costs only lower PnL), parity tests against a research prototype and TA-Lib, and manual mutation checks that confirmed the tests catch a deliberate bug.
- **Honest reporting.** In-sample against out-of-sample everywhere, random-subset baselines for any "pick the best" step, and survivorship, leverage and single-regime caveats stated next to the numbers.
- **Built with Claude Code as a tutor and reviewer.** `CLAUDE.md` defines a learning mode (the owner writes the core code, the assistant teaches and reviews). Where the assistant wrote code at the owner's request, the commits say so.

## Run it

```bash
cd backend && uv sync --group ifr2   # Python 3.12; the ifr2 group adds yfinance, scikit-learn, TA-Lib
make test                            # pytest: golden, property-based and unit tests
make lint                            # ruff, mypy and the notebook output guard
make notebook                        # JupyterLab on notebooks/
```

The notebooks download daily candles from Yahoo Finance and the CDI from the Central Bank (`samples/` is a gitignored cache; **the data itself is never committed**). The 123 de compra notebook reads MT5 "export bars" CSV files that you place in `samples/` yourself. The Plotly charts are interactive in JupyterLab or in an HTML export (`jupyter nbconvert --to html`); GitHub does not render them.

## Notebooks

| Notebook | What it does | Outputs |
| --- | --- | --- |
| `turtle_deep_dive.ipynb` | The nine shortlisted stocks in detail: portfolio view, per-stock charts and statistics, a selection check, and a dropdown over all candidates | published |
| `turtle_stocks.ipynb` | Which stocks suit Turtle, and whether the ranking holds up | published |
| `turtle.ipynb` | Turtle on liquid Ibovespa names and BDRs: fill rules, pyramiding, portfolios | published |
| `ifr2_liquid.ipynb` | IFR2 on liquid Ibovespa names and BDRs | published |
| `ifr2_universe.ipynb`, `ifr2.ipynb` | IFR2 across tickers, the optimizer, clusters, ticker k-fold | stripped |
| `123_de_compra.ipynb` | One ticker with 123 de compra, checked against real platform trades | stripped |

## Limitations

Survivorship bias (the tickers are today's liquid names, from a list written from memory), correlated tickers and one or two market regimes, raw prices with dividends ignored, no taxes, no slippage beyond the fee, no shared-cash rule for simultaneous signals, and the missing capital cap. The ticker lists are drafts, not B3's verified index composition. No license has been chosen.

## Documentation

[`docs/brief.md`](docs/brief.md) is the source of truth for the architecture, the trading rules and the open questions. See also [`docs/cdi.md`](docs/cdi.md), [`docs/ibov.md`](docs/ibov.md), [`docs/score.md`](docs/score.md), [`docs/data-notes.md`](docs/data-notes.md) and [`docs/learning-log.md`](docs/learning-log.md).
