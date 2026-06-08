//+------------------------------------------------------------------+
//| Change of Direction MultiPattern Pullback.mq5                     |
//| Multi-pattern with risk-based trailing stop                      |
//+------------------------------------------------------------------+
#property strict
#property version     "1.0"
#property description "COD MultiPattern with 1xRisk Trailing Stop"
#property copyright   "AlgoTrader Pro"

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+
input int      MIN_RED_CANDLES        = 2;       // Min consecutive red candles
input int      MIN_GREEN_CANDLES      = 2;       // Min green candles per pullback
input bool     ALLOW_SHORT            = true;    // Enable SELL signals
input bool     ALLOW_LONG             = true;    // Enable BUY signals
input double   RISK_PERCENT           = 1.0;     // Risk per trade (%)
input int      MAX_OPEN_POSITIONS     = 1;       // Max concurrent positions
input bool     PAPER_TRADING_MODE     = false;   // Paper trading mode
input bool     DEBUG_LOGS             = false;   // Debug logs
input double   EMA_BUFFER_PCT         = 0.2;     // EMA neutral zone buffer (%)

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
#define PHASE_INVALID     99

//+------------------------------------------------------------------+
//| Pattern Structure                                                 |
//+------------------------------------------------------------------+
struct Pattern
{
   int      id;
   string   direction;
   int      phase;
   
   // SELL state
   double   point_1;
   int      red_count;
   int      green1_count;
   double   pullback1_high;
   int      green2_count;
   double   pullback2_high;
   double   point_2;
   
   // BUY state
   int      green_count;
   int      red1_count;
   double   pullback1_low;
   int      red2_count;
   double   pullback2_low;
};

//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+
Pattern  sell_patterns[];
Pattern  buy_patterns[];
int      next_pattern_id = 1;

bool           is_position_open            = false;
ulong          current_position_ticket     = 0;
string         current_position_direction  = "";
double         current_position_entry_price = 0.0;
double         current_position_stop_loss  = 0.0;
double         current_position_take_profit = 0.0;
double         initial_risk                = 0.0;      // Initial risk in points
int            risk_levels_passed          = 0;        // How many 1xRisk levels passed

int            ema40_handle             = INVALID_HANDLE;
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
//| Get EMA40 value from M5 timeframe                                |
//+------------------------------------------------------------------+
double GetEMA40_M5()
{
   if(ema40_handle == INVALID_HANDLE) return 0.0;
   double ema_buf[];
   ArraySetAsSeries(ema_buf, true);
   if(CopyBuffer(ema40_handle, 0, 0, 1, ema_buf) <= 0) return 0.0;
   return ema_buf[0];
}

//+------------------------------------------------------------------+
//| Check if BUY is allowed based on trend                           |
//+------------------------------------------------------------------+
bool IsTrendBuyAllowed()
{
   if(!ALLOW_LONG) return false;
   double ema40 = GetEMA40_M5();
   if(ema40 <= 0.0) return true;
   
   double current_price = rates[1].close;
   double upper_zone = ema40 * (1.0 + EMA_BUFFER_PCT / 100.0);
   double lower_zone = ema40 * (1.0 - EMA_BUFFER_PCT / 100.0);
   
   if(current_price > upper_zone)
   {
      Log("[" + _Symbol + "] BUY allowed: price=" + DoubleToString(current_price, _Digits) 
          + " > upper_zone=" + DoubleToString(upper_zone, _Digits));
      return true;
   }
   
   Log("[" + _Symbol + "] BUY blocked: price in neutral zone");
   return false;
}

//+------------------------------------------------------------------+
//| Check if SELL is allowed based on trend                          |
//+------------------------------------------------------------------+
bool IsTrendSellAllowed()
{
   if(!ALLOW_SHORT) return false;
   double ema40 = GetEMA40_M5();
   if(ema40 <= 0.0) return true;
   
   double current_price = rates[1].close;
   double upper_zone = ema40 * (1.0 + EMA_BUFFER_PCT / 100.0);
   double lower_zone = ema40 * (1.0 - EMA_BUFFER_PCT / 100.0);
   
   if(current_price < lower_zone)
   {
      Log("[" + _Symbol + "] SELL allowed: price=" + DoubleToString(current_price, _Digits) 
          + " < lower_zone=" + DoubleToString(lower_zone, _Digits));
      return true;
   }
   
   Log("[" + _Symbol + "] SELL blocked: price in neutral zone");
   return false;
}

//+------------------------------------------------------------------+
//| Reset all patterns                                                |
//+------------------------------------------------------------------+
void ResetAllPatterns()
{
   ArrayResize(sell_patterns, 0);
   ArrayResize(buy_patterns, 0);
   Log("[" + _Symbol + "] All patterns reset");
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   ema40_handle = iMA(_Symbol, PERIOD_M5, 40, 0, MODE_EMA, PRICE_CLOSE);
   if(ema40_handle == INVALID_HANDLE)
      Print("[", _Symbol, "] WARNING: Failed to create EMA40 M5 handle.");
   else
      Print("[", _Symbol, "] EMA40 M5 trend filter initialized.");

   ArrayResize(sell_patterns, 0);
   ArrayResize(buy_patterns, 0);
   
   Print("[", _Symbol, "] COD MultiPattern Pullback v1.0 initialized | "
         "MIN_RED=", MIN_RED_CANDLES, " MIN_GREEN=", MIN_GREEN_CANDLES);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(ema40_handle != INVALID_HANDLE)
      IndicatorRelease(ema40_handle);
   Log("[" + _Symbol + "] COD MultiPattern Pullback deinitialized.");
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!UpdateRates()) return;

   static datetime last_candle_time = 0;
   if(rates[1].time == last_candle_time) return;
   last_candle_time = rates[1].time;

   MqlRates candle = rates[1];

   if(is_position_open)
   {
      UpdateTrailingStop(candle);
      CheckExitSignal(candle);
   }
   else
   {
      UpdateAllSellPatterns(candle);
      UpdateAllBuyPatterns(candle);
   }
}

//+------------------------------------------------------------------+
//| Update Trailing Stop based on 1xRisk levels                      |
//+------------------------------------------------------------------+
void UpdateTrailingStop(MqlRates &c)
{
   if(!is_position_open || initial_risk <= 0.0) return;
   
   double current_price = c.close;
   double profit_points = 0.0;
   
   if(current_position_direction == "BUY")
   {
      profit_points = current_price - current_position_entry_price;
   }
   else if(current_position_direction == "SELL")
   {
      profit_points = current_position_entry_price - current_price;
   }
   
   // Calculate how many risk levels we've passed
   int current_level = (int)MathFloor(profit_points / initial_risk);
   
   // If we've passed a new risk level, update SL and TP (less aggressive: 0.5x risk per level)
   if(current_level > risk_levels_passed && current_level >= 1)
   {
      risk_levels_passed = current_level;
      
      double new_stop_loss;
      double new_take_profit;
      
      if(current_position_direction == "BUY")
      {
         // Move SL up by 0.5x risk (less aggressive)
         new_stop_loss = current_position_entry_price + ((risk_levels_passed * 0.5) * initial_risk);
         // Move TP out by 1x risk
         new_take_profit = current_position_entry_price + ((risk_levels_passed + 2) * initial_risk);
      }
      else // SELL
      {
         // Move SL down by 0.5x risk (less aggressive)
         new_stop_loss = current_position_entry_price - ((risk_levels_passed * 0.5) * initial_risk);
         // Move TP out by 1x risk
         new_take_profit = current_position_entry_price - ((risk_levels_passed + 2) * initial_risk);
      }
      
      Print("[", _Symbol, "] Trailing Stop Update: Level ", risk_levels_passed, 
            " passed | New SL=", DoubleToString(new_stop_loss, _Digits),
            " New TP=", DoubleToString(new_take_profit, _Digits));
      
      // Update position
      if(!PAPER_TRADING_MODE)
      {
         if(ModifyPosition(new_stop_loss, new_take_profit))
         {
            current_position_stop_loss = new_stop_loss;
            current_position_take_profit = new_take_profit;
         }
      }
      else
      {
         current_position_stop_loss = new_stop_loss;
         current_position_take_profit = new_take_profit;
      }
   }
}

//+------------------------------------------------------------------+
//| Modify Position SL/TP                                             |
//+------------------------------------------------------------------+
bool ModifyPosition(double new_sl, double new_tp)
{
   if(!PositionSelect(_Symbol)) return false;
   
   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);
   
   req.action = TRADE_ACTION_SLTP;
   req.symbol = _Symbol;
   req.position = current_position_ticket;
   req.sl = NormalizeDouble(new_sl, _Digits);
   req.tp = NormalizeDouble(new_tp, _Digits);
   
   if(!OrderSend(req, res))
   {
      Print("[", _Symbol, "] ModifyPosition failed. Error=", GetLastError());
      return false;
   }
   
   if(res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[", _Symbol, "] Modify rejected. Retcode=", res.retcode);
      return false;
   }
   
   return true;
}

//+------------------------------------------------------------------+
//| Update All SELL Patterns                                          |
//+------------------------------------------------------------------+
void UpdateAllSellPatterns(MqlRates &c)
{
   bool is_red   = c.close < c.open;
   bool is_green = c.close > c.open;

   if(is_red)
   {
      int idx = ArraySize(sell_patterns);
      ArrayResize(sell_patterns, idx + 1);
      
      sell_patterns[idx].id              = next_pattern_id++;
      sell_patterns[idx].direction       = "SELL";
      sell_patterns[idx].phase           = PHASE1_DROP;
      sell_patterns[idx].point_1         = c.low;
      sell_patterns[idx].red_count       = 1;
      sell_patterns[idx].green1_count    = 0;
      sell_patterns[idx].pullback1_high  = 0.0;
      sell_patterns[idx].green2_count    = 0;
      sell_patterns[idx].pullback2_high  = 0.0;
      sell_patterns[idx].point_2         = 0.0;
      
      Log("[" + _Symbol + "] Pattern #" + IntegerToString(sell_patterns[idx].id) 
          + ": SELL PHASE1 started");
   }

   for(int i = 0; i < ArraySize(sell_patterns); i++)
   {
      if(UpdateSingleSellPattern(sell_patterns[i], c))
      {
         ResetAllPatterns();
         return;
      }
   }

   RemoveInvalidPatterns(sell_patterns);
}

//+------------------------------------------------------------------+
//| Update Single SELL Pattern                                        |
//+------------------------------------------------------------------+
bool UpdateSingleSellPattern(Pattern &p, MqlRates &c)
{
   bool is_red   = c.close < c.open;
   bool is_green = c.close > c.open;

   if(p.phase == PHASE1_DROP)
   {
      if(is_red)
      {
         p.red_count++;
         p.point_1 = MathMin(p.point_1, c.low);
      }
      else if(is_green && p.red_count >= MIN_RED_CANDLES)
      {
         p.phase = PHASE2_PULLBACK1;
         p.green1_count = 1;
         p.pullback1_high = c.high;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE2");
      }
      else
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE1");
      }
      return false;
   }

   if(p.phase == PHASE2_PULLBACK1)
   {
      if(is_green)
      {
         if(p.green1_count >= 1 && c.close < p.point_1)
         {
            p.phase = PHASE_INVALID;
            Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
                + ": INVALIDATED in PHASE2 - broke point_1");
            return false;
         }
         p.green1_count++;
         p.pullback1_high = MathMax(p.pullback1_high, c.high);
      }
      else if(is_red && p.green1_count >= MIN_GREEN_CANDLES)
      {
         p.phase = PHASE3_BREAK;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE3");
         if(c.close < p.point_1)
         {
            p.phase = PHASE4_PULLBACK2;
            p.green2_count = 0;
            p.pullback2_high = c.high;
            p.point_2 = 0.0;
            Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE4 (immediate)");
         }
      }
      return false;
   }

   if(p.phase == PHASE3_BREAK)
   {
      if(p.pullback1_high > 0.0 && c.close > p.pullback1_high)
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE3");
         return false;
      }
      if(c.close < p.point_1)
      {
         p.phase = PHASE4_PULLBACK2;
         p.green2_count = 0;
         p.pullback2_high = c.high;
         p.point_2 = 0.0;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE4");
      }
      return false;
   }

   if(p.phase == PHASE4_PULLBACK2)
   {
      if(p.pullback1_high > 0.0 && c.close > p.pullback1_high)
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE4");
         return false;
      }
      if(is_green)
      {
         if(p.green2_count >= 1 && c.close < p.point_1)
         {
            p.phase = PHASE_INVALID;
            Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
                + ": INVALIDATED in PHASE4 - broke point_1");
            return false;
         }
         p.green2_count++;
         p.pullback2_high = MathMax(p.pullback2_high, c.high);
         if(p.point_2 == 0.0) p.point_2 = c.low;
         else                 p.point_2 = MathMin(p.point_2, c.low);
      }
      else if(is_red && p.green2_count >= MIN_GREEN_CANDLES)
      {
         p.phase = PHASE5_ENTRY;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE5");
         if(p.point_2 > 0.0 && c.close <= p.point_2)
         {
            return GenerateSellEntry(p, c.close);
         }
      }
      return false;
   }

   if(p.phase == PHASE5_ENTRY)
   {
      if(p.pullback1_high > 0.0 && c.close > p.pullback1_high)
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE5");
         return false;
      }
      if(p.point_2 > 0.0 && c.close <= p.point_2)
      {
         return GenerateSellEntry(p, c.close);
      }
      return false;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Generate SELL Entry                                               |
//+------------------------------------------------------------------+
bool GenerateSellEntry(Pattern &p, double entry_price)
{
   if(!IsTrendSellAllowed())
   {
      p.phase = PHASE_INVALID;
      Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
          + ": SELL BLOCKED by trend filter");
      return false;
   }
   
   double stop_loss_price   = p.pullback2_high;
   double risk              = stop_loss_price - entry_price;
   double take_profit_price = entry_price - (risk * 2.0);

   Print("[", _Symbol, "] Pattern #", p.id, " SELL ENTRY: close=", DoubleToString(entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits),
         " TP=", DoubleToString(take_profit_price, _Digits),
         " risk=", DoubleToString(risk, _Digits));

   OpenPosition("SELL", stop_loss_price, take_profit_price, risk);
   return true;
}

//+------------------------------------------------------------------+
//| Update All BUY Patterns                                           |
//+------------------------------------------------------------------+
void UpdateAllBuyPatterns(MqlRates &c)
{
   bool is_green = c.close > c.open;
   bool is_red   = c.close < c.open;

   if(is_green)
   {
      int idx = ArraySize(buy_patterns);
      ArrayResize(buy_patterns, idx + 1);
      
      buy_patterns[idx].id              = next_pattern_id++;
      buy_patterns[idx].direction       = "BUY";
      buy_patterns[idx].phase           = PHASE1_DROP;
      buy_patterns[idx].point_1         = c.high;
      buy_patterns[idx].green_count     = 1;
      buy_patterns[idx].red1_count      = 0;
      buy_patterns[idx].pullback1_low   = 0.0;
      buy_patterns[idx].red2_count      = 0;
      buy_patterns[idx].pullback2_low   = 0.0;
      buy_patterns[idx].point_2         = 0.0;
      
      Log("[" + _Symbol + "] Pattern #" + IntegerToString(buy_patterns[idx].id) 
          + ": BUY PHASE1 started");
   }

   for(int i = 0; i < ArraySize(buy_patterns); i++)
   {
      if(UpdateSingleBuyPattern(buy_patterns[i], c))
      {
         ResetAllPatterns();
         return;
      }
   }

   RemoveInvalidPatterns(buy_patterns);
}

//+------------------------------------------------------------------+
//| Update Single BUY Pattern                                         |
//+------------------------------------------------------------------+
bool UpdateSingleBuyPattern(Pattern &p, MqlRates &c)
{
   bool is_green = c.close > c.open;
   bool is_red   = c.close < c.open;

   if(p.phase == PHASE1_DROP)
   {
      if(is_green)
      {
         p.green_count++;
         p.point_1 = MathMax(p.point_1, c.high);
      }
      else if(is_red && p.green_count >= MIN_GREEN_CANDLES)
      {
         p.phase = PHASE2_PULLBACK1;
         p.red1_count = 1;
         p.pullback1_low = c.low;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE2");
      }
      else
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE1");
      }
      return false;
   }

   if(p.phase == PHASE2_PULLBACK1)
   {
      if(is_red)
      {
         if(p.red1_count >= 1 && c.close > p.point_1)
         {
            p.phase = PHASE_INVALID;
            Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
                + ": INVALIDATED in PHASE2 - broke point_1");
            return false;
         }
         p.red1_count++;
         p.pullback1_low = MathMin(p.pullback1_low, c.low);
      }
      else if(is_green && p.red1_count >= MIN_RED_CANDLES)
      {
         p.phase = PHASE3_BREAK;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE3");
         if(c.close > p.point_1)
         {
            p.phase = PHASE4_PULLBACK2;
            p.red2_count = 0;
            p.pullback2_low = c.low;
            p.point_2 = 0.0;
            Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE4 (immediate)");
         }
      }
      return false;
   }

   if(p.phase == PHASE3_BREAK)
   {
      if(p.pullback1_low > 0.0 && c.close < p.pullback1_low)
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE3");
         return false;
      }
      if(c.close > p.point_1)
      {
         p.phase = PHASE4_PULLBACK2;
         p.red2_count = 0;
         p.pullback2_low = c.low;
         p.point_2 = 0.0;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE4");
      }
      return false;
   }

   if(p.phase == PHASE4_PULLBACK2)
   {
      if(p.pullback1_low > 0.0 && c.close < p.pullback1_low)
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE4");
         return false;
      }
      if(is_red)
      {
         if(p.red2_count >= 1 && c.close > p.point_1)
         {
            p.phase = PHASE_INVALID;
            Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
                + ": INVALIDATED in PHASE4 - broke point_1");
            return false;
         }
         p.red2_count++;
         p.pullback2_low = MathMin(p.pullback2_low, c.low);
         if(p.point_2 == 0.0) p.point_2 = c.high;
         else                 p.point_2 = MathMax(p.point_2, c.high);
      }
      else if(is_green && p.red2_count >= MIN_RED_CANDLES)
      {
         p.phase = PHASE5_ENTRY;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) + ": → PHASE5");
         if(p.point_2 > 0.0 && c.close >= p.point_2)
         {
            return GenerateBuyEntry(p, c.close);
         }
      }
      return false;
   }

   if(p.phase == PHASE5_ENTRY)
   {
      if(p.pullback1_low > 0.0 && c.close < p.pullback1_low)
      {
         p.phase = PHASE_INVALID;
         Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
             + ": INVALIDATED in PHASE5");
         return false;
      }
      if(p.point_2 > 0.0 && c.close >= p.point_2)
      {
         return GenerateBuyEntry(p, c.close);
      }
      return false;
   }

   return false;
}

//+------------------------------------------------------------------+
//| Generate BUY Entry                                                |
//+------------------------------------------------------------------+
bool GenerateBuyEntry(Pattern &p, double entry_price)
{
   if(!IsTrendBuyAllowed())
   {
      p.phase = PHASE_INVALID;
      Log("[" + _Symbol + "] Pattern #" + IntegerToString(p.id) 
          + ": BUY BLOCKED by trend filter");
      return false;
   }
   
   double stop_loss_price   = p.pullback2_low;
   double risk              = entry_price - stop_loss_price;
   double take_profit_price = entry_price + (risk * 2.0);

   Print("[", _Symbol, "] Pattern #", p.id, " BUY ENTRY: close=", DoubleToString(entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits),
         " TP=", DoubleToString(take_profit_price, _Digits),
         " risk=", DoubleToString(risk, _Digits));

   OpenPosition("BUY", stop_loss_price, take_profit_price, risk);
   return true;
}

//+------------------------------------------------------------------+
//| Remove Invalid Patterns                                           |
//+------------------------------------------------------------------+
void RemoveInvalidPatterns(Pattern &patterns[])
{
   int valid_count = 0;
   int size = ArraySize(patterns);
   
   for(int i = 0; i < size; i++)
   {
      if(patterns[i].phase != PHASE_INVALID)
      {
         if(valid_count != i)
            patterns[valid_count] = patterns[i];
         valid_count++;
      }
   }
   
   ArrayResize(patterns, valid_count);
}

//+------------------------------------------------------------------+
//| Check Exit Signal                                                 |
//+------------------------------------------------------------------+
void CheckExitSignal(MqlRates &c)
{
   if(!is_position_open) return;
   
   if(!PAPER_TRADING_MODE)
   {
      bool position_exists = false;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(PositionSelectByTicket(current_position_ticket))
         {
            position_exists = true;
            break;
         }
      }
      
      if(!position_exists)
      {
         Print("[", _Symbol, "] Position closed automatically (SL/TP)");
         is_position_open = false;
         return;
      }
   }

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
void OpenPosition(string direction, double stop_loss_price, double take_profit_price, double risk)
{
   if(is_position_open) return;

   if(PositionsTotal() >= MAX_OPEN_POSITIONS)
   {
      Log("[" + _Symbol + "] Max open positions reached");
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
   
   if(_Symbol == "XAUUSD" && tick_value < 0.5)
   {
      loss_per_lot = loss_per_lot * 10.0;
   }
   
   double lot_size = NormalizeVolume(risk_amt / loss_per_lot);

   // Store initial risk for trailing stop
   initial_risk = risk;
   risk_levels_passed = 0;

   if(PAPER_TRADING_MODE)
   {
      Print("[", _Symbol, "] [PAPER] ", direction, " @ ",
            DoubleToString(entry_ref, _Digits),
            " lot=", DoubleToString(lot_size, 2),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits),
            " Risk=", DoubleToString(risk, _Digits));
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
   req.comment   = "COD MultiPattern PB";

   if(direction == "BUY") { req.type = ORDER_TYPE_BUY;  req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK); }
   else                   { req.type = ORDER_TYPE_SELL; req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID); }
   req.price = NormalizeDouble(req.price, _Digits);

   if(!OrderSend(req, res))
   {
      Print("[", _Symbol, "] OrderSend failed. Error=", GetLastError(), " retcode=", res.retcode);
      return;
   }
   
   if(res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[", _Symbol, "] Order rejected. Retcode=", res.retcode);
      return;
   }

   is_position_open             = true;
   current_position_ticket      = res.deal;
   current_position_direction   = direction;
   current_position_entry_price = res.price;
   current_position_stop_loss   = stop_loss_price;
   current_position_take_profit = take_profit_price;

   Print("[", _Symbol, "] ", direction, " opened at ", DoubleToString(current_position_entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits),
         " TP=", DoubleToString(take_profit_price, _Digits),
         " Risk=", DoubleToString(risk, _Digits));
}

//+------------------------------------------------------------------+
//| Close Position                                                    |
//+------------------------------------------------------------------+
void ClosePosition(string close_reason)
{
   if(!is_position_open) return;

   if(PAPER_TRADING_MODE)
   {
      double exit_price = rates[1].close;
      double pnl = (current_position_direction == "BUY")
                   ? (exit_price - current_position_entry_price) * 100000.0
                   : (current_position_entry_price - exit_price) * 100000.0;
      
      Print("[", _Symbol, "] [PAPER] ", current_position_direction, " closed. ",
            close_reason, " | Entry=", DoubleToString(current_position_entry_price, _Digits),
            " Exit=", DoubleToString(exit_price, _Digits),
            " PnL=", DoubleToString(pnl, 2), " points");
      
      is_position_open = false;
      initial_risk = 0.0;
      risk_levels_passed = 0;
      return;
   }

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);

   req.action   = TRADE_ACTION_DEAL;
   req.symbol   = _Symbol;
   req.position = current_position_ticket;
   req.deviation = 20;

   if(current_position_direction == "BUY")
   {
      req.type  = ORDER_TYPE_SELL;
      req.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   }
   else
   {
      req.type  = ORDER_TYPE_BUY;
      req.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   }

   req.price = NormalizeDouble(req.price, _Digits);
   
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(PositionSelectByTicket(current_position_ticket))
      {
         req.volume = PositionGetDouble(POSITION_VOLUME);
         break;
      }
   }

   if(!OrderSend(req, res))
   {
      Print("[", _Symbol, "] Close failed. Error=", GetLastError());
      return;
   }

   Print("[", _Symbol, "] Position closed. ", close_reason);
   is_position_open = false;
   initial_risk = 0.0;
   risk_levels_passed = 0;
}
//+------------------------------------------------------------------+
