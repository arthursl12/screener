# ADR 0001: WIN and WDO intraday momentum, the search and the final test

Written Nov 17, 2026 by Claude Code at the owner's request ("just write and publish"). CLAUDE.md asks the owner to write ADRs in their own words, so the owner should rewrite or correct this one.

## Context

The owner asked whether the Noise Area intraday momentum strategy of Zarattini, Aziz and Barbon ("Beat the Market") works on the WIN mini Ibovespa future and the WDO mini dollar future. Development data: 2021-12-01 to 2024-12-30 (770 days). Final test: 2025-01-02 to 2026-10-30 (458 days), kept unread until the owner asked for it. Costs: the B3 fee plus one tick of slippage a side. Sizing: the paper's 2% volatility target with a leverage cap of 4.

## Decision

1. Build the strategy with the paper's rules as the default and every other choice (stop type, stop timing, exit time, sides, lookback, band width, decision frequency, first decision) as a searchable parameter. The engine reproduces the authors' loop exactly.
2. Search 50,000 random combinations of eight parameters (29.5% of 169,344), scored on WIN, on WDO and jointly (the worse of the two Sharpe ratios), and measure the selection effect with leave-one-year-out folds and a scrambled-data luck baseline.
3. Run the final test once, on six rows fixed on development data: the paper's rule, two variants of it, and the best trial by WIN, by WDO and jointly.
4. Nominate nothing for trading. No pass rule has been approved by the owner (the proposal in brief section 10 is reported, not applied). Nothing may be tuned on the final period any more.

## Consequences

- The paper's rule on the final period: WIN Sharpe 1.18, WDO -0.48, the 50/50 average 0.46 with a CAGR of 5.9% against 14.3% for the CDI.
- The shared-parameter search did not beat the paper's defaults out of sample: the joint winner scored -0.20 held out in leave-one-year-out, and on the final period its 50/50 Sharpe fell from 1.48 to 0.60 (CAGR 7.5%, below the CDI).
- The WDO-only winner collapsed (Sharpe 1.57 to -1.09), the overfitting that leave-one-year-out predicted.
- The best trial by WIN held on WIN (Sharpe 2.05 to 2.10, t 2.83, drawdown 5.6%, positive in both years). It is the one result consistent with a real edge, with the caveats recorded in brief section 10: one of six rows read, a favourable period for the paper's rule too, it fails on WDO, it does not beat the CDI on the 50/50 average, and it does not beat buying the IBOV (35% a year).
- Whether to treat the best-by-WIN trial as a candidate is open. The only clean confirmation is a later period.
- Not modelled: taxes, slippage beyond one tick, intraday margin calls, roll costs (the owner decided to treat roll days as normal days), carry and the interest on idle cash.
