# IBOV benchmark (DRAFT: waiting for the owner's approval)

The owner's request (Oct 18, 2026): add a "beats IBOV" comparison next to the CDI one. The CDI says whether the strategy was worth more than a risk-free investment; the IBOV says whether it was worth more than simply owning the market. This spec follows `docs/cdi.md`. Once approved, any change creates `ibov_benchmark_v2`.

## Proposed decisions (owner to confirm or change)

1. **The index is the Ibovespa close, buy and hold, fully invested.** The money is in the index from the close of the first candle to the close of the last one. No costs and no taxes on the index side: the index cannot be bought, and a fund such as BOVA11 would add a small fee, which is ignored here.
2. **Dividends are not adjusted on either side.** The strategy uses raw prices (owner's decision, swing trading). The Ibovespa is, by B3's methodology, a total-return index (dividends reinvested), so the points series already includes them. This favours the index slightly against a strategy on raw prices. (From memory, not yet verified against the B3 methodology: check before relying on it.)
3. **The index series comes from the notebook** (Yahoo Finance, symbol `^BVSP`, raw close), as the CDI does. `core` takes a table of dates and closes and downloads nothing.
4. **Both ends must exist.** The window needs an index close on its first and on its last candle date. A missing one is an error that names the date, not a silent fallback to a neighbouring day.
5. **No risk adjustment, same as the CDI.** `excess` compares CAGR with CAGR. The IBOV is 100% invested and the strategy often is not, so beating the IBOV with a small drawdown is a different achievement from beating it with a large one. The notebooks show `excess` next to the equity drawdown and Calmar. An IBOV drawdown column is not part of this spec.

## Inputs

| Input | Symbol | Definition |
| --- | --- | --- |
| IBOV closes | `I_d` | The Ibovespa close in points, indexed by date |
| Window | `[d0, d1]` | First and last candle dates of the evaluated data (the same window as the CDI) |
| Years | `years` | The same value the strategy's CAGR uses: calendar days between the first and last candle, divided by 365.25 |
| Strategy CAGR | `cagr` | Already in `Metrics` |

## Formula

```text
factor     = I_d1 / I_d0
ibov_cagr  = factor ^ (1 / years) - 1
excess     = cagr - ibov_cagr                 in percentage points of CAGR
beats_ibov = excess > 0
```

- The index is bought at the close of `d0`, the same moment the CDI starts, so the two benchmarks cover the same window.
- A zero-trade strategy has `cagr = 0`, so it beats the IBOV only when the index fell over the window. That is intended: cash at zero beats a falling market, and nothing else.
- A fall of more than 100% is impossible, so `factor > 0`. A non-positive or missing close is an error.

## Worked example (use as the first test)

An index at 100,000 points on `d0` and 110,000 on `d1`, a window of 366 calendar days (`years = 366 / 365.25 = 1.00205`):

| Step | Value |
| --- | --- |
| `factor = 110000 / 100000` | 1.10 |
| `ibov_cagr = 1.10 ^ (1 / 1.00205) - 1` | 9.9785% |
| Strategy `cagr` 12.00% | `excess` +2.02 points, `beats_ibov` true |
| Strategy `cagr` 9.00% | `excess` -0.98 points, `beats_ibov` false |
| Index falls to 90,000 (`factor` 0.90) | `ibov_cagr` -9.9806% |
| A short window, 100,000 to 100,150 over 3 days (`years = 3 / 365.25`) | `factor` 1.0015 |

## Tests to write first (once approved)

1. The worked example: `factor`, `ibov_cagr`, `excess`, both outcomes of `beats_ibov`.
2. A falling index: negative `ibov_cagr`, and a zero-CAGR strategy beats it.
3. A missing close on `d0` or on `d1` raises an error naming the date.
4. A non-positive close raises an error.
5. The window uses the first and last candle dates, not the first and last index dates: extra index rows outside the window do not change the factor.
6. Dates are read in `America/Sao_Paulo` like the CDI: a candle timestamp late in the evening local time maps to that local day.

## Where it lives

A pure function in `core` (`b3core/benchmark.py`, next to `compare_with_cdi`) takes the closes, the candle dates and the CAGR, and returns `factor`, `ibov_cagr`, `excess` and `beats_ibov`. `scan_universe` and the portfolio summary gain the IBOV columns. Downloading `^BVSP` happens in the notebook.

## Open questions for the owner

1. Is the Yahoo `^BVSP` close in points an acceptable index series (decision 3)?
2. Is an error on a missing close right (decision 4), or should the nearest earlier close be used?
3. Is it right that a zero-trade strategy beats the IBOV only in a falling market (see the second note under the formula)?
