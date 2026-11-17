//+------------------------------------------------------------------+
//| NoiseAreaIndicator.mq5                                           |
//| The Noise Area (upper and lower band), the session VWAP and the  |
//| position the rule holds (arrows where it changes). It uses the   |
//| same NoiseCore as the Expert Advisor.                            |
//| Educational only, not investment advice. docs/mql5-noise-area.md |
//| Defaults: the WIN OPTIMIZED trial (see NoiseAreaEA.mq5 for the   |
//| paper's values).                                                 |
//+------------------------------------------------------------------+
#property copyright "B3 Backtester (educational)"
#property version   "1.00"
#property description "Noise Area bands, VWAP and position (Zarattini, Aziz, Barbon). Educational only."
#property indicator_chart_window
#property indicator_buffers 7
#property indicator_plots   6

#property indicator_label1  "Upper band"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrLimeGreen
#property indicator_width1  2
#property indicator_label2  "Lower band"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrTomato
#property indicator_width2  2
#property indicator_label3  "Session VWAP"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrGold
#property indicator_width3  1
#property indicator_label4  "Long"
#property indicator_type4   DRAW_ARROW
#property indicator_color4  clrLimeGreen
#property indicator_label5  "Short"
#property indicator_type5   DRAW_ARROW
#property indicator_color5  clrTomato
#property indicator_label6  "Exit"
#property indicator_type6   DRAW_ARROW
#property indicator_color6  clrSilver

#include <NoiseArea/NoiseCore.mqh>

input int          Lookback      = 20;               // days of history (2..90)
input double       Mult          = 1.5;              // band multiplier k
input int          Cadence       = 60;               // a decision every N minutes (a multiple of the chart period)
input int          FirstDecision = 1200;             // HHMM: first decision at or after this time
input int          ExitTime      = 1820;             // HHMM: flat from this time on (2400 = hold to the close)
input ENUM_NA_STOP StopKind      = NA_STOP_BAND;     // stop
input bool         EveryBar      = true;             // act on the stop at every bar, not only on the checkpoints
input int          SessionStart  = 900;              // HHMM (server time): the market day starts here
input int          SessionEnd    = 1825;             // HHMM: the day's LAST bar closes here
input bool         UseRealVolume = true;             // VWAP weights: real volume (false: tick volume)

double BufUpper[], BufLower[], BufVwap[], BufLong[], BufShort[], BufExit[], BufHeld[];
CNoiseCore core;
int        g_done = 0;        // bars [0, g_done) have been processed (closed bars only)
double     g_prevHeld = 0.0;

//+------------------------------------------------------------------+
int OnInit()
  {
   const int periodMin = (int)(PeriodSeconds(_Period) / 60);
   if(periodMin < 1 || Cadence % periodMin != 0)
     {
      PrintFormat("NoiseArea: the chart period (%d min) must divide Cadence (%d min)", periodMin, Cadence);
      return INIT_PARAMETERS_INCORRECT;
     }
   SetIndexBuffer(0, BufUpper, INDICATOR_DATA);
   SetIndexBuffer(1, BufLower, INDICATOR_DATA);
   SetIndexBuffer(2, BufVwap, INDICATOR_DATA);
   SetIndexBuffer(3, BufLong, INDICATOR_DATA);
   SetIndexBuffer(4, BufShort, INDICATOR_DATA);
   SetIndexBuffer(5, BufExit, INDICATOR_DATA);
   SetIndexBuffer(6, BufHeld, INDICATOR_CALCULATIONS);
   for(int p = 0; p < 6; p++)
      PlotIndexSetDouble(p, PLOT_EMPTY_VALUE, 0.0);
   PlotIndexSetInteger(3, PLOT_ARROW, 233);   // up arrow
   PlotIndexSetInteger(4, PLOT_ARROW, 234);   // down arrow
   PlotIndexSetInteger(5, PLOT_ARROW, 251);   // cross
   IndicatorSetString(INDICATOR_SHORTNAME, "Noise Area");

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
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2)
      return 0;
   if(prev_calculated == 0)
     {
      core.Reset();
      g_done = 0;
      g_prevHeld = 0.0;
      ArrayInitialize(BufUpper, 0.0);
      ArrayInitialize(BufLower, 0.0);
      ArrayInitialize(BufVwap, 0.0);
      ArrayInitialize(BufLong, 0.0);
      ArrayInitialize(BufShort, 0.0);
      ArrayInitialize(BufExit, 0.0);
      ArrayInitialize(BufHeld, 0.0);
     }

   //--- the last bar is still forming: only the closed ones are processed, once each
   for(int i = g_done; i < rates_total - 1; i++)
     {
      core.Process(time[i], open[i], high[i], low[i], close[i], tick_volume[i], volume[i]);
      BufUpper[i] = core.BandOk ? core.Upper : 0.0;
      BufLower[i] = core.BandOk ? core.Lower : 0.0;
      BufVwap[i] = core.Vwap;
      BufHeld[i] = core.Held;
      BufLong[i] = 0.0;
      BufShort[i] = 0.0;
      BufExit[i] = 0.0;
      if(!core.NewDay && core.Held != g_prevHeld)
        {
         if(core.Held > 0.0 && g_prevHeld <= 0.0)
            BufLong[i] = open[i];
         else
            if(core.Held < 0.0 && g_prevHeld >= 0.0)
               BufShort[i] = open[i];
            else
               if(core.Held == 0.0)
                  BufExit[i] = open[i];
        }
      g_prevHeld = core.Held;
     }
   g_done = rates_total - 1;
   BufUpper[rates_total - 1] = 0.0;
   BufLower[rates_total - 1] = 0.0;
   BufVwap[rates_total - 1] = 0.0;
   BufLong[rates_total - 1] = 0.0;
   BufShort[rates_total - 1] = 0.0;
   BufExit[rates_total - 1] = 0.0;
   BufHeld[rates_total - 1] = 0.0;
   return rates_total;
  }
//+------------------------------------------------------------------+
