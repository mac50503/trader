//+------------------------------------------------------------------+
//| EMA Pullback Pro.mq5                                             |
//| Trend-following strategy using EMA pullback + dynamic trailing   |
//| stop. Identical logic to the Python implementation.              |
//+------------------------------------------------------------------+
#property strict
#property version   "1.0"
#property description "EMA Pullback Pro — Trend Following EA"
#property author    "AlgoTrader Pro"

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+

// Strategy Parameters
input int      EMA_FAST              = 21;      // Fast EMA period
input int      EMA_SLOW              = 50;      // Slow EMA period
input double   EXIT_PCT_BELOW_EMA    = 0.3;     // Exit % below/above EMA
input bool     ALLOW_SHORT           = false;   // Enable short selling
input int      ATR_PERIOD            = 14;      // ATR period

// Risk Management
input double   RISK_PERCENT          = 1.0;     // Risk per trade (%)
input double   MAX_DAILY_LOSS_PCT    = 3.0;     // Max daily loss (%) - reserved
input int      MAX_OPEN_POSITIONS    = 3;       // Max concurrent positions (all broker positions)

// Behavior
input int      TICK_INTERVAL         = 5;       // Seconds between ticks (for testing)
input bool     USE_RSI_FILTER        = false;   // Enable RSI filter
input int      RSI_PERIOD            = 14;      // RSI period

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+

int            ema_fast_handle;
int            ema_slow_handle;
int            atr_handle;
int            rsi_handle;

double         ema_fast_buffer[];
double         ema_slow_buffer[];
double         atr_buffer[];
double         rsi_buffer[];

bool           position_open = false;
ulong          position_ticket = 0;
string         position_direction = "";
double         position_entry_price = 0.0;
double         position_stop_loss = 0.0;

datetime       last_tick_time = 0;

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
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
    // Create indicator handles
    ema_fast_handle = iMA(_Symbol, _Period, EMA_FAST, 0, MODE_EMA, PRICE_CLOSE);
    ema_slow_handle = iMA(_Symbol, _Period, EMA_SLOW, 0, MODE_EMA, PRICE_CLOSE);
    atr_handle      = iATR(_Symbol, _Period, ATR_PERIOD);
    
    if (USE_RSI_FILTER) {
        rsi_handle = iRSI(_Symbol, _Period, RSI_PERIOD, PRICE_CLOSE);
    }
    
    // Validate handles
    if (ema_fast_handle == INVALID_HANDLE || 
        ema_slow_handle == INVALID_HANDLE || 
        atr_handle == INVALID_HANDLE) {
        Alert("Failed to create indicator handles");
        return INIT_FAILED;
    }
    
    Print("[", _Symbol, "] EMA Pullback Pro initialized");
    Print("  EMA_FAST=", EMA_FAST, " EMA_SLOW=", EMA_SLOW);
    Print("  EXIT_PCT=", EXIT_PCT_BELOW_EMA, "% ALLOW_SHORT=", ALLOW_SHORT);
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
    // Release indicator handles
    IndicatorRelease(ema_fast_handle);
    IndicatorRelease(ema_slow_handle);
    IndicatorRelease(atr_handle);
    if (USE_RSI_FILTER && rsi_handle != INVALID_HANDLE) {
        IndicatorRelease(rsi_handle);
    }
    
    Print("[", _Symbol, "] EMA Pullback Pro deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
    // Update rates from broker
    if(!UpdateRates())
        return;
    
    // Rate limiting (optional, for testing)
    if (TimeCurrent() - last_tick_time < TICK_INTERVAL) {
        return;
    }
    last_tick_time = TimeCurrent();
    
    // Get indicator values
    if (!GetIndicatorValues()) {
        return;
    }
    
    // Get current price
    double current_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    
    // Update trailing stop if position is open
    if (position_open) {
        UpdateTrailingStop(current_price);
        
        // Check if stop was hit
        if (CheckStopHit(current_price)) {
            ClosePosition("Stop loss hit");
            return;
        }
        
        // Check exit signal
        if (CheckExitSignal()) {
            ClosePosition("Exit signal");
            return;
        }
    } else {
        // Check entry signal
        CheckEntrySignal();
    }
}

//+------------------------------------------------------------------+
//| Get Indicator Values                                             |
//+------------------------------------------------------------------+
bool GetIndicatorValues() {
    // Copy EMA Fast
    if (CopyBuffer(ema_fast_handle, 0, 0, 2, ema_fast_buffer) < 2) {
        return false;
    }
    
    // Copy EMA Slow
    if (CopyBuffer(ema_slow_handle, 0, 0, 2, ema_slow_buffer) < 2) {
        return false;
    }
    
    // Copy ATR
    if (CopyBuffer(atr_handle, 0, 0, 1, atr_buffer) < 1) {
        return false;
    }
    
    // Copy RSI if enabled
    if (USE_RSI_FILTER && rsi_handle != INVALID_HANDLE) {
        if (CopyBuffer(rsi_handle, 0, 0, 1, rsi_buffer) < 1) {
            return false;
        }
    }
    
    return true;
}

//+------------------------------------------------------------------+
//| Check Entry Signal                                               |
//+------------------------------------------------------------------+
void CheckEntrySignal() {
    double open_p    = rates[0].open;
    double close     = rates[0].close;
    double ema_fast  = ema_fast_buffer[0];
    double ema_slow  = ema_slow_buffer[0];
    
    // Check if enough data
    if (ema_fast == 0 || ema_slow == 0) {
        return;
    }
    
    // ── BUY Signal ────────────────────────────────────────────────
    if (ema_fast > ema_slow) {
        // EMA touch: between open and close
        bool ema_between = (open_p <= ema_fast && ema_fast <= close) || 
                          (close <= ema_fast && ema_fast <= open_p);
        
        // Bounce: close above EMA
        bool bounced = close > ema_fast;
        
        if (ema_between && bounced) {
            // RSI filter (optional)
            if (USE_RSI_FILTER && rsi_buffer[0] > 70) {
                Print("[", _Symbol, "] RSI overbought, skip BUY");
                return;
            }
            
            // Calculate stop loss
            double stop_loss = close * (1.0 - EXIT_PCT_BELOW_EMA / 100.0);
            
            // Open position
            OpenPosition("BUY", stop_loss);
            return;
        }
    }
    
    // ── SELL Signal (if enabled) ──────────────────────────────────
    if (ALLOW_SHORT && ema_fast < ema_slow) {
        // EMA touch: between open and close
        bool ema_between = (open_p <= ema_fast && ema_fast <= close) || 
                          (close <= ema_fast && ema_fast <= open_p);
        
        // Bounce down: close below EMA
        bool bounced_down = close < ema_fast;
        
        if (ema_between && bounced_down) {
            // Calculate stop loss
            double stop_loss = close * (1.0 + EXIT_PCT_BELOW_EMA / 100.0);
            
            // Open position
            OpenPosition("SELL", stop_loss);
            return;
        }
    }
}

//+------------------------------------------------------------------+
//| Check Exit Signal                                                |
//+------------------------------------------------------------------+
bool CheckExitSignal() {
    double close    = rates[0].close;
    double ema_fast = ema_fast_buffer[0];
    double exit_level;
    
    if (position_direction == "BUY") {
        exit_level = ema_fast * (1.0 - EXIT_PCT_BELOW_EMA / 100.0);
        if (close < exit_level) {
            return true;
        }
    } else if (position_direction == "SELL") {
        exit_level = ema_fast * (1.0 + EXIT_PCT_BELOW_EMA / 100.0);
        if (close > exit_level) {
            return true;
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Update Trailing Stop                                             |
//+------------------------------------------------------------------+
void UpdateTrailingStop(double current_price) {
    double new_stop;
    double pct = EXIT_PCT_BELOW_EMA / 100.0;
    
    if (position_direction == "BUY") {
        new_stop = current_price * (1.0 - pct);
        if (new_stop > position_stop_loss) {
            // Modify order
            if (ModifyPosition(new_stop)) {
                Print("[", _Symbol, "] Trailing stop UP: ", 
                      DoubleToString(position_stop_loss, _Digits), " → ", 
                      DoubleToString(new_stop, _Digits));
                position_stop_loss = new_stop;
            }
        }
    } else if (position_direction == "SELL") {
        new_stop = current_price * (1.0 + pct);
        if (new_stop < position_stop_loss) {
            // Modify order
            if (ModifyPosition(new_stop)) {
                Print("[", _Symbol, "] Trailing stop DOWN: ", 
                      DoubleToString(position_stop_loss, _Digits), " → ", 
                      DoubleToString(new_stop, _Digits));
                position_stop_loss = new_stop;
            }
        }
    }
}

//+------------------------------------------------------------------+
//| Check Stop Hit                                                   |
//+------------------------------------------------------------------+
bool CheckStopHit(double current_price) {
    if (position_direction == "BUY") {
        if (current_price <= position_stop_loss) {
            return true;
        }
    } else if (position_direction == "SELL") {
        if (current_price >= position_stop_loss) {
            return true;
        }
    }
    return false;
}

//+------------------------------------------------------------------+
//| Open Position                                                    |
//+------------------------------------------------------------------+
void OpenPosition(string direction, double stop_loss) {
    if (position_open) {
        return;  // Already have an open position
    }

    // Check max open positions — counts ALL broker positions
    if (PositionsTotal() >= MAX_OPEN_POSITIONS) {
        Print("[", _Symbol, "] Max open positions reached (",
              PositionsTotal(), "/", MAX_OPEN_POSITIONS, ")");
        return;
    }

    // Calculate lot size correctly using tick_value and tick_size
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double risk_amount = balance * (RISK_PERCENT / 100.0);
    double stop_distance = MathAbs(rates[0].close - stop_loss);
    
    if (stop_distance <= 0.0) {
        Print("[", _Symbol, "] Invalid stop distance");
        return;
    }

    double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

    if(tick_value <= 0.0 || tick_size <= 0.0) {
        Print("[", _Symbol, "] Invalid tick_value or tick_size");
        return;
    }

    double loss_per_lot = (stop_distance / tick_size) * tick_value;
    double lot_size = risk_amount / loss_per_lot;
    lot_size = NormalizeVolume(lot_size);
    
    // Prepare order
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = _Symbol;
    request.volume = lot_size;
    request.sl = NormalizeDouble(stop_loss, _Digits);
    request.deviation = 20;
    request.comment = "EMA Pullback Pro";
    
    if (direction == "BUY") {
        request.type = ORDER_TYPE_BUY;
        request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    } else {
        request.type = ORDER_TYPE_SELL;
        request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    }
    
    request.price = NormalizeDouble(request.price, _Digits);
    
    // Send order
    if (!OrderSend(request, result)) {
        Print("[", _Symbol, "] OrderSend failed. Error=", GetLastError(),
              " retcode=", result.retcode);
        return;
    }
    
    if(result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED)
    {
        Print("[", _Symbol, "] Order rejected. Retcode=", result.retcode);
        return;
    }
    
    // Track position
    position_open = true;
    position_ticket = result.deal;
    position_direction = direction;
    position_entry_price = result.price;
    position_stop_loss = stop_loss;
    
    Print("[", _Symbol, "] ", direction, " opened at ", 
          DoubleToString(position_entry_price, _Digits), 
          " SL=", DoubleToString(stop_loss, _Digits));
}

//+------------------------------------------------------------------+
//| Close Position                                                   |
//+------------------------------------------------------------------+
void ClosePosition(string reason) {
    if (!position_open) {
        return;
    }
    
    if(!PositionSelect(_Symbol))
    {
        Print("[", _Symbol, "] No live position found to close");
        position_open = false;
        position_ticket = 0;
        position_direction = "";
        return;
    }
    
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = _Symbol;
    request.position = (ulong)PositionGetInteger(POSITION_TICKET);
    request.volume = PositionGetDouble(POSITION_VOLUME);
    request.deviation = 20;
    request.comment = reason;
    
    if (position_direction == "BUY") {
        request.type = ORDER_TYPE_SELL;
        request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    } else {
        request.type = ORDER_TYPE_BUY;
        request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    }
    
    request.price = NormalizeDouble(request.price, _Digits);
    
    if (!OrderSend(request, result)) {
        Print("[", _Symbol, "] Close failed. Error=", GetLastError(),
              " retcode=", result.retcode);
        return;
    }
    
    if(result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED)
    {
        Print("[", _Symbol, "] Close rejected. Retcode=", result.retcode);
        return;
    }
    
    Print("[", _Symbol, "] ", position_direction, " closed: ", reason);
    
    position_open = false;
    position_ticket = 0;
    position_direction = "";
}

//+------------------------------------------------------------------+
//| Modify Position (Update Stop Loss)                               |
//+------------------------------------------------------------------+
bool ModifyPosition(double new_stop) {
    if (!PositionSelect(_Symbol)) {
        return false;
    }
    
    MqlTradeRequest request;
    MqlTradeResult result;
    ZeroMemory(request);
    ZeroMemory(result);
    
    request.action = TRADE_ACTION_SLTP;
    request.symbol = _Symbol;
    request.position = (ulong)PositionGetInteger(POSITION_TICKET);
    request.sl = NormalizeDouble(new_stop, _Digits);
    request.tp = PositionGetDouble(POSITION_TP);
    
    return OrderSend(request, result);
}

//+------------------------------------------------------------------+
//| Helper: Get Position Info                                        |
//+------------------------------------------------------------------+
bool GetPositionInfo() {
    if (!PositionSelect(_Symbol)) {
        position_open = false;
        return false;
    }
    
    position_open = true;
    position_ticket = (ulong)PositionGetInteger(POSITION_TICKET);
    position_direction = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL";
    position_entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
    position_stop_loss = PositionGetDouble(POSITION_SL);
    
    return true;
}

//+------------------------------------------------------------------+
// End of file
//+------------------------------------------------------------------+
