# MQL5 (MetaTrader 5): Noise Area momentum

The rule of `docs/brief.md` section 10 as an **Expert Advisor** (trades, backtests in the Strategy Tester) and an **indicator** (bands, VWAP, arrows where the position changes), sharing one core.

| File | What it is |
| --- | --- |
| `mql5/Include/NoiseArea/NoiseCore.mqh` | the logic: bands, VWAP, the history of the moves, the stops, the position; fed one closed bar at a time |
| `mql5/Experts/NoiseAreaEA.mq5` | the Expert Advisor |
| `mql5/Indicators/NoiseAreaIndicator.mq5` | the indicator |

**It has not been compiled in MetaEditor by me** (no MetaTrader here). What was checked: the text of `NoiseCore.mqh`, compiled as C++ with small stand-ins for the MQL types (`MqlDateTime`, `TimeToStruct`, `ArrayResize`...), was run on all 687,506 one-minute bars of WIN (2021-12 to 2026-11-16) against the Python engine. See "What was checked". The EA's and the indicator's own code (inputs, `CopyRates`, `CTrade`, buffers, `SymbolInfoSessionTrade`) is not covered by that.

## Install

Copy the three folders' contents into the `MQL5` folder of the terminal's data directory (File > Open Data Folder), keeping the layout: `MQL5/Include/NoiseArea/NoiseCore.mqh`, `MQL5/Experts/NoiseAreaEA.mq5`, `MQL5/Indicators/NoiseAreaIndicator.mq5`. Open each `.mq5` in MetaEditor and compile (F7). The EA includes the core with `#include <NoiseArea/NoiseCore.mqh>`.

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

Other inputs: `SessionStart` (HHMM, **server time**, default 900), `SessionEnd` (HHMM the day's **last bar closes**: WIN 1825, 1755 on the days B3 closes early; stocks 1800), `AutoSessionEnd` (read it from the symbol's schedule instead), `UseRealVolume` (the VWAP weighs real volume, as the Python model does; false for tick volume), and for the EA `Lots` (a fixed number of contracts), `MagicNumber`, `DeviationPts`, `SendOrders` (false: compute and log only), `WriteLog`.

The WIN optimized default is the best trial **by WIN** of the 50,000-trial search, chosen on development data. On the final test its WIN Sharpe went from 2.05 to 2.10, but it failed on WDO and does not beat the CDI on the 50/50 average (`docs/adr/0001-winfut-intraday-momentum-final-test.md`). It is not a signal service.

## How it trades

At the **close of each bar** the core works out the position wanted for the next bar: what was decided at this close, flat from `ExitTime`, and flat by the day's last bar. The EA sets that position with market orders on the first tick of the new bar, so a fill is at the **next bar's open**, as in ProfitPro and as in the `entry_next_open` columns of `notebooks/winfut_trade_book.ipynb`. A reversal is a close and an order the other way. Unlike ProfitPro's backtest, MT5 shows the EA its position at once, so a stop on the first bar held is acted on at the next open (the Python model's way), not one bar late.

**No position is carried over a day boundary**, two ways. The flatten goes out one bar before the day's last bar (a market order sent at the last bar's close would fill the next morning), which needs `SessionEnd` to be the real close (332 of the 1,238 days in the WIN data close at 17:54, not 18:25). And whatever the last bar of a day wanted, the first bar of a new day starts flat.

Use a **minute chart** (1 minute is the exact one); the chart period must divide `Cadence`. Needs the lookback in days of history to be loaded. `WriteLog` writes `MQL5/Files/noise_area_log.csv` (one row per bar: time, close, sigma, bands, VWAP, the position decided, held and wanted) to compare with the Python engine bar by bar.

## Strategy Tester

Symbol: the same continuous WIN series the data was exported from (`WIN$N`), M1, with the deposit in reais. Costs: set the commission in the tester or the symbol (the model's are R$ 0.25 a side plus one tick of R$ 1.00 slippage). "Every tick" (or "1 minute OHLC") both fill the first tick of a new bar at its open. `Lots` 1 to compare with the one-contract model.

## What was checked

`NoiseCore.mqh` compiled with `g++ -Wall` (no warnings) and run on all the bars against `strategy_exposure`, for five configurations (WIN optimized; the paper; the opposite-band stop on the grid; the VWAP-only stop at every bar; VWAP+band at every bar with 15-minute steps, a 10:30 start and a 17:30 exit): **0 bars where the position held differs from the engine out of 687,506**, in all five. The position wanted for the next bar equals the next bar's held position, except in 2 bars of three of the configurations on 2026-03-10 and 2026-10-28, days whose last bar is missing in the data; and the wanted position is flat on the last two bars of every day that closes at 18:25.

## Not checked, to try in MT5

- That the three files compile in MetaEditor, and that the indicator draws (the buffers, the arrows).
- That `CTrade` fills correctly on the B3 symbol (`SetTypeFillingBySymbol`) and that `PositionClose` then an order the other way behaves on the account's margin mode (netting or hedging).
- `AutoSessionEnd`: whether the symbol's schedule (`SymbolInfoSessionTrade`) holds the early closes. If it just says 09:00 to 18:25, set `SessionEnd` by hand, or rely on the new-day flat.
- That the Strategy Tester's M1 history matches the exported CSV (it should: the data was exported from MT5).
