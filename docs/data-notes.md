# Data notes

Findings about the candle data. Nothing here is a trading rule; the rules are in `brief.md`.

## MT5 exports (`samples/`, gitignored)

- Files: PETR4, VALE3 and BBAS3 in Daily, H2 and H4, 2016-10 to 2026-09, tab separated, `<VOL>` is the real volume.
- All nine files parse with no ingest issues (timestamps sorted and unique, OHLC consistent, volume not negative).
- **Timezone (assumption).** Times are read as `America/Sao_Paulo` wall-clock time. The first H2 candle of every day opens at 10:00 in every year, including Brazil's DST years, which fits wall-clock time but does not prove it.
- **Adjustment.** Not yet checked: it is unknown whether prices are adjusted for dividends and splits.

## Comparison with three real QuantBrasil trades on PETR4 H2 (screenshots in `notebooks/sample_trades/`)

| Trade | Entry | Exit | Result | Our candles |
| --- | --- | --- | --- | --- |
| 02/09/2026 | 47.95 | 48.20 | +R$ 500 | Reproduced exactly (see below) |
| 08/09/2026 | 48.10 | 48.09 | -R$ 17 | Entry and exit prices match our open and close, but no valid 123 on our candles has the implied stop |
| 09/09/2026 | 48.80 | 48.45 | -R$ 700 | Signal exists (08/09 16:00), prices differ slightly (see below) |

What the trades show about QuantBrasil's engine:

- **Day-trade run.** All three exits are the end of the day, not a stop or a target. 48.20 and 48.09 are exactly the closes of our 16:00 H2 candles.
- **Orders carry overnight.** Trades 2 and 3 enter on the first candle of a day, filled at the open after a gap, from a signal on the previous day's 16:00 candle. Only the position is closed the same day.
- **Sizing.** The quantities (2000, 1700, 2000 shares) fit a maximum risk of R$ 2,000 and capital of R$ 100,000, with the risk measured from the actual fill to the stop, rounded down to the lot, and capped by capital. Trades 1 and 3 hit the capital cap. Trade 2's 1,700 implies a stop of 46.96, one tick below the 46.97 low of the 04/09 14:00 candle.
- **Trade 1 in detail.** c3 is the 02/09 12:00 candle (high 47.94, so the trigger is 47.95). The pattern, the EMA 8 over EMA 80 order and both slopes pass. The order fills on the 14:00 candle at the trigger. The AMP target (about 50.17) and the C3 stop (47.38) are never touched, so the position leaves at the 16:00 close, 48.20. 2,000 shares times 0.25 is R$ 500.

Where our data and QuantBrasil's differ:

- **Trade 3.** The 09/09 10:00 open is 48.74 in MT5 and 48.80 in the screenshot, and the 16:00 close is 48.42 against 48.45. Both are the first and the last candle of the day.
- **Trade 2.** On our candles the 04/09 16:00 low (46.80) is below the 14:00 low (46.97), so the pattern fails there. A valid pattern with the implied 46.96 stop would need that last candle's low to differ.
- **Likely cause (unverified).** The two sources probably treat the opening and closing auction differently in the first and last candle of the day. Candles in the middle of the day match.
- **Consequence.** Signals formed on the last candle of the day, and fills on the first one, can differ between the two sources. Do not expect trade-by-trade equality on those candles.
