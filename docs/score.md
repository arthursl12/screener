# score_v1 (APPROVED by the owner, not implemented yet)

Brief section 6 asks for an original 0 to 100 score, with the formula written here and approved before any code. The owner approved the formula and constants below. Any change creates `score_v2`.

## Why a score at all

Ranking a grid search on one raw ratio picks lucky combos. With `calmar`, a combo with 21 trades and no drawdown gives `inf` and ranks first, ahead of a combo with 300 trades and Calmar 13.8. The score combines several metrics and shrinks the result when the sample is small.

## Inputs

All computed on the evaluation period, from the same equity curve the metrics use.

| Input | Symbol | Definition |
| --- | --- | --- |
| Profit factor | `PF` | gross gains / gross losses (`inf` when there are no losses) |
| Max equity drawdown | `DD` | largest peak-to-trough fall of the daily equity curve, in % of the peak (open trades marked at the close) |
| Expectancy | `EV` | average PnL per trade as % of initial capital (brief section 6) |
| Trades | `n` | number of closed trades |

## Formula

Each component is clipped to the range 0 to 1:

```text
s_pf = clip((PF - 1) / 1.5, 0, 1)        PF 1.0 -> 0, PF 2.5 or more -> 1
s_dd = clip(1 - DD / 30, 0, 1)           DD 0% -> 1, DD 30% or more -> 0
s_ev = clip(EV / 0.5, 0, 1)              EV 0% -> 0, EV 0.5% or more -> 1

base = 100 * (0.35 * s_pf + 0.35 * s_dd + 0.30 * s_ev)
conf = n / (n + 30)                      n = 30 -> 0.50, n = 300 -> 0.91
score_v1 = base * conf
```

- `PF = inf` and `DD = 0` are valid inputs: they clip to 1 and do not break the formula. The `conf` factor is what stops a tiny sample from winning.
- `n < min_trades` is a hard gate, not part of the score: the combo is reported as "not enough trades" and is not ranked.
- Version tag: `score_v1`. Any change to a constant or weight creates `score_v2`.

## Worked example (use as the first test)

| | n | PF | DD | EV | s_pf | s_dd | s_ev | base | conf | score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A: all wins | 21 | inf | 0% | 1.0% | 1 | 1 | 1 | 100.0 | 0.412 | 41.2 |
| B: normal | 300 | 2.0 | 10% | 0.3% | 0.667 | 0.667 | 0.6 | 64.7 | 0.909 | 58.8 |

B ranks above A, which is the behaviour we want.

## Open questions for the owner

1. ~~Weights (35 / 35 / 30) and clip ranges (PF 2.5, DD 30%, EV 0.5%).~~ **Approved (owner).** Picked by hand, not fitted; revisit with `score_v2` if results look off.
2. ~~`n0 = 30` in `conf`.~~ **Approved (owner).**
3. ~~Should the score also look at out-of-sample?~~ **Decided (owner): no.** `score_v1` describes one period only. The optimizer reports `is_score`, `oos_score` and the `dropped` flag (`flag_drop` in `optimizer.py`) side by side. Reason: a score that depends on the split would change with `oos_fraction`, and ranking on out-of-sample data would leak it into selection. A combined robustness number, if ever wanted, gets its own metric and version tag.

## Tests to write first (approved, ready to write)

1. The worked example above, exact to one decimal.
2. Monotonic in each input with the others fixed.
3. `PF = inf` and `DD = 0` return a finite score.
4. The same metrics with more trades never score lower.
