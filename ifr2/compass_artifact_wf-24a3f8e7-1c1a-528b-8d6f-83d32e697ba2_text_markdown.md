# IFR2 / RSI(2) Strategies: Original Rules, Variants, Benchmarks, Algorithms and What Still Works (2026)

The best-supported IFR2 setup is still the simple long-only daily version: buy a liquid index ETF (SPY, or BOVA11 in Brazil) or a large, liquid stock at the close when RSI(2) is deeply oversold (below 10) and price is above its 200-day average, then exit on a short-term bounce (close above the 5-day SMA, or RSI(2) above 65–70). It has no stop and is in the market only about 10–30% of the time. The edge is real and has survived 17 years of out-of-sample data, but Empirica Lab (research note EL-R-2026-302, October 2026) found the average SPY trade fell from 0.79% to 0.51% after 1 January 2009, "a 35% drop in the average trade". In its words, the effect "survived publication, about a third smaller per trade." It loses to buy-and-hold on raw return, so its value is low drawdown and spare capital, not beating the index.

## TL;DR
- **Original (Connors & Alvarez, *Short Term Trading Strategies That Work*, 2008):** go long when close > SMA(200) and RSI(2) < 5 (or < 10), exit when the close is above SMA(5), with no stop. Shorts mirror this (close < SMA(200), RSI(2) > 95, exit when the close is below SMA(5)), but independent tests show the short side mostly loses on equities. The book's S&P 500 test (1995–2007) showed 49 trades and 83.6% winners. An independent replication got a 3.91% annual return and a −6.48% max drawdown over that period, falling to 1.35% a year with a −13.19% max drawdown in 2008–2015.
- **Benchmarks today:** the most rigorous independent rebuild (Empirica Lab, SPY, 1993–Sep 2026, 2 bps per side) found 265 trades, 77% winners, 0.63% per trade, 5.0% CAGR vs 10.8% for buy-and-hold, and a 14.8% max drawdown vs 55.2%. It was invested on only 893 of 8,475 days (10.5%), "in cash on about nine days in ten". Its Sharpe fell from 0.97 before 2009 to 0.68 after, below buy-and-hold's 0.87. On individual stocks, Alvarez measured the average RSI(2) trade falling from 0.89% (2003–07) to 0.52% (2010–18). Brazilian IFR2 backtests are positive on most Ibovespa stocks but are all gross of costs, and on BOVA11 they trailed the index.
- **Best versions (ranked):** (1) classic SMA200 + RSI(2) < 10 + SMA(5) or RSI > 70 exit on index ETFs; (2) Cumulative RSI(2) and RSI(4) "Power Zone"/RSI 25-75 variants on ETFs; (3) adding an IBS (close-in-range) filter; (4) stock-portfolio versions with liquidity filters, limit-order entries below the close and ranking, which have the highest CAGR but are the most fragile. Daily bars are much better than intraday: on 1-minute SPY a gross +23.9% CAGR became −22.3% after just 1 bp of round-trip friction.

## Key Findings

1. **The edge exists and is not a parameter fluke.** In the Empirica Lab rebuild, all 15 neighbouring settings (RSI lengths 2–4, thresholds 5–25) were positive. The real trades beat all 2,000 random-entry placebo runs, and the estimated probability of backtest overfitting was 4%.\[1\] QuantifiedStrategies' threshold sweep (RSI(2) < 5, 10, 15, 20) kept the profit factor between 1.72 and 2.17.\[2\]
2. **It has decayed, but has not died.** On SPY the average trade fell from 0.79% (1993–2008) to 0.51% (2009–2026), and the win rate from 81% to 74%.\[1\] QuantifiedStrategies' daily SPY RSI(2) profit factor declined from 2.01 (1998–2007) to 1.80 (2008–2016) to 1.52 (2017–2026).\[2\] Alvarez's Russell 3000 study called the verdict "slowly shrinking."\[3\]
3. **Index ETFs are the safest home and SPY is the best case.** Empirica found the identical rule positive on five other equity ETFs, but SPY's Sharpe (0.81) was well ahead of the others (0.38–0.53).\[1\] Individual stocks give more signals and higher potential CAGR but carry gap and idiosyncratic risk. Connors advised using much lower thresholds on single stocks.\[4\]
4. **Stops hurt; time stops and position sizing are the real risk control.** Connors & Alvarez wrote that "the overwhelming evidence from these tests shows that stop-losses, in general, hurt system performance."\[5\]\[6\] Alvarez's later tests found that wider stops did better and no stop did best.\[7\]\[8\] The worst losses come from overnight gaps that stops cannot prevent.\[7\]\[9\]
5. **Long beats short.** In StatOasis' sweep on SPY, QQQ, IWM and DIA, 89.7% of long-side variants made money vs 8.8% of short-side variants.\[10\]
6. **Daily beats intraday.** Below the 240-minute timeframe, the edge per trade is too small to survive costs.\[2\]

## Details

### 1. The original strategy (verified rules)

**Source:** Larry Connors & Cesar Alvarez, *Short Term Trading Strategies That Work* (TradingMarkets, November 2008).\[1\]\[11\] Alvarez says he has been "using and promoting RSI2 since 2004."\[12\] Most of the book's tests use 1995–2007 data.\[1\]

**Underlying statistic (book):** Across more than eight million trades from 1995 to 2007, stocks with RSI(2) below 10 beat the benchmark 1 day later (+0.07%), 2 days later (+0.21%) and 1 week later (+0.49%). The lower the RSI(2), the better the subsequent returns.\[11\]

**Core rules (as summarized by StockCharts ChartSchool and the book):**
- Trend filter: long only if close > SMA(200); short only if close < SMA(200).\[5\]
- Entry: long when RSI(2) < 10 (Connors found < 5 better than < 10; tested 0–10). Short when RSI(2) > 90 (> 95 better).\[5\]
- Exit: long when the close is above SMA(5); short when the close is below SMA(5).\[5\]\[13\] Alternative exits in the book include RSI(2) > 65–75.\[1\]\[14\]\[15\]
- Execution: at the close. No stop.\[1\]\[13\]\[16\]

**Book results vs independent replication (S&P 500, RSI(2) < 5, SMA(5) exit):**

| Test | Period | Trades | Win % | Other |
|---|---|---|---|---|
| Book | 1995–2007 | 49 | 83.6% | 522.92 points, about 3-day hold |
| Marwood (Amibroker/Norgate, no costs) | 1995–2007 | 49 | 83.7% | 3.91% annual return, −6.48% MDD |
| Marwood (same rules, out-of-sample) | 2008–2015 | 30 | 80% | 1.35% annual return, −13.19% MDD\[11\] |

**Interpretation:** The rules replicate almost exactly in-sample. Out-of-sample, the win rate held up but the return-to-drawdown ratio (CAR/MDD) fell from 0.60 to 0.10,\[11\] which is the decay pattern seen in every later study.

### 2. Triggers, filters, sizing and stops

**Entry triggers**
- Classic: RSI(2) < 10 (more trades) or < 5 (fewer, higher-quality trades).
- Cumulative RSI: the sum of the last 2 days' RSI(2) < 35 on SPY, or < 10 on stocks.\[11\]
- Brazilian "Stormer" IFR2: IFR2 ≤ 25 (or ≤ 30) at the close, often without a trend filter.\[17\]\[18\]\[19\]

**Exit triggers**
- Close > SMA(5): the original rule.
- RSI(2) > 65 or > 70: Connors' alternatives.\[14\]
- Close > the previous day's high (QuantifiedStrategies). This lowers the average gain but sharply cuts drawdown.\[15\]
- Highest high of the last 2 bars as a moving target: the Stormer standard in Brazil.\[17\]\[18\]\[19\]\[20\]
- Time stop: 5–10 bars (10 in many US tests, 7 in Brazil).\[18\]\[21\]\[22\]

**Trend and regime filters**
- SMA(200) is the standard filter. On SPY it raised the average trade from 0.9% to 0.95% and cut max drawdown from 34% to 31%, but CAGR dropped from 9% to 6.8% (QuantifiedStrategies, RSI(2) < 10 / exit > 80).\[15\]
- On individual stocks, Alvarez found the MA200 filter "does not add anything to the avg % p/l."\[3\]
- Alternatives used: SMA(100) on stocks, a rising MA50/EMA80 in Brazil, and ADX(10) > 30 in the ConnorsRSI pullback strategy.\[23\]\[24\]\[25\]

**Liquidity and universe filters**
- Book (stocks): price > $5 and average volume > 250,000 shares.\[11\]
- Alvarez 2018: Russell 3000, price > $1, 21-day average dollar volume > $500K.\[23\]
- ConnorsRSI guidebook: price > $5 and 21-day average volume ≥ 250,000.\[24\]

**Volatility / pullback depth (ConnorsRSI pullback):**
- The low is at least W% (2–8%) below the prior close.
- The close is in the bottom 10–25% of the day's range.\[24\]
- Ranking by 100-day historical volatility.\[23\]

**Scaling in**
- TPS (Time-Price-Scale), from *High Probability ETF Trading*: price above the 200-day MA and RSI(2) < 25 for two consecutive days. Buy 10% of the position, then add 20%, 30% and 40% on each lower close. Exit when RSI(2) > 70.\[26\]\[27\]
- RSI Power Zones: add a second unit at a deeper RSI(4) level.\[28\]
- Alvarez, however, reports that scaling in generally lowers overall returns in his tests.\[9\] Treat scaling as a risk-distribution choice, not an edge.

**Stops**
- The consistent research finding is that hard stops reduce mean-reversion performance.\[5\]\[8\]\[29\]
- In one example, a 2013 modified version of the model that added a $2,000 hard stop on S&P futures "does hurt the performance."\[16\]
- Practical risk control is therefore position sizing, a time stop, portfolio diversification, and the trend filter (which kept SPY flat from September 2000 to May 2003 and through 2008).\[1\]

### 3. Updated and derived versions

| Version | Rules | Origin |
|---|---|---|
| **Cumulative RSI(2)** | Close > SMA200; RSI(2) summed over 2 days < 35 (SPY) or < 10 (stocks); exit RSI(2) > 65 | Connors & Alvarez 2008\[11\] |
| **Double 7s** | Close > SMA200; close = 7-day closing low → buy; exit at 7-day closing high | Connors & Alvarez 2008\[30\] |
| **RSI 25/75 & RSI Power Zones** | Close > SMA200; RSI(4) < 25 (add < 20) or (30, 25); exit RSI(4) > 55 | *High Probability ETF Trading* (2009); *Buy the Fear, Sell the Greed*\[28\]\[31\] |
| **TPS** | Above 200-day MA; RSI(2) < 25 for 2 days; scale 10/20/30/40% on lower closes; exit RSI(2) > 70 | *High Probability ETF Trading*\[26\] |
| **ConnorsRSI(3,2,100)** | [RSI(Close,3) + RSI(Streak,2) + PercentRank(1-day return,100)] / 3; buy < 5–15, exit > 50–80 | Connors Research 2012\[24\] |
| **IBS combinations** | IBS = (C − L)/(H − L); require low IBS (e.g. < 0.2–0.5) alongside a low RSI | Pagonidis 2013; Kinlay\[32\]\[33\] |
| **Alvarez RSI2 stock pullback** | Russell 3000, close > MA100, RSI2 < 10; limit buy 5% below close; rank by HV100; exit RSI > 50 or 10 days | Alvarez 2018\[23\] |
| **Stormer IFR2 (Brazil)** | IFR2 ≤ 25/30 at close; exit at highest high of last 2 bars; optional 7-bar time stop; SMA200 optional | Alexandre Wolwacz "Stormer"\[18\]\[20\] |

**Evidence on each version**
- **Cumulative RSI:**
  - Book, SPY 1993–2007: 50 trades, 88% winners. Marwood could not replicate this (127 trades, 74%).
  - Book, stocks with cumulative RSI < 10: 77,068 signals from 1995 to 2008, "of which 69% of trades were profitable."
  - Marwood's S&P 1500 portfolio version (10 positions, 1995–2015, commissions included): 8,711 trades, 64.7% winners, 23.86% CAGR, −21.36% MDD. The strongest years were early (more than 80% gains in 1997, 1999 and 2000).\[11\]
  - QuantifiedStrategies' SPY cumulative RSI: 167 trades, 0.67% average, 83% winners, 14% MDD, about 7% time in market.\[34\]
- **Double 7s:**
  - Book stats as reported secondhand: SPY, 153 trades, 80.4% winners, 0.85% average.\[35\]
  - Alvarez's own update: beat buy-and-hold in 2000–2007 with about 26% exposure, but "has not held up as well since 2008." Both SPY and QQQ CAR fell below buy-and-hold in 2008–2015.\[36\]
  - StrategyQuant (SPY 1993–Sep 2026): 333 trades, PF 2.35, Sharpe 0.85, MDD about 12.5%.\[37\]
- **RSI Power Zones:** the book claims 90.59% winners for (30, 25, 55) and 92.52% for (25, 20, 55) on SPY.\[28\] These are reported, not independently verified. StatOasis could not reproduce the roughly 90% win rates of the related QuantifiedStrategies "Triple RSI" on SPY, getting 59–65%.\[38\]
- **ConnorsRSI:** the guidebook's base study covered about 6,000 liquid stocks from 2001 to mid-2012. Stocks with CRSI < 5 averaged +2.28% over the next 5 days; the 95+ bucket averaged −1.42%.\[24\] That is a strong monotonic gradient, but the test was in-sample and run by the indicator's creators.
- **IBS:**
  - Pagonidis (NAAIM, 2013) found that adding an IBS filter to an RSI strategy across equity ETFs "improves total returns by almost 10 percentage points while decreasing time spent in the market by almost 45%."\[39\]
  - IBS alone is hard to trade after costs.\[39\]
  - This is the best-documented "add-on" to RSI(2).
- **Alvarez 2018 ex-index tweak:** trading only stocks that had dropped out of the Russell 3000 raised CAR by 121% and cut MDD by 54%. Alvarez himself labelled the follow-up RSI2 < 15 variant "cherry picked." Readers flagged sub-$10 and OTC fills and an outlier trade.\[23\] Treat it as a research idea, not a deployable result.

**Decay evidence (2010s–2026)**
- Alvarez, Russell 3000, RSI2 crossing below 1, exit RSI2 > 70, 2001–2018, 88,750 trades:
  - The average trade was 0.52% overall, falling to 0.33% in the last two years and from 0.89% (2003–07) to 0.52% (2010–18).
  - The win rate held steady at about 65%.
  - Alvarez stopped trading his "simple" mean-reversion strategy in 2016 because of poor performance.\[3\]
- SPY: Sharpe 0.97 before 2009 vs 0.68 after (Empirica).\[1\] The post-2009 profit factor was still 2.4, but the rule returned 4.3% a year vs SPY's 14.9%.\[1\]
- Overall pattern: the win rate is stable, the average gain per trade shrinks, and relative performance vs buy-and-hold has worsened in the strong 2009–2026 bull market.

### 4. Benchmarks table (independent backtests unless noted)

| Strategy / source | Market, period | Trades | Win % | Avg trade | CAGR (B&H) | Max DD (B&H) | Time in mkt | Costs |
|---|---|---|---|---|---|---|---|---|
| Classic SMA200, RSI2<10, SMA5 exit — Empirica Lab | SPY 1993–2026 | 265 | 77% | 0.63% | 5.0% (10.8%) | 14.8% (55.2%) | 10.5% (893 of 8,475 days) | 2 bps/side |
| RSI2<10, exit RSI2>70 or 10 days, SMA200 — Guru Finance | SPY 2000–2026 | 181 | 82% | n/a | below B&H; Sharpe 0.62 vs 0.53 | n/a (55.2%) | 10.2% | "considered"\[22\] |
| RSI2<10, exit >80, no filter — QuantifiedStrategies | SPY 1993–2021 | n/a | n/a | 0.9% | 9% | 34% | 28% | none stated\[15\] |
| Same + SMA200 — QuantifiedStrategies | SPY 1993–2021 | n/a | n/a | 0.95% | 6.8% | 31% | 18% | none stated\[15\] |
| RSI2 daily, buy <10 / sell >80 — QuantifiedStrategies 2026 | SPY 1998–2026 | 338 | 70.7% | 0.424% | 4.87% gross / 4.74% at 1 bp | 22.8% | n/a | sensitivity\[2\] |
| Cumulative RSI — QuantifiedStrategies | SPY since 1993 | 167 | 83% | 0.67% | n/a | 14% | ~7% | none stated\[34\] |
| Cumulative RSI<10 stock portfolio — Marwood | S&P 1500 1995–2015 | 8,711 | 64.7% | n/a | 23.86% | 21.36% | n/a | $0.01/share\[11\] |
| RSI2 cross <1, exit >70 — Alvarez | Russell 3000 2001–2018 | 88,750 | ~65% | 0.52% | event study | n/a | n/a | none\[3\] |
| Double 7s — StrategyQuant | SPY 1993–2026 | 333 | n/a | n/a | PF 2.35, Sharpe 0.85 | ~12.5% | 28% | n/a\[37\] |
| IFR2 ≤30, exit 2-bar high — QuantBrasil | LREN3 2015–2020 | 160 | 74% | 0.86% | 138.54% total | 10.37% | n/a | none\[25\]\[40\] |
| IFR2<20, 5-bar/2×ATR exit — UNIPAMPA TCC | 33 Ibovespa stocks 2012–2021 | n/a | 54.41% | n/a | 12.59% (B&H 12.72%, BOVA11 5.96%, CDI 8.34%) | 46.38% | n/a | none |

**Reading the table:**
- On index ETFs, RSI(2) rarely beats buy-and-hold CAGR. Its edge is return per unit of exposure: Empirica Lab found that "on its days in the market it earned about 0.20% a day, four times the average SPY day," plus far smaller drawdowns.
- Portfolio stock versions show much higher CAGR because capital is always deployed across many signals. Those results are concentrated in the 1990s–2000s and are sensitive to fills at the close, slippage and survivorship-free data.

### 5. Algorithms (implementation-ready)

**Wilder RSI(n)**, with n = 2 for IFR2:
```
delta_t   = C_t − C_{t−1}
gain_t    = max(delta_t, 0);  loss_t = max(−delta_t, 0)
# seed (first value): simple mean of first n gains/losses
avgG_n = mean(gain_1..gain_n);  avgL_n = mean(loss_1..loss_n)
# Wilder smoothing (= EMA with alpha = 1/n; alpha = 0.5 for n=2)
avgG_t = (avgG_{t−1}·(n−1) + gain_t) / n
avgL_t = (avgL_{t−1}·(n−1) + loss_t) / n
RSI_t  = 100 if avgL_t == 0 else 100 − 100 / (1 + avgG_t/avgL_t)
```
Notes:
- Pine's `ta.rsi(close, 2)`, MQL5's `iRSI` and TradeStation's `RSI` all use Wilder smoothing.
- pandas: `ewm(alpha=1/n, adjust=False)`.
- With n = 2 the seed washes out within a few dozen bars. Still use at least 250 bars of history (also needed for the SMA200).
- Use split- and dividend-adjusted closes for signals.

**A. Classic Connors RSI(2) (long; mirror for short)**
```
setup_long  = C > SMA(C,200) and RSI(C,2) < 10      # strict: < 5
enter at today's close (MOC order a few minutes before the close on an estimated RSI)
exit_long   = C > SMA(C,5)                          # alt: RSI(C,2) > 70 (or 65)
optional    = time stop 10 bars; no price stop
short side  = C < SMA(C,200) and RSI(C,2) > 90/95 ; exit C < SMA(C,5)   # weak evidence
```

**B. Cumulative RSI(2)**
```
cumRSI = RSI(C,2) + RSI(C,2)[1]
long if C > SMA(C,200) and cumRSI < 35 (ETF) / < 10 (stocks, plus price > $5, avg vol > 250k)
exit when RSI(C,2) > 65
```

**C. RSI(4) Power Zone / RSI 25-75 (ETF)**
```
if C > SMA(C,200) and RSI(C,4) < 25: buy 1 unit at close
if in position and RSI(C,4) < 20:   buy 2nd unit
exit all when RSI(C,4) > 55
```

**D. TPS scale-in**
```
cond = C > SMA(C,200) and RSI(C,2) < 25 and RSI(C,2)[1] < 25
day1: buy 10%; each subsequent close lower than last entry: +20%, +30%, +40%
exit all when RSI(C,2) > 70
```

**E. ConnorsRSI(3,2,100)**
```
streak_t = streak_{t−1}+1 if C>C[1] (min 1) ; streak_{t−1}−1 if C<C[1] (max −1) ; 0 if equal
ret_t    = C/C[1] − 1
pr_t     = 100 · count(ret_{t−100..t−1} < ret_t) / 100
CRSI     = (RSI(C,3) + RSI(streak,2) + pr_t) / 3
```

**F. IBS filter add-on**
```
IBS = (C − L) / (H − L)    (set 0.5 if H == L)
long only if RSI condition true AND IBS < 0.2–0.5
```

**G. Stormer IFR2 (B3)**
```
entry: IFR2(C) ≤ 25 (or 30) → buy at close (optionally C > SMA200 or rising MA)
target: highest(H, 2) of the two prior bars, recalculated daily;
        fill at Open if Open > target else at target when H ≥ target
time stop: exit at close after 7 bars (QuantBrasil used 7; others 3–5)
```

**H. Alvarez RSI2 stock pullback (portfolio)**
```
universe: liquid stocks, price > $1–5, 21d avg $vol > $500K
setup: C > SMA(C,100) and RSI(C,2) < 10
entry: next-day limit at C × 0.95; max 10 positions; rank by 100-day HV (high first)
exit: RSI(C,2) > 50 or 10 bars, at next open
```

### 6. Best versions: ranked comparison

| Rank | Version | Evidence strength | Robustness / out-of-sample | Main weakness | Use it for |
|---|---|---|---|---|---|
| 1 | Classic RSI(2) < 10 + SMA200 + SMA5 / RSI > 70 exit, index ETFs | Highest: many independent replications, 17 yrs out-of-sample, placebo test, 15/15 neighbouring settings positive | Good; edge about 35% smaller since 2009 | Lags buy-and-hold CAGR; single-trade gap risk (bought 27 Jul 2011, sold 11 Aug 2011 10.2% lower; worst day −6.5% on 8 Aug; no new high until June 2013, per Empirica Lab) | Core sleeve in a multi-strategy book |
| 2 | Cumulative RSI(2) / RSI(4) Power Zone / RSI 25-75 on ETFs | Medium-high: book plus several independent tests; parameters smooth | Moderate; headline win rates (90%+) not reproduced | Fewer trades; in-sample book claims | Diversifying the entry definition |
| 3 | RSI(2) + IBS filter | Medium: academic-style paper (Pagonidis), several practitioner tests | Reported effect persisted 1990s–2010s | Small samples per ETF; needs a clean H/L | Improving return per unit of exposure |
| 4 | Double 7s | Medium: Alvarez's own out-of-sample update | Weakened after 2008 | Underperformed buy-and-hold 2008–2015 | Simple, price-only alternative |
| 5 | Stock-portfolio RSI(2)/Cumulative RSI/ConnorsRSI pullback with liquidity filters, limit entry, ranking | Mixed: high CAGR backtests but strongly decaying | Weakest; Alvarez's simple version stopped working in 2016 | Slippage, survivorship, data and parameter sensitivity | Only with point-in-time constituent data and realistic costs |
| 6 | Brazilian Stormer IFR2 on single stocks | Low-medium: gross-of-cost blog and thesis backtests only | Highly ticker-dependent | No costs or tax modelled; survivorship | Selective use on low-volatility, liquid B3 names |
| 7 | Short-side RSI(2) and intraday RSI(2) | Weak/negative | Fails costs or trend | Equity upward drift; friction | Avoid, unless as a hedge leg |

**Parameter guidance with the best evidence:**
- RSI length 2–4.
- Entry threshold 5–15 on ETFs (10 is the sweet spot; < 5 trades too rarely).\[41\]
- Exit at SMA(5) or RSI > 65–70, plus a 10-bar time stop.
- Trend filter SMA(200) on indices.
- No hard stop; size so that a 10–15% single-trade gap is survivable.

### 7. Intraday

QuantifiedStrategies (Sep 2026) applied the same RSI(2) buy < 10 / sell > 80 rule to SPY from July 1998 to September 2026 across nine timeframes:\[2\]

| Timeframe | Result |
|---|---|
| 1-minute | 131,738 trades, average 0.0047% (about 0.47 bp). Gross CAGR +23.9% became −22.3% with 1 bp of round-trip friction |
| 15-minute | Also turned negative with costs |
| 240-minute | 705 trades, 68.7% win, PF 1.33, 0.153% average, CAGR 3.57%, MDD 19.1%. Robust to costs and improved with longer RSI lookbacks (PF 1.33 → 1.69 → 2.10) |
| Daily | CAGR 4.87% gross, 4.74% at 1 bp, 4.24% at 5 bps |
| Weekly | PF 2.22 but only 71 trades |
| Monthly | Only 8 trades\[2\] |

Implications:
- The RSI(2) edge does not transfer usefully to bars shorter than about 4 hours for retail traders.
- The Brazilian Stormer TradingView script itself warns that intraday use makes "too little money to compensate for the operational cost."\[17\]
- Brazilian sites suggest 60- and 120-minute IFR2,\[18\] but no costed evidence supports it.

### 8. Brazil (B3) evidence

All of the B3 backtests found are gross of brokerage, emolumentos and income tax, and most suffer from survivorship bias (index membership taken at the end of the sample).

**QuantBrasil (Andressa Quintanilha, 2021)**

Setup: Stormer rules (IFR2 ≤ 30, exit at the 2-day high), Yahoo data,\[42\] R$10,000 starting capital, round lots, no compounding, no costs.\[19\]\[40\]

LREN3, 2015–2020, by entry level:

| Entry | Trades | Win rate | Total profit | Max DD |
|---|---|---|---|---|
| IFR2 ≤ 30 | 160 | 74% | 138.54% | 10.37% |
| IFR2 ≤ 20 | 128 | 78% | 134.82% | 7.11% |
| IFR2 ≤ 10 | 73 | 77% | 87.71% | 5.18% |
| IFR2 ≤ 5 | 36 | 81% | 58.10% | 5.35%\[40\] |

As in the US, deeper oversold levels raise the win rate but cut total profit.\[40\]

Other QuantBrasil results:
- **Moving-average filters** on LREN3 lowered total profit (MA50 filter: 69.25%). Switching the exit to IFR2 ≥ 70 raised profit per trade to 1.08%.\[21\]\[25\]
- **Dynamic list** (top-5 Ibovespa momentum stocks): 72 trades, 72% winners, 58.42% total, 26.2% drawdown with a 7-day time stop.\[21\]
- **All 81 Ibovespa stocks:**
  - Best: LCAM3 (+184.40%), TOTS3, CPLE6, PCAR3 (1.47% per trade).\[42\]
  - Lowest drawdowns: utilities EGIE3, ENGI11 and TAEE11 (about 7%).\[42\]
  - 12 of 81 stocks lost money (GOLL4 −55.40%, BRFS3 −46.50%, IRBR3 −44.35%), even though every stock had a win rate above 60%.\[42\]

**UNIPAMPA thesis (Soares, 2022)**

Setup: 33 Ibovespa stocks, 2012–2021, TradingView Pine code. Entry at IFR2 < 20 (buy at the next open), exit after 5 candles or at a 2×ATR(15) stop, no costs.\[43\]

| Strategy | Total return | CAGR |
|---|---|---|
| IFR2 | 227.27% | 12.59% |
| Equal-weight buy-and-hold | 231.10% | 12.72% |
| CDI | 122.81% | 8.34% |
| BOVA11 | 78.38% | 5.96% |

IFR2 also had a 54.41% win rate, PF 1.336 and a 46.38% maximum drawdown. It was the best of the three strategies in 14 stocks, buy-and-hold in 11 and CDI in 8.\[43\]

**No Alvo (community article, 2013–2018)**

Setup: IFR2 < 30 or < 10 with an SMA200 filter, compounding, data from ProfitPlus.\[44\]
- BOVA11 returned 26–61% depending on the variant, vs about 70% for the Ibovespa. IFR2 on the index ETF lost to simply holding it.\[44\]
- MGLU3 returned up to 414%, with exit on a close above the SMA5 beating the 2-bar-high exit.\[44\]

**Earlier and anecdotal reports**
- A 2010 blog reported a 62.39% win rate for Stormer's setup on the author's own stock list.\[45\]
- A Senhor Mercado forum backtest reported near-0% profitability after 4 years.\[46\] That forum page could not be retrieved, so this is unverified.

**Practical B3 adjustments**
- Restrict to liquid Ibovespa names. Utilities and other low-volatility stocks have had the smoothest curves.\[42\]
- Model B3 fees and slippage. B3's official fee table for regular (non-day-trade) cash-equity orders charges 0.0300% per side for investors with monthly ADTV up to R$3M (0.005% trading + 0.0224% CCP + 0.0026% TTA), and 0.0225% above R$3M.
- Account for tax. B3's Bora Investir (May 2026) states swing trades are taxed at 15% on profit, which can be exempt for stock sales up to R$20k a month, plus a 0.005% "dedo-duro" withholding on the sale value. A secondary source (DataBolsa) notes the exemption does not apply to ETFs such as BOVA11, which pay 15% on swing trades with no exempt band.
- Compare against the CDI earned on idle cash, since the strategy is mostly out of the market.

## Recommendations

1. **Start with the classic daily rule on index ETFs** (SPY/IVV; BOVA11 on B3): SMA200 filter, RSI(2) < 10, exit on close > SMA(5) or RSI(2) > 70, 10-bar time stop, no hard stop. Empirica Lab's SPY cost test (1993–2026) gives the realistic range: 5.3% a year at zero costs, 4.4% at 6 bps per side and 3.7% at 10 bps. That comes with about 10–15% exposure and roughly 15–23% max drawdown. Do not expect to beat buy-and-hold.
2. **Make idle capital work.** The case for RSI(2) depends on combining it with T-bills/CDI or other uncorrelated strategies. Alvarez and the QuantifiedStrategies portfolio studies both stress diversification across mean-reversion families (RSI2, IBS, Double 7s, %B).\[47\]\[48\]
3. **Add an IBS < 0.5 confirmation and/or the Cumulative RSI entry** before reaching for more parameters. These are the add-ons with independent support.
4. **For individual stocks, use a portfolio framework:**
   - Liquidity filters.
   - Rank multiple signals (e.g., by volatility or lowest RSI).
   - Cap at 10 positions.
   - Limit-order entries below the close.
   - Test with point-in-time index constituents.
   - Haircut backtest returns heavily, because the per-trade edge is now about 0.3–0.5%.
5. **On B3, rerun the Stormer setup with costs and tax**, on a survivorship-free universe, and compare against CDI. Trade only names where the edge survives (historically low-volatility utilities and quality names, not airlines or highly leveraged firms).
6. **Avoid the short side and sub-4-hour intraday versions** unless you have institutional-level costs.
7. **Execution:** submit market-on-close orders on an estimated RSI a few minutes before the close,\[1\] or use next-open entry and accept slightly worse results.\[17\] Test both.

## Caveats

- **Source quality.**
  - Many of the most-cited numbers (QuantifiedStrategies, StatOasis, Empirica Lab, Guru Finance) are practitioner backtests on blogs and Substacks, not peer-reviewed research. Book figures are in-sample results from the strategy's own authors.
  - Very high win-rate claims (90%+ for Power Zones and Triple RSI) were not independently reproduced.\[38\]
  - Some of the book's rules are cited secondhand.
- **Overfitting and data-mining.** Alvarez's own studies show that top optimization results mean-revert out-of-sample. Prefer parameter neighbourhoods over peaks.\[49\]
- **Survivorship and index-inclusion bias.** This affects most stock-level tests, especially the Brazilian ones and the ex-index tweak.
- **Costs and execution.** Closing-price fills on a signal that is only final at the close are optimistic.\[1\]\[11\] Brazilian tests ignore costs and tax entirely.\[43\] Intraday results collapse with costs.\[2\]
- **Regime dependence.** Mean reversion did best in volatile 1997–2007 markets and has lagged in the 2009–2026 bull run. Alvarez expects it may "come back during the next bear market," but that is a forecast, not evidence.\[3\]
- **Tail risk without stops.** A single trade can lose more than 10%: Empirica Lab's worst SPY trade was bought on 27 July 2011 and sold on 11 August 10.2% lower. Position sizing must assume gaps.

## Sources

1. [Connors' RSI(2) had a Sharpe of 0.97 before the book. Since then: 0.68.](https://empiricalab.substack.com/p/connors-rsi2-spy)
2. [Best Timeframe for RSI: We Backtested 9 Timeframes From 1-Minute to Monthly](https://quantifiedstrategies.substack.com/p/best-timeframe-for-rsi-we-backtested)
3. [How is mean reversion doing? Dead, Shrinking or Doing Just Fine](https://alvarezquanttrading.com/blog/how-is-mean-reversion-doing-dead-shrinking-or-doing-just-fine/)
4. [Testing The RSI 2 Trading Strategy On US Stocks](https://decodingmarkets.com/rsi-2-trading-strategy/)
5. [RSI(2)](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2)
6. [Short Term Trading Strategies That Work](https://medium.com/@setupalpha.capital/short-term-trading-strategies-that-work-507a8afa8485)
7. [Cesar Alvarez on trading ideas, backtesting pitfalls, and stops in mean reversion](https://bettersystemtrader.com/003-cesar-alvarez/)
8. [Maximum Loss Stops: Do you really need them?](https://alvarezquanttrading.com/blog/maximum-loss-stops-do-you-really-need-them/)
9. [Mean Reversion Strategy Rules: Regimes, Entries and Exits](https://bettersystemtrader.com/130-building-mean-reversion-strategies-with-cesar-alvarez-part-2/)
10. [RSI vs Stochastic vs Williams %R: 33,792 Backtests · StatOasis](https://statoasis.com/overfit/research/rsi-vs-stochastic-vs-williams-r)
11. [Testing The RSI 2 Trading Strategy](https://stocksoftresearch.com/rsi-2-trading-strategy/)
12. [General](https://alvarezquanttrading.com/blog/category/general/page/2/)
13. [This Simple Mean Reversion Strategy Has Stood the Test of Time](https://algotr.substack.com/p/this-simple-mean-reversion-strategy)
14. [RSI(2) Strategy by Larry Connors](https://stratbase.ai/en/blog/rsi-2-strategy-larry-connors)
15. [RSI 2 Strategy: Complete Guide To Larry Connors’ 2‑Period RSI Trading Rules - QuantifiedStrategies.com](https://www.quantifiedstrategies.com/rsi-2-strategy/)
16. [Connors 2-Period RSI Update for 2016 - Helping you Master EasyLanguage](https://easylanguagemastery.com/strategies/connors-rsi-update-2016/)
17. [OPEN-SOURCE SCRIPT](https://it.tradingview.com/script/UD0anrUb)
18. [IFR2](https://www.pivotrade.com.br/ifr2)
19. [Criando o Backtest da Estratégia de IFR2 em Python](https://quantbrasil.com.br/blog/criando-o-backtest-da-estrategia-de-ifr2-em-python/)
20. [IFR 2 Stormer RSI 2 — Strategy by Patolino1 — TradingView](https://www.tradingview.com/script/Y7Kt90xU/)
21. [Backtest da Estratégia de IFR2 em uma Lista de Ativos Dinâmica | QuantBrasil](https://quantbrasil.com.br/blog/backtest-da-estrategia-de-ifr2-em-uma-lista-de-ativos-dinamica/)
22. [I Backtested the Classic RSI(2) Mean-Reversion Strategy on 26 Years of SPY. 181 Trades, 82% Win Rate — Here's the Honest Result.](https://gurufinanceinsights.substack.com/p/i-backtested-the-classic-rsi2-mean)
23. [RSI2 Strategy: Double returns with a simple rule change](https://alvarezquanttrading.com/blog/rsi2-strategy-double-returns-with-a-simple-rule-change/)
24. <https://alvarezquanttrading.com/wp-content/uploads/2016/05/ConnorsRSIGuidebook.pdf>
25. [Backtest da Estratégia de IFR2 Utilizando Médias Móveis Como Filtro | QuantBrasil](https://quantbrasil.com.br/blog/backtest-da-estrategia-de-ifr2-utilizando-medias-moveis-como-filtro/)
26. [TPS Trading Strategy - Time, Price, Scale-In With 93.98% Win Rate](https://tradingstrategyguides.com/tps-trading-strategy/)
27. [Connors RSI2](https://www.mql5.com/en/market/product/172894)
28. [RSI PowerZones Signals and Backtesting - EdgeRater Blog](https://www.edgerater.com/blog/rsi-powerzones-signals-and-backtesting/)
29. [Adding Stops and Scaling Out to a Mean Reversion Strategy](https://alvarezquanttrading.com/blog/adding-stops-and-scaling-out-to-a-mean-reversion-strategy/)
30. [Professional Trading Strategies & Backtests](https://www.backtestedstrategies.com/strategies/)
31. [Larry Connors’ RSI 25 & RSI 75 (It Still Works)](https://www.quantifiedstrategies.com/larry-connors-rsi-25-rsi-75/)
32. [(IBS) Internal Bar Strength · Issue #468 · TA-Lib/ta-lib · GitHub](https://github.com/TA-Lib/ta-lib/issues/468)
33. [The Internal Bar Strength Indicator - Jonathan Kinlay](https://jonathankinlay.com/2019/07/the-internal-bar-strength-indicator/)
34. [The Cumulative RSI Indicator: A Guide by Larry Connors (83% Win Rate) - QuantifiedStrategies.com](https://www.quantifiedstrategies.com/cumulative-rsi-indicator/)
35. [Double 7s Trading Strategy - Short Term Trading Strategies that Work - Easycators Thinkorswim Downloads](https://easycators.com/thinkscript/connors-alvarez-double-7s-trading-strategy-for-thinkorswim-from-short-term-trading-strategies-that-work/)
36. [Double 7’s Strategy](https://alvarezquanttrading.com/blog/double-7s-strategy/)
37. [Larry Connor's Double 7 for SPY - StrategyQuant](https://strategyquant.com/shared/larry-connors-double-7-for-spy/)
38. [The Better-RSI Showdown: We Tested 4 RSI Upgrades on SPY, QQQ, IWM, and DIA · StatOasis](https://statoasis.com/overfit/research/better-rsi-backtest)
39. [The IBS Eﬀect: Mean Reversion in Equity ETFs Alexander Soﬀronow Pagonidis ∗](https://www.naaim.org/wp-content/uploads/2014/04/00V_Alexander_Pagonidis_The-IBS-Effect-Mean-Reversion-in-Equity-ETFs-1.pdf)
40. [Analisando Diferentes Parâmetros de Entrada para a Estratégia de IFR2](https://quantbrasil.com.br/blog/analisando-diferentes-parametros-de-entrada-para-a-estrategia-de-ifr2/)
41. [Testing Connors 2-Period RSI - EasyLanguage Mastery](https://easylanguagemastery.com/connors-rsi-update-for-2013/)
42. [Comparando os Resultados da Estratégia de IFR2 nos Ativos do Ibovespa | QuantBrasil](https://quantbrasil.com.br/blog/comparando-os-resultados-da-estrategia-de-ifr2-nos-ativos-do-ibovespa/)
43. <https://repositorio.unipampa.edu.br/server/api/core/bitstreams/40d98aa1-eb87-4de2-80a9-1a3c334342f0/content>
44. <https://noalvo.com/artigo/backtests-com-setup-ifr2>
45. [Análise Técnica: Setup do IFR2 Modificado no diário](http://alsant0z.blogspot.com/2010/01/setup-do-ifr2-modificado-no-diario.html)
46. [Simulação estratégia IFR2 -Fórum Senhor Mercado](https://www.senhormercado.com.br/forum/viewtopic.php?t=102)
47. [The Mean Reversion Portfolio That Had Only One Losing Year since 1998](https://algotr.substack.com/p/the-mean-reversion-portfolio-that)
48. [Episode 041 - Cesar Alvarez - A Novel Way to Combine Trend, Reversion, ETFs, Volatility & More!](https://algoadvantage.substack.com/p/episode-045-cesar-alvarez-a-novel)
49. [Optimization Mean Reversion - Alvarez Quant Trading](https://www.scribd.com/document/439781896/Optimization-Mean-Reversion-Alvarez-Quant-Trading)
