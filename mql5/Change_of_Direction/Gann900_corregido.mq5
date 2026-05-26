//+------------------------------------------------------------------+
//| Gann900.mq5 / Change of Direction                                |
//| Reversal-based strategy using candle patterns and price action    |
//+------------------------------------------------------------------+
#property strict
#property version     "1.0"
#property description "Change of Direction - Reversal EA"
#property copyright   "AlgoTrader Pro"

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+

// Strategy Parameters
input double   PIP_VALUE              = 0.01;    // Value of 1 pip (e.g., 0.01 for XAUUSD)
input int      STOP_LOSS_PIPS         = 15;      // Stop loss distance in pips
input int      TAKE_PROFIT_PIPS       = 45;      // Take profit distance in pips
input int      MIN_RED_CANDLES        = 2;       // Min consecutive red candles
input int      MIN_GREEN_CANDLES      = 2;       // Min consecutive green candles
input bool     ALLOW_SHORT            = true;    // Enable SELL signals
input bool     ALLOW_LONG             = true;    // Enable BUY signals

// Risk Management
input double   RISK_PERCENT           = 1.0;     // Risk per trade (%)
input double   MAX_DAILY_LOSS_PCT     = 30.0;    // Max daily loss (%) - reserved
input int      MAX_OPEN_POSITIONS     = 1;       // Max concurrent positions - reserved

// Paper Trading Mode
input bool     PAPER_TRADING_MODE     = true;    // If true: only print signals (no real orders)

//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+

bool           is_position_open = false;
ulong          current_position_ticket = 0;
string         current_position_direction = "";
double         current_position_entry_price = 0.0;
double         current_position_stop_loss = 0.0;
double         current_position_take_profit = 0.0;

datetime       last_tick_time = 0;
double         daily_pnl = 0.0;
bool           daily_loss_triggered = false;

MqlRates       rates[];

//+------------------------------------------------------------------+
//| Load candle data                                                  |
//+------------------------------------------------------------------+
bool UpdateRates(const int candles = 100)
{
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, _Period, 0, candles, rates);

   if(copied <= 0)
   {
      Print("[", _Symbol, "] CopyRates failed. Error=", GetLastError());
      return false;
   }

   return copied >= MathMin(candles, Bars(_Symbol, _Period));
}

//+------------------------------------------------------------------+
//| Normalize volume according to symbol settings                     |
//+------------------------------------------------------------------+
double NormalizeVolume(double volume)
{
   double min_volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step       = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(step <= 0.0)
      step = 0.01;

   volume = MathMax(min_volume, MathMin(volume, max_volume));
   volume = MathFloor(volume / step) * step;

   return NormalizeDouble(volume, 2);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("[", _Symbol, "] Change of Direction initialized");
   Print("  SL=", STOP_LOSS_PIPS, " pips, TP=", TAKE_PROFIT_PIPS, " pips");
   Print("  ALLOW_SHORT=", ALLOW_SHORT, " ALLOW_LONG=", ALLOW_LONG);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                  |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("[", _Symbol, "] Change of Direction deinitialized. Reason=", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!UpdateRates())
      return;

   double current_bid_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(is_position_open)
   {
      if(CheckExitSignal(current_bid_price))
         return;
   }
   else
   {
      CheckEntrySignal();
   }
}

//+------------------------------------------------------------------+
//| Check Entry Signal                                                |
//+------------------------------------------------------------------+
void CheckEntrySignal()
{
   if(Bars(_Symbol, _Period) < 10 || ArraySize(rates) < 10)
      return;

   if(ALLOW_SHORT && DetectSellSetup())
      return;

   if(ALLOW_LONG && DetectBuySetup())
      return;
}

//+------------------------------------------------------------------+
//| Detect SELL Setup                                                 |
//+------------------------------------------------------------------+
bool DetectSellSetup()
{
   int total_rates = ArraySize(rates);
   if(total_rates < MIN_RED_CANDLES + 2)
      return false;

   int consecutive_red_candles = 0;

   for(int i = 1; i < total_rates; i++)
   {
      if(rates[i].close < rates[i].open)
         consecutive_red_candles++;
      else
         break;
   }

   if(consecutive_red_candles < MIN_RED_CANDLES)
      return false;

   int first_red_candle_index = consecutive_red_candles;
   if(first_red_candle_index >= total_rates)
      return false;

   double first_red_candle_open = rates[first_red_candle_index].open;
   double current_candle_close  = rates[0].close;
   double current_candle_open   = rates[0].open;

   if(current_candle_close <= current_candle_open)
      return false;

   if(current_candle_close <= first_red_candle_open)
      return false;

   double point_of_change_direction = current_candle_open;
   double current_candle_low = rates[0].low;

   if(current_candle_low >= point_of_change_direction)
      return false;

   double new_point_of_change_direction = current_candle_low;

   if(current_candle_close > new_point_of_change_direction)
      return false;

   double entry_price = current_candle_close;
   double stop_loss_price = entry_price + (STOP_LOSS_PIPS * PIP_VALUE);
   double take_profit_price = entry_price - (TAKE_PROFIT_PIPS * PIP_VALUE);

   Print("[", _Symbol, "] COD SELL: Reversal confirmed. entry=",
         DoubleToString(entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits),
         " TP=", DoubleToString(take_profit_price, _Digits));

   OpenPosition("SELL", stop_loss_price, take_profit_price);
   return true;
}

//+------------------------------------------------------------------+
//| Detect BUY Setup                                                  |
//+------------------------------------------------------------------+
bool DetectBuySetup()
{
   int total_rates = ArraySize(rates);
   if(total_rates < MIN_GREEN_CANDLES + 2)
      return false;

   int consecutive_green_candles = 0;

   for(int i = 1; i < total_rates; i++)
   {
      if(rates[i].close > rates[i].open)
         consecutive_green_candles++;
      else
         break;
   }

   if(consecutive_green_candles < MIN_GREEN_CANDLES)
      return false;

   int first_green_candle_index = consecutive_green_candles;
   if(first_green_candle_index >= total_rates)
      return false;

   double first_green_candle_open = rates[first_green_candle_index].open;
   double current_candle_close    = rates[0].close;
   double current_candle_open     = rates[0].open;

   if(current_candle_close >= current_candle_open)
      return false;

   if(current_candle_close >= first_green_candle_open)
      return false;

   double point_of_change_direction = current_candle_open;
   double current_candle_high = rates[0].high;

   if(current_candle_high <= point_of_change_direction)
      return false;

   double new_point_of_change_direction = current_candle_high;

   if(current_candle_close < new_point_of_change_direction)
      return false;

   double entry_price = current_candle_close;
   double stop_loss_price = entry_price - (STOP_LOSS_PIPS * PIP_VALUE);
   double take_profit_price = entry_price + (TAKE_PROFIT_PIPS * PIP_VALUE);

   Print("[", _Symbol, "] COD BUY: Reversal confirmed. entry=",
         DoubleToString(entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits),
         " TP=", DoubleToString(take_profit_price, _Digits));

   OpenPosition("BUY", stop_loss_price, take_profit_price);
   return true;
}

//+------------------------------------------------------------------+
//| Check Exit Signal                                                 |
//+------------------------------------------------------------------+
bool CheckExitSignal(double current_bid_price)
{
   if(!is_position_open)
      return false;

   double current_candle_close = rates[0].close;

   if(current_position_direction == "SELL")
   {
      if(current_candle_close >= current_position_stop_loss)
      {
         ClosePosition("Stop Loss hit");
         return true;
      }

      if(current_candle_close <= current_position_take_profit)
      {
         ClosePosition("Take Profit hit");
         return true;
      }
   }
   else if(current_position_direction == "BUY")
   {
      if(current_candle_close <= current_position_stop_loss)
      {
         ClosePosition("Stop Loss hit");
         return true;
      }

      if(current_candle_close >= current_position_take_profit)
      {
         ClosePosition("Take Profit hit");
         return true;
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Open Position                                                     |
//+------------------------------------------------------------------+
void OpenPosition(string direction, double stop_loss_price, double take_profit_price)
{
   if(is_position_open)
      return;

   double entry_reference_price = rates[0].close;
   double account_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = account_balance * (RISK_PERCENT / 100.0);
   double stop_distance = MathAbs(entry_reference_price - stop_loss_price);

   if(stop_distance <= 0.0)
   {
      Print("[", _Symbol, "] Invalid stop distance");
      return;
   }

   double calculated_lot_size = risk_amount / stop_distance;
   calculated_lot_size = NormalizeVolume(calculated_lot_size);

   if(PAPER_TRADING_MODE)
   {
      Print("[", _Symbol, "] [PAPER] SIMULATED ", direction, " @ ",
            DoubleToString(entry_reference_price, _Digits),
            " lot=", DoubleToString(calculated_lot_size, 2),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits));

      is_position_open = true;
      current_position_ticket = 0;
      current_position_direction = direction;
      current_position_entry_price = entry_reference_price;
      current_position_stop_loss = stop_loss_price;
      current_position_take_profit = take_profit_price;
      return;
   }

   MqlTradeRequest trade_request;
   MqlTradeResult trade_result;
   ZeroMemory(trade_request);
   ZeroMemory(trade_result);

   trade_request.action = TRADE_ACTION_DEAL;
   trade_request.symbol = _Symbol;
   trade_request.volume = calculated_lot_size;
   trade_request.sl = NormalizeDouble(stop_loss_price, _Digits);
   trade_request.tp = NormalizeDouble(take_profit_price, _Digits);
   trade_request.deviation = 20;
   trade_request.comment = "Change of Direction";

   if(direction == "BUY")
   {
      trade_request.type = ORDER_TYPE_BUY;
      trade_request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   }
   else
   {
      trade_request.type = ORDER_TYPE_SELL;
      trade_request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   }

   trade_request.price = NormalizeDouble(trade_request.price, _Digits);

   if(!OrderSend(trade_request, trade_result))
   {
      Print("[", _Symbol, "] OrderSend failed. Error=", GetLastError(),
            " retcode=", trade_result.retcode);
      return;
   }

   if(trade_result.retcode != TRADE_RETCODE_DONE && trade_result.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[", _Symbol, "] Order rejected. Retcode=", trade_result.retcode);
      return;
   }

   is_position_open = true;
   current_position_ticket = trade_result.deal;
   current_position_direction = direction;
   current_position_entry_price = trade_result.price;
   current_position_stop_loss = stop_loss_price;
   current_position_take_profit = take_profit_price;

   Print("[", _Symbol, "] ", direction, " opened at ",
         DoubleToString(current_position_entry_price, _Digits),
         " SL=", DoubleToString(stop_loss_price, _Digits),
         " TP=", DoubleToString(take_profit_price, _Digits));
}

//+------------------------------------------------------------------+
//| Close Position                                                    |
//+------------------------------------------------------------------+
void ClosePosition(string close_reason)
{
   if(!is_position_open)
      return;

   if(PAPER_TRADING_MODE)
   {
      double exit_price = rates[0].close;
      double pnl = 0.0;

      if(current_position_direction == "BUY")
         pnl = (exit_price - current_position_entry_price) * 100000.0;
      else
         pnl = (current_position_entry_price - exit_price) * 100000.0;

      Print("[", _Symbol, "] [PAPER] SIMULATED CLOSE ", current_position_direction,
            " @ ", DoubleToString(exit_price, _Digits),
            " PnL=", DoubleToString(pnl, 2),
            " | ", close_reason);

      is_position_open = false;
      current_position_ticket = 0;
      current_position_direction = "";
      return;
   }

   if(!PositionSelect(_Symbol))
   {
      Print("[", _Symbol, "] No live position found to close");
      is_position_open = false;
      current_position_ticket = 0;
      current_position_direction = "";
      return;
   }

   MqlTradeRequest trade_request;
   MqlTradeResult trade_result;
   ZeroMemory(trade_request);
   ZeroMemory(trade_result);

   trade_request.action = TRADE_ACTION_DEAL;
   trade_request.symbol = _Symbol;
   trade_request.position = (ulong)PositionGetInteger(POSITION_TICKET);
   trade_request.volume = PositionGetDouble(POSITION_VOLUME);
   trade_request.deviation = 20;
   trade_request.comment = close_reason;

   if(current_position_direction == "BUY")
   {
      trade_request.type = ORDER_TYPE_SELL;
      trade_request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   }
   else
   {
      trade_request.type = ORDER_TYPE_BUY;
      trade_request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   }

   trade_request.price = NormalizeDouble(trade_request.price, _Digits);

   if(!OrderSend(trade_request, trade_result))
   {
      Print("[", _Symbol, "] Close failed. Error=", GetLastError(),
            " retcode=", trade_result.retcode);
      return;
   }

   if(trade_result.retcode != TRADE_RETCODE_DONE && trade_result.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[", _Symbol, "] Close rejected. Retcode=", trade_result.retcode);
      return;
   }

   Print("[", _Symbol, "] ", current_position_direction, " closed: ", close_reason);

   is_position_open = false;
   current_position_ticket = 0;
   current_position_direction = "";
}

//+------------------------------------------------------------------+
//| End of file                                                       |
//+------------------------------------------------------------------+
