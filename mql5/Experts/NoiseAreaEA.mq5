//+------------------------------------------------------------------+
//| NoiseAreaEA.mq5                                                  |
//| Noise Area intraday momentum as an Expert Advisor: it works out  |
//| the position the rule wants at each bar's close and trades it    |
//| with market orders (they fill at the next bar's open).           |
//| Educational only, not investment advice. docs/mql5-noise-area.md |
//|                                                                  |
//| The inputs are the parameters themselves, so the Strategy Tester |
//| can optimize them. Their defaults are the WIN OPTIMIZED trial:   |
//| the best trial by WIN of the 50,000-trial search (development    |
//| data only): 20 days, k 1.5, every 60 min from 12:00, exit 18:20, |
//| stop = back inside the band, acted on at every bar.              |
//| The PAPER (original) rule is, instead:                           |
//|   Lookback 14, Mult 1.0, Cadence 30, FirstDecision 900,          |
//|   ExitTime 2400, StopKind NA_STOP_VWAP_BAND, EveryBar false.     |
//| The days of history needed before a band shows is Lookback - 1.  |
//+------------------------------------------------------------------+
#property copyright "B3 Backtester (educational)"
#property version   "1.00"
#property description "Noise Area intraday momentum (Zarattini, Aziz, Barbon). Educational only."

#include <Trade/Trade.mqh>
#include <NoiseArea/NoiseCore.mqh>

input int          Lookback      = 20;               // days of history (2..90)
input double       Mult          = 1.5;              // band multiplier k
input int          Cadence       = 60;               // a decision every N minutes (a multiple of the chart period)
input int          FirstDecision = 1200;             // HHMM: first decision at or after this time
input int          ExitTime      = 1820;             // HHMM: flat from this time on (2400 = hold to the close)
input ENUM_NA_STOP StopKind      = NA_STOP_BAND;     // stop
input bool         EveryBar      = true;             // act on the stop at every bar, not only on the checkpoints
input int          SessionStart  = 900;              // HHMM (server time): the market day starts here
input int          SessionEnd    = 1825;             // HHMM: the day's LAST bar closes here (WIN 1825, 1755 in some seasons; stocks 1800)
input bool         AutoSessionEnd = false;           // read the day's session end from the symbol's schedule (else SessionEnd)
input bool         UseRealVolume = true;             // VWAP weights: real volume (false: tick volume)
input double       Lots          = 1.0;              // contracts per trade, fixed
input long         MagicNumber   = 20261117;         // magic number of the orders
input int          DeviationPts  = 50;               // allowed slippage, in points
input bool         SendOrders    = true;             // false: only compute (and log)
input bool         WriteLog      = false;            // write MQL5/Files/noise_area_log.csv, one row per bar

CTrade     trade;
CNoiseCore core;
datetime   g_lastProcessed = 0;
datetime   g_lastBarSeen   = 0;
int        g_log           = INVALID_HANDLE;

//+------------------------------------------------------------------+
void LogBar(const datetime t, const double c)
  {
   if(g_log == INVALID_HANDLE)
      return;
   FileWrite(g_log, TimeToString(t, TIME_DATE | TIME_MINUTES), DoubleToString(c, 2),
             DoubleToString(core.Sigma, 6), DoubleToString(core.Upper, 2), DoubleToString(core.Lower, 2),
             DoubleToString(core.Vwap, 2), (int)core.PosAfter, (int)core.Held, (int)core.Target);
  }

//+------------------------------------------------------------------+
//| The bars [from, to] by open time, oldest first, fed to the core.  |
//+------------------------------------------------------------------+
int Feed(const datetime from, const datetime to, const bool log)
  {
   MqlRates r[];
   ArraySetAsSeries(r, false);
   const int n = CopyRates(_Symbol, _Period, from, to, r);
   for(int i = 0; i < n; i++)
     {
      if(r[i].time <= g_lastProcessed)
         continue;
      core.Process(r[i].time, r[i].open, r[i].high, r[i].low, r[i].close, r[i].tick_volume, r[i].real_volume);
      g_lastProcessed = r[i].time;
      if(log)
         LogBar(r[i].time, r[i].close);
     }
   return n;
  }

//+------------------------------------------------------------------+
//| The time (HHMM) the symbol's last trading session of a weekday    |
//| ends, from the symbol's schedule; -1 if it has none.              |
//+------------------------------------------------------------------+
int SessionEndHhmm(const ENUM_DAY_OF_WEEK dow)
  {
   datetime from, to;
   int best = -1;
   for(uint i = 0; i < 10; i++)
     {
      if(!SymbolInfoSessionTrade(_Symbol, dow, i, from, to))
         break;
      const int minutes = (int)(to / 60);
      if(minutes > best)
         best = minutes;
     }
   if(best <= 0)
      return -1;
   return (best / 60) * 100 + best % 60;
  }

//+------------------------------------------------------------------+
//| Make the position equal to the wanted one: -1, 0 or +1 (times     |
//| Lots). A reversal is a close and an order the other way.          |
//+------------------------------------------------------------------+
void Act(const double wanted)
  {
   const int want = (int)MathRound(wanted);
   int have = 0;
   if(PositionSelect(_Symbol))
      have = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
   if(want == have)
      return;
   if(have != 0)
     {
      if(!trade.PositionClose(_Symbol))
         PrintFormat("NoiseArea: close failed, %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
   if(want == 1)
     {
      if(!trade.Buy(Lots, _Symbol, 0.0, 0.0, 0.0, "NoiseArea"))
         PrintFormat("NoiseArea: buy failed, %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
   else
      if(want == -1)
        {
         if(!trade.Sell(Lots, _Symbol, 0.0, 0.0, 0.0, "NoiseArea"))
            PrintFormat("NoiseArea: sell failed, %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   const int periodMin = (int)(PeriodSeconds(_Period) / 60);
   if(periodMin < 1 || Cadence % periodMin != 0)
     {
      PrintFormat("NoiseArea: the chart period (%d min) must divide Cadence (%d min)", periodMin, Cadence);
      return INIT_PARAMETERS_INCORRECT;
     }
   core.Lookback = Lookback;
   core.Mult = Mult;
   core.Cadence = Cadence;
   core.FirstDecision = FirstDecision;
   core.ExitTime = ExitTime;
   core.StopKind = StopKind;
   core.EveryBar = EveryBar;
   core.SessionStart = SessionStart;
   core.SessionEnd = SessionEnd;
   core.PeriodMin = periodMin;
   core.UseRealVolume = UseRealVolume;
   core.Reset();

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(DeviationPts);
   trade.SetTypeFillingBySymbol(_Symbol);

   if(WriteLog)
     {
      g_log = FileOpen("noise_area_log.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      if(g_log != INVALID_HANDLE)
         FileWrite(g_log, "time", "close", "sigma", "upper", "lower", "vwap", "pos_after", "held", "target");
     }

   //--- warm up on the closed bars before the current one: the history of the moves needs the lookback
   const int barsPerDay = 650 / periodMin + 1;
   const int warm = (core.Lookback + 12) * barsPerDay;
   MqlRates r[];
   ArraySetAsSeries(r, false);
   const int got = CopyRates(_Symbol, _Period, 1, warm, r);
   for(int i = 0; i < got; i++)
     {
      core.Process(r[i].time, r[i].open, r[i].high, r[i].low, r[i].close, r[i].tick_volume, r[i].real_volume);
      g_lastProcessed = r[i].time;
     }
   g_lastBarSeen = iTime(_Symbol, _Period, 0);
   PrintFormat("NoiseArea: warmed up on %d bars of %s %s", got, _Symbol, EnumToString(_Period));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_log != INVALID_HANDLE)
      FileClose(g_log);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   const datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == 0 || cur == g_lastBarSeen)
      return;
   g_lastBarSeen = cur;

   //--- a new bar has opened: the bars closed since the last one are processed, then the position
   //    wanted for this new bar is set (a market order: it fills at this bar's open)
   const datetime from = g_lastProcessed + 1;
   const datetime to = cur - 1;
   if(from > to)
      return;
   if(AutoSessionEnd)
     {
      MqlDateTime d;
      TimeToStruct(cur, d);
      const int e = SessionEndHhmm((ENUM_DAY_OF_WEEK)d.day_of_week);
      if(e > 0 && e != core.SessionEnd)
        {
         PrintFormat("NoiseArea: session end of the day is %04d (from the symbol's schedule)", e);
         core.SetSessionEnd(e);
        }
     }
   if(Feed(from, to, true) <= 0)
      return;
   //--- nothing carries over a day boundary: a new day starts flat, whatever the last bar of the
   //    day before wanted (an early close that SessionEnd did not know about)
   double wanted = core.Target;
   if((long)(cur / 86400) != (long)(g_lastProcessed / 86400))
      wanted = 0.0;
   if(SendOrders)
      Act(wanted);
  }
//+------------------------------------------------------------------+
