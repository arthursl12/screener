# B3 Backtester

A notebook-first backtester for B3 stocks and BDRs (and, in a proof of concept, the WIN and WDO mini futures), built to answer one question honestly: **is there a trading strategy here that beats leaving the money in the CDI?**

> **Disclaimer.** This project is educational and is not investment advice. Backtest and optimizer results are historical and do not predict future results.

## Status: on hold (Oct 22, 2026)

**The answer was no.** Across three strategies, about 50 liquid Brazilian stocks and BDRs, and 14 years of daily data, nothing survived all of these at once: out-of-sample testing, realistic fills, no hidden leverage, and no selection bias. A fully invested CDI had less risk than anything found here, and the one result that beat it out-of-sample (a basket of BDRs) did worse than simply holding the same BDRs, on a short sample in a bull market. The project is paused, and the money stays in the CDI.

The engineering is complete for what it set out to do, and the negative result is the result. The details are below.

> **Needs further investigation (Nov 2026).** A small proof of concept on the branch `feat/momentum-tilt` (not merged) tests a different idea from the three strategies above: a monthly momentum tilt on the 20 most liquid stocks, inspired by a public Romanian index. Its first run, with settings fixed in advance, **failed the pass rule that was written before the run**. It beat the CDI, as plain equal-weight did on the same survivor list, but its edge over equal-weight was not distinguishable from noise (monthly t-statistic 0.28) and it lost in the first half of the window. It is a single run on 14 years of survivors, so it neither confirms nor rules out momentum on B3, and the project stays on hold. Open questions: other lookbacks and universes, each with its own pass rule written first, and whether anything beyond plain momentum is worth a model. See `docs/brief.md` section 10 and `notebooks/momentum_tilt.ipynb` on that branch.

> **Intraday futures (Nov 17, 2026), a second proof of concept, merged into `main` as code, notebooks and a ProfitPro script, not as a recommendation.** The "Noise Area" intraday momentum strategy of Zarattini, Aziz and Barbon, on the WIN mini Ibovespa and WDO mini dollar futures, with costs (B3 fee plus one tick a side), a volatility-targeted size and a development period (2021 to 2024) kept apart from a final test (2025 to October 2026) read once. A 50,000-trial parameter search found combinations scoring up to 2.05 on development data, but selection explains most of that: the best shared-parameter trial fell from 1.48 to 0.60 on the final test and **did not beat the CDI** (7.5% a year against 14.3%). The paper's own rule made 5.9% a year on the 50/50 average of the two futures, also below the CDI, with WIN positive (Sharpe 1.18) and WDO negative. One trial chosen on WIN alone held up on WIN (Sharpe 2.05 to 2.10, positive in both years), the only result here consistent with a real edge. It does not beat the CDI on the 50/50 average or buying the IBOV (35% a year over the window), it is one of six rows read, and it needs a later period to confirm. A ProfitPro (NTSL) version of the rule, backtested by the owner over three weeks, **matched the Python model on all 13 trades**. Nothing is nominated; the project stays on hold. See `docs/adr/0001-winfut-intraday-momentum-final-test.md`, `docs/ntsl-noise-area.md`, `docs/brief.md` section 10, and the notebooks `winfut_wdo_optimization`, `winfut_best_vs_paper`, `winfut_final_test` and `winfut_trade_book`. A Pine Script port exists on the branch `feat/pine-noise-area` (not merged): it did not display on TradingView and is not relied on.

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

**The WIN and WDO futures (Nov 2026).** A different data set and a different test: MT5 1-minute bars of the continuous contracts `WIN$N` and `WDO$N`, daily returns of an account sized by the paper's volatility target (2% a day, leverage at most 4), costs of the B3 fee plus one tick a side, a development period of 2021-12 to 2024-12 (770 days) and a final test of 2025-01 to 2026-10 (458 days) read once. Over the final window the CDI ran at 14.3% a year and the IBOV at 35.1%. Sharpe ratios are of daily returns.

| Question | Result |
| --- | --- |
| The paper's rule, development period | WIN Sharpe 0.46 and CAGR 6.3%, WDO 0.44 and 6.0%, against 12.0% for the CDI and 5.9% for buying the IBOV: it beat the IBOV by under a point and the CDI on neither. |
| Where does it earn? | At the end of the day. Holding to the last bar returned +38.5% on development data, while the owner's 17:30 exit returned −2.8%. The late profit is not a closing-call artifact and is positive every year. |
| How much cost can it take? | Little. The paper's rule on WIN made +20.9% over development at one tick a side and +4.1% at two. WDO costs about twice WIN's relative to what a contract controls. |
| A 50,000-trial search of eight parameters (29.5% of 169,344 combinations) | Best score in-sample: 1.12 for the worse-of-the-two Sharpe ratios. With leave-one-year-out, the winners trained at 1.20 and scored **−0.20 held out**, against 0.24 for the paper's rule. On shuffled data the same procedure trains at 0.62 and scores −0.46 held out. Real data still beats the shuffled baseline (best joint trial of 5,000: 0.92 against 0.43), so some structure is real, but the selection is not. Ten times the trials (3,000 to 50,000) raised the best in-sample score by 0.11 and not the held-out one. |
| The final test, the paper's rule | WIN Sharpe 1.18 (CAGR 22.8%), WDO −0.48 (−9.7%), the 50/50 average 0.46 (5.9%): below the CDI. |
| The final test, the search's winners | Best joint trial: 50/50 Sharpe 1.48 to 0.60 (CAGR 7.5%, 4.1 points under the CDI). Best WDO-only trial: WDO 1.57 to −1.09. No row beats the CDI on the 50/50 average and none beats the IBOV. |
| The one that held | The best trial by WIN: WIN Sharpe 2.05 to 2.10 (t 2.83, drawdown 5.6%, positive in 2025 and 2026), but WDO 0.38, the 50/50 average 12.4% (1.5 points under the CDI), and 204 round trips. It is one of six rows read, and the paper's rule also rose on WIN (0.46 to 1.18), so the period favoured the strategy. A later period is the only clean confirmation. |
| Does a ProfitPro backtest agree? | Yes. Over 26 October to 16 November, 13 of 13 trades matched the model on side and entry (ProfitPro fills a market order at the next candle's open), 11 of 13 exactly on exit too. The two differences: a half-day cut in the data file, and a stop on the first candle held, which ProfitPro's backtest acts on one candle late (47 of 583 trades, worth +4.5% of the model's points: the backtest reads slightly better than the model). |

Two further cautions for the futures. The continuous series is unadjusted and has roll gaps (18 in development, treated as ordinary days by the owner's decision), and it holds a 14.5% overnight gap on 2026-10-26 that could not be checked against another source. And the volatility target runs positions of about 10 contracts on average (20 at most) on a R$ 100,000 account: the cap of 4x, not the R$ 1,000 margin, is what limits them (`docs/sizing-bridge.md`).

Exploratory work that is not kept in the repo reached the same conclusion: changing the position size, adding a trend filter or a lower RSI entry, and re-picking tickers each year did not turn any setting into one that beat the CDI at a deployable size.

## What is built

- **`backend/core` (`b3core`)**: a pure domain package, with no web or database code. Deterministic: the same input gives the same output, and randomness only from seeded generators.
  - Engines for **123 de compra** (swing and day-trade mode), **IFR2** and **Turtle** (with pyramiding, a close-based stop, and fills at the signal close or the next open).
  - Metrics, a composite `score_v1` (`docs/score.md`), and equity-curve based drawdown and Calmar.
  - Benchmarks: the CDI, the IBOV and buy and hold, with strict checks (a missing CDI day is an error that names the date, never a silent fill).
  - Equal-split portfolios of independent slots, and a scan of one setting over many tickers.
  - A parameter optimizer: grid and random search, a content-addressed result cache (`run_hash`), a SQLite registry of runs and trials, an in-sample against out-of-sample split with an overfitting flag, and a neighbourhood heatmap.
  - **The intraday futures strategy** (`noise_area`, `intraday_momentum`, `intraday_search`, `winfut`): the Noise Area bands, the stops (the paper's, and three alternatives, each acted on at the half-hour grid or at every bar), volatility-targeted sizing in whole contracts, costs, intraday equity, trade lists, profit factor, Sortino, Calmar and CAGR; a seeded search with leave-one-year-out folds and a shuffled-data luck baseline; and a loader that refuses to return the final test period unless asked. The engine reproduces the authors' own loop exactly.
- **`backend/report` (`b3report`)**: Plotly charts for notebooks.
- **`notebooks/`**: all analysis, with no trading logic in them.
- **`docs/`**: the specification of every trading rule (`docs/brief.md`), the benchmark specs, data notes, and a learning log.
- **`ntsl/noise_area_win.ntsl`**: the same rule as a ProfitPro (Nelogica NTSL) indicator and, with `SendOrders(true)`, a strategy to backtest there. Its logic was checked against the Python engine bar by bar (0 differing bars out of 276,517 one-minute bars on WIN from 2023-01), and the strategy against ProfitPro's own backtest (`docs/ntsl-noise-area.md`).
- **`mql5/Experts/NoiseAreaEA.mq5`**: the same rule as one MetaTrader 5 Expert Advisor (trades, backtests in the Strategy Tester, and draws the bands, VWAP and position arrows), with the paper's volatility-target sizing as an option. Run tick by tick on WIN from 2021-12, its trades match the model's (579 of 581 on the WIN optimized rule, all exits in the same minute); the difference in profit is fill timing, about one tick a side. Validating it found a real flaw (positions held overnight on the days B3 closed at 17:55), now fixed. Details, results by sizing and account size in `docs/mql5-noise-area.md`. Not new evidence about the edge: the runs use the data already read in the final test.
- **`tools/check_notebook_outputs.py`**: a guard that refuses a published notebook that prints raw candles.

Not built: 123 de venda, a genetic-algorithm optimizer, the API, the database and the frontend (the brief's later phases).

## How it was built

- **Spec first.** No trading rule is implemented until it is written in `docs/brief.md`; ambiguities are listed as open questions instead of guessed. Several rules were reverse-engineered against real platform trades, and the differences are documented.
- **Tests first.** 463 tests: golden cases whose every number is worked out by hand in the spec, Hypothesis property tests (no look-ahead through prefix invariance, no overlapping trades, determinism, costs only lower PnL), parity tests against a research prototype and TA-Lib, and manual mutation checks that confirmed the tests catch a deliberate bug.
- **Honest reporting.** In-sample against out-of-sample everywhere, a final test period that stays unread until the rule and code are frozen (then read once, with a log of every look at the development data, nine so far), random-subset baselines for any "pick the best" step, and survivorship, leverage and single-regime caveats stated next to the numbers.
- **Built with Claude Code as a tutor and reviewer.** `CLAUDE.md` defines a learning mode (the owner writes the core code, the assistant teaches and reviews). Where the assistant wrote code at the owner's request, the commits say so.

## Run it

```bash
cd backend && uv sync --group ifr2   # Python 3.12; the ifr2 group adds yfinance, scikit-learn, TA-Lib
make test                            # pytest: golden, property-based and unit tests
make lint                            # ruff, mypy and the notebook output guard
make notebook                        # JupyterLab on notebooks/
```

The futures notebooks (`winfut_*`) read MT5 1-minute exports of `WIN$N` and `WDO$N` placed in `samples/` (one file per symbol: the loader refuses two); extra comparison files, such as a ProfitPro operations report, go in `samples/comparison/`. The search notebook takes its size from the environment (`N_TRIALS`, `N_NULL`; the 50,000-trial run took 2.3 hours on 11 cores and saves its results to a git-ignored file). The notebooks download daily candles from Yahoo Finance and the CDI from the Central Bank (`samples/` is a gitignored cache; **the data itself is never committed**). The 123 de compra notebook reads MT5 "export bars" CSV files that you place in `samples/` yourself. The Plotly charts are interactive in JupyterLab or in an HTML export (`jupyter nbconvert --to html`). GitHub cannot run them, so `turtle_deep_dive.ipynb` also stores a still image of each chart, made with `kaleido` (the dropdown's image shows its first ticker). `kaleido` drives a headless Chrome, which it downloads itself (`kaleido.get_chrome_sync()`); on a minimal Linux or WSL install Chrome also needs `libnss3`, `libnspr4` and `libasound2` (`sudo apt install libnss3 libnspr4 libasound2t64`). Without `kaleido` the notebook still runs, with interactive charts only.

## Notebooks

| Notebook | What it does | Outputs |
| --- | --- | --- |
| `turtle_deep_dive.ipynb` | The nine shortlisted stocks in detail: portfolio view, per-stock charts and statistics, a selection check, and a dropdown over all candidates | published |
| `turtle_stocks.ipynb` | Which stocks suit Turtle, and whether the ranking holds up | published |
| `turtle.ipynb` | Turtle on liquid Ibovespa names and BDRs: fill rules, pyramiding, portfolios | published |
| `ifr2_liquid.ipynb` | IFR2 on liquid Ibovespa names and BDRs | published |
| `ifr2_universe.ipynb`, `ifr2.ipynb` | IFR2 across tickers, the optimizer, clusters, ticker k-fold | stripped |
| `123_de_compra.ipynb` | One ticker with 123 de compra, checked against real platform trades | stripped |
| `winfut_final_test.ipynb` | The final test of the intraday futures strategy (the paper's rule and the search's best trials), read once | published |
| `winfut_wdo_optimization.ipynb` | The 50,000-trial parameter search on WIN and WDO, with timing, leave-one-year-out, transfer and a shuffled-data baseline | published |
| `winfut_best_vs_paper.ipynb` | The best trials against the paper's rule on more metrics (profit factor, Sortino, Calmar, CAGR, against the CDI and the IBOV) | published |
| `winfut_intraday_momentum.ipynb` | The strategy on development data: bands, stops, the sizing bridge, drawdowns, variants | stripped |
| `winfut_beat_the_market.ipynb` | The paper's tables, figures and FAQ recreated on WIN | stripped |
| `winfut_trade_book.ipynb` | The last N trades of one configuration, and the comparison with a ProfitPro operations report | stripped |
| `winfut_contracts_and_cdi.ipynb` | How many contracts on a small account: the paper's sizing by account size, one contract per R$ X, risk of ruin with a 60% stop-out, when to add a contract, and head to head with the CDI with a monthly deposit | stripped |

## Limitations

Survivorship bias (the tickers are today's liquid names, from a list written from memory), correlated tickers and one or two market regimes, raw prices with dividends ignored, no taxes, no slippage beyond the fee (for the stocks), no shared-cash rule for simultaneous signals, and the missing capital cap. The ticker lists are drafts, not B3's verified index composition. For the futures: about five years of one instrument family, a Brazilian equity bull run in the final window, an unadjusted continuous series with roll gaps and one unexplained 14.5% gap, costs of the fee plus one tick with little margin for more, no margin calls and no intraday liquidity limit, a final test that is now spent (a new period is the only clean confirmation), and a ProfitPro backtest that acts on a first-candle stop one candle late. No license has been chosen.

## Documentation

[`docs/brief.md`](docs/brief.md) is the source of truth for the architecture, the trading rules and the open questions. See also [`docs/sizing-bridge.md`](docs/sizing-bridge.md) (the paper's share sizing as WIN contracts), [`docs/ntsl-noise-area.md`](docs/ntsl-noise-area.md) (the ProfitPro script and its comparison), [`docs/adr/0001-winfut-intraday-momentum-final-test.md`](docs/adr/0001-winfut-intraday-momentum-final-test.md), [`docs/cdi.md`](docs/cdi.md), [`docs/ibov.md`](docs/ibov.md), [`docs/score.md`](docs/score.md), [`docs/data-notes.md`](docs/data-notes.md) and [`docs/learning-log.md`](docs/learning-log.md).
