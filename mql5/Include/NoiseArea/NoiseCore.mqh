//+------------------------------------------------------------------+
//| NoiseCore.mqh                                                    |
//| Noise Area intraday momentum (Zarattini, Aziz and Barbon,        |
//| "Beat the Market"), ported from the Python reference in          |
//| backend/core/src/b3core (noise_area.py, intraday_momentum.py)    |
//| and from ntsl/noise_area_win.ntsl, whose logic was checked       |
//| against the engine bar by bar.                                   |
//| Educational only, not investment advice. docs/mql5-noise-area.md |
//|                                                                  |
//| Feed it the CLOSED bars one by one, oldest first (Process). It   |
//| keeps the day, the history of the moves (a ring of days x a      |
//| column per minute since the session start) and the position.     |
//+------------------------------------------------------------------+
#ifndef NOISE_CORE_MQH
#define NOISE_CORE_MQH

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

#endif
