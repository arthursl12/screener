# IFR2 on B3: Origin, Brazilian Setups, Algorithms, Backtests and the Best Versions for Swing Trade

Short answer: no. Stormer (Alexandre Wolwacz) is not the original author of RSI(2). Larry Connors and Cesar Alvarez published the 2-period RSI pullback in the US in their 2008 book.\[1\]\[2\] Stormer is the person who turned it into "o setup IFR2" in Brazil.\[3\] The swing-trade version most Brazilians call "IFR2 do Stormer" is his own adaptation, and it differs from Connors' rules: it has no trend filter by default, it exits at the highest high of the last 2 candles, and it often uses a time stop instead of a stop loss.\[4\]

The backtests that exist for B3 are all before costs, and none covers data after 2021. They show high win rates (about 65–80%) and small average gains per trade, and results depend heavily on the stock.\[5\]\[6\] One 10-year academic test found that IFR2 merely matched buy-and-hold.\[7\]\[8\]

## TL;DR

- **Who invented it:** Connors/Alvarez own the RSI(2) concept (the 2008 book). Stormer popularized it in Brazil and wrote the Brazilian variants: the 2010 "Tática IFR2" (IFR2 < 5, buy at the close, stop at 130% of the signal candle, partial exits) and the later standard "IFR2 ≤ 20–25, exit at the highest high of the last 2 candles, optional 7-candle time stop". The earliest dated Brazilian reference I found is January 2010. Whether Stormer arrived at RSI(2) independently cannot be verified: he describes creating it himself and credits only Wilder, while Brazilian media say Connors created it.
- **Best version for B3 swing trade:**
  - Daily chart, IFR2 ≤ 20–30, buy at or near the close, exit at the highest high of the 2 prior candles, 7-candle time stop.
  - Use it only on stocks you have pre-selected, which in practice means low-volatility utilities and defensive names.
  - A Connors-style MM200 filter with a close-above-MM5 exit is the main alternative.
  - Treat every published figure as an upper bound. None includes the B3 fee of 0.0300% per side for individual swing traders (0.0050% negociação + 0.0250% liquidação, per Nelogica's blog), slippage or tax, and the stock lists carry survivorship bias.
- **What to do:** do not trust the "80% de acerto" marketing claims. Re-run the setup yourself on split- and dividend-adjusted data for 2021–2026 with costs included, using a fixed list of liquid stocks. Treat intraday versions on WIN/WDO as unproven.

## Key Findings

1. **Attribution is mixed, and the sources contradict each other.**
   - Several Brazilian outlets credit Larry Connors: InfoMoney (sponsored XP content, 2024), Invest Academy, No Alvo, FL Journal/TC.\[3\]\[6\]\[9\]\[10\]
   - Others call it "criado pelo trader brasileiro Alexandre Wolwacz": Up Traders (2012), TradingView scripts, Nelogica's blog.\[11\]\[12\]\[13\]
   - The InfoMoney piece states plainly that "O setup IFR2, criado originalmente pelo trader norte-americano Larry Connors, é largamente adaptado mundo afora. A versão brasileira, do Stormer…".\[3\]
   - In a GainCast video (read via an automatic transcript, date not visible), Stormer describes building IFR2 himself as a volatility system to beat a 9-period moving-average trend system. He credits Wilder's RSI and, in the part available, does not mention Connors.\[14\]
   - The most defensible reading: Connors published first; Stormer adapted and popularized it in Brazil.
2. **There are two distinct "Stormer IFR2" rule sets.**
   - The 2010 seminar/DVD version: IFR2 < 5, buy at the close, stop at 130% of the candle's range projected downward, MME49 as an auxiliary filter, partial profit at +2% (daily) or +4% (weekly), MME5 trailing stop.\[11\]
   - The later popular version: IFR2 ≤ 20–25, exit at the highest high of the last 2 candles, optional 7-bar time stop, no stop loss.\[15\]\[16\]
3. **The "IFR2 modificado" label means different things in different sources.**
   - In January 2010 a blogger called his EMA-filtered, optimizer-tuned version "IFR2 Modificado".\[17\]
   - In February 2011 Marco Correia used the same name for a cumulative IFR2 (sum of 2–3 IFR2 values), which is essentially Connors' Cumulative RSI.\[18\]\[19\]
4. **The best B3 evidence is QuantBrasil's 2021 Python series.**
   - Data: Yahoo, January 2015 to December 2020.\[5\]
   - On LREN3: 160 trades, 74% win rate, +138.5% total, 10.4% maximum drawdown at IFR2 ≤ 30.\[20\]\[21\]
   - Across 81 Ibovespa stocks with a 7-day time stop: win rates of 61–86%. PCAR3 earned 1.47% per trade, while IRBR3 lost 0.48% per trade.\[5\]
   - Costs are not modeled.
5. **The only academic test I found shows no clear edge after risk.**
   - It is a UNIPAMPA undergraduate thesis (TCC, 2022): 33 Ibovespa stocks, 2012–2021, no costs, entry at IFR2 < 20.\[8\]\[22\]
   - It found a CAGR of 12.59% vs 12.72% for buy-and-hold, an average win rate of 54.41% and an average maximum drawdown of 46.38%.\[22\]
   - Its exit rule was not the canonical one (a 5-candle time exit or an ATR stop).\[22\]
6. **The edge varies sharply by sector.**
   - Utilities and defensive names had the lowest drawdowns in QuantBrasil's ranking: EGIE3 6.82%, ENGI11 6.86%, TAEE11 7.09%, EQTL3 9.34%.\[5\]
   - Cyclical and distressed names lost money: GOLL4, BRFS3, COGN3, CSNA3, USIM5, IRBR3, CIEL3.\[5\]
   - Stormer himself says it works better on some assets. He cites CPLE6 at "93% de lucro, com nível de acerto de 72%, em dois anos" and notes Petrobras options.\[3\] These are his anecdotes, not audited results.
7. **Edge decay on B3 is untested.** I found no B3 study covering 2021–2026. Empirica Lab's research note (Substack, 11 Oct 2026) tested Connors' rule on SPY from Jan 1993 to Sep 2026 at 2 bps per side, splitting the sample on 1 Jan 2009. Before the split: 116 trades, 81% winners, 0.79% per trade, Sharpe 0.97 vs 0.42 for buy-and-hold. After: 149 trades, 74% winners, 0.51% per trade, Sharpe 0.68 vs 0.87 for buy-and-hold. The author cautions that the split "shows that the effect shrank after publication, not that publication caused it". That suggests, but does not prove, decay in Brazil too.

## Details

### 1. Origin and timeline (verified vs. unverified)

| Date | Event | Status |
|---|---|---|
| 1978 | J. Welles Wilder publishes the RSI/IFR in *New Concepts in Technical Trading Systems*\[10\]\[23\] | Verified, widely cited |
| Nov 2008 | Connors and Alvarez publish *Short Term Trading Strategies That Work* (TradingMarkets). Rules: above MM200, RSI(2) < 5–10, exit on a close above MM5; also Cumulative RSI\[2\]\[24\] | Verified (multiple independent sources) |
| 14 Jan 2010 | Blog "Análise Técnica" (alsant0z): "Executei a estratégia padrão definida pelo Stormer (www.leandrostormer.com.br)…" plus a post titled "Setup do IFR2 Modificado no diário"\[17\] | Verified, the earliest dated Brazilian mention I found |
| 2010 | "Tática IFR2 (Seminários Leandro & Stormer – Linha Premium)", a 1-hour video plus a PDF study guide\[25\] | Catalogued as 2010 on a resale site; content known only from secondhand copies |
| 26 Sep 2010 | Carlos Sampaio blog: "Estratégia Operacional (Setup IFR2)", described as a volatility setup, not trend-following, with a "segunda forma de entrada… filtro de segurança"\[26\] | Verified via a compiled document |
| 24 Feb 2011 | Marco Correia: "SETUP IFR2 Modificado" = IFR2C(x), a sum of x IFR2 values (buy when IFR2C2 < 20 or 15, sell when IFR2C2 > 190), also used on mini-índice and mini-dólar\[18\]\[19\] | Verified |
| Jun 2012 | Up Traders blog summarizes the DVD "Tática IFR2": IFR2 < 5, stop at 130%, MME49, partial exits\[11\] | Verified (secondary) |
| 2017 (upload) | "Táticas operacionais de position – Metodologia Stormer" PDF: IFR2 < 5, buy at the close, weekly variant buying at Friday's close, "Tática do IFR2 com filtro"\[27\] | Unofficial copy; authorship plausible but unverified |
| 2020 | SmarttBot IFR2 e-book (robot: IFR2 below 25, exits by highest high of x candles, time, ATR, or IFR2 > 70/75) quoting Stormer: "Um modelo de volatilidade com trades de curto prazo, durando em média de 2 a 3 candles. Alto nível de acerto, com um payoff um pouco mais baixo"\[28\]\[29\] | Verified (vendor material) |
| Jan–Mar 2021 | QuantBrasil's Python backtest series (Andressa Quintanilha)\[5\]\[30\] | Verified |
| 29 Feb 2024 | InfoMoney/XP "Sociedade do Gain": Stormer presents "sua adaptação do IFR2", described as having 80% accuracy "quando executado com perfeição"\[3\] | Verified, but sponsored content |
| Mar 2026 (2025 edition) | InfoMoney (28 Mar 2026) reports Stormer "foi eleito o Top Traders InfoMoney 2025, conquistando o primeiro lugar", by peer vote of more than 150 traders; IFR2 is "um dos setups mais conhecidos associados ao seu nome" | Verified |

**Verdict.** Stormer is the popularizer and the author of the Brazilian rule sets, not the inventor of RSI(2). He may have reached the idea independently, but that cannot be verified. Even the outlet that presented him (InfoMoney/XP) credits Connors with the original.\[3\]

### 2. Brazilian strategy variants (exact rules)

| # | Setup (Brazilian name) | Entry | Filter | Exit | Stop | Source |
|---|---|---|---|---|---|---|
| A | **IFR2 "padrão Stormer"** (the most common) | Daily close with IFR2 ≤ 25 (some use 20 or 30); buy at the close (around 10 minutes before the closing auction) or at the next open\[4\]\[31\] | None ("completely disregards the current trend")\[31\] | Highest high of the 2 previous candles; the target moves each day\[16\] | None, or a time stop of 7 bars\[4\] | Pivô Trade; TradingView (EduardoMattje); QuantBrasil "IFR2 de Compra" (default IFR 20, window 2, stop 7 candles); João Malossi/Medium (81 assets, IFR2 < 25, next open, no stop)\[4\]\[13\]\[15\]\[16\] |
| B | **Tática IFR2 (2010)** | IFR2 < 5; buy the close of the signal candle\[11\] | "Maior segurança" if price is above MME49\[11\] | Sell half at +2% (daily) or +4% (weekly); hold while MME5 points up; when MME5 turns down, move the stop to that candle's low\[11\] | 130% of the signal candle's range projected downward\[11\] | Up Traders (2012); Stormer PDF |
| C | **IFR2 com filtro** | Same as B but with a "safety" confirmation added for traders uncomfortable buying into a fall\[27\] | — | As B | As B | Carlos Sampaio (2010); Stormer PDF |
| D | **IFR2 Connors-style** | IFR2 < 10 (or < 30)\[9\]\[10\] | Close above MM200 | Close above MM5\[9\]\[10\] | None | No Alvo; FL Journal/TC |
| E | **IFR2 short side (Connors)** | IFR2 > 90 | Close below MM200 | Close below MM5\[9\] | — | FL Journal/TC. Stormer himself rejects the short side: "o movimento de queda vem com muita velocidade, e a metodologia perde a precisão"\[3\] |
| F | **IFR2 exit by indicator** | IFR2 ≤ 30 | Optional MM50 rising | IFR2 ≥ 70 (or 80) at the close | Time stop of 7 days\[20\]\[30\] | QuantBrasil exit-parameter series\[20\] |
| G | **IFR2 Modificado (EMA-optimized, 2010)** | IFR2 < 5 | Close above MME99 (or 88) | MME28 turns down, or MME28 crosses below MME99\[17\] | — | alsant0z (Wealth-Lab optimizer) |
| H | **IFR2C / Cumulative IFR2 ("modificado", 2011)** | IFR2C2 < 20 (or 15)\[18\] | Divergence check on MACD(12,26,9) and IFR5 in the same or the next-lower timeframe | IFR2C2 > 190 (short)\[19\] | — | Marco Correia |
| I | **IFR2 day trade (Stormer)** | IFR2 below a chosen level at the candle close (20 by default); market buy at the next open\[32\] | — | Highest high of the 2 previous candles, or a time exit after N candles\[32\] | 127% extension of the signal candle\[32\] | MQL5 freelance spec summarizing an Arena Trader XP video, so secondhand |
| J | **IFR2 WIN 15-min** | IFR2 < 5 buy / > 95 sell at the candle close | — | Target unspecified; stop moved to break-even at 2/3 of the target\[33\] | — | "Setup Daytrade XP para Mini Índice" (Scribd); unverified |
| K | **IFR2 WIN 5-min + MME20** | IFR2 < 5 on 5 minutes | MME20 trend on 5 minutes\[34\] | — | — | Trader Brasil blog |
| L | **Pyramiding / "múltiplas entradas"** | Add to the position each time IFR2 prints below the previous entry level\[28\] | — | As A | — | SmarttBot robot ("aumento de posição"); Stormer video title "IFR2: na prática com múltiplas entradas" (2021)\[28\]\[35\] |

**What I could not find documented in a Brazilian source:**
- No sourced, rule-exact "IFR2 + Bollinger" or "IFR2 + IBS" setup. A "Códigos para Profit Chart" compilation includes a separate Bollinger-band setup alongside IFR2, but not a combined one.\[36\]
- No sourced options version. Stormer mentions Petrobras options only anecdotally.
- No sourced WDO version, apart from Correia's note that he adjusts IFR2C thresholds for mini-dólar.\[19\]

Treat these gaps as "no reliable Brazilian specification found".

### 3. Algorithms

**IFR formula.** IFR = 100 − 100/(1 + FR), where FR = average gain / average loss over n periods (n = 2 here).\[37\]\[38\]

**Platform differences** (these matter a lot at n = 2):
- **Wilder smoothing, called "clássico":** the first average is a simple average. After that, AvgGain_t = (AvgGain_{t−1}·(n−1) + Gain_t)/n, and the same for losses. Toro's and Nelogica's articles describe this as Wilder's method.\[37\]\[38\]
- **Profit (Nelogica):** offers two calculation modes, "IFR Simples" (plain averages of gains and losses over the window) and "IFR Clássico" (smoothed averages).\[23\] With n = 2, the simple version becomes very jumpy and hits 0 or 100 whenever the last two closes move in the same direction. Your thresholds therefore will not transfer between modes. Nelogica itself notes values "podem variar levemente entre plataformas".\[37\]
- **QuantBrasil's Python code** implements Wilder (seeded with a simple average),\[30\] so it should broadly match TradingView's `ta.rsi`, which uses Wilder's RMA. I did not test this.
- **Practical rule:** fix one platform and one mode, and recalibrate the threshold if you switch.

**Reference pseudocode (setup A + time stop):**
```
for each daily bar t:
  ifr = RSI_Wilder(close, 2)[t]
  if flat and ifr <= L (e.g. 25):          buy at close[t] (or open[t+1])
  if long:
     target = max(high[t-1], high[t-2])    # moving target
     if high[t] > target: sell at max(open[t], target)   # gap-up fills at the open
     elif bars_in_trade == N (e.g. 7):     sell at close[t]
```
This mirrors QuantBrasil's `strategy_points` function, which sells at the open if the open is above the target and otherwise at the target,\[5\] and its `algorithm_with_stop` function. QuantBrasil also rounds share quantity down to multiples of 100, the lote padrão.\[5\]\[39\]

**Ready-made code found in Brazilian sources:**
- **Python:** QuantBrasil blog series (`rsi()`, `strategy_points()`, `algorithm_with_stop()`, `get_drawdown()`),\[5\] plus a CLI: `quantbrasil backtests run ifr2 PETR4 --timeframe D1 --param rsi=30`.\[40\]
- **Pine Script:**
  - "IFR2" by EduardoMattje (open strategy; enter below 25, exit at the max of 2 previous highs). The UNIPAMPA thesis used his script.\[13\]\[22\]
  - "IFR 2 Stormer RSI 2" by Patolino1 (protected; oversold 10, exit at the max of the last 2, SMA200 filter).\[41\]
- **NTSL/Profit:** "Códigos para Análise de Estratégias no Profit Chart – Versão 3" (Studocu). It contains an IFR2 Connors-style code (IFR2 < 25) and an IFR2 < 5 code, and its IFR4 example uses `RSI(4,0)` with a date-based 7-day stop.\[36\]
- **MQL5:** only freelance specifications for a "Stormer IFR2" EA (exit at the max of 2 candles, time exit, 127% stop); I found no public code.\[32\]
- **Wealth-Lab:** used by Malossi and alsant0z (code shared privately).\[15\]\[17\]

**Illustrative Pine v5** (my own condensation of setup A; check before use):
```pinescript
//@version=5
strategy("IFR2 B3 - padrão", overlay=true, process_orders_on_close=true,
     commission_type=strategy.commission.percent, commission_value=0.03)
lvl   = input.int(25, "IFR2 máx")
tstop = input.int(7,  "Stop no tempo (candles)")
useMM = input.bool(false, "Filtro MM200")
r     = ta.rsi(close, 2)
okMM  = not useMM or close > ta.sma(close, 200)
if strategy.position_size == 0 and r <= lvl and okMM
    strategy.entry("L", strategy.long)
if strategy.position_size > 0
    strategy.exit("alvo", "L", limit=math.max(high, high[1]))  // máx. dos 2 candles anteriores ao próximo
    if bar_index - strategy.opentrades.entry_bar_index(0) >= tstop
        strategy.close("L")
```

**Illustrative NTSL** (unverified syntax; check `RSI(2,0)`'s calculation-type argument and the fill timing in Profit's editor):
```
input Nivel(25); MaxBarras(7);
var nBar : Integer;
begin
  if not HasPosition then
  begin
    if RSI(2,0) <= Nivel then begin BuyAtMarket; nBar := CurrentBar; end;
  end
  else
  begin
    SellToCoverLimit(Max(High, High[1]));
    if (CurrentBar - nBar) >= MaxBarras then ClosePosition;
  end;
end;
```

### 4. Backtest evidence on B3

| Study | Universe / period | Rules | Results | Costs/tax | Main biases |
|---|---|---|---|---|---|
| QuantBrasil, entry parameters (2021) | LREN3, 2015–2020 | IFR2 ≤ 30/20/10/5, exit at the max of 2 highs | ≤30: 160 trades, 74%, +138.5%, maximum drawdown 10.4%. ≤20: 128 trades, 78%, +134.8%, drawdown 7.1%. ≤10: 73 trades, 77%, +87.7%, drawdown 5.2%\[21\] | None | One stock in a strong uptrend |
| QuantBrasil, exit parameters (28 Jan 2021) | LREN3, 2015–2020 | IFR2 ≤ 30; exit IFR2 ≥ 50/60/70/80; time stops 3/5/7/9 | Exit at ≥80: 113 trades, 72%, +149.5%, drawdown 10.3%. The 3-day stop was clearly worse; 7 days was best.\[30\] The author warns that LREN3's uptrend favors late exits\[30\] | None | Hand-picked stock; parameter mining |
| QuantBrasil, MM filters | LREN3 | IFR2 ≤ 30 plus rising MM200/80/50 | Unfiltered: 0.86% per trade, drawdown 10.37%. The filter cut profit by about 20% while cutting drawdown only about 6.7%. Best filtered result: MMA50 with exit IFR2 ≥ 70, 1.08% per trade, +98.35%, drawdown 9.49%\[20\]\[42\] | None | — |
| QuantBrasil, dynamic list | 5 strongest Ibovespa stocks over 100 days, 2015–2020 | Setup A | 70 trades, 71%, +51.1%, 0.73% per trade, drawdown 28.6%. With a 7-day stop: 72 trades, 72%, +58.4%, drawdown 26.2%\[5\]\[42\] | None | Momentum selection hurts mean reversion |
| QuantBrasil, all Ibovespa stocks (4 Mar 2021) | 81 Ibovespa stocks (2021 composition), Jan 2015–Dec 2020, R$10,000, lots of 100\[5\] | IFR2 ≤ 30, max of 2 highs, 7-day stop | Best per trade: PCAR3 1.47% (86% win rate), NTCO3 1.43%, LCAM3 1.17%, ENGI11 0.96%, TOTS3, B3SA3, EQTL3, CPLE6 0.91%. Lowest drawdown: EGIE3 6.82%, ENGI11 6.86%, TAEE11 7.09%. Losers: IRBR3 −44%, GOLL4 −55% (drawdown 135.6%), BRFS3 −46.5%, COGN3 −35.3%. Win rates 61–86% for every stock, including losers\[5\] | None | **Survivorship/look-ahead:** today's index members applied back to 2015; rankings are in-sample |
| No Alvo (community article) | BOVA11, ITUB4, LCAM3, PSSA3, VALE3, MGLU3; 2013–2018; ProfitPlus data; R$50,000 all-in, compounded\[10\] | IFR2 < 30 or < 10, MM200 filter, exit close > MM5 or max of 2 highs, no stop\[10\] | Exit by MM5 at IFR2 < 30: MGLU3 +414%, LCAM3 +384%, PSSA3 +150%, ITUB4 +131%, VALE3 +60%, BOVA11 +42%, against IBOV at about +70%. MM5 beat the max-of-2 exit; < 10 raised the win rate but lowered profit\[10\] | None | 6 hand-picked stocks; MGLU3's 2016–18 mega-rally |
| UNIPAMPA TCC (César E. T. Soares, 2022) | 33 Ibovespa stocks, 2012–2021, R$10,000 each\[22\] | IFR2 < 20, next-open entry, 5-candle exit or ATR stop, no trend filter (Pine/EduardoMattje)\[22\] | Average: +227.27%, CAGR 12.59%, win rate 54.41%, profit factor about 1.34, Sharpe about 0.135, maximum drawdown 46.38%. Buy-and-hold: 231.10% / 12.72%. CDI: 122.81% / 8.34%. BOVA11: 78.38% / 5.96%\[22\] | None, and buy-and-hold excludes dividends (which flatters IFR2 relative to buy-and-hold)\[22\] | Current index members; non-canonical exit |
| alsant0z blog (2010) | His own stock list, Wealth-Lab | Stormer standard vs optimized EMA version | Standard: 62.39% win rate, +6.35% average win, 2.37% average per trade. Optimized (MME28/99): 67.52%, 6.03% average per trade\[17\] | None | Brute-force optimization of fast MA 1–30 × slow MA 1–100, so heavily overfit\[17\] |
| Stormer (sponsored event, 2024) | CPLE6 | His version | "93% de lucro… acerto de 72%, em dois anos"\[3\] | Unknown | Anecdote, not reproducible |
| Genial (TradingView idea) | WIN 15-min, Aug 2021–Nov 2025 | "RSI" overbought/oversold, period unspecified | 337 trades, 62.02% win rate, R$5,376 accumulated\[43\] | Unknown | Not clearly IFR2; vendor marketing |

**How to interpret this evidence:**
- **High win rate, thin edge.** Average gains are only about 0.3–1.0% per trade before costs. Win rates of 61–86% hold even for stocks that lost money overall, so win rate on its own tells you almost nothing.\[5\]
- **Costs matter at this size.** A round trip at 0.06% in B3 fees, plus slippage, takes roughly 6–20% of the typical edge.
- **Regime dependence:**
  - The setup does best in stocks with steady uptrends or low volatility, such as utilities and dividend payers, which QuantBrasil itself concludes.\[5\]
  - It collapses in structural decliners (airlines, steel, IRB, Cielo, Cogna), because with no stop loss you "buy the dip" all the way down.
  - QuantBrasil's GOLL4 drawdown above 100% shows how one bad stock can wipe out a non-stop version.\[5\]
- **Edge decay:** none of the B3 studies covers 2021–2026. Empirica Lab's SPY replication (Jan 1993–Sep 2026, 2 bps per side; Sharpe 0.97 before 2009 vs 0.68 after, when buy-and-hold had 0.87) is the best available proxy and points toward a weaker edge, not a stronger one.

### 5. Brazil-specific implementation

- **B3 fees for stocks and ETFs:**
  - Swing trade: 0.0050% negociação + 0.0250% liquidação = 0.030% per side.\[44\]\[45\]
  - Day trade (up to R$1M per day): 0.023% per side.\[44\]\[46\]
  - Trades in the opening or closing auctions (not day trade) pay a 0.0070% negociação fee,\[46\] which matters because IFR2 entries usually happen near or in the closing call.
  - Many brokers charge zero corretagem; Inter, for example, cites about 0.031% in B3 costs only.\[47\]
- **Tax:**
  - Swing trade: 15% on net gains, exempt when total monthly stock sales are R$20,000 or less. The exemption is lost entirely if sales exceed the limit.\[48\]\[49\]
  - Day trade: 20% with no exemption.\[50\]
  - IRRF (the "dedo-duro" withholding): 0.005% of sales for swing trade, 1% of the gain for day trade. DARF code 6015.\[48\]\[51\]
  - Losses offset gains only within the same category.\[49\]
  - **ETFs such as BOVA11 do not get the R$20,000 exemption**,\[49\] so IFR2 on BOVA11 is fully taxed.
  - On 8 Oct 2025 the Câmara dos Deputados voted 251–193 to pull MP 1.303/2025 from the agenda, so it lapsed (Agência Câmara). The 15% (ações) and 20% (day trade) rates therefore remain in force for 2026, instead of the single 18% rate the MP would have introduced.
  - With dozens of short trades a year, the exemption mostly helps small accounts.
- **Lots:**
  - The lote padrão is 100 shares; the fracionário market trades 1–99 shares under the ticker with an "F" suffix (e.g. PETR4F).\[52\]\[53\]
  - The fracionário has less liquidity and wider spreads, especially in small caps.\[54\]\[55\]
  - IFR2 trades are short and frequent, so use the lote padrão whenever capital allows. QuantBrasil's simulator assumes multiples of 100.\[5\]\[16\]
- **Liquidity and slippage:** published tests assume fills at the exact close or target. On mid-caps, buying "at the close" really means the closing auction, and the target fill (max of 2 highs) may be partial. Restrict the universe to IBOV/IBrX-100 names with high average daily traded value. The specific liquidity cutoff is my recommendation; no Brazilian study I found tested one.
- **Data:**
  - Unadjusted prices turn dividends, splits and reverse splits into false price moves, which Nelogica's backtest guide warns about.\[56\]
  - For IFR2 this is critical: an ex-dividend gap pushes IFR2 toward zero, producing false "oversold" buys exactly in the high-yield utilities that rank best.
  - Sources: Yahoo/yfinance (used by QuantBrasil; `Close` is split-adjusted, `Adj Close` is also dividend-adjusted); ProfitPlus/Profit (used by No Alvo); bolsai API (raw and adjusted OHLC built from the official COTAHIST files plus corporate actions); open-source pipelines built on B3 COTAHIST plus B3's corporate-actions API.\[57\]\[58\]
  - Signals should be computed on adjusted series, while execution prices and lot sizes should be based on actual prices.

### 6. Ranked comparison: best versions for B3

| Rank | Version | Why | Main caveat |
|---|---|---|---|
| 1 | **Setup A + 7-candle time stop** (IFR2 ≤ 20–30, buy at the close, exit at the max of 2 highs) on a **pre-selected, fixed list of low-volatility liquid stocks** (utilities, defensives) | Most reproducible B3 evidence (QuantBrasil, 81 stocks); low drawdowns in utilities; fast trades (2–3 candles on average per Stormer's description)\[5\]\[28\] | The stock selection itself is in-sample; no data after 2021; no costs |
| 2 | **Connors-style D** (MM200 filter, IFR2 < 10–30, exit close > MM5) | The trend filter is the most logical protection against structural decliners; No Alvo found the MM5 exit more profitable than the max-of-2 exit\[10\] | Fewer trades; QuantBrasil found MA filters can lower total profit\[20\] |
| 3 | **Exit by indicator F** (IFR2 ≥ 70/80 + 7-day stop) | Lets winners run in uptrending stocks | The LREN3 result depends on the regime\[30\] |
| 4 | **Tática IFR2 2010 (B/C)** (IFR2 < 5, 130% stop, partial exits) | The only version with a real stop loss, which limits damage in GOLL4-type collapses | Few signals; no systematic B3 backtest found |
| 5 | **Cumulative IFR2C (H)** | Smoother signal; Connors' Cumulative RSI concept | Only blog evidence |
| 6 | **Optimized EMA "IFR2 modificado" (G)** | — | Brute-force optimization, the classic overfitting case |
| — | **Intraday (I, J, K) on WIN/WDO or stocks** | Exists and Stormer has a day-trade version with a 127% stop | No reproducible tests; sources (Invest Academy, a TradingView script author) say IFR2 is meant for the daily chart and that intraday gains are too small to cover costs;\[6\]\[13\] day-trade tax is 20%\[6\] |

## Recommendations

1. **Start with Rank 1 and test it out of sample:**
   - Calibrate the IFR2 threshold and the stock list on 2012–2020.
   - Then freeze them and test on 2021–2026 without changes.
   - QuantBrasil's simulator and CLI accept recent date ranges;\[40\] otherwise use the Python or Pine code above.
2. **Model reality:**
   - 0.0300% per side in B3 fees plus at least one tick of slippage.
   - Closing-auction fills.
   - Lots of 100.
   - 15% tax, and no exemption at all for ETFs.
   - Adjusted data for signals.
3. **Add a disaster brake.** Use either the MM200 filter or the 2010 stop at 130% of the signal candle. The no-stop version wins most of the time until it meets a stock like GOLL4 or IRBR3.
4. **Diversify across 5–10 uncorrelated qualifying stocks** rather than one stock. Signals are rare per stock (about 25–30 a year at ≤ 30) and results vary widely between stocks.
5. **Use a portfolio-level benchmark.** Compare against CDI and BOVA11 buy-and-hold with dividends, not just against "win rate". The UNIPAMPA test shows that IFR2 can match buy-and-hold while carrying a 46% average drawdown.\[22\]
6. **Treat intraday IFR2 on WIN/WDO as a research project,** not a ready-made strategy.

## Caveats

- **Marketing vs. evidence:**
  - "80% de acertos" comes from a sponsored XP/InfoMoney article and is qualified with "quando executado com perfeição".\[3\]
  - The CPLE6 "+93%" figure is Stormer's own anecdote.
  - SmarttBot, Pivô Trade and Genial are vendors.
  - None of these is an audited track record.
- **Secondhand material:**
  - Stormer's exact current parameters (threshold, entry at the close vs. the next open, time stop) are known mainly through third parties: an MQL5 spec of an Arena Trader XP video, Pivô Trade, forum posts.
  - The 2010 rules come from blog summaries and unofficial PDF copies.
  - The GainCast quotes come from an automatic transcript.
- **All B3 backtests here exclude costs and tax.** Most also use current index members applied to past data (survivorship bias), and several hand-pick stocks or optimize parameters on the same data they report.
- **Platform calculations differ.** Profit's "IFR Simples" vs "Clássico" modes\[23\] and data adjustment can change which days generate signals at n = 2. Thresholds do not transfer between setups.
- **The code above is illustrative** and has not been executed; check it on your platform before relying on it.

## Sources

1. [Connors' RSI(2) had a Sharpe of 0.97 before the book. Since then: 0.68.](https://empiricalab.substack.com/p/connors-rsi2-spy)
2. [Testing The RSI 2 Trading Strategy On US Stocks](https://stocksoftresearch.com/rsi-2-trading-strategy/)
3. [Evento da XP ensina como o trader pode alcançar a excelência e mostra setup com 80% de acertos](https://www.infomoney.com.br/patrocinados/xp-investimentos/evento-da-xp-ensina-como-o-trader-pode-alcancar-a-excelencia-e-mostra-setup-com-80-de-acertos/)
4. [IFR2](https://www.pivotrade.com.br/ifr2)
5. [Comparando os Resultados da Estratégia de IFR2 nos Ativos do Ibovespa | QuantBrasil](https://quantbrasil.com.br/blog/comparando-os-resultados-da-estrategia-de-ifr2-nos-ativos-do-ibovespa/)
6. [IFR2: como usar a estratégia de volatilidade no swing trade](https://portal.invest.academy/ifr2-como-usar-a-estrategia-de-volatilidade-no-swing-trade/)
7. [Backtest da estratégia de análise técnica de IFR2 sem filtro](https://repositorio.unipampa.edu.br/items/5ad58c5a-39dc-4497-9dc5-e0307b127531)
8. [Backtest da estratégia de análise técnica de IFR2 sem filtro](https://dspace.unipampa.edu.br/handle/riu/7598)
9. [Setups de volatilidade utilizando IFR (2) e IFR (4) - FL Journal](https://flj.com.br/renda-variavel/setup-trader-ifr2-ifr4/)
10. [Backtests com setup IFR2](https://noalvo.com/artigo/backtests-com-setup-ifr2)
11. [Up Traders: Setup: IFR2](http://uptraders.blogspot.com/2012/06/setup-ifr2.html)
12. [Alexandre Wolwacz: conheça tudo sobre o Stormer](https://blog.nelogica.com.br/alexandre-wolwacz-stormer-o-crocodilo-do-mercado-financeiro/)
13. [IFR2 — Estratégia de EduardoMattje — TradingView](https://br.tradingview.com/script/UD0anrUb/)
14. [Como o Stormer criou o IFR 2 | Setup de trade com até 80% de acerto | GainCast Transcripts](https://ytscribe.com/v/LXUkvygAop4)
15. [Mapeamento de resultados de ativos utilizando o IFR2 - João Malossi - Medium](https://medium.com/joaomalossi/mapeamento-de-resultados-de-ativos-utilizando-o-ifr2-3f27ea1fb75d)
16. [IFR2 de Compra](https://quantbrasil.com.br/estrategias/ifr2-de-compra/)
17. [Setup do IFR2 Modificado no diário](http://alsant0z.blogspot.com/2010/01/setup-do-ifr2-modificado-no-diario.html)
18. [Marco Correia: SETUP IFR2C(x) - Larry Connors "Modificado"](http://marcobragacorreia.blogspot.com/p/setup-ifr2cx-larry-connors-modificado.html)
19. [Marco Correia: SETUP IFR2 Modificado (Pedido Vinícius)](http://marcobragacorreia.blogspot.com/2011/02/setup-ifr2-modificado-pedido-vinicius.html)
20. [Backtest da Estratégia de IFR2 Utilizando Médias Móveis Como Filtro](https://quantbrasil.com.br/blog/backtest-da-estrategia-de-ifr2-utilizando-medias-moveis-como-filtro/)
21. [Analisando Diferentes Parâmetros de Entrada para a Estratégia de IFR2](https://quantbrasil.com.br/blog/analisando-diferentes-parametros-de-entrada-para-a-estrategia-de-ifr2/)
22. <https://dspace.unipampa.edu.br/bitstream/riu/7598/1/1801571038_Cesar_Emmanuell_Teixeira_Soares_.pdf>
23. [IFR (Índice de Força Relativa)](https://ajuda.nelogica.com.br/hc/pt-br/articles/360040975932-IFR-%C3%8Dndice-de-For%C3%A7a-Relativa)
24. [RSI-2 Strategy by Larry Connors: Complete Trading System Guide](https://swingfolio.com/education/level-6-advanced-strategies/rsi-2-strategy)
25. [Tática IFR2 (Seminários Leandro & Stormer - Linha Premium)](https://catalogotrader.shop/tatica-ifr2-seminarios-leandro-stormer-linha-premium-stormer/)
26. [Setups Stormer \[pd49dzd921n9\]](https://idoc.pub/documents/setups-stormer-pd49dzd921n9)
27. [\[PDF\] Táticas operacionais de position Metodologia Stormer - Free Download PDF](https://silo.tips/download/taticas-operacionais-de-position-metodologia-stormer)
28. [Indicador IFR](https://smarttbot.com/wp-content/uploads/2020/07/Ebook-IFR2.pdf)
29. [Smarttbot](https://smarttbot.com/assets/data/Ebook-IFR2)
30. [Analisando Diferentes Parâmetros de Saída para a Estratégia de IFR2 | QuantBrasil](https://quantbrasil.com.br/blog/analisando-diferentes-parametros-de-saida-para-a-estrategia-de-ifr2/)
31. [OPEN-SOURCE SCRIPT](https://br.tradingview.com/script/UD0anrUb)
32. [Preciso de um EA baseado na estratégia IFR2 do Stormer - an order to develop the trading robot at MQL5.community Freelance service - Budget: 30 - 50 USD - MQL5 - Experts](https://www.mql5.com/en/job/224109)
33. [Setup IFR2 para Day Trade Mini Índice](https://www.scribd.com/document/216212130/Setup-Daytrade-XP-Para-MINI-INDICE)
34. [Setup de Day Trade no Mini Índice: 3 Estratégias](https://www.traderbrasil.com/blog/setup-day-trade-mini-indice.php)
35. [IFR2: NA PRÁTICA COM MULTIPLAS ENTRADAS! - YouTube](https://www.youtube.com/watch?v=N0CPEpf8ESQ)
36. [Códigos para Análise de Estratégias no Profit Chart - Versão 3 - Studocu](https://www.studocu.com/pt-br/document/anhanguera-educational/resistencia-dos-materias/codigos-profit-chart/15332968)
37. [IFR: o que é e como calcular o Índice de Força Relativa](https://blog.nelogica.com.br/ifr/)
38. [Índice de Força Relativa (IFR): o que é e como utilizar no Day Trade?](https://blog.toroinvestimentos.com.br/trading/ifr/?hs_amp=true)
39. [Criando o Backtest da Estratégia de IFR2 em Python](https://quantbrasil.com.br/blog/criando-o-backtest-da-estrategia-de-ifr2-em-python/)
40. [quantbrasil backtests run](https://quantbrasil.com.br/docs/cli/comandos/backtests/run/)
41. [IFR 2 Stormer RSI 2 — Strategy by Patolino1 — TradingView](https://www.tradingview.com/script/Y7Kt90xU/)
42. [Backtest da Estratégia de IFR2 em uma Lista de Ativos Dinâmica](https://quantbrasil.com.br/blog/backtest-da-estrategia-de-ifr2-em-uma-lista-de-ativos-dinamica/)
43. [Testando Utilização de IFR no contrato futuro de Mini Índice para BMFBOVESPA:WIN1! de Genial\_Investimentos — TradingView](https://br.tradingview.com/chart/WIN1!/d852amhn/)
44. [Emolumentos: o que é e como calcular](https://blog.nelogica.com.br/emolumentos/)
45. [Taxa de liquidação B3: o que é, quanto custa e como funciona](https://www.c6bank.com.br/blog/taxa-de-liquidacao-b3)
46. [Emolumentos - BOVESPA](https://ajuda.modalmais.com.br/hc/pt-br/articles/360058823813-Emolumentos-BOVESPA)
47. [Quais as taxas para investir em ações? - Ajuda Inter](https://ajuda.inter.co/investimentos/quais-as-taxas-para-investir-em-acoes)
48. [Diferenças do Imposto de Renda para day trade e swing trade](https://blog.nelogica.com.br/imposto-de-renda-para-day-trade-e-swing-trade-quais-as-diferencas/)
49. [Swing trade: o que é e como é tributado - Arena do Dinheiro](https://arenadodinheiro.com.br/noticias/swing-trade-o-que-e-e-como-e-tributado/)
50. [Imposto de renda em day trade e swing trade: alíquotas, DARF 6015 e como declarar sem erro](https://investilize.com.br/blog/ir-day-trade-swing-trade/)
51. [Venda Descoberta 2026: Short Selling na B3, Aluguel 0,03-5% a.a. e IR 15-20% - Renova Invest](https://renovainvest.com.br/blog/venda-descoberta-entenda-o-que-e-como-funciona-e-seus-riscos/)
52. [Como comprar frações de ações e investir com pouco dinheiro](https://www.serasa.com.br/blog/como-comprar-fracoes-de-acoes/)
53. [Qual a diferença entre comprar ações fracionárias e em lote?](https://investnews.com.br/colunistas/qual-a-diferenca-entre-comprar-acoes-fracionarias-e-em-lote/)
54. [Vale a pena investir no mercado fracionário? - Master Clear](https://master.clear.com.br/mercado-fracionario/)
55. [Lote Padrão e Mercado Fracionário: como funciona](https://traders.com.br/blog/posts/lote-padrao-mercado-fracionario)
56. [Dados históricos da B3 para backtesting: passo a passo](https://blog.nelogica.com.br/dados-historicos-b3-backtesting/)
57. [Backtest de Carteira em Python: Dados Históricos Ajustados (2026) — bolsai](https://usebolsai.com/blog/backtest-carteira-python-dados-historicos-ajustados-2026)
58. [GitHub - tneves95/b3-pipeline-data-and-backtest-framework · GitHub](https://github.com/tneves95/b3-pipeline-data-and-backtest-framework)
