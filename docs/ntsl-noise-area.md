# NTSL indicator (ProfitPro): Noise Area momentum

`ntsl/noise_area_win.ntsl` draws the strategy of `docs/brief.md` section 10 on a ProfitPro chart: the Noise Area (green upper band, red lower band), the session VWAP (yellow) and the position the rule would hold (candles painted green when long, red when short). It is an **indicator**: it places no orders. An execution (`BuyAtMarket` and so on) version can follow.

**It has not been compiled in ProfitPro by me.** The language was read from Nelogica's official "Documentação Módulo Estratégias (NTSL)" (the PDF hosted at neotraderbot.com, 2023-05-31) and from the owner's two example scripts. What was checked is the logic (below), not the syntax.

## Use

1. ProfitPro, strategy editor, new strategy, paste `ntsl/noise_area_win.ntsl`, compile, apply to a chart of WIN or WDO (continuous contract).
2. Use a **minute chart**. 1 minute is the exact one; 5 minutes also runs (a few positions differ, see below). `Cadence` must be a multiple of the candle (a 30-minute step on a 5-minute chart is fine).
3. **Preset** input: `1` Paper (original), `2` WIN optimized, `3` Custom (the other inputs).

| | Preset 1, Paper | Preset 2, WIN optimized |
| --- | --- | --- |
| Lookback, minimum history | 14 days, 13 | 20 days, 19 |
| Band multiplier | 1.0 | 1.5 |
| Decision | every 30 minutes from 09:00 | every 60 minutes from 12:00 |
| Exit time | none (held to the close) | 18:20 |
| Stop | back inside the band or across the VWAP | back inside the band (no VWAP) |
| Stop acted on | at the half-hour checkpoints | at every candle |

Preset 2 is the best trial **by WIN** of the 50,000-trial search, chosen on development data. On the final test its WIN Sharpe went from 2.05 to 2.10, but it failed on WDO and does not beat the CDI on the 50/50 average (`docs/brief.md` section 10; `docs/adr/0001-winfut-intraday-momentum-final-test.md`). It is not a signal service.

Custom inputs: `Lookback` (up to 90), `MinDays`, `Mult`, `Cadence`, `FirstDecision` (HHMM), `ExitTime` (HHMM, 2400 = hold to the close), `StopKind` (1 VWAP+band, 2 band, 3 opposite band, 4 VWAP only), `EveryBar`. `SessionStart` (default 900) anchors the day.

The bands need the lookback in days of candle history; until then no band is drawn. If nothing shows, load more history first.

## How it follows the language

- **A candle can be processed many times** and every variable is global (manual, "Fluxo de Execução"). So every value is rebuilt from the previous candle's series value (`DayN[1]`, `CumPV[1]`, `PosAfter[1]`, `PrevClose[1]`, ...), never accumulated in place: a candle processed twice gives the same result.
- **Time**: `Time` is the candle's open time (HHMM); `BarDuration` gives the candle's minutes; the key of a candle is the minutes since `SessionStart` at its close. The decision grid, the first decision and the history of the moves all use that key, as the Python reference does with clock times.
- **The history of the moves** is a static `Array[1..156000] of Float` (260 days x 600 minutes, a ring). A day's row is cleared on its first candle and filled as the day goes; sigma is the mean of the last `Lookback` observations of that minute found going back day by day (a day with no candle at that minute is skipped, as the engine does). 260 days is about a year: the late-session minutes have no candles in the short-session seasons (17:54 closes), and a shallower ring cannot find enough observations after them.
- **VWAP**: the typical price `(high + low + close) / 3` weighted by `Quantity` (contracts), reset each day. The built-in `VWAP(1)` was not used so that it matches the engine.
- **No `Max` or `Min` functions** in the manual's list: the reference values are chosen with `if`.
- Drawing: `Plot`, `Plot2`, `Plot3`, `SetPlotColor`, `PaintBar`. When there is no band or VWAP the script calls `NoPlot(n)` for that candle; the manual only says it "removes a plot", so if a line is drawn through a gap instead, that call is the one to look at.

## What was checked

A line-by-line Python transliteration of the script (the ring of days, the series built from the previous candle, the decision and stop logic) was compared with the engine (`strategy_exposure`) on WIN development bars from 2023-01 (276,517 one-minute bars):

| Case | 1-minute bars differing | 5-minute bars differing |
| --- | --- | --- |
| Preset 1, paper | 0 | 0.10% |
| Preset 2, WIN optimized | 0 | 0.31% |
| Opposite band, grid | 0 | 0.03% |
| VWAP only, every bar | 0 | 0.93% |
| VWAP+band, every bar, 15 min, 10:30, exit 17:30 | 0 | 0.41% |

The same on the 481 of 499 days with no missing minute and a 09:00 first candle: also 0 on 1-minute bars. On 5-minute bars the VWAP is built from coarser candles and an every-candle stop is checked on each chart candle, so a few positions differ; this is a property of the chart, not a bug.

## Not checked, to try in ProfitPro

- That it compiles (types of `Floor`, `Mod`, `TimeToMinutes`, array indexing with an `Integer` expression, `else if` chains).
- `Date <> Date[1]` through an assigned variable (`Dia`) as the new-day test.
- That `BarDuration` is 1 on a 1-minute chart and `Quantity` is the contracts traded.
- Speed: a loop of 600 per new day and up to 259 steps per candle for the rare late-session minutes. If it is slow, lower `Rows` and the array size to 130 (the cost is bands that come later after the short-session seasons).
- The candle's first tick has `[0]` zeroed (manual): in real time the position is rebuilt each tick from `[1]`, so the last candle can flicker until it closes.
