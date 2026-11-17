# Sizing: from the paper's SPY shares to WIN contracts

The paper sizes its position in **shares of SPY**. This project trades **WIN mini contracts**. This note shows that the two rules are the same rule, and where they differ in how the position is held. All numbers below come from the development data; the final test period has not been read.

## 1. The one idea

For a strategy that is in the market only during the day, the **profit of a day as a share of the equity** is

```
gain / equity  =  leverage  x  (index move captured, as a share of the open)
```

where `leverage = exposure / equity`, and `exposure` is the **index value the position controls** (in reais or dollars). The signal decides which way and when (the index move captured); the sizing decides only the leverage. Shares and contracts are two ways of holding the same exposure.

## 2. SPY shares against WIN contracts

| | SPY (the paper) | WIN (here) |
| --- | --- | --- |
| One unit is | one share, worth the price `P` | one contract, worth `R$ 0.20 x points` of exposure |
| What you pay to hold it | the price (cash), or borrowed money above 1x | **margin** as collateral (R$ 1,000 a contract, owner's figure), not spent |
| How leverage above 1x is held | borrowing in a margin account, capped at 4x by the broker | simply more contracts; the margin allows far more than 4x |
| Profit and loss | change of the share price | change of the index in points x R$ 0.20, settled in cash each day |
| Costs | commission per share | B3 fee per contract and side |
| Shorting | needs a share to borrow | symmetric, no borrow |
| Extras the model ignores | interest on borrowed money, dividends | carry between contracts (shows as the roll gap in the continuous series), interest on idle cash |

So WIN is not "bought" like a share; it is closer to a leveraged position where margin is the guarantee and the daily result is cash-settled. What matters for the sizing is that **the exposure is what drives the gain**, and the exposure can be chosen freely in both.

## 3. The two formulas side by side

Let `leverage = min(2% / sigma_t, 4)`, with `sigma_t` the standard deviation of the 14 daily returns before the previous day (the authors' notebook; the paper includes the previous day).

| | Paper (shares) | Here (contracts) |
| --- | --- | --- |
| Exposure wanted | `equity x leverage` | `equity x leverage` |
| Value of one unit | `Open` (the price of a share) | `Open x R$ 0.20` (the exposure of a contract) |
| Units | `equity x leverage / Open` | `equity x leverage / (Open x R$ 0.20)` |

The only change is the value of one unit. Dividing the wanted exposure by the exposure of one unit gives the number of units, whatever the unit is. At 100% size (`leverage = 1`) the paper holds shares worth the equity, and here the contracts control an index value equal to the equity.

## 4. Why the return is the same

For one day, with `Open` the day's open and `points` the profit of the position in index points per contract:

```
gain          = contracts x R$ 0.20 x points
exposure      = contracts x R$ 0.20 x Open
leverage      = exposure / equity

gain / equity = contracts x 0.20 x points / equity
              = (contracts x 0.20 x Open / equity) x (points / Open)
              = leverage x (points / Open)
```

For shares the same steps with `shares x P` in place of `contracts x 0.20 x Open` give `leverage x (points / Open)` again. The instrument drops out. The engine reports `exposure` and `leverage` for every day, and a test pins this identity on random bars.

## 5. A real day

2023-07-31, development data, the final model (the paper's rule: no exit time, R$ 0.25 a side). The equity is **simulated**: it starts at R$ 100,000 on the first traded day and each day's size is set on the equity at the end of the day before, so it is the R$ 100,000 plus the net result of the 402 traded days before this one (fees included), R$ 16,477 in all. It follows the path of the run (R$ 97,575 at the end of 2021, R$ 117,274 at the end of 2022, R$ 135,576 at the end of 2023), so the same rule trades 9 contracts here and other numbers on other days.

| | |
| --- | --- |
| Open | 121,390 points, so one contract controls R$ 24,278 |
| Daily volatility `sigma_t` | 1.09%, so the target leverage is 2% / 1.09% = 1.83 |
| Equity at the start | R$ 116,477 |
| Contracts | 116,477 x 1.83 / 24,278 = 8.8, rounded to **9** |
| Exposure and leverage taken | R$ 218,502 and **1.88** |
| Margin tied up | 9 x R$ 1,000 = R$ 9,000 (7.7% of the equity; the rest stays in the account) |
| The day's two trades | +360 points in total, which is 0.297% of the open |
| Gain on equity | 1.88 x 0.297% = **0.556%**, which is exactly gross / equity |

## 6. What whole contracts change

A share can be split; a contract cannot. The rounding to whole contracts moves the exposure by at most **half a contract** (about R$ 12,000 here, or up to 12% of a R$ 100,000 account on a day). Measured over the 757 development days, with no fees, against the paper's fractional exposure (the same rule with the rounding taken out):

- the daily returns have a correlation of **0.9996**, and differ by 1.7 basis points on average;
- the realised leverage is within **0.05** of the target on average (largest 0.11), and its mean error is 0.001;
- the equity multiple after the period is 1.442 with whole contracts against 1.453 fractional.

The smaller the account, the coarser the rounding: with R$ 10,000 the rule takes 1.2 contracts on average, with R$ 100,000 about 10, with R$ 300,000 about 30. The average leverage stays near 1.9 at every size, but the day-to-day error grows as the account shrinks.

## 7. Where the margin enters

Margin is a **separate constraint**, not part of the formula:

- The paper's cap of 4x is a risk rule borrowed from a US broker's day-trading limit. On WIN it is **much tighter than the margin**: R$ 1,000 against R$ 24,000 of exposure is 4.2%, so the margin alone would allow about 24x.
- With the default R$ 100,000 and a cap of 4, the largest position is about 20 contracts, R$ 20,000 of margin, a fifth of the account. The margin never limits it, and the code only caps the contracts at `equity / margin` as a guard for a very small or very leveraged account.
- Margin is collateral. It is not spent, but a loss larger than the free equity is taken from it, and a broker may close the position before that.

## 8. What the account size means

In the formula `equity` is a **risk budget**: the capital against which the 2% daily volatility target is measured. For a margin-only account it is not the margin. The development data suggests the budget should cover the drawdown: one contract's worst drawdown was about R$ 2,800, and the volatility-targeted account's about R$ 22,000 (with a path of up to 20 contracts). The settings that move the risk are `capital`, `target_vol` and `max_leverage`; `fixed_contracts` replaces the rule with a constant number of contracts (1 is the single-contract version).

## 9. Where to read the sizing

- Paper, **Beat the Market** (Zarattini, Aziz and Barbon): p. 10 (100% of equity, `Shares = AUM / Open`), p. 14 to 15 (the volatility-targeted size, the 2% target, the 14-day volatility and the cap of 4x), Table 3.
- Counter-paper (Paz Serpa, 2026): p. 4, section 3.4, equation (3).
- The authors' notebook: the `shares = round(previous_aum / open_price * min(target_vol / spx_vol, max_leverage))` line of the backtest cell, and the `spy_dvol` computation in the data-preparation cell. The replication repo has the same at `src/zarattini_intraday_momentum.py`, lines 157 to 163.
- This project: `contracts_for` and the `exposure` and `leverage` columns of `run_intraday_momentum` in `backend/core/src/b3core/intraday_momentum.py`; the tests `test_the_profit_of_a_day_is_the_leverage_times_the_index_move_on_the_equity` and `test_the_leverage_taken_is_the_papers_target_up_to_the_rounding_of_whole_contracts`.
