# CDI benchmark (APPROVED by the owner on Oct 18, 2026)

The owner's rule (Oct 18, 2026): a strategy that does not beat the CDI over the same period failed, because the money could have stayed in a risk-free investment. Brief section 10 lists the definition as open. The owner approved it as written. Any change creates `cdi_benchmark_v2`.

## Decisions already taken by the owner

- Idle cash earns nothing in the strategy. The strategy has to beat the CDI by being in the market.
- No reinvestment: the strategy trades a fixed capital, so its result is not compounded.
- Income tax and slippage are out of scope for now.

## Inputs

| Input | Symbol | Definition |
| --- | --- | --- |
| CDI daily rates | `r_t` | The Central Bank's series SGS 12, "CDI", in percent per business day, for every business day in the window |
| Window | `[d0, d1]` | First and last candle dates of the evaluated data. The money is invested at the close of `d0`, so the CDI starts accruing on the first business day after `d0` and ends on `d1` |
| Years | `years` | The same value the strategy's CAGR uses: calendar days between the first and last candle, divided by 365.25 |
| Strategy CAGR | `cagr` | Already in `Metrics` (annualised result of the closed trades on the initial capital) |

## Formula

```text
factor    = product over the business days t in (d0, d1] of (1 + r_t / 100)
cdi_cagr  = factor ^ (1 / years) - 1
excess    = cagr - cdi_cagr                 in percentage points of CAGR
beats_cdi = excess > 0
```

- The CDI is compounded day by day, as the real CDI is. A window with no CDI rate for some business day is an error, not a silent gap, and the error names the missing days. A business day is a date of the evaluated candles, so no holiday calendar is needed; CDI dates that are not candle dates are still compounded.
- A strategy with zero trades has `cagr = 0`, so it loses to any positive CDI. That is intended: doing nothing is not an edge, it is cash at zero.
- `excess` compares CAGR with CAGR. It does not adjust for risk. A strategy can beat the CDI and still deserve no money if its drawdown is large, so the notebooks show `excess` next to the equity drawdown and Calmar.

## Worked example (use as the first test)

A constant rate of 0.04% per business day over 252 business days, a window of 366 calendar days (`years = 366 / 365.25 = 1.00205`):

| Step | Value |
| --- | --- |
| `factor = 1.0004 ^ 252` | 1.10603 |
| `cdi_cagr = 1.10603 ^ (1 / 1.00205) - 1` | 10.58% |
| Strategy `cagr` | 12.00% |
| `excess` | +1.42 points, `beats_cdi` is true |
| Same window, strategy `cagr` 9.00% | `excess` -1.58 points, `beats_cdi` is false |

A short window, three business days at 0.04%, 0.05% and 0.06%: `factor = 1.0004 * 1.0005 * 1.0006 = 1.0015007`.

Sanity check against the owner's rule of thumb: 0.04% per day for 21 days is 0.84% a month, close to "about 1% a month" at a higher rate.

## Tests to write first (once approved)

1. The worked example: `factor`, `cdi_cagr`, `excess`, both outcomes of `beats_cdi`.
2. A window with a missing business day raises an error naming the day.
3. A zero rate gives `cdi_cagr = 0`, so any positive CAGR beats it.
4. The three-day factor above, exact to 7 decimals.
5. The window excludes `d0` itself and includes `d1`: moving `d1` by one business day multiplies the factor by that day's rate.

## Data sources

The function takes any table of daily rates, so the source is a notebook decision. In order: the Central Bank's SGS 12 (the exact CDI); if its API is blocked, the Selic target rate from Ipeadata (series `BM366_TJOVER366`, percent a year) minus 0.10 points, converted to a business-day rate as `(1 + a / 100) ^ (1 / 252) - 1` and restricted to trading days. That second source is an approximation: checked against the CDI of 2019 to 2023 (5.96%, 2.76%, 4.42%, 12.39%, 13.04%, from memory) it came within about 0.1 points a year (5.85, 2.73, 4.33, 12.33, 12.99). Notebooks print which source they used. Added Oct 18, 2026 at the owner's request, because the Central Bank API was unreachable.

## Where it lives

A pure function in `core` takes a table of dates and daily rates and returns `factor`, `cdi_cagr`, `excess` and `beats_cdi`. Downloading the series from the Central Bank happens in the notebook, never in `core`.

## Decisions (owner, Oct 18, 2026)

1. The CDI accrues from the business day after the first candle. Approved.
2. `beats_cdi` is `excess > 0`, no margin. Approved. A "beats IBOV" comparison comes later and is not part of this spec.
