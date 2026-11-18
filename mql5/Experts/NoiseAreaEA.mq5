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
//|                                                                  |
//| ONE FILE: the rule (class CNoiseCore), then the inputs, the chart|
//| drawing (bands, VWAP and arrows where the position changes, as   |
//| chart objects) and the trading, in that order.                   |
//+------------------------------------------------------------------+
#property copyright "B3 Backtester (educational)"
#property version   "1.00"
#property description "Noise Area intraday momentum (Zarattini, Aziz, Barbon). Educational only."

#include <Trade/Trade.mqh>

//+------------------------------------------------------------------+
//| The rule (class CNoiseCore; no trading or drawing in it).         |
//+------------------------------------------------------------------+
#define NA_ROWS 260   // a ring of about a year of days
#define NA_COLS 600   // minutes since the session start (a WIN day is about 565)

enum ENUM_NA_STOP
  {
   NA_STOP_VWAP_BAND = 1,   // back inside the band, or across the VWAP
   NA_STOP_BAND      = 2,   // back inside the band
   NA_STOP_OPPOSITE  = 3,   // hold the last breakout until the opposite band
   NA_STOP_VWAP_ONLY = 4    // across the VWAP
  };

class CNoiseCore
  {
public:
   //--- settings: set them, then call Reset()
   int               Lookback;        // days of history (2..90)
   double            Mult;            // band multiplier k
   int               Cadence;         // a decision every N minutes (a multiple of the chart period)
   int               FirstDecision;   // HHMM: first decision at or after this time
   int               ExitTime;        // HHMM: flat from this time on (2400 = hold to the close)
   int               StopKind;        // ENUM_NA_STOP
   bool              EveryBar;        // act on the stop at every bar, not only on the checkpoints
   int               SessionStart;    // HHMM: the market day starts here (server time)
   int               SessionEnd;      // HHMM: the time the day's LAST bar closes
   int               PeriodMin;       // the chart period in minutes
   bool              UseRealVolume;   // VWAP weights: real volume (true) or tick volume (false)

   //--- results of the last Process()
   bool              NewDay;
   bool              BandOk;
   double            Sigma, Upper, Lower, Vwap;
   double            PosAfter;        // the position decided at this bar's close
   double            Held;            // the position held DURING this bar (decided at the previous close)
   double            Target;          // the position wanted for the NEXT bar
   int               Key;             // minutes since the session start, at this bar's close

private:
   double            m_hist[];
   int               m_dayN;
   long              m_dayId;
   double            m_dayOpen, m_prevClose, m_lastClose, m_cumPV, m_cumV, m_pos;
   bool              m_hasPrev;
   int               m_nDays, m_nMin, m_firstMin, m_exitMin, m_startMin, m_endMin;

   int               Minutes(const int hhmm) { return (hhmm / 100) * 60 + hhmm % 100; }

public:
                     CNoiseCore()
     {
      Lookback = 20; Mult = 1.5; Cadence = 60; FirstDecision = 1200; ExitTime = 1820;
      StopKind = NA_STOP_BAND; EveryBar = true; SessionStart = 900; SessionEnd = 1825;
      PeriodMin = 1; UseRealVolume = true;
     }

   void              Reset()
     {
      m_nDays = Lookback;
      if(m_nDays > 90)
         m_nDays = 90;
      if(m_nDays < 2)
         m_nDays = 2;
      m_nMin = m_nDays - 1;                       // as in the search: the days needed is the lookback minus 1
      m_firstMin = Minutes(FirstDecision);
      m_exitMin  = (ExitTime >= 2400) ? 1440 : Minutes(ExitTime);
      m_startMin = Minutes(SessionStart);
      m_endMin   = Minutes(SessionEnd);
      ArrayResize(m_hist, NA_ROWS * NA_COLS + 1);
      ArrayInitialize(m_hist, -1.0);
      m_dayN = 0;
      m_dayId = -1;
      m_dayOpen = 0.0;
      m_prevClose = 0.0;
      m_lastClose = 0.0;
      m_cumPV = 0.0;
      m_cumV = 0.0;
      m_pos = 0.0;
      m_hasPrev = false;
      NewDay = false; BandOk = false;
      Sigma = 0.0; Upper = 0.0; Lower = 0.0; Vwap = 0.0;
      PosAfter = 0.0; Held = 0.0; Target = 0.0; Key = 0;
     }

   //--- the time the day's last bar closes may change from day to day (early closes)
   void              SetSessionEnd(const int hhmm)
     {
      SessionEnd = hhmm;
      m_endMin = Minutes(hhmm);
     }

   //--- one CLOSED bar; `t` is its open time (server time)
   void              Process(const datetime t, const double o, const double h, const double l, const double c,
                             const long tickVolume, const long realVolume)
     {
      MqlDateTime dt;
      TimeToStruct(t, dt);
      const int openMin = dt.hour * 60 + dt.min;
      const long dayId = (long)(t / 86400);

      NewDay = (dayId != m_dayId);
      if(NewDay)
        {
         m_dayId = dayId;
         m_dayN++;
         m_dayOpen = o;
         m_prevClose = m_lastClose;              // the previous bar's close: the previous day's last
         m_hasPrev = (m_lastClose > 0.0);
         m_cumPV = 0.0;
         m_cumV = 0.0;
         const int newRow = m_dayN % NA_ROWS;
         for(int k = 1; k < NA_COLS; k++)
            m_hist[newRow * NA_COLS + k] = -1.0;
        }
      const int row = m_dayN % NA_ROWS;
      Key = openMin + PeriodMin - m_startMin;

      //--- the session VWAP: typical price (high + low + close) / 3, weighted by the volume
      const double typical = (h + l + c) / 3.0;
      const double weight = UseRealVolume ? (double)realVolume : (double)tickVolume;
      m_cumPV += typical * weight;
      m_cumV += weight;
      const bool vwOk = (m_cumV > 0.0);
      Vwap = vwOk ? m_cumPV / m_cumV : 0.0;

      //--- sigma: the mean |close / day open - 1| at this time of day over the last `Lookback`
      //    observations of it, going back day by day (a day with no bar at this time is skipped)
      Sigma = -1.0;
      BandOk = false;
      Upper = 0.0;
      Lower = 0.0;
      if(Key >= 1 && Key <= NA_COLS - 1 && m_dayOpen > 0.0)
        {
         const double move = MathAbs(c / m_dayOpen - 1.0);
         double sum = 0.0;
         int count = 0;
         int back = 1;
         while(count < m_nDays && back <= NA_ROWS - 1 && m_dayN - back >= 1)
           {
            const double v = m_hist[((m_dayN - back) % NA_ROWS) * NA_COLS + Key];
            if(v >= 0.0)
              {
               sum += v;
               count++;
              }
            back++;
           }
         if(count >= m_nMin)
            Sigma = sum / count;
         m_hist[row * NA_COLS + Key] = move;     // today's move is stored after reading: a day never sees itself
        }

      //--- the Noise Area (the first day has no previous close and so no band)
      if(Sigma >= 0.0 && m_hasPrev)
        {
         const double width = Mult * Sigma;
         const double hi = (m_dayOpen > m_prevClose) ? m_dayOpen : m_prevClose;
         const double lo = (m_dayOpen < m_prevClose) ? m_dayOpen : m_prevClose;
         Upper = hi * (1.0 + width);
         Lower = lo * (1.0 - width);
         BandOk = true;
        }
      const bool aboveU = BandOk && (c > Upper);
      const bool belowL = BandOk && (c < Lower);
      const bool aboveV = vwOk && (c > Vwap);
      const bool belowV = vwOk && (c < Vwap);

      //--- the position
      const double before = NewDay ? 0.0 : m_pos;
      double st = before;
      const bool isDecision = (Cadence > 0) && (Key % Cadence == 0) && (m_startMin + Key >= m_firstMin);
      if(isDecision)
        {
         switch(StopKind)
           {
            case NA_STOP_VWAP_BAND:
               st = (aboveU && aboveV) ? 1.0 : (belowL && belowV) ? -1.0 : 0.0;
               break;
            case NA_STOP_BAND:
               st = aboveU ? 1.0 : belowL ? -1.0 : 0.0;
               break;
            case NA_STOP_OPPOSITE:
               st = aboveU ? 1.0 : belowL ? -1.0 : before;
               break;
            default: // NA_STOP_VWAP_ONLY: leave when the close is no longer on the position's side of the VWAP, then enter
              {
               double p = before;
               if((p > 0.0 && !aboveV) || (p < 0.0 && !belowV))
                  p = 0.0;
               st = (p == 0.0) ? (aboveU ? 1.0 : belowL ? -1.0 : 0.0) : p;
              }
           }
        }
      else
         if(EveryBar && before != 0.0)
           {
            bool stopped = false;
            switch(StopKind)
              {
               case NA_STOP_VWAP_BAND:
                  stopped = (before > 0.0) ? !(aboveU && aboveV) : !(belowL && belowV);
                  break;
               case NA_STOP_BAND:
                  stopped = (before > 0.0) ? !aboveU : !belowL;
                  break;
               case NA_STOP_OPPOSITE:
                  stopped = (before > 0.0) ? belowL : aboveU;
                  break;
               default:
                  stopped = (before > 0.0) ? !aboveV : !belowV;
              }
            if(stopped)
               st = 0.0;
           }
      m_pos = st;
      PosAfter = st;

      //--- what is held DURING this bar was decided at the previous close; flat from the bar that
      //    opens at or after the exit time
      Held = (openMin >= m_exitMin) ? 0.0 : before;

      //--- what is wanted for the NEXT bar: this decision, flat from the exit time, and flat by the day's
      //    last bar: a market order fills at the next bar's open, and the last bar has no next bar that
      //    day, so the flatten is sent one bar early and fills at the last bar's open
      const int closeMin = openMin + PeriodMin;
      Target = st;
      if(closeMin >= m_exitMin)
         Target = 0.0;
      if(closeMin + PeriodMin >= m_endMin)
         Target = 0.0;

      m_lastClose = c;
     }
  };

//+------------------------------------------------------------------+
//| The Expert Advisor: inputs and state.                             |
//+------------------------------------------------------------------+

input int          Lookback      = 20;               // days of history (2..90)
input double       Mult          = 1.5;              // band multiplier k
input int          Cadence       = 60;               // a decision every N minutes (a multiple of the chart period)
input int          FirstDecision = 1200;             // HHMM: first decision at or after this time
input int          ExitTime      = 1820;             // HHMM: flat from this time on (2400 = hold to the close)
input ENUM_NA_STOP StopKind      = NA_STOP_BAND;     // stop
input bool         EveryBar      = true;             // act on the stop at every bar, not only on the checkpoints
input int          SessionStart  = 900;              // HHMM (server time): the market day starts here
input int          SessionEnd    = 1825;             // HHMM: the day's LAST bar closes here (the start value with AutoSessionEnd; WIN 1825 or 1755, stocks 1800)
input bool         AutoSessionEnd = true;            // the day's end is the previous day's last bar close (else SessionEnd always)
input bool         UseRealVolume = true;             // VWAP weights: real volume (false: tick volume)
enum ENUM_NA_SIZING
  {
   NA_SIZE_FIXED  = 0,   // fixed: Lots contracts every day
   NA_SIZE_VOLTGT = 1    // the paper's: the leverage that targets the daily volatility
  };
input ENUM_NA_SIZING Sizing      = NA_SIZE_FIXED;    // position size
input double       Lots          = 1.0;              // Sizing fixed: contracts per trade
input double       TargetVol     = 0.02;             // Sizing volatility: the daily volatility to target (paper 2%)
input double       MaxLeverage   = 4.0;              // Sizing volatility: leverage cap (paper 4)
input double       MarginPerContract = 1000.0;       // Sizing volatility: contracts never exceed balance / this (0 = no limit)
input long         MagicNumber   = 20261117;         // magic number of the orders
input int          DeviationPts  = 50;               // allowed slippage, in points
input bool         SendOrders    = true;             // false: only compute (and log)
input bool         WriteLog      = false;            // write MQL5/Files/noise_area_log.csv, one row per bar
input bool         DrawChart     = true;             // draw the bands, the VWAP and the position arrows (not in a non-visual test)
input int          DrawDays      = 5;                // keep the drawing of the last N days

CTrade     trade;
CNoiseCore core;
datetime   g_lastProcessed = 0;
double     g_lastClose     = 0.0;
double     g_closes[];        // the last close of each past day, oldest first
double     g_size          = 0.0; // contracts of the day
datetime   g_lastBarSeen   = 0;
int        g_log           = INVALID_HANDLE;
bool       g_draw          = false;
datetime   g_drawFrom      = 0;       // bars before this time are not drawn
datetime   g_prevT         = 0;
double     g_prevU = 0.0, g_prevL = 0.0, g_prevV = 0.0, g_prevHeld = 0.0;
const string NA_PREFIX     = "NoiseArea_";


//+------------------------------------------------------------------+
//| The drawing. Each closed bar adds a segment of each    |
//| line (from the previous bar of the same day) and, where the held  |
//| position changes, an arrow at that bar's open.                    |
//+------------------------------------------------------------------+
void Segment(const string tag, const datetime t0, const double v0, const datetime t1, const double v1, const color clr, const int width)
  {
   const string name = NA_PREFIX + tag + IntegerToString((long)t1);
   if(ObjectFind(0, name) >= 0)
      return;
   ObjectCreate(0, name, OBJ_TREND, 0, t0, v0, t1, v1);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void Arrow(const datetime t, const double price, const int code, const color clr)
  {
   const string name = NA_PREFIX + "A" + IntegerToString((long)t);
   if(ObjectFind(0, name) >= 0)
      return;
   ObjectCreate(0, name, OBJ_ARROW, 0, t, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void DrawBar(const datetime t, const double open)
  {
   if(!g_draw || t < g_drawFrom)
      return;
   const bool same = (g_prevT > 0 && (long)(g_prevT / 86400) == (long)(t / 86400));
   if(same && core.BandOk && g_prevU > 0.0)
     {
      Segment("U", g_prevT, g_prevU, t, core.Upper, clrLimeGreen, 2);
      Segment("L", g_prevT, g_prevL, t, core.Lower, clrTomato, 2);
     }
   if(same && core.Vwap > 0.0 && g_prevV > 0.0)
      Segment("V", g_prevT, g_prevV, t, core.Vwap, clrGold, 1);
   if(!core.NewDay && core.Held != g_prevHeld)
     {
      if(core.Held > 0.0 && g_prevHeld <= 0.0)
         Arrow(t, open, 233, clrLimeGreen);
      else
         if(core.Held < 0.0 && g_prevHeld >= 0.0)
            Arrow(t, open, 234, clrTomato);
         else
            if(core.Held == 0.0)
               Arrow(t, open, 251, clrSilver);
     }
   g_prevT = t;
   g_prevU = core.BandOk ? core.Upper : 0.0;
   g_prevL = core.BandOk ? core.Lower : 0.0;
   g_prevV = core.Vwap;
   g_prevHeld = core.Held;
  }

//--- a new day: drop the drawing older than DrawDays days
void Prune(const datetime now)
  {
   if(!g_draw)
      return;
   const datetime cutoff = now - (datetime)DrawDays * 86400;
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
     {
      const string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, NA_PREFIX) != 0)
         continue;
      if((datetime)ObjectGetInteger(0, name, OBJPROP_TIME, 0) < cutoff)
         ObjectDelete(0, name);
     }
  }

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
//| The day's contracts. Sizing volatility is the model's (and the    |
//| authors' notebook's): balance / (day open x point value) x the    |
//| leverage target / volatility, capped at MaxLeverage, where the    |
//| volatility is the sample standard deviation of the 14 daily       |
//| close-to-close returns of days d-15 .. d-2 (the day before is     |
//| left out, as in the notebook). Without 14 returns it uses the cap.|
//+------------------------------------------------------------------+
double ComputeSize(const double dayOpen)
  {
   if(Sizing == NA_SIZE_FIXED)
      return Lots;
   const double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   const double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0.0 || tickValue <= 0.0 || dayOpen <= 0.0)
      return 0.0;
   const double pointValue = tickValue / tickSize;
   const double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double leverage = MaxLeverage;
   const int n = ArraySize(g_closes);          // g_closes[n-1] is the day before: left out
   if(n >= 16)
     {
      double sum = 0.0, sum2 = 0.0;
      for(int k = n - 15; k <= n - 2; k++)
        {
         const double r = g_closes[k] / g_closes[k - 1] - 1.0;
         sum += r;
         sum2 += r * r;
        }
      const double mean = sum / 14.0;
      const double var = (sum2 - 14.0 * mean * mean) / 13.0;
      if(var > 0.0)
         leverage = MathMin(TargetVol / MathSqrt(var), MaxLeverage);
     }
   double wanted = MathRound(balance / (dayOpen * pointValue) * leverage);
   if(MarginPerContract > 0.0)
      wanted = MathMin(wanted, MathFloor(balance / MarginPerContract));
   const double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0.0)
      wanted = MathFloor(wanted / step + 1e-9) * step;
   return wanted;
  }

//+------------------------------------------------------------------+
//| One closed bar into the core. With AutoSessionEnd, the day's end  |
//| is the previous day's: the close of its last bar (B3 moved its    |
//| close between 17:55 and 18:25 with the seasons), seen when the    |
//| first bar of a new day arrives. An end before the first decision  |
//| is a cut file, not a close, and is ignored.                       |
//+------------------------------------------------------------------+
void ProcessBar(const MqlRates &b)
  {
   if(g_lastProcessed == 0 || (long)(b.time / 86400) != (long)(g_lastProcessed / 86400))
     {
      if(g_lastProcessed > 0)
        {
         const int n = ArraySize(g_closes);
         if(n >= 40)
           {
            for(int k = 1; k < n; k++)
               g_closes[k - 1] = g_closes[k];
            ArrayResize(g_closes, n - 1);
           }
         ArrayResize(g_closes, ArraySize(g_closes) + 1);
         g_closes[ArraySize(g_closes) - 1] = g_lastClose;
        }
      g_size = ComputeSize(b.open);
      if(Sizing == NA_SIZE_VOLTGT && b.time >= g_drawFrom)
         PrintFormat("NoiseArea: %s %.0f contracts", TimeToString(b.time, TIME_DATE), g_size);
     }
   if(AutoSessionEnd && g_lastProcessed > 0 && (long)(b.time / 86400) != (long)(g_lastProcessed / 86400))
     {
      MqlDateTime d;
      TimeToStruct(g_lastProcessed + PeriodSeconds(_Period), d);
      const int e = d.hour * 100 + d.min;
      if(e >= FirstDecision && e != core.SessionEnd)
         core.SetSessionEnd(e);
     }
   core.Process(b.time, b.open, b.high, b.low, b.close, b.tick_volume, b.real_volume);
   g_lastProcessed = b.time;
   g_lastClose = b.close;
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
      ProcessBar(r[i]);
      DrawBar(r[i].time, r[i].open);
      if(log)
         LogBar(r[i].time, r[i].close);
     }
   return n;
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
   if(want != 0 && g_size <= 0.0)
      return;   // a day sized at no contracts
   if(have != 0)
     {
      if(!trade.PositionClose(_Symbol))
         PrintFormat("NoiseArea: close failed, %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
   if(want == 1)
     {
      if(!trade.Buy(g_size, _Symbol, 0.0, 0.0, 0.0, "NoiseArea"))
         PrintFormat("NoiseArea: buy failed, %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
   else
      if(want == -1)
        {
         if(!trade.Sell(g_size, _Symbol, 0.0, 0.0, 0.0, "NoiseArea"))
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
   g_draw = DrawChart && (!MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_VISUAL_MODE));
   const int barsPerDay = 650 / periodMin + 1;
   const int warm = (core.Lookback + 12) * barsPerDay;
   MqlRates r[];
   ArraySetAsSeries(r, false);
   const int got = CopyRates(_Symbol, _Period, 1, warm, r);
   if(got > 0)
      g_drawFrom = r[got - 1].time - (datetime)DrawDays * 86400;
   for(int i = 0; i < got; i++)
     {
      ProcessBar(r[i]);
      DrawBar(r[i].time, r[i].open);
     }
   g_lastBarSeen = iTime(_Symbol, _Period, 0);
   PrintFormat("NoiseArea: warmed up on %d bars of %s %s", got, _Symbol, EnumToString(_Period));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, NA_PREFIX);
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
   if(Feed(from, to, true) <= 0)
      return;
   if((long)(cur / 86400) != (long)(g_lastProcessed / 86400))
     {
      g_drawFrom = cur - (datetime)DrawDays * 86400;
      Prune(cur);
     }
   //--- nothing carries over a day boundary: a new day starts flat, whatever the last bar of the
   //    day before wanted (an early close that SessionEnd did not know about)
   double wanted = core.Target;
   if((long)(cur / 86400) != (long)(g_lastProcessed / 86400))
      wanted = 0.0;
   if(SendOrders)
      Act(wanted);
  }
//+------------------------------------------------------------------+
