# IBOV and buy-and-hold benchmarks (APPROVED by the owner on Oct 18, 2026)

The owner's request (Oct 18, 2026): add a "beats IBOV" comparison next to the CDI one, and a comparison with buying and holding the same ticker. The CDI says whether the strategy was worth more than a risk-free investment; the IBOV says whether it was worth more than simply owning the market; buy and hold says whether trading the ticker was worth more than just owning it. This spec follows `docs/cdi.md`. Once approved, any change creates `buy_and_hold_benchmark_v2`.

## Proposed decisions (owner to confirm or change)

1. **The index is the Ibovespa close, buy and hold, fully invested.** The money is in the index from the close of the first candle to the close of the last one. No costs and no taxes on the index side: the index cannot be bought, and a fund such as BOVA11 would add a small fee, which is ignored here.
2. **Dividends are not adjusted on either side.** The strategy uses raw prices (owner's decision, swing trading). The Ibovespa is, by B3's methodology, a total-return index (dividends reinvested), so the points series already includes them. This favours the index slightly against a strategy on raw prices. (From memory, not yet verified against the B3 methodology: check before relying on it.)
3. **The index series comes from the notebook** (Yahoo Finance, symbol `^BVSP`, raw close), as the CDI does. `core` takes a table of dates and closes and downloads nothing.
4. **Both ends must exist.** The window needs an index close on its first and on its last candle date. A missing one is an error that names the date, not a silent fallback to a neighbouring day.
5. **No risk adjustment, same as the CDI.** `excess` compares CAGR with CAGR. The IBOV is 100% invested and the strategy often is not, so beating the IBOV with a small drawdown is a different achievement from beating it with a large one. The notebooks show `excess` next to the equity drawdown and Calmar. An IBOV drawdown column is not part of this spec.

6. **Buy and hold of the same ticker uses the same raw close.** The money buys the ticker at the close of its first candle and holds to the close of its last one, no costs, no dividends (the owner's raw-close decision). On B3 the dividends of a typical stock are a large part of the long-run return, so a raw-price buy and hold is understated, which flatters the strategy. Both the number and this caveat appear in the notebooks.
7. **A portfolio is compared with the equal-weight buy and hold of its own tickers.** The capital is split equally at the start, each part buys its ticker at that ticker's first close and holds, with no rebalancing. This is the same slot model as the portfolio of independent slots, so the comparison is like for like.
8. **Buy and hold gets a drawdown too.** Both buy-and-hold benchmarks are an equity curve (capital times close over first close), so their equity drawdown and Calmar come from the same code as the strategy's. This is the answer to "beat the market with how much risk": proposed for the IBOV as well, which replaces the last line of decision 5.

## Inputs

| Input | Symbol | Definition |
| --- | --- | --- |
| IBOV closes | `I_d` | The Ibovespa close in points, indexed by date |
| Ticker closes | `P_d` | The raw close of the traded ticker, from the evaluated candles (no extra data) |
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

- Buy and hold of a ticker is the same formula with the ticker's closes: `bh_factor = P_d1 / P_d0`, `bh_cagr = bh_factor ^ (1 / years) - 1`, `excess_bh = cagr - bh_cagr`, `beats_buy_and_hold = excess_bh > 0`. Its window is the ticker's own candles, so it needs no missing-date rule.
- Buy and hold of a portfolio of `N` tickers: the benchmark curve is the sum over the tickers of `(capital / N) * P_t / P_first`, built with the same edge rule as `combine_equity` (a ticker holds its first value before it starts and its last value after it ends). Its CAGR, equity drawdown and Calmar come from `summarize_portfolio`.
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
| Ticker 20.00 on `d0` and 22.00 on `d1`, same window, strategy `cagr` 12% | `bh_cagr` 9.9785%, `excess_bh` +2.02 points, `beats_buy_and_hold` true |
| Two tickers, 10.00 to 12.00 and 10.00 to 8.00, capital 100,000 | portfolio benchmark ends at 50,000 * 1.2 + 50,000 * 0.8 = 100,000, so `bh_factor` 1.00: the equal-weight benchmark is the mean of the ratios, not a ratio of means |
| A short window, 100,000 to 100,150 over 3 days (`years = 3 / 365.25`) | `factor` 1.0015 |

## Tests to write first (once approved)

1. The worked example: `factor`, `ibov_cagr`, `excess`, both outcomes of `beats_ibov`.
2. A falling index: negative `ibov_cagr`, and a zero-CAGR strategy beats it.
3. A missing close on `d0` or on `d1` raises an error naming the date.
4. A non-positive close raises an error.
5. The window uses the first and last candle dates, not the first and last index dates: extra index rows outside the window do not change the factor.
6. Buy and hold of a ticker: the worked example, and a ticker that falls (the zero-trade strategy beats it).
7. Buy and hold of a portfolio: the two-ticker example above, the drawdown of the combined curve, and a ticker that starts later holding its first value before its start.
8. Dates are read in `America/Sao_Paulo` like the CDI: a candle timestamp late in the evening local time maps to that local day.

## Where it lives

A pure function in `core` (`b3core/benchmark.py`, next to `compare_with_cdi`) takes the closes, the candle dates and the CAGR, and returns `factor`, `ibov_cagr`, `excess` and `beats_ibov`. `scan_universe` and the portfolio summary gain the IBOV columns. Downloading `^BVSP` happens in the notebook.

## Decisions (owner, Oct 18, 2026)

The owner accepted every proposal above and the answers to the five questions below. Decision 6 gains one addition: the notebooks also show an **adjusted-close** buy and hold beside the raw one, labelled as such, so the size of the dividend effect is visible. The strategy itself stays on raw closes.

## Questions that were open

1. Is the Yahoo `^BVSP` close in points an acceptable index series (decision 3)?
2. Is an error on a missing close right (decision 4), or should the nearest earlier close be used?
3. Is it right that a zero-trade strategy beats the IBOV only in a falling market (see the second note under the formula)?
4. Buy and hold on raw closes ignores dividends (decision 6). Is that acceptable for the comparison, or do you want an adjusted-close buy and hold shown beside it, labelled as such, so the size of the dividend effect is visible?
5. Do you agree that the buy-and-hold benchmarks carry their own drawdown (decision 8)?
