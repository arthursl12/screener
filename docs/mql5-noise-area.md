# MQL5 (MetaTrader 5): Noise Area momentum

The rule of `docs/brief.md` section 10 as **one file**, `mql5/Experts/NoiseAreaEA.mq5`: an Expert Advisor that trades (and backtests in the Strategy Tester) and also draws the bands, the VWAP and arrows where the position changes, as chart objects. (MT5 does not allow one file to be both an EA and an indicator; the drawing is done by the EA.) In the file, in order: the rule (class `CNoiseCore`: bands, VWAP, history of the moves, stops, position; fed one closed bar at a time), the inputs, the drawing, the trading.

**It has not been compiled in MetaEditor by me** (no MetaTrader here). What was checked: the text of `CNoiseCore` (the class in the file), compiled as C++ with small stand-ins for the MQL types (`MqlDateTime`, `TimeToStruct`, `ArrayResize`...), was run on all 687,506 one-minute bars of WIN (2021-12 to 2026-11-16) against the Python engine. See "What was checked". The rest of the file (inputs, `CopyRates`, `CTrade`, the chart objects, `SymbolInfoSessionTrade`) is not covered by that.

## Install

Copy `NoiseAreaEA.mq5` into `MQL5/Experts/` in the terminal's data directory (File > Open Data Folder), open it in MetaEditor and compile (F7). Drag it onto a chart. Nothing else is needed.

The drawing: `DrawChart` (on by default; off in a non-visual Strategy Tester run) and `DrawDays` (the drawing of the last 5 days is kept; older objects are deleted on each new day). To trade nothing and only look at the bands, set `SendOrders` to false.

## Inputs

The inputs are the parameters themselves, so the Strategy Tester can optimize them. The defaults are the **WIN optimized** trial; the paper's rule is typed in by hand.

| Input | Default: WIN optimized | The paper (original) |
| --- | --- | --- |
| `Lookback` (days; the days needed before a band shows is this minus 1) | 20 | 14 |
| `Mult` (band multiplier k) | 1.5 | 1.0 |
| `Cadence` (decision every N minutes) | 60 | 30 |
| `FirstDecision` (HHMM) | 1200 | 900 |
| `ExitTime` (HHMM, 2400 = hold to the close) | 1820 | 2400 |
| `StopKind` | `NA_STOP_BAND` (back inside the band) | `NA_STOP_VWAP_BAND` (inside the band or across the VWAP) |
| `EveryBar` (act on the stop at every bar) | true | false (the checkpoints only) |

Other inputs: `SessionStart` (HHMM, **server time**, default 900), `SessionEnd` (HHMM the day's **last bar closes**: WIN 1825, 1755 on the days B3 closes early; stocks 1800), `AutoSessionEnd` (on by default: the day's end is the close of the previous day's last bar, so the 17:55 and 18:25 seasons are followed; `SessionEnd` is then only the start value), `UseRealVolume` (the VWAP weighs real volume, as the Python model does; false for tick volume), and for the EA `Sizing` (`NA_SIZE_FIXED`: `Lots` contracts every day; `NA_SIZE_VOLTGT`: the paper's volatility target, below), `Lots`, `MagicNumber`, `DeviationPts`, `SendOrders` (false: compute and log only), `WriteLog`.

The WIN optimized default is the best trial **by WIN** of the 50,000-trial search, chosen on development data. On the final test its WIN Sharpe went from 2.05 to 2.10, but it failed on WDO and does not beat the CDI on the 50/50 average (`docs/adr/0001-winfut-intraday-momentum-final-test.md`). It is not a signal service.

## How it trades

At the **close of each bar** the core works out the position wanted for the next bar: what was decided at this close, flat from `ExitTime`, and flat by the day's last bar. The EA sets that position with market orders on the first tick of the new bar, so a fill is at the **next bar's open**, as in ProfitPro and as in the `entry_next_open` columns of `notebooks/winfut_trade_book.ipynb`. A reversal is a close and an order the other way. Unlike ProfitPro's backtest, MT5 shows the EA its position at once, so a stop on the first bar held is acted on at the next open (the Python model's way), not one bar late.

**No position is carried over a day boundary**, two ways. The flatten goes out one bar before the day's last bar (a market order sent at the last bar's close would fill the next morning), which needs the real close (332 of the 1,238 days in the WIN data close at 17:54, not 18:25: the US-DST months of 2022 and 2023). With `AutoSessionEnd` off and `SessionEnd` 1825, the EA held 52 trades overnight in the 2021-12 to 2026-11 test. With it on, the first day of a season that closes earlier (2022-03-14, 2023-03-13) is still not known in advance. And whatever the last bar of a day wanted, the first bar of a new day starts flat.

Use a **minute chart** (1 minute is the exact one); the chart period must divide `Cadence`. Needs the lookback in days of history to be loaded. `WriteLog` writes `MQL5/Files/noise_area_log.csv` (one row per bar: time, close, sigma, bands, VWAP, the position decided, held and wanted) to compare with the Python engine bar by bar.

## Strategy Tester

Symbol: the same continuous WIN series the data was exported from (`WIN$N`), M1, with the deposit in reais. Costs: set the commission in the tester or the symbol (the model's are R$ 0.25 a side plus one tick of R$ 1.00 slippage). "Every tick" (or "1 minute OHLC") both fill the first tick of a new bar at its open. `Lots` 1 to compare with the one-contract model.

## What was checked

The `CNoiseCore` class (copied verbatim from the earlier `NoiseCore.mqh`, checked identical) compiled with `g++ -Wall` (no warnings) and run on all the bars against `strategy_exposure`, for five configurations (WIN optimized; the paper; the opposite-band stop on the grid; the VWAP-only stop at every bar; VWAP+band at every bar with 15-minute steps, a 10:30 start and a 17:30 exit): **0 bars where the position held differs from the engine out of 687,506**, in all five. The position wanted for the next bar equals the next bar's held position, except in 2 bars of three of the configurations on 2026-03-10 and 2026-10-28, days whose last bar is missing in the data; and the wanted position is flat on the last two bars of every day that closes at 18:25.

## Not checked, to try in MT5

- That the file compiles in MetaEditor, and that the chart objects draw (segments, arrows).
- That `CTrade` fills correctly on the B3 symbol (`SetTypeFillingBySymbol`) and that `PositionClose` then an order the other way behaves on the account's margin mode (netting or hedging).
- `AutoSessionEnd` (the previous day's last bar): rerun 2021-12 to 2026-11 and check there is no position held over a night.
- That the Strategy Tester's M1 history matches the exported CSV (it should: the data was exported from MT5).

## Position size

`Sizing = NA_SIZE_VOLTGT` is the paper's sizing, as in the Python model (`contracts_for`): each day, contracts = balance / (day open x point value) x min(`TargetVol` / volatility, `MaxLeverage`), rounded, and never more than balance / `MarginPerContract`. The volatility is the sample standard deviation of the 14 daily close-to-close returns of days d-15 to d-2 (the day before is left out, as in the authors' notebook); with fewer than 14 returns the cap is used. Defaults: 2%, 4, R$ 1,000. The balance is the account's balance at the start of the day (it compounds, as the model's does; a R$ 100,000 deposit in the tester matches the model's start). The point value is read from the symbol (WIN: R$ 0.20). The day's contracts are written to the Experts log.

Checked: the volatility, computed with the EA's indexing over the 770 development days, equals `daily_volatility` on all of them. Not checked in MT5: the sizing end to end (the contracts of each day against the model's `contracts` column).

For the paper's rule, use `Sizing = NA_SIZE_VOLTGT` with the paper's inputs (see the header of the file).

