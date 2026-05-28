//+------------------------------------------------------------------+
//| Change of Direction V2.mq5                                       |
//| Reversal strategy — 4-phase state machine + protective filters   |
//+------------------------------------------------------------------+
#property strict
#property version     "4.0"
#property description "Change of Direction V2 — With Trend, Risk & Session Filters"
#property copyright   "AlgoTrader Pro"

//+------------------------------------------------------------------+
//| Input Parameters — Original                                       |
//+------------------------------------------------------------------+
input int      MIN_RED_CANDLES        = 2;       // Min consecutive red candles (initial drop)
input int      MIN_GREEN_CANDLES      = 2;       // Min green candles per pullback (not consecutive)
input bool     ALLOW_SHORT            = true;    // Enable SELL signals
input bool     ALLOW_LONG             = true;    // Enable BUY signals
input double   RISK_PERCENT           = 1.0;     // Risk per trade (%)
input double   MAX_DAILY_LOSS_PCT     = 30.0;    // Max daily loss (%) - reserved
input int      MAX_OPEN_POSITIONS     = 1;       // Max concurrent positions (all broker positions)
input bool     PAPER_TRADING_MODE     = false;   // true = only print, false = real orders
input bool     DEBUG_LOGS             = false;   // true = print all phase transitions, false = silent

//+------------------------------------------------------------------+
//| Input Parameters — V2 Filters                                     |
//+------------------------------------------------------------------+
input bool     USE_TREND_FILTER       = true;    // Enable H1 EMA trend filter
input int      TREND_EMA_PERIOD       = 50;      // EMA period for trend filter
input ENUM_TIMEFRAMES TREND_TIMEFRAME = PERIOD_H1; // Timeframe for trend EMA

input int      MAX_CONSECUTIVE_LOSSES = 5;       // Pause after N consecutive SL hits
input double   MAX_RISK_POINTS        = 30.0;    // Max allowed risk in points (skip if larger)
input double   MIN_RISK_POINTS        = 3.0;     // Min pattern size in points (skip noise)

input bool     USE_SESSION_FILTER     = true;    // Enable trading hours filter
input int      TRADING_HOUR_START     = 8;       // Start hour (server time, inclusive)
input int      TRADING_HOUR_END       = 18;      // End hour (server time, exclusive)

//+------------------------------------------------------------------+
//| Logging helper                                                    |
//+------------------------------------------------------------------+
void Log(string message)
{
   if(DEBUG_LOGS)
      Print(message);
}

//+------------------------------------------------------------------+
//| State Machine Phases                                              |
//+------------------------------------------------------------------+
#define PHASE_IDLE        0
#define PHASE1_DROP       1
#define PHASE2_PULLBACK1  2
#define PHASE3_BREAK      3
#define PHASE4_PULLBACK2  4
#define PHASE5_ENTRY      5

//+------------------------------------------------------------------+
//| Global Variables — Position                                       |
//+------------------------------------------------------------------+
bool           is_position_open            = false;
ulong          current_position_ticket     = 0;
string         current_position_direction  = "";
double         current_position_entry_price = 0.0;
double         current_position_stop_loss  = 0.0;
double         current_position_take_profit = 0.0;

//+------------------------------------------------------------------+
//| Global Variables — V2 Filters                                     |
//+------------------------------------------------------------------+
int            consecutive_losses          = 0;    // Counter for consecutive SL hits
bool           trading_paused              = false; // Pause flag after max losses
int            trend_ema_handle            = INVALID_HANDLE; // Handle for trend EMA indicator

//+------------------------------------------------------------------+
//| Global Variables — SELL state machine                             |
//+------------------------------------------------------------------+
int            sell_phase               = PHASE_IDLE;
double         sell_reset_level         = 0.0;
double         sell_point_1             = 0.0;
int            sell_red_count           = 0;
int            sell_green1_count        = 0;
double         sell_pullback1_high      = 0.0;
int            sell_green2_count        = 0;
double         sell_pullback2_high      = 0.0;
double         sell_point_2             = 0.0;

//+------------------------------------------------------------------+
//| Global Variables — BUY state machine (mirror)                    |
//+------------------------------------------------------------------+
int            buy_phase                = PHASE_IDLE;
double         buy_reset_level          = 0.0;
double         buy_point_1              = 0.0;
int            buy_green_count          = 0;
int            buy_red1_count           = 0;
double         buy_pullback1_low        = 0.0;
int            buy_red2_count           = 0;
double         buy_pullback2_low        = 0.0;
double         buy_point_2              = 0.0;

MqlRates       rates[];

//+------------------------------------------------------------------+
//| Load candle data                                                  |
//+------------------------------------------------------------------+
bool UpdateRates(const int candles = 100)
{
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, _Period, 0, candles, rates);
   if(copied <= 0) { Print("[", _Symbol, "] CopyRates failed. Error=", GetLastError()); return false; }
   return copied >= MathMin(candles, Bars(_Symbol, _Period));
}

//+------------------------------------------------------------------+
//| Normalize volume                                                  |
//+------------------------------------------------------------------+
double NormalizeVolume(double volume)
{
   double min_v = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_v = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0) step = 0.01;
   volume = MathMax(min_v, MathMin(volume, max_v));
   volume = MathFloor(volume / step) * step;
   return NormalizeDouble(volume, 2);
}

//+------------------------------------------------------------------+
//| V2: Get Trend EMA value from higher timeframe                    |
//+------------------------------------------------------------------+
double GetTrendEMA()
{
   if(trend_ema_handle == INVALID_HANDLE) return 0.0;
   double ema_buf[];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(trend_ema_handle, 0, 0, 1, ema_buf) <= 0) return 0.0;
   return ema_buf[0];
}

//+------------------------------------------------------------------+
//| V2: Check if current hour is within trading session              |
//+------------------------------------------------------------------+
bool IsWithinTradingHours()
{
   if(!USE_SESSION_FILTER) return true;
   MqlDateTime dt;
   TimeCurrent(dt);
   int hour = dt.hour;
   if(TRADING_HOUR_START < TRADING_HOUR_END)
      return (hour >= TRADING_HOUR_START && hour < TRADING_HOUR_END);
   else // overnight session (e.g., 22 to 6)
      return (hour >= TRADING_HOUR_START || hour < TRADING_HOUR_END);
}

//+------------------------------------------------------------------+
//| V2: Check trend filter — returns true if direction is allowed    |
//+------------------------------------------------------------------+
bool IsTrendAllowed(string direction)
{
   if(!USE_TREND_FILTER) return true;
   double ema = GetTrendEMA();
   if(ema <= 0.0) return true; // no data yet, allow
   double current_price = rates[1].close;
   if(direction == "BUY"  && current_price < ema)
   {
      Log("[" + _Symbol + "] V2 TREND FILTER: BUY rejected. Price=" + DoubleToString(current_price, _Digits)
          + " < EMA_H1=" + DoubleToString(ema, _Digits));
      return false;
   }
   if(direction == "SELL" && current_price > ema)
   {
      Log("[" + _Symbol + "] V2 TREND FILTER: SELL rejected. Price=" + DoubleToString(current_price, _Digits)
          + " > EMA_H1=" + DoubleToString(ema, _Digits));
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| V2: Check risk size filter — returns true if risk is acceptable  |
//+------------------------------------------------------------------+
bool IsRiskAcceptable(double risk_points)
{
   if(risk_points > MAX_RISK_POINTS)
   {
      Print("[", _Symbol, "] V2 RISK FILTER: Rejected. Risk=", DoubleToString(risk_points, _Digits),
            " > MAX=", DoubleToString(MAX_RISK_POINTS, _Digits));
      return false;
   }
   if(risk_points < MIN_RISK_POINTS)
   {
      Log("[" + _Symbol + "] V2 MIN RISK FILTER: Rejected noise. Risk=" + DoubleToString(risk_points, _Digits)
          + " < MIN=" + DoubleToString(MIN_RISK_POINTS, _Digits));
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Reset SELL state                                                  |
//+------------------------------------------------------------------+
void ResetSellState()
{
   sell_phase              = PHASE_IDLE;
   sell_reset_level        = 0.0;
   sell_point_1            = 0.0;
   sell_red_count          = 0;
   sell_green1_count       = 0;
   sell_pullback1_high     = 0.0;
   sell_green2_count       = 0;
   sell_pullback2_high     = 0.0;
   sell_point_2            = 0.0;
}

//+------------------------------------------------------------------+
//| Reset BUY state                                                   |
//+------------------------------------------------------------------+
void ResetBuyState()
{
   buy_phase               = PHASE_IDLE;
   buy_reset_level         = 0.0;
   buy_point_1             = 0.0;
   buy_green_count         = 0;
   buy_red1_count          = 0;
   buy_pullback1_low       = 0.0;
   buy_red2_count          = 0;
   buy_pullback2_low       = 0.0;
   buy_point_2             = 0.0;
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   // Create trend EMA indicator handle on higher timeframe
   if(USE_TREND_FILTER)
   {
      trend_ema_handle = iMA(_Symbol, TREND_TIMEFRAME, TREND_EMA_PERIOD, 0, MODE_EMA, PRICE_CLOSE);
      if(trend_ema_handle == INVALID_HANDLE)
      {
         Print("[", _Symbol, "] WARNING: Failed to create trend EMA handle. Trend filter disabled.");
      }
   }

   Print("[", _Symbol, "] Change of Direction V2 (v4.0) initialized");
   Print("[", _Symbol, "] Filters: TrendEMA=", USE_TREND_FILTER, " (", TREND_EMA_PERIOD, " on ",
         EnumToString(TREND_TIMEFRAME), ")");
   Print("[", _Symbol, "] MaxConsecLosses=", MAX_CONSECUTIVE_LOSSES,
         " MaxRisk=", MAX_RISK_POINTS, " MinRisk=", MIN_RISK_POINTS);
   Print("[", _Symbol, "] Session=", USE_SESSION_FILTER, " (", TRADING_HOUR_START, ":00 - ",
         TRADING_HOUR_END, ":00)");

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(trend_ema_handle != INVALID_HANDLE)
      IndicatorRelease(trend_ema_handle);
   Log("[" + _Symbol + "] Change of Direction V2 deinitialized. Reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//| OnTick — only process on new closed candle                        |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!UpdateRates()) return;

   static datetime last_candle_time = 0;
   if(rates[1].time == last_candle_time) return;
   last_candle_time = rates[1].time;

   MqlRates candle = rates[1];

   if(is_position_open)
      CheckExitSignal(candle);
   else
   {
      // V2: Check if trading is paused due to consecutive losses
      if(trading_paused)
      {
         Log("[" + _Symbol + "] V2: Trading PAUSED after " + IntegerToString(consecutive_losses)
             + " consecutive losses. Waiting for pattern reset...");
         // Reset pause when both state machines are idle (full reset)
         if(sell_phase == PHASE_IDLE && buy_phase == PHASE_IDLE)
         {
            trading_paused = false;
            consecutive_losses = 0;
            Print("[", _Symbol, "] V2: Trading RESUMED after pattern reset.");
         }
         else
         {
            // Force reset both machines to start fresh
            ResetSellState();
            ResetBuyState();
            return;
         }
      }

      // V2: Check trading hours
      if(!IsWithinTradingHours())
      {
         Log("[" + _Symbol + "] V2: Outside trading hours. Skipping.");
         return;
      }

      if(ALLOW_SHORT) UpdateSellState(candle);
      if(ALLOW_LONG)  UpdateBuyState(candle);
   }
}

//+------------------------------------------------------------------+
//| SELL State Machine                                                |
//+------------------------------------------------------------------+
void UpdateSellState(MqlRates &c)
{
   bool is_red   = c.close < c.open;
   bool is_green = c.close > c.open;

   // RESET: only in PHASE4/PHASE5
   if((sell_phase == PHASE4_PULLBACK2 || sell_phase == PHASE5_ENTRY) && sell_pullback1_high > 0.0)
   {
      if(c.close > sell_pullback1_high)
      {
         Log("[" + _Symbol + "] COD SELL RESET: close=" + DoubleToString(c.close, _Digits)
             + " > pullback1_high=" + DoubleToString(sell_pullback1_high, _Digits));
         ResetSellState();
         return;
      }
   }

   if(sell_phase == PHASE_IDLE)
   {
      if(is_red)
      {
         sell_phase          = PHASE1_DROP;
         sell_reset_level    = c.high;
         sell_point_1        = c.low;
         sell_red_count      = 1;
         Log("[" + _Symbol + "] COD SELL PHASE1: first red. point_1="
             + DoubleToString(sell_point_1, _Digits));
      }
      return;
   }

   if(sell_phase == PHASE1_DROP)
   {
      if(is_red)
      {
         sell_red_count++;
         sell_point_1 = MathMin(sell_point_1, c.low);
         Log("[" + _Symbol + "] COD SELL PHASE1: red #" + IntegerToString(sell_red_count)
             + " point_1=" + DoubleToString(sell_point_1, _Digits));
      }
      else if(is_green && sell_red_count >= MIN_RED_CANDLES)
      {
         sell_phase              = PHASE2_PULLBACK1;
         sell_green1_count       = 1;
         sell_pullback1_high     = c.high;
         Log("[" + _Symbol + "] COD SELL PHASE2: pullback1 started.");
      }
      else
      {
         Log("[" + _Symbol + "] COD SELL RESET PHASE1: green before "
             + IntegerToString(MIN_RED_CANDLES) + " reds (" + IntegerToString(sell_red_count) + ")");
         ResetSellState();
      }
      return;
   }

   if(sell_phase == PHASE2_PULLBACK1)
   {
      if(is_green)
      {
         if(c.low < sell_point_1)
         {
            Log("[" + _Symbol + "] COD SELL RESET PHASE2: green low below point_1 ("
                + DoubleToString(c.low, _Digits) + " < " + DoubleToString(sell_point_1, _Digits) + ")");
            ResetSellState();
            return;
         }
         sell_green1_count++;
         sell_pullback1_high = MathMax(sell_pullback1_high, c.high);
         Log("[" + _Symbol + "] COD SELL PHASE2: green #" + IntegerToString(sell_green1_count)
             + " ph1=" + DoubleToString(sell_pullback1_high, _Digits));
      }
      else if(is_red)
      {
         if(sell_green1_count >= MIN_GREEN_CANDLES)
         {
            sell_phase = PHASE3_BREAK;
            Log("[" + _Symbol + "] COD SELL PHASE3: waiting break of point_1="
                + DoubleToString(sell_point_1, _Digits)
                + " pullback1_high=" + DoubleToString(sell_pullback1_high, _Digits));
            CheckSellBreak(c);
         }
         else
         {
            Log("[" + _Symbol + "] COD SELL RESET PHASE2: not enough greens ("
                + IntegerToString(sell_green1_count) + "/" + IntegerToString(MIN_GREEN_CANDLES) + ")");
            ResetSellState();
         }
      }
      return;
   }

   if(sell_phase == PHASE3_BREAK) { CheckSellBreak(c); return; }

   if(sell_phase == PHASE4_PULLBACK2)
   {
      if(is_green)
      {
         sell_green2_count++;
         sell_pullback2_high = MathMax(sell_pullback2_high, c.high);
         if(sell_point_2 == 0.0) sell_point_2 = c.low;
         else                    sell_point_2 = MathMin(sell_point_2, c.low);
         Log("[" + _Symbol + "] COD SELL PHASE4: green #" + IntegerToString(sell_green2_count)
             + " ph2=" + DoubleToString(sell_pullback2_high, _Digits)
             + " point_2=" + DoubleToString(sell_point_2, _Digits));
      }
      else if(is_red)
      {
         if(sell_green2_count >= MIN_GREEN_CANDLES)
         {
            sell_phase = PHASE5_ENTRY;
            Log("[" + _Symbol + "] COD SELL PHASE5: waiting break of point_2="
                + DoubleToString(sell_point_2, _Digits)
                + " SL=" + DoubleToString(sell_pullback2_high, _Digits));
            CheckSellEntry(c);
         }
      }
      return;
   }

   if(sell_phase == PHASE5_ENTRY) CheckSellEntry(c);
}

//+------------------------------------------------------------------+
//| Check SELL break of point_1                                       |
//+------------------------------------------------------------------+
void CheckSellBreak(MqlRates &c)
{
   if(c.close < sell_point_1)
   {
      sell_phase          = PHASE4_PULLBACK2;
      sell_green2_count   = 0;
      sell_pullback2_high = c.high;
      sell_point_2        = 0.0;
      Log("[" + _Symbol + "] COD SELL PHASE4: point_1 broken. close="
          + DoubleToString(c.close, _Digits)
          + " < point_1=" + DoubleToString(sell_point_1, _Digits));
   }
   else
      Log("[" + _Symbol + "] COD SELL PHASE3 waiting: close="
          + DoubleToString(c.close, _Digits)
          + " >= point_1=" + DoubleToString(sell_point_1, _Digits));
}

//+------------------------------------------------------------------+
//| Check SELL entry — with V2 filters                               |
//+------------------------------------------------------------------+
void CheckSellEntry(MqlRates &c)
{
   if(sell_point_2 == 0.0) return;

   if(c.close <= sell_point_2)
   {
      double entry_price       = c.close;
      double stop_loss_price   = sell_pullback2_high;
      double risk              = stop_loss_price - entry_price;
      double take_profit_price = entry_price - (risk * 2.0);

      // V2: Check trend filter
      if(!IsTrendAllowed("SELL"))
      {
         ResetSellState();
         return;
      }

      // V2: Check risk size
      if(!IsRiskAcceptable(risk))
      {
         ResetSellState();
         return;
      }

      Print("[", _Symbol, "] COD SELL ENTRY: close=", DoubleToString(entry_price, _Digits),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits),
            " risk=", DoubleToString(risk, _Digits));

      ResetSellState();
      OpenPosition("SELL", stop_loss_price, take_profit_price);
   }
   else
      Log("[" + _Symbol + "] COD SELL PHASE5 waiting: close="
          + DoubleToString(c.close, _Digits)
          + " > point_2=" + DoubleToString(sell_point_2, _Digits));
}

//+------------------------------------------------------------------+
//| BUY State Machine (mirror of SELL)                               |
//+------------------------------------------------------------------+
void UpdateBuyState(MqlRates &c)
{
   bool is_green = c.close > c.open;
   bool is_red   = c.close < c.open;

   // RESET: only in PHASE4/PHASE5
   if((buy_phase == PHASE4_PULLBACK2 || buy_phase == PHASE5_ENTRY) && buy_pullback1_low > 0.0)
   {
      if(c.close < buy_pullback1_low)
      {
         Log("[" + _Symbol + "] COD BUY RESET: close=" + DoubleToString(c.close, _Digits)
             + " < pullback1_low=" + DoubleToString(buy_pullback1_low, _Digits));
         ResetBuyState();
         return;
      }
   }

   if(buy_phase == PHASE_IDLE)
   {
      if(is_green)
      {
         buy_phase            = PHASE1_DROP;
         buy_reset_level      = c.low;
         buy_point_1          = c.high;
         buy_green_count      = 1;
      }
      return;
   }

   if(buy_phase == PHASE1_DROP)
   {
      if(is_green) { buy_green_count++; buy_point_1 = MathMax(buy_point_1, c.high); }
      else if(is_red && buy_green_count >= MIN_GREEN_CANDLES)
      {
         buy_phase              = PHASE2_PULLBACK1;
         buy_red1_count         = 1;
         buy_pullback1_low      = c.low;
         Log("[" + _Symbol + "] COD BUY PHASE2: pullback1 started.");
      }
      else
      {
         Log("[" + _Symbol + "] COD BUY RESET PHASE1: red before "
             + IntegerToString(MIN_GREEN_CANDLES) + " greens (" + IntegerToString(buy_green_count) + ")");
         ResetBuyState();
      }
      return;
   }

   if(buy_phase == PHASE2_PULLBACK1)
   {
      if(is_red)
      {
         if(c.high > buy_point_1)
         {
            Log("[" + _Symbol + "] COD BUY RESET PHASE2: red high above point_1 ("
                + DoubleToString(c.high, _Digits) + " > " + DoubleToString(buy_point_1, _Digits) + ")");
            ResetBuyState();
            return;
         }
         buy_red1_count++;
         buy_pullback1_low = MathMin(buy_pullback1_low, c.low);
         Log("[" + _Symbol + "] COD BUY PHASE2: red #" + IntegerToString(buy_red1_count)
             + " pullback1_low=" + DoubleToString(buy_pullback1_low, _Digits));
      }
      else if(is_green)
      {
         if(buy_red1_count >= MIN_RED_CANDLES)
         {
            buy_phase = PHASE3_BREAK;
            Log("[" + _Symbol + "] COD BUY PHASE3: waiting break of point_1="
                + DoubleToString(buy_point_1, _Digits));
            CheckBuyBreak(c);
         }
         else
         {
            Log("[" + _Symbol + "] COD BUY RESET PHASE2: not enough reds ("
                + IntegerToString(buy_red1_count) + "/" + IntegerToString(MIN_RED_CANDLES) + ")");
            ResetBuyState();
         }
      }
      return;
   }

   if(buy_phase == PHASE3_BREAK) { CheckBuyBreak(c); return; }

   if(buy_phase == PHASE4_PULLBACK2)
   {
      if(is_red)
      {
         buy_red2_count++;
         buy_pullback2_low = MathMin(buy_pullback2_low, c.low);
         if(buy_point_2 == 0.0) buy_point_2 = c.high;
         else                   buy_point_2 = MathMax(buy_point_2, c.high);
         Log("[" + _Symbol + "] COD BUY PHASE4: red #" + IntegerToString(buy_red2_count)
             + " pullback2_low=" + DoubleToString(buy_pullback2_low, _Digits)
             + " point_2=" + DoubleToString(buy_point_2, _Digits));
      }
      else if(is_green && buy_red2_count >= MIN_RED_CANDLES)
      {
         buy_phase = PHASE5_ENTRY;
         Log("[" + _Symbol + "] COD BUY PHASE5: waiting break of point_2="
             + DoubleToString(buy_point_2, _Digits)
             + " SL=" + DoubleToString(buy_pullback2_low, _Digits));
         CheckBuyEntry(c);
      }
      return;
   }

   if(buy_phase == PHASE5_ENTRY) CheckBuyEntry(c);
}

//+------------------------------------------------------------------+
//| Check BUY break of point_1                                        |
//+------------------------------------------------------------------+
void CheckBuyBreak(MqlRates &c)
{
   if(c.close > buy_point_1)
   {
      buy_phase         = PHASE4_PULLBACK2;
      buy_red2_count    = 0;
      buy_pullback2_low = c.low;
      buy_point_2       = 0.0;
      Log("[" + _Symbol + "] COD BUY PHASE4: point_1 broken. close="
          + DoubleToString(c.close, _Digits)
          + " > point_1=" + DoubleToString(buy_point_1, _Digits));
   }
   else
      Log("[" + _Symbol + "] COD BUY PHASE3 waiting: close="
          + DoubleToString(c.close, _Digits)
          + " <= point_1=" + DoubleToString(buy_point_1, _Digits));
}

//+------------------------------------------------------------------+
//| Check BUY entry — with V2 filters                                |
//+------------------------------------------------------------------+
void CheckBuyEntry(MqlRates &c)
{
   if(buy_point_2 == 0.0) return;

   if(c.close >= buy_point_2)
   {
      double entry_price       = c.close;
      double stop_loss_price   = buy_pullback2_low;
      double risk              = entry_price - stop_loss_price;
      double take_profit_price = entry_price + (risk * 2.0);

      // V2: Check trend filter
      if(!IsTrendAllowed("BUY"))
      {
         ResetBuyState();
         return;
      }

      // V2: Check risk size
      if(!IsRiskAcceptable(risk))
      {
         ResetBuyState();
         return;
      }

      Print("[", _Symbol, "] COD BUY ENTRY: close=", DoubleToString(entry_price, _Digits),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits),
            " risk=", DoubleToString(risk, _Digits));

      ResetBuyState();
      OpenPosition("BUY", stop_loss_price, take_profit_price);
   }
   else
      Log("[" + _Symbol + "] COD BUY PHASE5 waiting: close="
          + DoubleToString(c.close, _Digits)
          + " < point_2=" + DoubleToString(buy_point_2, _Digits));
}

//+------------------------------------------------------------------+
//| Check Exit Signal                                                 |
//+------------------------------------------------------------------+
void CheckExitSignal(MqlRates &c)
{
   if(!is_position_open) return;

   if(current_position_direction == "SELL")
   {
      if(c.close >= current_position_stop_loss)  { ClosePosition("Stop Loss hit"); return; }
      if(c.close <= current_position_take_profit) { ClosePosition("Take Profit hit"); return; }
   }
   else if(current_position_direction == "BUY")
   {
      if(c.close <= current_position_stop_loss)  { ClosePosition("Stop Loss hit"); return; }
      if(c.close >= current_position_take_profit) { ClosePosition("Take Profit hit"); return; }
   }
}

//+------------------------------------------------------------------+
//| Open Position                                                     |
//+------------------------------------------------------------------+
void OpenPosition(string direction, double stop_loss_price, double take_profit_price)
{
   if(is_position_open) return;

   if(PositionsTotal() >= MAX_OPEN_POSITIONS)
   {
      Log("[" + _Symbol + "] Max open positions reached ("
          + IntegerToString(PositionsTotal()) + "/" + IntegerToString(MAX_OPEN_POSITIONS) + ")");
      return;
   }

   double entry_ref = rates[1].close;
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amt  = balance * (RISK_PERCENT / 100.0);
   double stop_dist = MathAbs(entry_ref - stop_loss_price);

   if(stop_dist <= 0.0) { Print("[", _Symbol, "] Invalid stop distance"); return; }

   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tick_value <= 0.0 || tick_size <= 0.0)
   {
      Print("[", _Symbol, "] Invalid tick_value or tick_size");
      return;
   }

   double loss_per_lot = (stop_dist / tick_size) * tick_value;
   double lot_size = NormalizeVolume(risk_amt / loss_per_lot);

   if(PAPER_TRADING_MODE)
   {
      Print("[", _Symbol, "] [PAPER] SIMULATED ", direction, " @ ",
            DoubleToString(entry_ref, _Digits),
            " lot=", DoubleToString(lot_size, 2),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits));
      is_position_open             = true;
      current_position_ticket      = 0;
      current_position_direction   = direction;
      current_position_entry_price = entry_ref;
      current_position_stop_loss   = stop_loss_price;
      current_position_take_profit = take_profit_price;
      return;
   }

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);

   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.volume    = lot_size;
   req.sl        = NormalizeDouble(stop_loss_price, _Digits);
   req.tp        = NormalizeDouble(take_profit_price, _Digits);
   req.deviation = 20;
   req.comment   = "COD V2";

   if(direction == "BUY") { req.type = ORDER_TYPE_BUY;  req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK); }
   else                   { req.type = ORDER_TYPE_SELL; req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID); }
   req.price = NormalizeDouble(req.price, _Digits);

   if(!OrderSend(req, res)) { Print("[", _Symbol, "] OrderSend failed. Error=", GetLastError(), " retcode=", res.retcode); return; }
   if(res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED) { Print("[", _Symbol, "] Order rejected. Retcode=", res.retcode); return; }

   is_position_open             = true;
   current_position_ticket      = res.deal;
   current_position_direction   = direction;
   current_position_entry_price = res.price;
   current_position_stop_loss   = stop_loss_price;
   current_position_take_profit = take_profit_price;

   Print("[", _Symbol, "] ", direction, " opened at ", DoubleToString(current_position_entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits), " TP=", DoubleToString(take_profit_price, _Digits));
}

//+------------------------------------------------------------------+
//| Close Position — with V2 consecutive loss tracking               |
//+------------------------------------------------------------------+
void ClosePosition(string close_reason)
{
   if(!is_position_open) return;

   // V2: Track consecutive losses
   if(close_reason == "Stop Loss hit")
   {
      consecutive_losses++;
      Print("[", _Symbol, "] V2: Consecutive losses = ", consecutive_losses, "/", MAX_CONSECUTIVE_LOSSES);
      if(consecutive_losses >= MAX_CONSECUTIVE_LOSSES)
      {
         trading_paused = true;
         Print("[", _Symbol, "] V2: TRADING PAUSED after ", consecutive_losses, " consecutive losses!");
      }
   }
   else if(close_reason == "Take Profit hit")
   {
      consecutive_losses = 0; // Reset counter on win
   }

   if(PAPER_TRADING_MODE)
   {
      double exit_price = rates[1].close;
      double pnl = (current_position_direction == "BUY")
                   ? (exit_price - current_position_entry_price) * 100000.0
                   : (current_position_entry_price - exit_price) * 100000.0;
      Print("[", _Symbol, "] [PAPER] SIMULATED CLOSE ", current_position_direction,
            " @ ", DoubleToString(exit_price, _Digits),
            " PnL=", DoubleToString(pnl, 2), " | ", close_reason);
      is_position_open = false; current_position_ticket = 0; current_position_direction = "";
      return;
   }

   if(!PositionSelect(_Symbol))
   {
      Print("[", _Symbol, "] No live position found");
      is_position_open = false; current_position_ticket = 0; current_position_direction = "";
      return;
   }

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);

   req.action    = TRADE_ACTION_DEAL;
   req.symbol    = _Symbol;
   req.position  = (ulong)PositionGetInteger(POSITION_TICKET);
   req.volume    = PositionGetDouble(POSITION_VOLUME);
   req.deviation = 20;
   req.comment   = close_reason;

   if(current_position_direction == "BUY") { req.type = ORDER_TYPE_SELL; req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID); }
   else                                    { req.type = ORDER_TYPE_BUY;  req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK); }
   req.price = NormalizeDouble(req.price, _Digits);

   if(!OrderSend(req, res)) { Print("[", _Symbol, "] Close failed. Error=", GetLastError(), " retcode=", res.retcode); return; }
   if(res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED) { Print("[", _Symbol, "] Close rejected. Retcode=", res.retcode); return; }

   Print("[", _Symbol, "] ", current_position_direction, " closed: ", close_reason);
   is_position_open = false; current_position_ticket = 0; current_position_direction = "";
}

//+------------------------------------------------------------------+
//| End of file                                                       |
//+------------------------------------------------------------------+
