# B3 Backtester: Implementation Guidelines for Claude

Oct 2, 2026 · @Arthur

## 1. Purpose and scope

Claude builds a B3 strategy backtester in the spirit of QuantBrasil. Phase 0 is a barebones but functional MVP: engine, strategies and optimizer in a notebook, with no infrastructure yet. The web app comes after it. It is a portfolio project, so tests, documentation and clean architecture count as much as features.

**MVP, what the user can do in a notebook:**

- Pick a strategy, a timeframe, a ticker (stocks, BDRs, ETFs, indices) and a period, then run a backtest from a notebook cell.
- Read the result as stats (trades, win rate, result, average gain and loss, EV, best and worst streak, profit factor, drawdown), a score, and Plotly charts: equity curve, monthly returns, a calendar and a per-trade candle chart.
- Use the first two strategies, 123 de compra and 123 de venda, in swing and day-trade modes.
- Optimize parameters over start, stop and step ranges with a grid or a genetic algorithm, and validate the best results out of sample (section 12).

**Non-goals for the MVP:** the web app (API, jobs, React UI), live trading or order routing, taxes, WhatsApp alerts, multi-user auth, tick-level data. Do not copy the reference product's branding, wording or assets; build an original UI when the web phase comes.

**Disclaimer.** The app is educational and is not investment advice. The first cell of every notebook, every results page and the README say so clearly.

**Next, after the MVP:** the web app, with the API and jobs first (Phase 4) and the React UI after (Phase 5). **Later, in this order:** benchmark comparison (buy and hold, Ibovespa), Monte Carlo reshuffle of trades, walk-forward testing, screener, portfolio view, multi-ticker runs, alerts.

## 2. Operating directives for Claude

Follow these rules in every session. In the first commit, write a short `CLAUDE.md` at the repo root that condenses this section and points to this brief.

**Learning mode comes first.** The owner is building this project to learn the stack, so section 11 overrides the default of writing code for them. Read it before starting any task.

1. **Work in thin vertical slices.** Each slice is: write a failing test, make it pass with the smallest change, refactor, commit. Never write a large module before its first test.
2. **The spec is the source of truth.** Implement only trading rules written in sections 6 and 7. If a rule is ambiguous or missing, stop, add it to the open questions in section 10, and ask. Never guess a market rule.
3. **Keep the core pure.** The `core` package imports no FastAPI, SQLAlchemy, Redis or network code. It takes DataFrames or arrays in and returns plain results out.
4. **Be deterministic.** The same inputs produce the same outputs. No wall-clock reads and no unseeded randomness inside the core.
5. **Time and money conventions.** Store timestamps as UTC `timestamptz`; evaluate trading rules in `America/Sao_Paulo`. Candle prices are float64; round to the instrument tick when filling orders.
6. **Do not add dependencies outside section 3** without asking. Pin versions and commit the lockfiles.
7. **Never commit** credentials, `.env` files, or real vendor market data. Commit only small synthetic fixtures.
8. **Commit style.** Use Conventional Commits, one logical change per commit, and keep `main` green.
9. **Document decisions.** Record every non-obvious choice as a short ADR in `docs/adr/` (context, decision, consequences).
10. **Report honestly.** If a test fails, a benchmark misses its budget, or a result looks too good, say so in the summary instead of tuning until it passes.

**Definition of done for every slice:** tests written first and passing, `make lint` and `make test` green, types checked, docs or ADR updated if behaviour changed, and, from Phase 1 on, `docker compose up` still brings the stack up healthy.

## 3. Architecture and stack

Postgres is the single source of truth, Redis is an ephemeral job queue, and the pure `core` package is shared by the API and the worker.

**Phasing.** The first MVP (Phase 0) uses only `core` and `report`, driven from a notebook on candles from CSV files and yfinance. `db`, `collector` and Postgres arrive in Phases 1 and 2, and the `api`, `worker` and `web` services and Redis in Phases 4 and 5.

&#91;embedded content: system architecture · 5 services, 1 external collector\]

The web app talks REST to the API, which enqueues long jobs in Redis for the worker. Both read and write Postgres through `core`'s `DataProvider`, and the MT5 collector fills Postgres from the Windows host.

**Database decision.** Use one Postgres 16 database for candles, instruments, corporate events, runs and trades. A single ticker's candles are small, roughly a few thousand rows per year on hourly data, so Postgres serves one backtest quickly. Redis holds jobs and results in transit and nothing worth keeping.

**When a second datastore is allowed.** Add a Parquet and DuckDB cache only if a benchmark shows that multi-ticker scans miss the budgets in section 9 because of Postgres reads. Postgres stays the source of truth, and the cache is rebuilt from it. Do not add it earlier.

**Stack:**

| Layer | Choice |
| --- | --- |
| Language and tooling | Python 3.12, uv, ruff, mypy, pytest, Hypothesis |
| Core | pandas and NumPy; numba only if a benchmark demands it |
| Notebook and plots | JupyterLab, Plotly, nbstripout |
| Data | Postgres 16, SQLAlchemy 2, Alembic, psycopg 3; optional Parquet and DuckDB cache (see above) |
| API (Phase 4) | FastAPI, Pydantic v2 |
| Jobs (Phase 4) | ARQ on Redis |
| Frontend (Phase 5) | Vite, React, strict TypeScript, TanStack Query, lightweight-charts, Vitest |
| Packaging and CI | Docker Compose, GitHub Actions |

## 4. Repository layout and early phases

Phase 0 is a barebones but functional MVP: the engine, the 123 strategies, the backtest metrics and the optimizer, run from a notebook on candles read from CSV files or yfinance. It uses no Docker, no database and no CI, so the first results come fast. Phase 1 then adds the project foundation, and the remaining phases follow the roadmap in section 10.

**Phase 0 tasks, in order.** Each one starts with a failing test.

1. Minimal setup: a uv project with the `core` and `report` packages, a `CLAUDE.md`, a `Makefile` with `test`, `lint`, `fmt` and `notebook`, and ruff, mypy, pytest, Hypothesis, JupyterLab, Plotly and nbstripout (installed as a git filter). Add a `notebooks/` folder and a gitignored `data/` folder. One trivial core test proves the TDD loop.
2. Data: the `DataProvider` interface, `CsvProvider` and `YfinanceProvider` with a CSV cache in `data/`, and the ingest validation from section 5.
3. Engine and strategies: the rules in section 6 and the 123 definition in section 7, with the golden and property tests from section 8, the metrics, and `score_v1`.
4. Notebook slice: one ticker with 123 de compra, checked against the worked example, with the `report` charts.
5. Optimizer: section 12, in its build order: grid search, then the split and heatmap, then the genetic algorithm.

**Acceptance for Phase 0:** the worked example from section 7 passes, the property tests are green, the notebook runs a backtest and an optimization on one ticker, and the genetic algorithm matches the grid on a small space.

**Phase 1, foundation.** With Phase 0 working, add the infrastructure around it. Phase 1 ends when `docker compose up` starts the database healthy and CI is green.

**Monorepo layout:**

```text
b3-backtester/
  CLAUDE.md                 # condensed directives, pointer to docs/brief.md
  README.md
  Makefile                  # test, lint, fmt, notebook; later up, down, migrate
  compose.yaml              # Phase 1: db only; redis, api, worker, web come in Phases 4 and 5
  .env.example
  .pre-commit-config.yaml   # Phase 1
  .github/workflows/ci.yml  # Phase 1
  backend/
    pyproject.toml          # uv workspace
    core/                   # Phase 0: package b3core: pure domain, engine, optimizer, no I/O
    report/                 # Phase 0: package b3report: Plotly charts and tables for notebooks
    db/                     # Phase 1: package b3db: SQLAlchemy models, Alembic migrations, PostgresProvider
    collector/              # Phase 2: MT5 collector, runs on the Windows host, not in Docker
    api/                    # Phase 4: FastAPI app
    worker/                 # Phase 4: ARQ jobs that call core
  frontend/                 # Phase 5: Vite + React + TypeScript
  notebooks/                # Phase 0: backtests and optimization, imports workspace packages only
  data/                     # Phase 0: gitignored CSV cache of candles
  docs/
    brief.md                # this document, exported to Markdown
    adr/                    # architecture decision records
    data-notes.md           # findings about MT5 data (adjustment, depth, gaps)
```

**Compose services:**

| Service | Role | Port | Notes |
| --- | --- | --- | --- |
| `db` | Postgres 16 | 5432 | Named volume, healthcheck with `pg_isready` |
| `redis` | Job queue and result cache | 6379 | Ephemeral, no persistence needed |
| `api` | FastAPI | 8000 | Multi-stage image, non-root user, healthcheck on `/health` |
| `worker` | ARQ worker | none | Same base image as `api`, depends on `db` and `redis` |
| `web` | Vite build served by nginx (prod) or dev server | 5173 | Dev profile mounts source for hot reload |

`compose.yaml` arrives in Phase 1 with only `db`. The `redis`, `api`, `worker` and `web` services are added in Phases 4 and 5.

**Phase 1 tasks, in order.** Each one starts with a failing test where a test makes sense.

- [ ] 1\. Harden the repo: license, `.editorconfig`, pre-commit with ruff, mypy and nbstripout, and `make up`, `make down` and `make migrate` targets.
- [ ] 2\. Database: Postgres 16 in `compose.yaml` with a healthcheck, then a `db` package with a SQLAlchemy 2 engine and session and Alembic with an empty baseline migration. Add an integration test that applies migrations to a real Postgres (testcontainers or the compose service).
- [ ] 3\. CI: GitHub Actions jobs for lint, type check and backend tests with a Postgres service. Cache uv.
- [ ] 4\. Write the first ADRs: stack choice, Postgres as the single store, the notebook as the MVP, MT5 collector outside Docker.

**Acceptance for Phase 1:** a fresh clone runs `cp .env.example .env && make up` and reaches a healthy database; `make test` and `make lint` pass locally and in CI.

**Deferred to Phases 4 and 5:** the FastAPI skeleton with `GET /health` and `GET /version`, the ARQ worker with a `ping` job, the Vite and React page that calls `/health`, the Dockerfiles for `api`, `worker` and `web`, and the Docker image build in CI.

## 5. Data layer

From Phase 2, Postgres holds all market and application data, and the core reads it only through a `DataProvider` interface. MT5 is the first real source, collected by a separate script that never runs inside Docker. Phase 0 uses the same interface over CSV files and yfinance, with no database.

**Tables (Phase 2, via Alembic):**

| Table | Key columns | Notes |
| --- | --- | --- |
| `instruments` | `id`, `symbol`, `asset_class`, `tick_size`, `lot_size`, `currency`, `active` | Asset class: stock, bdr, etf, index, future |
| `candles` | PK `(instrument_id, timeframe, ts)`, `open`, `high`, `low`, `close`, `volume` | Double precision for cheap loads; `ts` is the candle open time in UTC |
| `corporate_events` | `instrument_id`, `ex_date`, `type`, `factor`, `amount`, `source` | Raw events; adjustment is applied on read, never baked in |
| `ingest_runs` | `id`, `source`, `instrument_id`, `timeframe`, `range`, `rows`, `status`, `started_at` | Audit trail for every collector run |
| `backtest_runs` | `id`, `run_hash`, `params` (JSONB), `metrics` (JSONB), `status`, `created_at` | Unique on `run_hash` for result caching |
| `trades` | `run_id`, `n`, `side`, `entry_ts`, `exit_ts`, `entry`, `exit`, `qty`, `pnl`, `r_multiple`, `exit_reason` | One row per simulated trade |

**DataProvider interface (in `core`):**

```python
class DataProvider(Protocol):
    def get_candles(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Columns: ts (UTC), open, high, low, close, volume. Sorted, unique ts."""
```

Implementations: `CsvProvider` (tests, fixtures and a local CSV cache in `data/`) and `YfinanceProvider` in Phase 0, then `PostgresProvider` (production) in Phase 2. `YfinanceProvider` stays as the fallback when Postgres has no data for the requested instrument or timeframe, and as the data source for the public demo. Its history is short and its quality is not guaranteed, so results computed from it are labelled as limited data, and the data source goes into the data version used by `run_hash`. Later: COTAHIST and brapi providers behind the same interface.

**MT5 collector rules:**

- Runs on the Windows host with the `MetaTrader5` package, writes straight to Postgres using `DATABASE_URL`. Nothing else imports it.
- Idempotent: upsert with `ON CONFLICT (instrument_id, timeframe, ts) DO UPDATE`. Incremental: start from the latest stored `ts` per instrument and timeframe.
- Pull native MT5 timeframes (for example H1 and H2) with `copy_rates_range`, in chunks. Do not resample H1 into H2 unless the session boundaries have been verified against B3's calendar.
- Provide `--dry-run`, `--symbols` and `--since` flags, and log one `ingest_runs` row per symbol and timeframe.
- Session hours and holidays live in config per asset class. Do not hardcode them from memory; verify them against B3 and record the source in `docs/data-notes.md`.

**Validation on ingest:** timestamps strictly increasing, no duplicates, `high >= max(open, close)`, `low <= min(open, close)`, `volume >= 0`. Report gaps and bad rows; never silently fill or drop them.

**First investigation task:** find out whether the broker's MT5 history is adjusted for dividends and splits, and how far back H1 and H2 go. Record both findings in `docs/data-notes.md` before any strategy results are trusted.

**Licensing:** B3 and broker data cannot be redistributed. The public repo ships synthetic fixtures and a README section on running the collector with one's own account. yfinance is an unofficial wrapper around Yahoo's data, so check Yahoo's terms before serving that data from a public demo.

## 6. Backtest engine rules and domain model

The engine turns closed candles into signals, orders, fills and trades under the fixed rules below. Every rule gets a test before it gets code.

**Domain types (in `core`):** `Timeframe`, `Candle` series, `Strategy` (a pure function from candles to `Signal`s), `Order`, `Fill`, `Trade`, `EquityCurve`, `Metrics`, `BacktestConfig`, `BacktestResult`.

**Execution rules:**

1. **No look-ahead.** A signal is computed on a closed candle. Its order can fill no earlier than the next candle.
2. **Entry.** A stop-entry order triggers when a later candle trades through the trigger price. Fill at the trigger, or at the open if the candle gaps through it.
3. **Stop and target in the same candle.** Assume the stop is hit first (pessimistic). Make this an `intrabar_policy` setting so a finer timeframe can replace it later.
4. **Sizing from risk.** The user sets a maximum risk per trade in R$. Quantity is the maximum risk divided by the distance from entry to stop, rounded down to the lot size, and capped so that quantity times entry does not exceed the available capital.
5. **Target.** Either the amplitude of the three-candle pattern or a multiple of the entry-to-stop distance (section 7), so results can also be read in R multiples.
6. **Day-trade mode.** Entries are allowed only between the configured minimum and limit hours. Any open position is closed at the configured session exit time. No overnight positions.
7. **Fixed capital, no compounding.** Each trade is sized from the same configured capital. Equity is initial capital plus cumulative PnL.
8. **One position per symbol at a time.** No pyramiding.
9. **Costs.** Brokerage per order, B3 fees as a percentage of volume, and slippage in ticks. All are configurable and default to zero so golden tests stay readable. The cost model carries a version number.
10. **Taxes** are out of scope for the MVP.

**Metrics.** The reference screenshot's numbers are consistent with the definitions below, using initial capital as the denominator (173 trades, 102 wins, average gain R$ 613.75, average loss R$ 427.72, capital R$ 100,000 give a result of 32.2% and a profit factor of 2.06). Use them as a regression check for the metrics code.

```latex
\text{Result} = \frac{\sum \text{PnL}}{\text{Capital}}
\qquad
\text{EV} = \frac{w\,\overline{G} - (1-w)\,\overline{L}}{\text{Capital}}
\qquad
\text{PF} = \frac{\sum \text{gains}}{\sum \text{losses}}
```

Here `w` is the win rate, `G` the average gain and `L` the average absolute loss. Also compute: number of trades, win count, best and worst streak, and maximum drawdown as the largest peak-to-trough fall of cumulative PnL divided by initial capital (verify this denominator against the reference before relying on it).

**Score.** The reference product's score is proprietary, so define an original `score_v1` from 0 to 100. Before coding it, write the formula in `docs/score.md` (inputs such as profit factor, drawdown, EV and a trade-count confidence penalty), get approval, then implement it with tests and a version tag.

**Engine implementation.** Generate signals vectorized with pandas and NumPy. Simulate trades by looping over signals, not over candles, with numba only if a benchmark demands it. Later, add an event-driven engine behind the same `Engine` interface returning the same `BacktestResult`.

**The notebook is the MVP's front end.** Start with one ticker and 123 de compra in a Jupyter notebook in `notebooks/`. Check the worked example from section 7 by hand, then plot the candles with entries and exits, the equity curve and the monthly returns with `report`. There is no UI: parameters are plain variables or typed config objects (`BacktestConfig`, and a `ParamRange` with start, stop and step for the optimizer) set in code. Configs serialize to JSON, so the same objects feed `run_hash` and the API later. The notebook imports the workspace packages and holds no trading logic. Strip outputs before committing (for example with nbstripout), so diffs stay readable and no vendor data lands in git.

## 7. Strategy spec: 123 de compra (123 de venda follows)

**Status.** On Oct 4, 2026 the owner supplied pseudocode that replaces my earlier readings of the QuantBrasil page (which had the pattern on highs instead of lows). The rules below restate it in our own words and keep its parameter names. They were checked against three real QuantBrasil trades on PETR4 H2; what matched and what did not is in `docs/data-notes.md`. Anything marked **(assumption)** is a detail the pseudocode does not state; it is pinned by a test, listed in the open questions in section 10, and needs the owner's sign-off. 123 de venda (the mirror) is not specified yet.

**123 de compra (buy).** Look at the last three closed candles: c3 is the signal candle, c2 the middle one and c1 the oldest (the pseudocode's `[0]`, `[1]` and `[2]`).

- **Pattern:** c2 has the lowest low of the three: `Low[c3] > Low[c2]` and `Low[c2] < Low[c1]` (strict comparisons).
- **Trend context:** every enabled check must pass. With `fast` and `slow` the exponential moving averages of the close: `use_ma_order` needs `fast > slow` on c3; `use_fast_slope` needs `fast` higher on c3 than on c2; `use_slow_slope` needs the same of `slow`; `use_price_above_fast` needs the close above `fast` on c1, c2 and c3.
- **Size filter:** when `max_c3_ticks` is above zero, the range of c3 (high minus low) must be at most that many ticks.
- **Levels, computed once at the signal and then frozen:** `entry = High[c3] + entry_offset_ticks * tick`; `amplitude` is the highest high minus the lowest low of the three candles; `stop` is `Low[c3]` (`stop_mode` C3) or `Low[c2]` (C2), minus `stop_offset_ticks * tick`; `risk = entry - stop`; `target` is `entry + target_mult * amplitude` (`target_mode` AMP) or `entry + target_mult * risk` (RISK), rounded to the nearest tick.
- **Order:** a stop-buy at `entry`, live for `entry_validity_bars` bars after c3. It fills at `entry`, or at the open if the candle gaps above it (section 6, rule 2). The stop and the target stay at their frozen levels; they are not recomputed from the fill price.
- **No second signal** is looked for while an order is pending or a position is open.

**Parameters:**

| Parameter | Default | Range or grid | Notes |
| --- | --- | --- | --- |
| `capital_brl` | 100000 | > 0 | Fixed per trade, no compounding |
| `max_risk_brl` | 2000 | > 0 | Maximum loss per trade, drives quantity |
| `tick_size` | 0.01 | > 0 | Instrument tick |
| `lot_size` | 100 | 1 or more | Instrument lot |
| `ma_fast_period` | 8 | 5 to 13 | EMA period of the close |
| `ma_slow_period` | 80 | 50 to 200 | EMA period of the close |
| `use_ma_order` | on | on or off | `fast > slow` |
| `use_fast_slope` | on | on or off | `fast` rising |
| `use_slow_slope` | on | on or off | `slow` rising |
| `use_price_above_fast` | off | on or off | Three closes above `fast` |
| `max_c3_ticks` | 0 | 0 (off) or more | Size cap of c3 |
| `entry_offset_ticks` | 1 | 0 to 2 | Added to the trigger |
| `entry_validity_bars` | 1 | 1 or more | Bars the order stays live |
| `stop_mode` | `C3` | `C3`, `C2` | Which low is the stop |
| `stop_offset_ticks` | 1 | 0 or more | Ticks below that low |
| `target_mode` | `AMP` | `AMP`, `RISK` | Target from amplitude or from risk |
| `target_mult` | 1.61 | AMP: 1, 1.272, 1.61, 2; RISK: 1, 1.5, 2, 3 | Target multiple, above 0 |
| `day_trade` | off | on or off | When on, no position is held overnight (see below) |
| `min_entry_time` | `00:00` (start of day) | `HH:MM` | Day-trade only: earliest candle open for a fill |
| `max_entry_time` | none, meaning `exit_time` | `HH:MM`, at most `exit_time` | Day-trade only: a fill candle must open before it |
| `exit_time` | `16:30` | `HH:MM` | Day-trade only: forced exit time (the owner's end-of-day call; B3 hours are still an open question) |
| `day_exit_policy` | `last_candle_close` | `last_candle_close`, `auto`, `last_candle_open` | Day-trade only: how the forced exit is priced |

**Day-trade mode (the owner's rules, Oct 4, 2026).** When `day_trade` is on, no position is held overnight. Times are São Paulo wall-clock times and the engine needs the candle length (`timeframe`), so it refuses the daily timeframe.

- **Pattern and order:** the pattern may use candles of the previous day, and an order may fill on the first candles of the next day, as the sample QuantBrasil trades did. Only the position is forced out the day it opens.
- **Entry window:** a fill is allowed only on a candle that opens at or after `min_entry_time` and before `max_entry_time`, and that ends no later than `exit_time`. So the candle that contains the exit time is never an entry candle. Signals can form at any time.
- **Forced exit:** a position still open when a candle that ends after `exit_time` begins (the candle containing the exit time, or a later one) is closed on that candle. The exit reason is `time`. The price depends on `day_exit_policy`:
  - `last_candle_close`: that candle is evaluated like any other (gap rules, then stop before target) and, if neither level is hit, the position leaves at its close. On H2 candles this is the 16:00 candle's close, a price from after 16:30. It matches the sample QuantBrasil trades.
  - `auto`: with finer-timeframe candles (`intraday`) supplied, the exit is pinpointed. The stop and target are checked on the finer candles from the exit candle's open up to, but not including, the last finer candle that starts at or before `exit_time`, and the open of that candle is the exit price (exact when a finer candle starts at `exit_time`, for example 16:30 on M30 data). Without finer candles it behaves like `last_candle_open`.
  - `last_candle_open`: exit at the open of the exit candle, before its range is looked at. It never uses prices after `exit_time`.
- **Stop and target** keep working during the day.

**Engine assumptions, all pending sign-off:**

1. **Entry candle (assumption).** The stop check also applies on the candle that fills the entry: if that candle's low reaches the stop, the trade is stopped out (section 6, rule 3, pessimistic).
2. **Gaps on exit (assumption).** If a candle opens beyond the stop, the stop fills at the open (a worse price). If it opens beyond the target, the target fills at the target price. If the fill itself gaps to or past the target, the position leaves at the fill price with zero PnL.
3. **Sizing (from the sample trades).** Quantity is `max_risk_brl / (fill - stop)` using the actual fill price, rounded down to the lot and capped by `capital_brl / fill`.
4. **Quantity below one lot (assumption).** If the rounded-down quantity is zero, no trade is taken.
5. **One working order or position (assumption).** A new signal is considered only if its c3 is at or after the bar where the previous order expired or the previous trade exited.
6. **Open position at the end of the data (assumption).** It is not a closed trade and is left out of the results.
7. **Wins and losses (assumption).** A win has PnL above zero and a loss below zero. A zero-PnL trade is neither and breaks a streak.
8. **Moving averages (assumption).** `EMA` is the standard recursion with factor `2 / (period + 1)`, seeded with the first close. When any average-based check is on, signals are only considered from bar number `ma_slow_period` on (the warm-up). An out-of-sample slice restarts its averages, so it loses its first bars to the warm-up.
9. **Day-trade exit candle (assumption).** Fills never happen on the candle that ends after `exit_time`; policies `auto` and `last_candle_open` do not evaluate that candle's stop and target unless finer candles cover it.
10. **Short days (assumption).** If a day ends before any candle ends after `exit_time` and a day-trade position is open, it is closed at the close of that day's last candle (known only once the next day's first candle arrives).
11. **Zero risk (assumption).** With `entry_offset_ticks` and `stop_offset_ticks` both 0 and `C3` as the stop, a c3 whose high equals its low gives an entry equal to the stop, so the quantity cannot be sized; that signal is dropped.

**Worked example for the first golden test** (tick R$ 0.01, lot 100, capital R$ 100,000, max risk R$ 200, the moving-average checks off, `C3` stop with offset 1, `RISK` target with multiple 2, offset 1, validity 1):

| Candle | Open | High | Low | Close | What happens |
| --- | --- | --- | --- | --- | --- |
| c1 | 10.50 | 10.60 | 10.40 | 10.45 | Oldest candle |
| c2 | 10.45 | 10.50 | 10.20 | 10.30 | Lowest low of the three |
| c3 | 10.30 | 10.40 | 10.25 | 10.38 | Higher low than c2: signal. Entry 10.41, stop 10.24, target 10.75 |
| c4 | 10.38 | 10.45 | 10.35 | 10.44 | High reaches 10.41: entry fills at 10.41 |
| c5 | 10.44 | 10.80 | 10.40 | 10.78 | High reaches 10.75: exit at target |

Expected result: risk per share 0.17, quantity `floor(200 / 0.17) = 1176`, rounded down to the lot, 1100 shares. PnL is 1100 times 0.34, which is **+R$ 374.00**, exactly 2.0 R. The amplitude is 10.60 minus 10.20 = 0.40.

**Golden cases to write, one test each:** the worked example; the entry candle also reaching the stop; a gap-up fill with frozen levels (quantity from the actual fill, target unchanged); a fill that gaps past the target; stop and target inside one candle; gap through the stop and through the target; trigger never reached within the validity window, and reached on the second bar with validity 2; the `C2` stop, the stop offset and the entry offset; the `AMP` target; the size filter at its edge; each trend check on and off; quantity rounding to zero; the capital cap; equal lows not forming the pattern; the day-trade cases (forced exit at the close, at the open and pinpointed with finer candles, an order carried overnight, entry window edges, the exit candle never an entry, stop still working, short day).

**Not specified yet, blocked by an open question:** the mirror 123 de venda.

## 8. Testing strategy

Tests drive the engine: golden cases pin exact behaviour, and property-based tests guard the invariants that backtests most often break. Write the test first in every slice.

| Layer | Tool | What it covers |
| --- | --- | --- |
| Unit and golden | pytest | Pure functions in `core` on 10 to 20 candle series with hand-computed results |
| Property-based | Hypothesis | Invariants over generated candle series (list below) |
| Integration | pytest, httpx, real Postgres | API endpoints, migrations, repositories, the ARQ worker |
| Frontend | Vitest, Testing Library | Param form, result rendering, loading and error states |
| End to end | Playwright (Phase 5) | One smoke path: run a backtest and see the equity curve |
| Performance | pytest-benchmark | Engine speed budgets (section 9) |

**Invariants to encode in Hypothesis:**

- **Prefix invariance (no look-ahead):** running the backtest on candles up to time T gives the same trades as running on all candles, for every trade that closes before T.
- Sum of trade PnL equals final equity minus initial capital.
- Every exit is after its entry, and no two trades overlap for the same symbol.
- For longs, stop is below entry and target is above entry; the reverse for shorts.
- Quantity times entry never exceeds capital, and quantity is a multiple of the lot size.
- In day-trade mode, no trade is open after the session exit time.
- The same inputs and `run_hash` produce byte-identical results.

**Rules:**

- Fixtures are small synthetic CSVs committed to the repo; never real vendor data.
- Integration tests use a real Postgres, not mocks of the database.
- Target at least 90% line coverage on `core`. Consider mutation testing on the engine once it stabilises.
- A bug fix starts with a failing test that reproduces the bug.

## 9. API and frontend guidelines

The API is a thin shell over `core`, and the frontend should feel instant: cached runs return immediately and the UI never blocks on a spinner when a skeleton will do.

**Timing:** this section applies to Phases 4 and 5, after the notebook MVP is complete.

**API (FastAPI, Pydantic v2, versioned under `/api/v1`):**

| Method and path | Purpose |
| --- | --- |
| `GET /strategies` | List strategies with their parameter JSON Schema, which drives the frontend form |
| `GET /instruments` | Searchable instrument list with asset class |
| `POST /backtests` | Create a run. Returns the cached result at once if `run_hash` exists, else a run id |
| `GET /backtests/{id}` | Status and metrics |
| `GET /backtests/{id}/trades` | Trades, paginated |
| `GET /backtests/{id}/events` | Server-sent events for progress on long jobs |
| `GET /candles` | Candles for a trade chart, windowed around a trade |

- **Caching:** `run_hash` is a SHA-256 over strategy id and version, canonical parameters, instrument, timeframe, period, data version, cost model version and engine version. Same hash, same result, returned immediately.
- **Inline versus job:** run small single-ticker backtests inline. Send multi-ticker or long runs to ARQ and stream progress over SSE.
- **Payloads:** return columnar arrays for equity curves and candles, not arrays of objects. Paginate trades.
- **Errors:** one error envelope with a stable `code`; validation errors come from the Pydantic models.

**Frontend (Vite, React, strict TypeScript):**

- Layout: a parameter panel on the left; on the right stat cards, the score, and tabs for equity curve, monthly returns, calendar and trades.
- TanStack Query for all server state, with sensible `staleTime` so revisiting a result costs nothing.
- `lightweight-charts` for candles and the equity curve, loaded lazily. Split code by route.
- Generate the parameter form from the strategy JSON Schema, so adding a strategy needs no new form code.
- Use skeletons instead of spinners, keep the previous result visible while a new run loads, and show clear empty and error states.
- Generate API types from the OpenAPI schema; do not hand-write them.

**Initial performance budgets (confirm with benchmarks as each part is built, then enforce in CI):**

| Budget | Target |
| --- | --- |
| Engine run, one ticker, 2 years of H1 candles, excluding I/O | under 200 ms |
| Candle load from Postgres for that series | under 100 ms |
| Cached result end to end | under 150 ms |
| Initial JavaScript bundle | under 200 KB gzipped |

**Second datastore trigger:** if multi-ticker scans miss their budget because of Postgres reads, add the Parquet and DuckDB cache described in section 3. Do not add it earlier.

## 10. CI, roadmap and open questions

Nothing merges to `main` unless the quality gates pass, and each phase has an exit criterion Claude checks before starting the next one.

**Quality gates in CI:**

- ruff lint and format check, mypy in strict mode on `core`, eslint and `tsc --noEmit` on the frontend.
- pytest with a Postgres service, at least 90% line coverage on `core`; Vitest for the frontend.
- Docker images build (from Phase 4); `pip-audit` and `npm audit` run on dependencies.
- Benchmarks run on a schedule and fail on a regression beyond the budgets in section 9.

**Roadmap, in order:**

1. **Phase 0, barebones MVP.** Section 4: engine, 123 buy and sell, metrics, `score_v1`, the optimizer (section 12) and `report` charts in a notebook, on candles from CSV files and yfinance. Exit: the worked example passes, property tests are green, the genetic algorithm matches the grid on a small space, budgets are measured.
2. **Phase 1, foundation.** Compose with the database, SQLAlchemy and Alembic, pre-commit, CI, ADRs. Exit: healthy database and green CI.
3. **Phase 2, data.** Schema and migrations, MT5 collector, `PostgresProvider`, corporate events, ingest validation. Exit: PETR4 on H1 and H2 loaded, and `docs/data-notes.md` records adjustment and history depth.
4. **Phase 3, MVP on real data.** Point the notebook at Postgres, re-run the Phase 0 backtests and optimizations on MT5 data, and compare them with the yfinance results. Exit: differences between sources are explained in `docs/data-notes.md`, and the in-sample against out-of-sample report runs on real data. **The MVP is complete here.**
5. **Phase 4, API and jobs.** Endpoints, `run_hash` cache, ARQ worker, server-sent progress, optimizer endpoints. Exit: integration tests green and a cached run under budget.
6. **Phase 5, frontend.** Parameter form with optimize toggles, stat cards, equity curve, trade chart, monthly returns, calendar, optimizer results, a visible disclaimer, Playwright smoke test.
7. **Phase 6, portfolio polish.** README, a demo deployed through a CD workflow the owner writes and running on the yfinance fallback, limitations section. Add the Parquet and DuckDB cache only if a benchmark demands it.
8. **After that.** Benchmark comparison (buy and hold, Ibovespa), Monte Carlo reshuffle of trades, walk-forward testing, screener, portfolio view, multi-ticker runs, alerts.

**Portfolio polish checklist:** a README with what and why, an architecture diagram, a three-command quick start, the backtest rules and honest limitations (look-ahead handling, slippage, survivorship, data adjustment), a screenshot or GIF, a reproducible example, links to the ADRs, and CI badges.

**Open questions (resolve before the phase that needs them):**

- [x] 123 de compra definition: the owner supplied pseudocode on Oct 4, 2026 (lowest-low pattern, EMA trend context, frozen levels), written in section 7. It replaces the earlier QuantBrasil-page reading.
- [ ] Sign off the section 7 assumptions: entry-candle stop check, gap fills on exit (and a fill gapping past the target), no trade below one lot, one working order or position, open position at end of data, zero-PnL trades, EMA seed and warm-up, day-trade exit candle and short days, zero risk.
- [x] Day-trade mode: the owner gave the rules and the 16:30 exit time; orders may carry overnight and the forced exit is priced at the exit candle's close by default (Oct 4, 2026).
- [ ] Export a finer timeframe (M30 or M15) from MT5 to pinpoint 16:30 with policy `auto`.
- [ ] Explain the vendor differences found against the QuantBrasil sample trades (opening and closing auction handling in the first and last candle of the day), recorded in `docs/data-notes.md`.
- [ ] Define 123 de venda.
- [ ] Choose the MVP instrument universe, for example a few liquid stocks, one ETF and one index.
- [ ] Find out whether the broker's MT5 history is adjusted and how deep H1 and H2 go.
- [ ] Confirm B3 session hours per asset class. The day-trade exit time is a parameter, set to 16:30 for the owner's case; the official value is not recorded.
- [ ] Confirm the timezone of MT5 exported bar times. Working assumption: `America/Sao_Paulo` wall-clock time (the owner says broker and B3 share a timezone, but cannot say which one the export uses). Verify against the B3 calendar and record in `docs/data-notes.md`.
- [ ] Approve the `score_v1` formula in `docs/score.md`.
- [ ] Pick the repo license and the hosting target for the demo.

## 11. Learning mode

The owner is building this project to learn the stack and to defend every part of it in an interview, so Claude teaches and reviews by default and writes code only where the table below says so. React is rusty; FastAPI, Postgres, Redis, SQLAlchemy, DuckDB and Docker were only used briefly; TanStack Query and CD are new; CI is somewhat new. TDD is already familiar, so Claude skips TDD primers and goes straight to the test. GitHub Copilot in VS Code is the owner's typing assistant.

Three modes: **Learn** (the owner writes, Claude teaches and reviews), **Refresh** (Claude drafts, the owner rewrites parts), **Delegate** (Claude writes, the owner explains it back). The owner can switch any task's mode at any time by saying so, and Claude then follows the new mode.

| Area | Mode | What happens |
| --- | --- | --- |
| Engine, 123 rules, metrics (`core`) | Learn | Owner writes the tests and the code; Claude explains concepts and reviews |
| FastAPI, SQLAlchemy, Alembic, Postgres schema | Learn | Owner writes the first endpoint, model and migration; Claude extends them in the owner's pattern |
| Redis and ARQ | Learn | Owner writes the `ping` job and the first backtest job |
| MT5 collector | Learn | Owner writes it |
| Deployment (CD) | Learn | Owner writes the deploy workflow in Phase 6; Claude reviews |
| React UI and TanStack Query | Refresh | Claude drafts; the owner restructures and writes one component and one query hook per phase |
| Docker and Compose, GitHub Actions CI | Refresh | Claude writes the first Dockerfile and the first workflow; the owner writes the next ones and explains every line |
| Linting and config | Delegate | Claude writes; the owner reads it |
| DuckDB cache | Later | Only after the benchmark gate, starting with a notebook spike |

In Phase 0, task 1 (minimal setup) is Refresh, with the owner writing the first core test, and tasks 2 to 5 (data, engine, notebook, optimizer) are Learn. In Phase 1, task 2 (database) is Learn, tasks 1 and 3 (repo hardening, CI) are Refresh, and in task 4 the owner writes the ADRs in their own words.

**Claude's checklist at the start of every task:**

1. Say which mode the task falls under, using the table.
2. For a Learn task, give a short primer (what the concept is, why it is used here, one common pitfall), name the failing test the owner writes first, then stop and wait.
3. Do not write production code in a Learn area unprompted. If the owner says to just do it, state in one line what learning is skipped, then do it.
4. Review the owner's code with specific findings and the concept behind each, not a rewrite.
5. For Refresh and Delegate tasks, write the code, then walk through the non-obvious parts.

**Checkpoint at the end of every slice:**

- Ask two or three explain-back questions about what was just built, wait for the answers, and correct them kindly.
- Add an entry to `docs/learning-log.md`: concept, where it is used, status (explained, shaky, to revisit) and date.
- Prompt the owner to write the ADR for any decision made, in their own words.
- Merge only when the owner can explain the change without looking at it.

**Learning ramp:**

The rows come into play in this order: the genetic algorithm in Phase 0; Postgres, SQLAlchemy, Alembic, Docker Compose for the database and GitHub Actions CI in Phases 1 and 2; FastAPI, Redis and ARQ, React, TanStack Query and Docker images from Phase 4 on; CD in Phase 6; DuckDB only if the benchmark gate triggers.

| Tool | Starting point | The owner first writes | Must be able to explain |
| --- | --- | --- | --- |
| FastAPI | New | `GET /health`, then a `POST /backtests` stub | Dependency injection, Pydantic validation, sync versus async handlers |
| SQLAlchemy 2 and Alembic | New | The `instruments` model and the first migration | Session lifecycle, `select()` queries, what autogenerate cannot detect |
| Postgres | Brief | DDL for `candles` with its composite key, then `EXPLAIN` on a candle query | Indexes, why key order matters, B-tree versus BRIN |
| Redis and ARQ | New | The `ping` job, then a backtest job | Queues, retries, result expiry, why the worker is a separate process |
| React | Rusty | One page that calls `/health` | Components, props versus state, effects |
| TanStack Query | New | A query hook for `/health`, then one mutation | Server state versus UI state, query keys, caching and invalidation |
| Docker and Compose | Brief | The `web` Dockerfile and its healthcheck | Images versus containers, multi-stage builds, volumes, networks, `depends_on` with healthchecks |
| GitHub Actions CI | Somewhat new | The lint job, then the Postgres-backed test job | Workflows, jobs, service containers, caching, why CI runs on every push |
| CD | New | A workflow that deploys the demo after CI passes on `main` | Environments and secrets, rollbacks, why deploy is separate from CI |
| DuckDB and Parquet | New | A notebook that reads a Parquet file | When columnar storage beats row storage |

**Using GitHub Copilot alongside Claude:**

- Copilot is for typing speed inside code the owner is already writing: completions, repetitive tests, boilerplate. Claude is for design, explanation and review.
- In Learn areas, write the first version of each new concept by hand, typing the signature and a comment before accepting any completion, and read every suggestion before keeping it.
- Add `.github/copilot-instructions.md` that repeats the key rules from `CLAUDE.md`, so both assistants follow the same conventions.
- Never accept a Copilot suggestion for a trading rule or a metric formula unless a test pins its behaviour.

## 12. Optimizer

The optimizer searches a strategy's parameter space for the combination that scores best on a chosen objective, with guardrails against overfitting. It lives in `core` as pure code and is part of the MVP: Phase 0 builds it and runs it from the notebook, and Phases 4 and 5 add the API job and the UI.

**What the user sets:**

- For each parameter: a fixed value, or "optimize" with a start, a stop and a step (a time window or a list of options for non-numeric parameters).
- An objective: `score_v1`, profit factor, net result, EV, or minimum drawdown, plus optional constraints such as at least 30 trades or a drawdown cap.
- An algorithm: grid search or genetic algorithm. The optimizer reports the size of the search space before running and recommends the grid when it is small.
- A period split: in-sample for the search, out-of-sample to validate the best results.
- A budget: maximum evaluations and maximum time.

**Grid or genetic algorithm.** For the 123 strategy a grid is probably enough. For example, `target_mult` from 1 to 5 in steps of 0.5 (9 values), `entry_offset_ticks` from 0 to 3 (4) and `entry_validity_bars` from 1 to 5 (5) give 180 combinations, and at the 200 ms engine budget that takes well under a minute. Adding entry-window times, say 8 values each, gives about 11,500 combinations, which is tens of minutes on one core. A genetic algorithm pays off from there upward, and the grid still has one advantage: it produces the full map of results, which is the best overfitting diagnostic. Build both.

**Design rules:**

1. Generate each parameter's values from an integer index (`start + i * step`) to avoid floating-point drift. Drop combinations that break a constraint, such as `min_entry_time` after `max_entry_time`, before evaluating them.
2. Every evaluation is a normal backtest keyed by `run_hash`, so repeated individuals and re-runs hit the cache. The stored trials double as heatmap data.
3. All algorithms sit behind one `Optimizer` interface: `GridSearch` first, `RandomSearch` next (a few lines), `GeneticSearch` after. Each takes a seeded random generator, so the same seed and config give the same result.
4. The genetic algorithm encodes an individual as one index per parameter. Use tournament selection, uniform crossover, mutation by stepping an index up or down, elitism, and stop on a generation limit or when there is no improvement. Fitness is the objective, with a heavy penalty for violated constraints.
5. Test the genetic algorithm against the grid: on a small space where the grid's best is known, the genetic search must find it, or land within one step, across several seeds.
6. Evaluate trials in a process pool. Keep queue and web code out of `core`.
7. Always report the number of trials next to the best result, because the best of many trials is partly luck.

**Overfitting guardrails (not optional):**

- Run the search on the in-sample period only. Re-run the top results on out-of-sample data and show both side by side, flagging large drops.
- Show a neighbourhood view or heatmap. A good parameter set surrounded by bad neighbours is a warning sign; a broad plateau is a good sign.
- Walk-forward optimization with rolling windows comes after the first version.
- Optimizer output is historical and carries the same disclaimer as backtests.

**Data model and API:**

- Tables `optimization_runs` (`id`, `config` JSONB, `objective`, `algorithm`, `seed`, `status`, `created_at`) and `optimization_trials` (`run_id`, `params` JSONB, `run_hash`, `objective_value`, `phase` as in-sample or out-of-sample).
- Endpoints: `POST /optimizations`, `GET /optimizations/{id}`, `GET /optimizations/{id}/trials`, and `GET /optimizations/{id}/events` for server-sent progress (generation and best so far). The run is an ARQ job and can be cancelled.

**UI:** each parameter gets an "optimize" toggle with start, stop and step. Results show a ranked table, a heatmap for any two parameters, a convergence chart for the genetic algorithm, and in-sample versus out-of-sample columns. Clicking a row opens that backtest.

**Build order and modes:**

1. `GridSearch`, objectives and constraints, with tests, run from the notebook (Phase 0, Refresh).
2. In-sample and out-of-sample split, plus a heatmap in the notebook (Phase 0, Learn).
3. `GeneticSearch` with the grid comparison test (Phase 0, Learn: the owner writes it).
4. API job, endpoints and server-sent progress (Phase 4, Refresh).
5. UI (Phase 5, Refresh).

Later: multi-objective search (profit versus drawdown) returning a Pareto front. Optuna is a mature alternative with Postgres storage, but it is outside the stack in section 3, so use it only as a benchmark to compare the hand-written genetic algorithm against, and ask first.
