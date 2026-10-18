# Learning log

Status: **explained**, **shaky** or **to revisit**. The owner asked Claude to write the Phase 0 code
("just do it"), so every entry starts as *to revisit* until the owner has explained it back.

| Date | Concept | Where it is used | Status |
| --- | --- | --- | --- |
| 2026-10-04 | Timezone-aware parsing: localize to America/Sao_Paulo, convert to UTC, fail on ambiguous or nonexistent local times, never a fixed offset (Brazil had DST until 2019) | `b3core/data.py` `CsvProvider` | to revisit |
| 2026-10-04 | Ingest validation that reports problems and never drops or fills rows | `b3core/data.py` `validate_candles` | to revisit |
| 2026-10-04 | Golden tests with hand-computed expectations (the worked example and its variations) | `core/tests/test_engine_golden.py` | to revisit |
| 2026-10-04 | No look-ahead: a signal on a closed c3 fills from c4; prefix invariance as a Hypothesis property | `b3core/engine.py`, `test_engine_properties.py` | to revisit |
| 2026-10-04 | Pessimistic intrabar policy (stop before target) and gap fills | `b3core/engine.py` `_find_exit` | to revisit |
| 2026-10-04 | Risk-based position sizing (max risk / stop distance, floored to the lot, capped by capital) | `b3core/engine.py` `_quantity` | to revisit |
| 2026-10-04 | Metrics: result, EV, profit factor, streaks, max drawdown over initial capital; regression check against the reference numbers | `b3core/metrics.py` | to revisit |
| 2026-10-04 | Parameter ranges built from an integer index (no float drift) | `b3core/optimizer.py` `ParamRange` | to revisit |
| 2026-10-04 | One `evaluate(indices)` seam shared by every optimizer, with cache, process pool and budget | `b3core/optimizer.py` | to revisit |
| 2026-10-04 | `run_hash`: a SHA-256 over everything that determines a result, used as a cache key | `b3core/optimizer.py` | to revisit |
| 2026-10-04 | In-sample search, out-of-sample validation, drop flag, neighbourhood heatmap; why the best of many trials is partly luck | `optimize`, `heatmap_figure`, the notebook | to revisit |
| 2026-10-04 | Day trade: no position survives its day; entries only inside a window on the fill candle; the exit candle is decided from the candle schedule (open + length), never from later candles, so no look-ahead | `b3core/engine.py` `_DayContext`, `_find_exit_day` | to revisit |
| 2026-10-04 | Forced exit priced by finer candles when supplied (pinpoint 16:30), with a named stopgap policy that can be swapped later | `b3core/engine.py` `_forced_exit`, `day_exit_policy` | to revisit |
| 2026-10-04 | Dropping invalid parameter combinations (min entry < max entry <= exit) before evaluating, by indexing only the valid ones | `b3core/optimizer.py` `ParamSpace.restricted` | to revisit |
| 2026-10-04 | Passing the same time cut to the finer candles when splitting in-sample and out-of-sample | `b3core/optimizer.py` `optimize` | to revisit |
| 2026-10-04 | Spec first when the rule changes: the pattern was rebuilt from the owner's pseudocode after a wrong reading of the reference page; spec, then tests, then code | `docs/brief.md` section 7, `core/tests/test_engine_golden.py` | to revisit |
| 2026-10-04 | EMA as a standard recursion, trend context from three comparisons, and a warm-up so unstable averages never produce signals | `b3core/indicators.py`, `find_signals` | to revisit |
| 2026-10-04 | Levels frozen at the signal; the fill price (gap at the open) only changes the entry and the position size | `b3core/engine.py` `run_backtest` | to revisit |
| 2026-10-04 | Validating an engine against a real reference: matching three real trades, and tracing the mismatches to vendor data (auction handling in the first and last candle) | `docs/data-notes.md`, notebook section 6 | to revisit |
| 2026-10-18 | Wilder smoothing for RSI and ATR (seed with a simple mean, then `(avg*(n-1)+x)/n`), flat windows giving NaN, parity with TA-Lib as the oracle | `b3core/indicators.py` `rsi`, `atr` | to revisit |
| 2026-10-18 | IFR2 engine: entry at the signal close as a named exception to "act on the next candle", exits checked from the next candle in a fixed order (target, time stop, RSI), gap fill at the open | `b3core/ifr2.py` `run_ifr2` | to revisit |
| 2026-10-18 | ATR-based sizing when there is no stop: risk budget over `atr_mult * ATR`, floored to the lot, capped by capital; the ATR distance is a sizing device, not an exit, so a loss can exceed `max_risk` | `b3core/ifr2.py` `_quantity` | to revisit |
| 2026-10-18 | Balance drawdown (closed trades) against equity drawdown (open trades marked at each close), CAGR and annualised Calmar; the denominator choice (peak or initial capital) is still open | `b3core/metrics.py` | to revisit |
| 2026-10-18 | `score_v1`: clipped components, weights, and a confidence factor `n/(n+30)` so a tiny perfect sample cannot win; out-of-sample kept as a separate flag, not inside the score | `docs/score.md`, `b3core/score.py` | to revisit |
| 2026-10-18 | Mutation testing by hand: break the code on purpose and check that a test fails (found two real test gaps: entry cost in the equity curve, `validate` skipping constrained params) | scratch scripts, `test_ifr2.py`, `test_optimizer.py` | to revisit |
| 2026-10-18 | Strategy protocol: the optimizer asks a strategy for its id, version, config class, a run method and a validity hook; `run_hash` includes the strategy so caches never mix; read-only protocol properties so frozen dataclasses fit | `b3core/strategy.py`, `b3core/optimizer.py` | to revisit |
| 2026-10-18 | Dropping irrelevant and duplicate combinations per exit mode before evaluating, so the trial count is honest (best of many trials is partly luck) | `b3core/strategy.py` `Ifr2Strategy` | to revisit |
| 2026-10-18 | Warn instead of refuse for out-of-spec input (non-daily IFR2): the user can experiment, the output says it is outside the spec | `b3core/ifr2.py` `run_ifr2` | to revisit |
| 2026-10-18 | A persistent result cache and run history: content-addressed `results`, runs linked to trials by phase, read-through cache, batched commits and a flush per batch so a crash loses nothing | `b3core/trialstore.py`, `TrialCache`, `optimize` | to revisit |
| 2026-10-18 | The CDI as the cost of capital: compound the daily rate over `(d0, d1]` and compare CAGRs; `beats_cdi = excess > 0`; the trading-day window and the missing-day error | `docs/cdi.md`, `b3core/benchmark.py` | to revisit |
| 2026-10-18 | Scanning one config over many tickers, and ranking parameter combinations across tickers by the median objective so one lucky ticker cannot carry them | `b3core/universe.py` | to revisit |
| 2026-10-18 | Per-ticker tuning overfits: in-sample CAGR doubles and the out-of-sample CAGR falls below the untouched default | `notebooks/ifr2_universe.ipynb` sections 6 and 7 | to revisit |
| 2026-10-18 | Equal-split portfolio of independent slots: the sum of slot equity curves, forward and back fill at the edges, drawdown from the capital; diversification narrows the spread and the drawdown but not the median CAGR | `b3core/portfolio.py`, notebook section 8 | to revisit |
| 2026-10-18 | Choosing tickers in-sample and judging them out-of-sample, against random subsets of the same size (percentile of random); selection inflates the percentile at large N | notebook section 9 | to revisit |
| 2026-10-18 | Clusters: KMeans on behaviour features, hierarchical clustering on `1 - correlation`, and greedy diversification by strategy-return correlation; clusters built on in-sample results are not an independent test | notebook section 10 | to revisit |
| 2026-10-18 | Ticker k-fold: choose the shared setting on the other tickers, test on the hidden fold, repeat with fresh random folds; the OOS window of hidden tickers is the clean reading, the IS window of hidden tickers is optimistic | notebook section 11 | to revisit |
