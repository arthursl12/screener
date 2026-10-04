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
