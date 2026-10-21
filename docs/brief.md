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

## 7. Strategy specs: 123 de compra (123 de venda follows) and IFR2

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

**IFR2 (RSI 2) de compra. Drafted by Claude from the owner's decisions of Oct 17, 2026; the owner reviewed it, signed off the assumptions and widened two grids. The owner still rewrites it in their own words.** The idea comes from the research notes in `ifr2/`, which are secondary sources whose numbers are not verified. The rules below are the only IFR2 rules the engine implements. Long only, specified for daily candles. Other timeframes run, since every rule counts candles, but they raise a warning and are outside the spec (owner decision, Oct 18, 2026).

- **Indicators**, on the raw close (split-adjusted, dividends ignored): `RSI` with Wilder smoothing over `rsi_period`, and `ATR` with Wilder smoothing over `atr_period` (both in `indicators.py`).
- **Signal:** on a closed candle t, `RSI[t] <= rsi_entry`. While `RSI` or `ATR` is not yet available (the first `max(rsi_period, atr_period)` bars), the signal is ignored.
- **Entry:** a buy at `Close[t]`, the close of the signal candle. This is a named exception to section 6, rule 1 (a signal fills no earlier than the next candle): it is a fixed property of IFR2, called `entry_at_signal_close`, with its own test. Live, the order goes in about 10 minutes before the close, so the backtest fill is an approximation of it. An entry needs no open position (section 6, rule 8). When the previous trade exited on this same candle, a new entry is allowed only if `allow_same_day_reentry` is on.
- **Sizing:** `quantity = max_risk_brl / (atr_mult * ATR[t])`, rounded down to the lot and capped so that `quantity * entry` does not exceed `capital_brl`. The ATR distance only sizes the position. It is not a stop, because IFR2 has none, so a bad trade can lose more than `max_risk_brl`. If `ATR[t]` is zero or missing, or the quantity rounds to zero, no trade is taken.
- **Exits.** From the candle after the entry. Which exits are on follows `exit_mode`, plus the time stop when `max_days` is set. The target comes first; when several fire on the same candle the order is target, then time stop, then RSI exit:
  1. **Target** (`exit_mode` `target` or `target_or_rsi`): `target` is the highest high of the previous `target_lookback` candles, not including the current one, and it moves every candle. When `High[t] > target`, the exit fills at `target`, or at `Open[t]` if the candle opens above it.
  2. **Time stop:** after `max_days` candles in the trade (`none` means off), the exit fills at `Close[t]`. The entry candle is day 0, so `max_days` 1 exits at the close of the next candle.
  3. **RSI exit** (`exit_mode` `rsi` or `target_or_rsi`): when `RSI[t] >= rsi_exit`, the exit fills at `Close[t]`.
- **No stop loss.** The research notes report that stops usually hurt mean reversion, and gaps jump past them anyway. Risk is managed by sizing, the time stop and the choice of instruments.
- **Costs:** `cost_pct` percent of traded value on each side. The IFR2 preset is 0.03; the engine default stays 0 so golden tests stay readable (section 6, rule 9). Fixed capital, no compounding (section 6, rule 7).

**IFR2 parameters:**

| Parameter | Default | Range or grid | Notes |
| --- | --- | --- | --- |
| `rsi_period` | 2 | 2 to 4 | Wilder RSI length |
| `rsi_entry` | 30 | 5 to 40, step 5 | Buy when RSI is at or below this |
| `exit_mode` | `target` | `target`, `rsi`, `target_or_rsi` | Which exits are on (the time stop is separate) |
| `rsi_exit` | 70 | 50 to 80, step 10 | Only used when the mode has `rsi`; must be above `rsi_entry` |
| `target_lookback` | 2 | 2 to 10, step 1 | Only used when the mode has `target` |
| `max_days` | none | none, 3, 5, 7, 9 | Time stop in candles; none means off |
| `allow_same_day_reentry` | off | on or off | Entry on the candle where the previous trade exited |
| `atr_period` | 5 | 2 or more | Wilder ATR length |
| `atr_mult` | 2 | above 0 | Risk distance as a multiple of ATR |
| `max_risk_brl` | 2000 | > 0 | Risk budget per trade, drives quantity |
| `capital_brl` | 100000 | > 0 | Fixed per trade, no compounding |
| `lot_size` | 1 | 1 or more | Fractional market |
| `cost_pct` | 0.03 (preset) | 0 or more | Percent of traded value per side |

`rsi_exit` and `target_lookback` are conditional: the optimizer drops combinations where the chosen `exit_mode` makes them irrelevant (no duplicate runs), and combinations with `rsi_entry >= rsi_exit`.

**IFR2 engine assumptions (owner signed off Oct 17, 2026):**

1. **Comparisons are inclusive or strict as written:** `RSI <= rsi_entry`, `RSI >= rsi_exit`, and `High > target`. Equality is rare with floating-point values, so this only matters in hand-computed tests.
2. **Entry candle.** Exits are not evaluated on the entry candle itself, because the entry is at its close.
3. **Exit order.** The target comes first and fills at its own price. The time stop and the RSI exit both fill at the close, so their order only decides the exit reason: `time` when both fire (the owner's order is target, time stop, RSI exit).
4. **Gap above the target.** The exit fills at the open, a better price than the target, as in the prototype. There is no gap case for losses because there is no stop.
5. **Flat RSI window.** A window with no gains and no losses gives no RSI value, so there is no signal. TA-Lib would return 0, which would read as oversold.
6. **Open position at the end of the data** is not a closed trade and is left out (same as 123, assumption 6).
7. **Dividends and JCP are ignored.** Trades through an ex-date book the price drop without the payment, which is pessimistic. Holds are short, so the effect is expected to be small.
8. **Fill at the close is optimistic.** The real close is an auction price. Slippage is not modelled yet, and stays that way for now.

**Worked example for the first IFR2 golden test** (daily candles, `rsi_period` 2, `rsi_entry` 30, `exit_mode` `target`, `target_lookback` 2, `max_days` none, `atr_period` 2, `atr_mult` 2, `max_risk_brl` 100, `capital_brl` 10,000, `lot_size` 1, no costs):

| Bar | Open | High | Low | Close | RSI(2) | ATR(2) | What happens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10.00 | 10.10 | 9.90 | 10.00 | none | none | Warm-up |
| 1 | 10.00 | 10.60 | 10.00 | 10.50 | none | none | Warm-up |
| 2 | 10.50 | 10.60 | 10.10 | 10.20 | 62.50 | 0.5500 | First values |
| 3 | 10.20 | 10.30 | 9.70 | 9.80 | 31.25 | 0.5750 | Above 30: no signal |
| 4 | 9.80 | 9.90 | 9.40 | 9.50 | 17.86 | 0.5375 | Signal: buy at the close, 9.50 |
| 5 | 9.60 | 10.00 | 9.50 | 9.90 | | | Target is max(10.30, 9.90) = 10.30; High 10.00 does not reach it |
| 6 | 9.90 | 10.10 | 9.80 | 10.00 | | | Target is max(9.90, 10.00) = 10.00; High 10.10 reaches it: exit at 10.00 |

Expected result: risk distance `2 * 0.5375 = 1.075`, quantity `floor(100 / 1.075) = 93`, cost `93 * 9.50 = R$ 883.50`, within the capital cap. PnL is `93 * (10.00 - 9.50)`, which is **+R$ 46.50**, after 2 candles in the trade. (These RSI and ATR values were checked against `b3core.indicators`.)

**IFR2 golden cases to write, one test each:** the worked example; RSI exactly at the threshold; the target built from previous candles only; a gap above the target filling at the open; the RSI exit at the close; `target_or_rsi` with both firing on one candle; the time stop and its day counting; no exit check on the entry candle; no entry while a position is open; same-day re-entry off and on; warm-up bars never signal; ATR zero or missing skipping the signal; quantity rounding to zero; the capital cap; costs of 0.03% on both sides; an open position at the end of the data left out; a flat start giving no signal; a non-daily timeframe running with a warning.

## 7c. Strategy spec: Turtle breakout with ATR pyramiding (de compra)

**Status. Drafted by Claude on Oct 21, 2026 from the owner's TradingView script (`turtle/turtle.pine`) and the owner's answers of the same day. The owner rewrites it in their own words.** The script is the source of truth; where it is silent, the rule is marked **(assumption)**, pinned by a test and listed in section 10. Long only, specified for daily candles. This strategy is a validation exercise: results are read as "does the rule set work", not as an account that could be funded (see the capital cap below).

**Turtle de compra.** A channel breakout that adds to a winning position in steps of ATR and leaves on a channel breakdown or an ATR stop. All signals are read on a closed candle `t`.

- **Indicators**, on the raw close: `ATR` with Wilder smoothing over `atr_period` (`indicators.py`). The channels use the highs and lows of the previous candles only, never the current one: `entry_level[t] = max(High[t-entry_period .. t-1])` and `exit_level[t] = min(Low[t-exit_period .. t-1])`.
- **Warm-up:** a signal needs the entry channel (`entry_period` previous candles), `ATR[t]` and, for adds and stops, `ATR[t-1]`. Until they exist, nothing is signalled (owner, Oct 21, 2026).
- **State.** The position is a list of **units**, each with its quantity and fill price. `avg` is the quantity-weighted average price of the current units, costs excluded. It starts over when the position is flat. The reference price `ref` is `avg`, or the price of the last unit when `use_last_fill` is on.
- **Signals on candle `t`:**
  - `buy`: flat at the start of the candle, and `Close[t] > entry_level[t]` (strict).
  - `sell`: long, and `Close[t] < exit_level[t]` (strict).
  - `stop`: long, and `Close[t] < avg - ATR[t-1]`. The stop is read on the close. It is **not** a resting order, so a gap or an intraday drop is not stopped at the stop price; the position leaves at the close and can lose more than one ATR (owner: follow the script).
  - `add`: long, `units < max_units`, and `Close[t] > ref + add_atr_mult * ATR[t-1]`.
- **Sizing.** `risk_budget = capital_brl * risk_pct / 100`. A new unit, entry or add, has quantity `floor(risk_budget / ATR[t])`, rounded down to the lot, with the current candle's `ATR[t]` (not `t-1`). So units differ in size. If the quantity is below one lot, or `ATR[t]` is zero or missing, the unit is skipped, the unit count does not advance, and the candle is counted for the warning below.
- **Exits.** All units leave together. When both fire, `sell` takes priority over `stop`, and a candle that exits takes no add (**assumption**: the script places the add before the exit, which only adds a zero-PnL unit and its costs). The exit price depends on `fill_at`.
- **One add per candle** (owner, Oct 21, 2026). If, after an add, the recomputed `avg` and add level would still be passed by the same close while `units < max_units`, that candle justified more than one add. It is counted.
- **Warnings** (owner, Oct 21, 2026): the run emits one warning for each of the two cases, with the number of candles, and the result stores both counts: (1) a unit was skipped because its quantity was below one lot; (2) a candle justified more than one add.
- **No re-entry on the exit candle:** a new `buy` is possible from the next candle on, because the position state is read at the start of the candle (**assumption**, equal to the script).
- **Fills (`fill_at`).**
  - `signal_close` (default, the script): every fill, entry, add and exit, is at `Close[t]` of the signal candle. This is the same named exception to section 6 rule 1 as IFR2 (`entry_at_signal_close`). Live, the order would go in shortly before the close; the real close is an auction price, so this is optimistic and no slippage is modelled.
  - `next_open`: the signal, the quantity and the levels come from candle `t`, and the order fills at `Open[t+1]`. The units are in the position from that fill, so the average price uses the actual fills. While an order is pending nothing new is signalled. A signal on the last candle of the data has no next open and takes no trade. The owner runs both and compares them.
- **Costs:** `cost_pct` percent of traded value on every fill, both sides. The preset is 0.03; the engine default is 0.
- **No capital cap (owner, Oct 21, 2026).** `capital_brl` only sets the risk budget. The money in the position is not limited by it: with a 3% ATR one unit costs about R$ 17,000 and four units about R$ 67,000 against R$ 25,000. The result reports the **peak money in the position** (the largest `sum(quantity * fill price)` of the open units), and any CAGR on `capital_brl` is read next to it. The cap is a deferred rule (section 10).
- **One position at a time, long only**, and the trade statistics treat the whole position, from its first unit to the exit, as **one trade** with the sum of its units' PnL and the number of units.
- **Open position at the end of the data** is not a closed trade and is left out of the trade statistics, but the equity curve marks it at the last close, as IFR2 does (owner, Oct 21, 2026). The result reports how many units were open.
- **Dividends and JCP are ignored**, raw closes, fixed capital with no compounding (section 6, rule 7).

**Turtle parameters:**

| Parameter | Default | Range or grid | Notes |
| --- | --- | --- | --- |
| `entry_period` | 20 | 1 or more | Highest-high channel length |
| `exit_period` | 20 | 1 or more | Lowest-low channel length |
| `atr_period` | 14 | 1 or more | Wilder ATR length |
| `add_atr_mult` | 1.0 | above 0 | An add every this many ATR above `ref` |
| `max_units` | 4 | 1 to 10 | 1 means no pyramiding |
| `use_last_fill` | off | on or off | Measure the add level from the last fill instead of `avg` |
| `capital_brl` | 25000 | > 0 | Sets the risk budget only (no cap) |
| `risk_pct` | 2.0 | above 0 | Percent of `capital_brl` risked per unit (the script's "risk per trade") |
| `lot_size` | 1 | 1 or more | Any whole number of shares (owner: 72, 143, ...) |
| `fill_at` | `signal_close` | `signal_close`, `next_open` | See fills above |
| `cost_pct` | 0.03 (preset) | 0 or more | Percent of traded value, per fill |

The stop distance is fixed at one ATR, as in the script; it is not a parameter.

**Worked example for the first Turtle golden test** (daily candles, `entry_period` 2, `exit_period` 2, `atr_period` 2, `add_atr_mult` 1, `max_units` 1, `capital_brl` 10,000, `risk_pct` 2 so `risk_budget` is R$ 200, `lot_size` 1, `fill_at` `signal_close`, no costs):

| Bar | Open | High | Low | Close | ATR(2) | Entry level | Exit level | What happens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 10.00 | 10.20 | 9.90 | 10.10 | none | none | none | Warm-up |
| 1 | 10.10 | 10.30 | 10.00 | 10.20 | none | none | none | Warm-up |
| 2 | 10.20 | 10.40 | 10.10 | 10.30 | 0.3000 | 10.30 | 9.90 | Close equals the entry level: strict, no signal |
| 3 | 10.30 | 10.60 | 10.25 | 10.55 | 0.3250 | 10.40 | 10.00 | Close above 10.40: buy at 10.55, quantity `floor(200 / 0.325) = 615` |
| 4 | 10.85 | 11.20 | 10.80 | 11.10 | 0.4875 | 10.60 | 10.10 | Add level `10.55 + 0.325 = 10.875` is passed, but `max_units` is 1: nothing |
| 5 | 11.10 | 11.30 | 11.00 | 11.20 | 0.3938 | 11.20 | 10.25 | Nothing. Stop is `10.55 - 0.4875 = 10.0625` |
| 6 | 11.00 | 11.05 | 10.60 | 10.70 | 0.4969 | 11.30 | 10.80 | Close 10.70 is below the exit level 10.80: sell at 10.70 |

Expected result: one trade, 615 shares, entry 10.55, exit 10.70, PnL `615 * 0.15 =` **+R$ 92.25**, after 3 candles in the trade, peak money in the position `615 * 10.55 = R$ 6,488.25`. (The ATR values were checked against `b3core.indicators`.)

**Second worked example, pyramiding** (same candles, `max_units` 2): bar 4 passes the add level 10.875, so it adds `floor(200 / 0.4875) = 410` shares at 11.10 (sized with the current candle's ATR, not the previous one). The average price becomes `(615 * 10.55 + 410 * 11.10) / 1025 = 10.7702`. Bar 5 does not add (the limit is reached, and 11.20 is below the new level `10.7702 + 0.4875 = 11.2577`). Bar 6 sells all 1,025 shares at 10.70: PnL `615 * 0.15 + 410 * (-0.40) =` **-R$ 71.75**, 2 units, peak money in the position `615 * 10.55 + 410 * 11.10 = R$ 11,039.25`.

**Turtle golden cases to write, one test each:** the worked example; the second (pyramiding) example; the close equal to the entry level; the channel excluding the current candle; warm-up bars never signal; the stop on the close, with the exit at the close and not at the stop price; `sell` and `stop` on one candle (sell wins); a candle with `sell` that would also add (no add); the add level from the average and from the last fill; a unit sized with the current ATR; a quantity below one lot skipped, counted and warned; a candle that justifies more than one add, counted and warned; `max_units` as the ceiling; no re-entry on the exit candle; costs of 0.03% on every fill; the peak money in the position; an open position at the end of the data (equity marked, not a trade); `next_open` fills, a pending order blocking new signals, and a signal on the last candle taking no trade; a non-daily timeframe running with a warning (copied from IFR2, assumption).

**Turtle engine assumptions (pending the owner's sign-off):** the add on an exit candle is dropped; the whole position is one trade; the `next_open` details above; the strict comparisons as written; the order of the warm-up checks; a non-daily timeframe runs with a warning.

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
- [x] Approve the `score_v1` formula in `docs/score.md` (owner approved, Oct 17, 2026). Out-of-sample stays a separate flag, not part of the score.
- [ ] IFR2 (RSI 2) rules, decided by the owner on Oct 17, 2026; the owner writes them as a new subsection of section 7, and the items below are pinned by tests first:
  - [x] Entry at the close of the signal candle (live: the order goes in about 10 minutes before the close). This is a named exception to section 6 rule 1, a setting rather than a silent change.
  - [x] Exit on a bar: the highest-high target fills at the target price, or at the open when the bar gaps above it; the time stop and the RSI exit fill at the close. When several fire on the same bar, the target wins (assumption, needs a test).
  - [x] Re-entry on the same bar as an exit: off by default, kept as a boolean parameter so the optimizer can search it.
  - [x] Warm-up: signals are ignored until the RSI has `period` bars (assumption, needs a test).
  - [x] Sizing: ATR-based. Quantity = max risk / (k x ATR(n)), rounded down to the lot, capped by available capital. The ATR distance sizes the position and is not an exit, because the strategy has no stop. Capital-fraction sizing is a later, simpler mode.
  - [x] ATR details (owner, Oct 17, 2026): Wilder smoothing; `atr_period` (default 5) and `atr_mult` k (default 2) are both parameters the optimizer can search. Zero or not-yet-available ATR: skip the signal (assumption, needs a test; owner did not answer).
  - [x] Lot size 1, raw (split-adjusted, not dividend-adjusted) prices with dividends ignored, costs of 0.03% per side as the IFR2 preset (the engine default stays 0), fixed capital with no reinvestment.
  - [ ] Confirm the B3 fee of 0.03% per side (0.005% trading + 0.025% settlement) against B3's published table; the figure comes from a research note.
  - [x] Optimization results registry: a SQLite file (standard library) with `results` (cache by `run_hash`), `optimization_runs` and `optimization_trials`, the tables planned for Postgres (owner decision, Oct 18, 2026). Postgres implements the same store later. Registry files are git-ignored. Open: incremental per-ticker caching when new data arrives, and a pruning policy for old data versions.
  - [x] IFR2 RSI input: raw close everywhere, dividends and splits ignored (owner decision, Oct 18, 2026: swing trading, not buy and hold). The research prototype computes the RSI on the adjusted close; with the same input both engines give the same trades.
  - [ ] IFR2 benchmark: compare the strategy with the CDI over the same period (owner, Oct 18, 2026: a strategy that does not beat the CDI failed, because the money could have stayed in a risk-free investment). The exact definition (which CDI series, how idle cash is treated, which return is compared) needs the owner's approval in `docs/` before any code, as `score_v1` did. Income tax and slippage stay out of scope for now.
  - [ ] Report equity drawdown (open trades marked at the close) next to balance drawdown (closed trades only), and rank on equity. Decide whether to use the intraday low for the worst case.
- [x] IFR2 assumptions in section 7 signed off by the owner (Oct 17, 2026), including exit order target, time stop, RSI exit.
- [ ] Owner rewrites the IFR2 subsection of section 7 in their own words.
- [ ] IFR2 sizing after losses (found Oct 18, 2026): the quantity uses the fixed initial `capital_brl`, not the current equity, so a run that loses most of its capital keeps trading the same size and the equity curve can go below zero (VALE3, whole history, capital 10,000, risk 2,000: equity drawdown 111%). The spec does not say what happens at ruin: stop trading, size on current equity, or leave as is. The current behaviour is the fixed-capital reading; no rule has been guessed. Owner to decide.
- [ ] Turtle (breakout with ATR pyramiding), rules from `turtle/turtle.pine` and the owner's answers of Oct 21, 2026, written as section 7c:
  - [x] Warm-up, one add per candle, exits, the fill timing of the script (`signal_close`) and the `next_open` alternative, lot size 1, costs of 0.03% (preset), the stop read on the close: decided by the owner.
  - [x] Both warnings: a unit skipped because its quantity is below one lot, and a candle that justified more than one add (owner, Oct 21, 2026).
  - [ ] **Capital cap (deferred rule).** The script never checks funds, so the money in the position can far exceed `capital_brl`. The owner wants it checked in the ideal world and chose to validate the strategy first. Decide whether the cap applies to each unit or to the whole position, and what a skipped unit does to the count.
  - [ ] Sign off the Turtle assumptions in section 7c: the add on an exit candle is dropped, the whole position is one trade, the `next_open` details, the strict comparisons, a non-daily timeframe.
  - [ ] Owner rewrites section 7c in their own words.
  - [ ] Turtle benchmark: the CDI, IBOV and buy-and-hold comparisons of `docs/cdi.md` and `docs/ibov.md` apply unchanged; decide how to read them next to the peak money in the position.
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
