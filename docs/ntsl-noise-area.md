# NTSL indicator (ProfitPro): Noise Area momentum

`ntsl/noise_area_win.ntsl` draws the strategy of `docs/brief.md` section 10 on a ProfitPro chart: the Noise Area (green upper band, red lower band), the session VWAP (yellow) and the position the rule would hold (candles painted green when long, red when short). By default it is an **indicator** that places no orders. With the input `SendOrders(true)` it is also a **strategy**: it sends the orders, to be applied as an execution rule and backtested in ProfitPro (see "The strategy part"). The paper's rule and the WIN optimized trial differ only by the input values (table below).

**It has not been compiled in ProfitPro by me.** The language was read from Nelogica's official "Documentação Módulo Estratégias (NTSL)" (the PDF hosted at neotraderbot.com, 2023-05-31) and from the owner's two example scripts. What was checked is the logic (below), not the syntax.

## Use

1. ProfitPro, strategy editor, new strategy, paste `ntsl/noise_area_win.ntsl`, compile, apply to a chart of WIN or WDO (continuous contract).
2. Use a **minute chart**. 1 minute is the exact one; 5 minutes also runs (a few positions differ, see below). `Cadence` must be a multiple of the candle (a 30-minute step on a 5-minute chart is fine).
3. There are **no presets**: the inputs are the parameters themselves, so ProfitPro's optimizer can sweep them. The defaults are the **WIN optimized** trial; the paper's rule is the second column, typed in by hand (it is also written in the comments at the top of the file).

| Input | Default: WIN optimized | The paper (original) |
| --- | --- | --- |
| `Lookback` (days; the days needed before a band shows is this minus 1) | 20 | 14 |
| `Mult` (band multiplier k) | 1.5 | 1.0 |
| `Cadence` (decision every N minutes) | 60 | 30 |
| `FirstDecision` (HHMM) | 1200 | 900 |
| `ExitTime` (HHMM, 2400 = hold to the close) | 1820 | 2400 |
| `StopKind` (1 VWAP+band, 2 band, 3 opposite band, 4 VWAP only) | 2 (back inside the band) | 1 (inside the band or across the VWAP) |
| `EveryBar` (act on the stop at every candle) | true | false (the half-hour checkpoints only) |

The WIN optimized default is the best trial **by WIN** of the 50,000-trial search, chosen on development data. On the final test its WIN Sharpe went from 2.05 to 2.10, but it failed on WDO and does not beat the CDI on the 50/50 average (`docs/brief.md` section 10; `docs/adr/0001-winfut-intraday-momentum-final-test.md`). It is not a signal service.

Other inputs: `SessionStart` (default 900), `ShowBands`, `ShowVwap`, `PaintPosition`, and for the strategy part `SendOrders`, `Contracts`, `SessionEnd`.

The bands need the lookback in days of candle history; until then no band is drawn. If nothing shows, load more history first.

## The strategy part (`SendOrders(true)`)

Inputs: `SendOrders` (false by default), `Contracts` (a fixed number, default 1) and `SessionEnd` (HHMM of the last candle's close, default 1825; B3 closes WIN at 17:55 in some seasons, set 1755 then).

At the end of each candle the script works out the position wanted for the next candle: what was decided at this close, **flat** when the candle closes at or after the exit time or at `SessionEnd`. It compares that with the position actually held and sends one order: `ClosePosition` to go flat, `BuyAtMarket(Contracts)` or `SellShortAtMarket(Contracts)` from flat, and `ReversePosition` to turn around (the manual: a Buy sent while short is only a cover, and a ToCover order never reverses). Because it compares with the real position, a candle processed twice sends nothing new.

Apply it as an execution rule ("Inserir Regra de Execução") on a 1-minute chart, set the backtest's costs to the model's (fee R$ 0.25 a side plus one tick, R$ 1.00 slippage, on WIN) and `Contracts` to 1.

**Compare with the Python model** using `notebooks/winfut_trade_book.ipynb`: it runs the same configuration with one fixed contract and prints the last N trades (side, entry and exit times and prices, points, reais), with the next bar's open beside the Python fill (the close of the decision bar), and writes the full list to a CSV. For the comparison with ProfitPro's recent data, the 3 to 16 November 2026 WIN file lives in `samples/comparison/` (outside the project loader, which takes one file per symbol); the notebook adds it after the history and lists every trade from `COMPARE_FROM`. The 16 November day is cut at 17:30 in that file, so the model closes its last trade there. What the notebook cannot say is where ProfitPro fills a market order sent at the end of a candle: the manual says orders are sent when the candle ends and that backtest orders are simulated "at the end of the execution flow of the candle", not whether at that candle's close or the next open. The two price columns are there to find out.

**Positions kept overnight (found by the owner on stocks, 17 Nov 2026).** ProfitPro fills a market order at the next candle's open, so an order sent at the close of the day's last candle fills the next morning. The flatten is therefore sent **one candle early**: at the close of the candle before the last, filling at the last candle's open (the model's own exit at `ExitTime` is unchanged when `ExitTime` falls inside the day). This needs `SessionEnd` to be the time the last candle really closes: WIN 1825 (1755 in some seasons), **stocks 1800**. For stocks also set `SessionStart` (1000), `Contracts` (a lot is 100 shares) and, if you do not want a time exit, `ExitTime(2400)`. The backtest's own option to force a close at a set time does the same from the platform side and can be used instead.

What the strategy part does not do: the paper's volatility-targeted size (the contracts are fixed), a stop order resting in the market (the stop is evaluated at the candle's close), or a flat at the true last candle of a day with an early close (`SessionEnd` must be set by season; a position left over on such a day is only closed at the next day's first candle by the exit rule, not by this code).

Checked in Python: the position wanted for the next candle equals the position the model holds in the next candle on all 276,018 candles of WIN from 2023-01 (the WIN optimized inputs).

## Compared with the ProfitPro backtest (17 November 2026)

The owner ran the WIN optimized inputs (`SendOrders(true)`, `Contracts(1)`, 1-minute chart, no commissions) over 26 October to 16 November and exported the operations (`samples/comparison/ops_profit.csv`, git-ignored: it holds account data). `notebooks/winfut_trade_book.ipynb`, section 3c, matches them to the Python model:

- **13 ProfitPro operations, 13 model trades, 13 matched** on side and entry time, with **identical entry prices**: ProfitPro fills a market order at the **open of the candle after the signal**, which is the model's `entry_next_open`, not its decision-close fill (the two differ by 5 points or less per fill).
- **11 of 13 identical to the point** on exit time and exit price (next-open fills).
- **Two differences, both explained:**
  1. 9 Nov, long 15:00: the model leaves at the 15:00 candle's close (the price is 83 points inside the band, a clear stop) and fills at the 15:01 open, 172,920 (-25 points); ProfitPro left at 15:02, 172,990 (+45 points). The stop fell on the **first candle held**. A second export after changing the close to `if HasPosition or (PosBefore <> 0)` gave the same 15:02 exit, so that change was reverted. The reading that fits: the backtest does not let the code see, or close, a position entered at a candle's open until the next candle has run, so a stop on the first held candle waits one candle. It looks like a property of ProfitPro's backtest, not of the rule. **How much it matters** (Python, WIN optimized, one contract, whole history): 47 of 583 trades (8.1%) exit on their first held candle; leaving one candle later changes them by 55 points each on average (standard deviation 85) and adds **+1,205 points over the history, +4.5% of the 26,785 points** of the next-open model, because later exits happen to be better than immediate ones (-72 against -46 points a trade). So the ProfitPro backtest reads slightly better than the model, by that amount, and any one trade can differ by a hundred points. It does not change a rule, and it is not known whether live automation behaves the same.
  2. 16 Nov, short 14:00: the file stops at 17:30, so the model closed it at 17:31 (170,845); ProfitPro closed it at 18:20 (170,910). Not a disagreement.
- Total over the 13: **215 points (R$ 43.00) in ProfitPro, 210 points (R$ 42.00) in the model** with next-open fills; the 5 points are the first difference net of the second.

So the model's rule, its sigma, bands, VWAP, checkpoints, stop and exit are the same as the NTSL strategy's on these three weeks. What remains different is how a fill is priced (next open against the model's decision-close convention), which is a convention, not a rule. The model's costs (R$ 1.25 a side) are not in ProfitPro's report.

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
| The paper's inputs | 0 | 0.10% |
| The WIN optimized inputs | 0 | 0.31% |
| Opposite band, grid | 0 | 0.03% |
| VWAP only, every bar | 0 | 0.93% |
| VWAP+band, every bar, 15 min, 10:30, exit 17:30 | 0 | 0.41% |

The same on the 481 of 499 days with no missing minute and a 09:00 first candle: also 0 on 1-minute bars. On 5-minute bars the VWAP is built from coarser candles and an every-candle stop is checked on each chart candle, so a few positions differ; this is a property of the chart, not a bug.

## Not checked, to try in ProfitPro

- That it compiles (types of `Floor`, `Mod`, `TimeToMinutes`, array indexing with an `Integer` expression, `else if` chains).
- `Date <> Date[1]` through an assigned variable (`Dia`) as the new-day test.
- That `BarDuration` is 1 on a 1-minute chart and `Quantity` is the contracts traded.
- The strategy part: that `ReversePosition`, `ClosePosition` and the order calls compile and behave as the manual says; where the backtest fills a market order (decision candle close or next open); that a script with order calls still draws its plots.
- Speed: a loop of 600 per new day and up to 259 steps per candle for the rare late-session minutes. If it is slow, lower `Rows` and the array size to 130 (the cost is bands that come later after the short-session seasons).
- The candle's first tick has `[0]` zeroed (manual): in real time the position is rebuilt each tick from `[1]`, so the last candle can flicker until it closes.
