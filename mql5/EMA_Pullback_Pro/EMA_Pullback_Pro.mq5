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
input double   MAX_DAILY_LOSS_PCT    = 3.0;     // Max daily loss (%)
input int      MAX_OPEN_POSITIONS    = 3;       // Max concurrent positions

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
int            position_ticket = 0;
string         position_direction = "";
double         position_entry_price = 0.0;
double         position_stop_loss = 0.0;

datetime       last_tick_time = 0;
double         daily_pnl = 0.0;
bool           daily_loss_triggered = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
    // Create indicator handles
    ema_fast_handle = iMA(Symbol(), Period(), EMA_FAST, 0, MODE_EMA, PRICE_CLOSE);
    ema_slow_handle = iMA(Symbol(), Period(), EMA_SLOW, 0, MODE_EMA, PRICE_CLOSE);
    atr_handle      = iATR(Symbol(), Period(), ATR_PERIOD);
    
    if (USE_RSI_FILTER) {
        rsi_handle = iRSI(Symbol(), Period(), RSI_PERIOD, PRICE_CLOSE);
    }
    
    // Validate handles
    if (ema_fast_handle == INVALID_HANDLE || 
        ema_slow_handle == INVALID_HANDLE || 
        atr_handle == INVALID_HANDLE) {
        Alert("Failed to create indicator handles");
        return INIT_FAILED;
    }
    
    Print("[", Symbol(), "] EMA Pullback Pro initialized");
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
    
    Print("[", Symbol(), "] EMA Pullback Pro deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
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
    double current_price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
    
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
    double open_p    = Open[0];
    double close     = Close[0];
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
                Print("[", Symbol(), "] RSI overbought, skip BUY");
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
    double close    = Close[0];
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
                Print("[", Symbol(), "] Trailing stop UP: ", 
                      DoubleToString(position_stop_loss, 5), " → ", 
                      DoubleToString(new_stop, 5));
                position_stop_loss = new_stop;
            }
        }
    } else if (position_direction == "SELL") {
        new_stop = current_price * (1.0 + pct);
        if (new_stop < position_stop_loss) {
            // Modify order
            if (ModifyPosition(new_stop)) {
                Print("[", Symbol(), "] Trailing stop DOWN: ", 
                      DoubleToString(position_stop_loss, 5), " → ", 
                      DoubleToString(new_stop, 5));
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
    
    // Calculate lot size
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double risk_amount = balance * (RISK_PERCENT / 100.0);
    double stop_distance = MathAbs(Close[0] - stop_loss);
    
    if (stop_distance <= 0) {
        Print("[", Symbol(), "] Invalid stop distance");
        return;
    }
    
    double lot_size = risk_amount / stop_distance;
    lot_size = MathMax(0.01, MathMin(lot_size, 10.0));
    lot_size = NormalizeDouble(lot_size, 2);
    
    // Prepare order
    MqlTradeRequest request = {};
    MqlTradeResult result = {};
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = Symbol();
    request.volume = lot_size;
    request.price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
    request.sl = stop_loss;
    request.comment = "EMA Pullback Pro";
    
    if (direction == "BUY") {
        request.type = ORDER_TYPE_BUY;
    } else {
        request.type = ORDER_TYPE_SELL;
    }
    
    // Send order
    if (!OrderSend(request, result)) {
        Print("[", Symbol(), "] Order failed: ", GetLastError());
        return;
    }
    
    // Track position
    position_open = true;
    position_ticket = result.deal;
    position_direction = direction;
    position_entry_price = result.price;
    position_stop_loss = stop_loss;
    
    Print("[", Symbol(), "] ", direction, " opened at ", 
          DoubleToString(position_entry_price, 5), 
          " SL=", DoubleToString(stop_loss, 5));
}

//+------------------------------------------------------------------+
//| Close Position                                                   |
//+------------------------------------------------------------------+
void ClosePosition(string reason) {
    if (!position_open) {
        return;
    }
    
    MqlTradeRequest request = {};
    MqlTradeResult result = {};
    
    request.action = TRADE_ACTION_DEAL;
    request.symbol = Symbol();
    request.volume = PositionGetDouble(POSITION_VOLUME);
    request.price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
    request.comment = reason;
    
    if (position_direction == "BUY") {
        request.type = ORDER_TYPE_SELL;
    } else {
        request.type = ORDER_TYPE_BUY;
    }
    
    if (!OrderSend(request, result)) {
        Print("[", Symbol(), "] Close failed: ", GetLastError());
        return;
    }
    
    Print("[", Symbol(), "] ", position_direction, " closed: ", reason);
    
    position_open = false;
    position_ticket = 0;
    position_direction = "";
}

//+------------------------------------------------------------------+
//| Modify Position (Update Stop Loss)                               |
//+------------------------------------------------------------------+
bool ModifyPosition(double new_stop) {
    if (!PositionSelect(Symbol())) {
        return false;
    }
    
    MqlTradeRequest request = {};
    MqlTradeResult result = {};
    
    request.action = TRADE_ACTION_SLTP;
    request.symbol = Symbol();
    request.sl = new_stop;
    request.tp = PositionGetDouble(POSITION_TP);
    
    return OrderSend(request, result);
}

//+------------------------------------------------------------------+
//| Helper: Get Position Info                                        |
//+------------------------------------------------------------------+
bool GetPositionInfo() {
    if (!PositionSelect(Symbol())) {
        position_open = false;
        return false;
    }
    
    position_open = true;
    position_ticket = (int)PositionGetTicket(0);
    position_direction = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? "BUY" : "SELL";
    position_entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
    position_stop_loss = PositionGetDouble(POSITION_SL);
    
    return true;
}

//+------------------------------------------------------------------+
// End of file
//+------------------------------------------------------------------+
