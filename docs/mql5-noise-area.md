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

Other inputs: `SessionStart` (HHMM, **server time**, default 900), `SessionEnd` (HHMM the day's **last bar closes**: WIN 1825, 1755 on the days B3 closes early; stocks 1800), `AutoSessionEnd` (on by default: the day's end is the earlier of the last two days' closes, so the 17:55 and 18:25 seasons are followed and a day that runs a minute longer than the next does not leave the flatten late; `SessionEnd` is then only the start value), `UseRealVolume` (the VWAP weighs real volume, as the Python model does; false for tick volume), and for the EA `Sizing` (`NA_SIZE_FIXED`: `Lots` contracts every day; `NA_SIZE_VOLTGT`: the paper's volatility target, below), `Lots`, `MagicNumber`, `DeviationPts`, `SendOrders` (false: compute and log only), `WriteLog`.

The WIN optimized default is the best trial **by WIN** of the 50,000-trial search, chosen on development data. On the final test its WIN Sharpe went from 2.05 to 2.10, but it failed on WDO and does not beat the CDI on the 50/50 average (`docs/adr/0001-winfut-intraday-momentum-final-test.md`). It is not a signal service.

## How it trades

At the **close of each bar** the core works out the position wanted for the next bar: what was decided at this close, flat from `ExitTime`, and flat by the day's last bar. The EA sets that position with market orders on the first tick of the new bar, so a fill is at the **next bar's open**, as in ProfitPro and as in the `entry_next_open` columns of `notebooks/winfut_trade_book.ipynb`. A reversal is a close and an order the other way. Unlike ProfitPro's backtest, MT5 shows the EA its position at once, so a stop on the first bar held is acted on at the next open (the Python model's way), not one bar late.

**No position is carried over a day boundary**, two ways. The flatten goes out one bar before the day's last bar (a market order sent at the last bar's close would fill the next morning), which needs the real close (332 of the 1,238 days in the WIN data close at 17:54, not 18:25: the US-DST months of 2022 and 2023). With `AutoSessionEnd` off and `SessionEnd` 1825, the EA held 52 trades overnight in the 2021-12 to 2026-11 test. With it on (the previous day's close only), 5 of 1,486 trades of the paper's rule still went overnight: 2 on the first day of an earlier-closing season (2022-03-14, 2023-03-13, not known in advance) and 3 on days that happened to close a minute before the day before. The earlier-of-two-days rule removes the second kind (checked on the data's closes: the flatten is late on only those two season days). And whatever the last bar of a day wanted, the first bar of a new day starts flat.

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

## Validation in MT5 (Nov 17, 2026)

The Strategy Tester (tick by tick, WIN$N, M1 unless said, 2021-12-01 to 2026-11-16, with the tester's random delay on the later runs) against the Python model, trade by trade (matched on side and entry minute). The reports are in the git-ignored `samples/comparison/`.

| Run | Trades | Matched to the model | Held overnight |
| --- | --- | --- | --- |
| WIN optimized, 1 lot, 2025-01 to 2026-11 | 212 | 212 of 212, all exits in the same minute | 0 |
| WIN optimized, 1 lot, 2021-12 to 2026-11 (first EA) | 582 | 580 | 52 |
| same, after `AutoSessionEnd` (previous day's close) | 581 | 579 | 2 |
| same on M5 (the model run on 5-minute bars through the C++-checked core) | 549 | 547 | 2 |
| paper's rule, volatility sizing, no margin limit | 1,486 | 1,473 | 5 |
| WIN optimized, volatility sizing, no margin limit, R$ 100,000 | 581 | 579 | 1 |
| same, R$ 10,000 | 570 | 570 of the 581 above | 1 |

What was found:
- **Signals and exits agree.** Every difference is explained: the warm-up (MT5 has history before 2021-12-01, the model does not: 2 to 13 trades in December 2021), the flatten one bar before the day's last bar (by design), and the season-switch days below.
- **Overnight positions were a real flaw, found by the 2021 run.** B3 closed at 17:55 in the US-DST months of 2022 and 2023, and at 18:25 otherwise (a few days run a minute longer). With a fixed `SessionEnd` 1825 the EA held 52 trades overnight. It now takes the day's end as the earlier of the last two days' closes. What remains is the first day of a season that closes earlier (2022-03-14, 2023-03-13), which cannot be known in advance, and the mirror day (2022-11-07) when one trade is missed.
- **Fill timing is the difference in P&L.** MT5 fills at the first tick of the next bar, with the tester's random delay, a few seconds after the open. On the same trades it earns 7.1% fewer points than the model at next-open prices with the WIN optimized rule (6.9 points a trade) and 27.3 against 37.3 points per contract round trip with the paper's rule (every 30-minute checkpoint, more at the open and close). The model's one tick a side of slippage (10 points a round trip) brings the model within 0.2% of MT5 for the paper's rule (R$ 69,760 against R$ 69,876) and within 5% for the WIN optimized (MT5 higher). It is a good average and not a constant.
- **Sizing.** The paper's volatility target (`Sizing = NA_SIZE_VOLTGT`) reproduces the model's formula: given MT5's own balance, 899 of 905 days of the paper run have exactly the expected contracts (the other 6 are December 2021, where MT5 had volatility history and the model used the cap).

Results of the sized runs (gross of costs, which are about R$ 15,100 on the R$ 100,000 run at R$ 0.25 and a tick a side):

| | Paper's rule, R$ 100k | WIN optimized, R$ 100k | WIN optimized, R$ 10k |
| --- | --- | --- | --- |
| Net profit | R$ 70,256 | R$ 142,055 | R$ 14,255 |
| Max drawdown (balance, equity) | 21.1%, 22.1% | 6.5%, 9.3% | 7.2%, 9.4% |
| Profit factor | 1.13 | 2.01 | 1.89 |
| Contracts, mean (max) | 8.7 (19) | 10.4 (24) | 1.2 (2) |
| CAGR, gross; after costs | 11.3%; about 6.7% | 19.5%; 18.0% | the same as the R$ 100k in percent |

- The WIN optimized rule is less aggressive than the paper's because it is in the market less (118 minutes a trade, a trade on 31% of days, from 12:00), not because the size is smaller. Its 2024 to 2026 profits make R$ 120k of the R$ 142k.
- **Not new evidence.** The WIN optimized trial was chosen on 2021-12 to 2024 (so that part is in sample) and its 2025-26 result was already read in the final test. This run confirms that the EA reproduces the model and prices fills, not that the edge is real. The same trial had a Sharpe of 0.38 on WDO. No pass rule is approved and nothing is nominated.
- **Account size.** At R$ 10,000 a day is 1 or 2 contracts (a contract is worth R$ 21,000 to R$ 40,000), and 11 of the 581 days round to 0 contracts (days of high volatility, median 4% a day). The return in percent is the same as at R$ 100,000 (+142.6% against +142.1%): the effective leverage is 2.06 on average against a target of 1.94, 10% of days at more than 1.5 times the target. So the rounding is noise day by day, not a bias, but the leverage target decides the result: with the sizing the strategy trades at about 1.9 times its capital, and its return scales with that.
