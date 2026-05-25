//+------------------------------------------------------------------+
//| Change of Direction.mq5                                          |
//| Reversal-based strategy using candle patterns and price action   |
//| Identical logic to the Python implementation.                    |
//+------------------------------------------------------------------+
#property strict
#property version   "1.0"
#property description "Change of Direction — Reversal EA"
#property author    "AlgoTrader Pro"

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
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
input double   MAX_DAILY_LOSS_PCT     = 30.0;     // Max daily loss (%)
input int      MAX_OPEN_POSITIONS     = 1;       // Max concurrent positions (always 1 for COD)

// Paper Trading Mode
input bool     PAPER_TRADING_MODE     = true;    // If true: only print signals (no real orders)
                                                  // If false: execute real orders via OrderSend()

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+

bool           is_position_open = false;
int            current_position_ticket = 0;
string         current_position_direction = "";
double         current_position_entry_price = 0.0;
double         current_position_stop_loss = 0.0;
double         current_position_take_profit = 0.0;

datetime       last_tick_time = 0;
double         daily_pnl = 0.0;
bool           daily_loss_triggered = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
    Print("[", Symbol(), "] Change of Direction initialized");
    Print("  SL=", STOP_LOSS_PIPS, " pips, TP=", TAKE_PROFIT_PIPS, " pips");
    Print("  ALLOW_SHORT=", ALLOW_SHORT, " ALLOW_LONG=", ALLOW_LONG);
    
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
    Print("[", Symbol(), "] Change of Direction deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick() {
    // Get current price
    double current_bid_price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
    
    // Check if position is open
    if (is_position_open) {
        // Check if stop or take profit was hit
        if (CheckExitSignal(current_bid_price)) {
            return;
        }
    } else {
        // Check for entry signals
        CheckEntrySignal();
    }
}

//+------------------------------------------------------------------+
//| Check Entry Signal                                               |
//+------------------------------------------------------------------+
void CheckEntrySignal() {
    // Need at least 10 candles
    if (Bars(Symbol(), Period()) < 10) {
        return;
    }
    
    // Check for SELL setup
    if (ALLOW_SHORT) {
        if (DetectSellSetup()) {
            return;
        }
    }
    
    // Check for BUY setup
    if (ALLOW_LONG) {
        if (DetectBuySetup()) {
            return;
        }
    }
}

//+------------------------------------------------------------------+
//| Detect SELL Setup                                                |
//+------------------------------------------------------------------+
bool DetectSellSetup() {
    // ════════════════════════════════════════════════════════════════
    // PATTERN RECOGNITION
    // ════════════════════════════════════════════════════════════════
    
    // Step 1: Find 2+ consecutive RED candles (close < open)
    int consecutive_red_candles = 0;
    for (int i = 1; i < Bars(Symbol(), Period()); i++) {
        if (Close[i] < Open[i]) {
            consecutive_red_candles++;
        } else {
            break;
        }
    }
    
    if (consecutive_red_candles < MIN_RED_CANDLES) {
        return false;  // Not enough red candles
    }
    
    // Get the first red candle in the sequence
    int first_red_candle_index = consecutive_red_candles;
    double first_red_candle_open = Open[first_red_candle_index];
    
    // Step 2: Next candle should be GREEN (close > open)
    double current_candle_close = Close[0];
    double current_candle_open = Open[0];
    
    if (current_candle_close <= current_candle_open) {
        return false;  // Current candle is not green
    }
    
    // Step 3: Condition - close_green > open_first_red
    if (current_candle_close <= first_red_candle_open) {
        return false;  // Green close is not higher than first red open
    }
    
    // Step 4: Mark open_green as Point of Change Direction (PCD)
    double point_of_change_direction = current_candle_open;
    
    // ════════════════════════════════════════════════════════════════
    // BREAKOUT CONFIRMATION
    // ════════════════════════════════════════════════════════════════
    
    // Step 1: Wait for price to break below PCD (low crosses PCD)
    double current_candle_low = Low[0];
    
    if (current_candle_low >= point_of_change_direction) {
        return false;  // Price hasn't broken PCD yet - still waiting
    }
    
    // Step 2: Store the new lowest point as New PCD
    double new_point_of_change_direction = current_candle_low;
    
    // ════════════════════════════════════════════════════════════════
    // ENTRY CONFIRMATION
    // ════════════════════════════════════════════════════════════════
    
    // Step 1: When close <= New PCD → SELL Entry
    if (current_candle_close > new_point_of_change_direction) {
        return false;  // Close is not at or below New PCD - still waiting
    }
    
    // ✅ SELL Entry Confirmed - All conditions met!
    double entry_price = current_candle_close;
    
    // Step 2: Stop Loss = entry_price + 15 pips
    double stop_loss_price = entry_price + (STOP_LOSS_PIPS * PIP_VALUE);
    
    // Step 3: Take Profit = entry_price - 45 pips
    double take_profit_price = entry_price - (TAKE_PROFIT_PIPS * PIP_VALUE);
    
    Print("[", Symbol(), "] COD SELL: Reversal confirmed. "
          "entry=", DoubleToString(entry_price, 5), 
          " SL=", DoubleToString(stop_loss_price, 5),
          " TP=", DoubleToString(take_profit_price, 5));
    
    OpenPosition("SELL", stop_loss_price, take_profit_price);
    return true;
}

//+------------------------------------------------------------------+
//| Detect BUY Setup                                                 |
//+------------------------------------------------------------------+
bool DetectBuySetup() {
    // ════════════════════════════════════════════════════════════════
    // PATTERN RECOGNITION
    // ════════════════════════════════════════════════════════════════
    
    // Step 1: Find 2+ consecutive GREEN candles (close > open)
    int consecutive_green_candles = 0;
    for (int i = 1; i < Bars(Symbol(), Period()); i++) {
        if (Close[i] > Open[i]) {
            consecutive_green_candles++;
        } else {
            break;
        }
    }
    
    if (consecutive_green_candles < MIN_GREEN_CANDLES) {
        return false;  // Not enough green candles
    }
    
    // Get the first green candle in the sequence
    int first_green_candle_index = consecutive_green_candles;
    double first_green_candle_open = Open[first_green_candle_index];
    
    // Step 2: Next candle should be RED (close < open)
    double current_candle_close = Close[0];
    double current_candle_open = Open[0];
    
    if (current_candle_close >= current_candle_open) {
        return false;  // Current candle is not red
    }
    
    // Step 3: Condition - close_red < open_first_green
    if (current_candle_close >= first_green_candle_open) {
        return false;  // Red close is not lower than first green open
    }
    
    // Step 4: Mark open_red as Point of Change Direction (PCD)
    double point_of_change_direction = current_candle_open;
    
    // ════════════════════════════════════════════════════════════════
    // BREAKOUT CONFIRMATION
    // ════════════════════════════════════════════════════════════════
    
    // Step 1: Wait for price to break above PCD (high crosses PCD)
    double current_candle_high = High[0];
    
    if (current_candle_high <= point_of_change_direction) {
        return false;  // Price hasn't broken PCD yet - still waiting
    }
    
    // Step 2: Store the new highest point as New PCD
    double new_point_of_change_direction = current_candle_high;
    
    // ════════════════════════════════════════════════════════════════
    // ENTRY CONFIRMATION
    // ════════════════════════════════════════════════════════════════
    
    // Step 1: When close >= New PCD → BUY Entry
    if (current_candle_close < new_point_of_change_direction) {
        return false;  // Close is not at or above New PCD - still waiting
    }
    
    // ✅ BUY Entry Confirmed - All conditions met!
    double entry_price = current_candle_close;
    
    // Step 2: Stop Loss = entry_price - 15 pips
    double stop_loss_price = entry_price - (STOP_LOSS_PIPS * PIP_VALUE);
    
    // Step 3: Take Profit = entry_price + 45 pips
    double take_profit_price = entry_price + (TAKE_PROFIT_PIPS * PIP_VALUE);
    
    Print("[", Symbol(), "] COD BUY: Reversal confirmed. "
          "entry=", DoubleToString(entry_price, 5), 
          " SL=", DoubleToString(stop_loss_price, 5),
          " TP=", DoubleToString(take_profit_price, 5));
    
    OpenPosition("BUY", stop_loss_price, take_profit_price);
    return true;
}

//+------------------------------------------------------------------+
//| Check Exit Signal                                                |
//+------------------------------------------------------------------+
bool CheckExitSignal(double current_bid_price) {
    if (!is_position_open) {
        return false;
    }
    
    double current_candle_close = Close[0];
    
    if (current_position_direction == "SELL") {
        // Check SL (above entry)
        if (current_candle_close >= current_position_stop_loss) {
            ClosePosition("Stop Loss hit");
            return true;
        }
        // Check TP (below entry)
        if (current_candle_close <= current_position_take_profit) {
            ClosePosition("Take Profit hit");
            return true;
        }
    } else if (current_position_direction == "BUY") {
        // Check SL (below entry)
        if (current_candle_close <= current_position_stop_loss) {
            ClosePosition("Stop Loss hit");
            return true;
        }
        // Check TP (above entry)
        if (current_candle_close >= current_position_take_profit) {
            ClosePosition("Take Profit hit");
            return true;
        }
    }
    
    return false;
}

//+------------------------------------------------------------------+
//| Open Position                                                    |
//+------------------------------------------------------------------+
void OpenPosition(string direction, double stop_loss_price, double take_profit_price) {
    if (is_position_open) {
        return;  // Already have an open position
    }
    
    // Calculate lot size
    double account_balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double risk_amount = account_balance * (RISK_PERCENT / 100.0);
    double stop_distance = MathAbs(Close[0] - stop_loss_price);
    
    if (stop_distance <= 0) {
        Print("[", Symbol(), "] Invalid stop distance");
        return;
    }
    
    double calculated_lot_size = risk_amount / stop_distance;
    calculated_lot_size = MathMax(0.01, MathMin(calculated_lot_size, 10.0));
    calculated_lot_size = NormalizeDouble(calculated_lot_size, 2);
    
    // ════════════════════════════════════════════════════════════════
    // PAPER TRADING MODE CHECK
    // ════════════════════════════════════════════════════════════════
    
    if (PAPER_TRADING_MODE) {
        // SIMULATION MODE: Only print, don't execute real order
        Print("[", Symbol(), "] [PAPER] SIMULATED ", direction, " @ ", 
              DoubleToString(Close[0], 5), 
              " lot=", DoubleToString(calculated_lot_size, 2),
              " SL=", DoubleToString(stop_loss_price, 5),
              " TP=", DoubleToString(take_profit_price, 5));
        
        // Track position in memory (for simulation)
        is_position_open = true;
        current_position_ticket = 0;  // No real ticket in paper mode
        current_position_direction = direction;
        current_position_entry_price = Close[0];
        current_position_stop_loss = stop_loss_price;
        current_position_take_profit = take_profit_price;
        
        return;
    }
    
    // ════════════════════════════════════════════════════════════════
    // LIVE TRADING MODE: Execute real order
    // ════════════════════════════════════════════════════════════════
    
    // Prepare order
    MqlTradeRequest trade_request = {};
    MqlTradeResult trade_result = {};
    
    trade_request.action = TRADE_ACTION_DEAL;
    trade_request.symbol = Symbol();
    trade_request.volume = calculated_lot_size;
    trade_request.price = SymbolInfoDouble(Symbol(), SYMBOL_ASK);
    trade_request.sl = stop_loss_price;
    trade_request.tp = take_profit_price;
    trade_request.comment = "Change of Direction";
    
    if (direction == "BUY") {
        trade_request.type = ORDER_TYPE_BUY;
    } else {
        trade_request.type = ORDER_TYPE_SELL;
    }
    
    // Send order
    if (!OrderSend(trade_request, trade_result)) {
        Print("[", Symbol(), "] Order failed: ", GetLastError());
        return;
    }
    
    // Track position
    is_position_open = true;
    current_position_ticket = trade_result.deal;
    current_position_direction = direction;
    current_position_entry_price = trade_result.price;
    current_position_stop_loss = stop_loss_price;
    current_position_take_profit = take_profit_price;
    
    Print("[", Symbol(), "] ", direction, " opened at ", 
          DoubleToString(current_position_entry_price, 5), 
          " SL=", DoubleToString(stop_loss_price, 5),
          " TP=", DoubleToString(take_profit_price, 5));
}

//+------------------------------------------------------------------+
//| Close Position                                                   |
//+------------------------------------------------------------------+
void ClosePosition(string close_reason) {
    if (!is_position_open) {
        return;
    }
    
    // ════════════════════════════════════════════════════════════════
    // PAPER TRADING MODE CHECK
    // ════════════════════════════════════════════════════════════════
    
    if (PAPER_TRADING_MODE) {
        // SIMULATION MODE: Only print, don't execute real order
        double exit_price = Close[0];
        double pnl = 0.0;
        
        if (current_position_direction == "BUY") {
            pnl = (exit_price - current_position_entry_price) * 100000;  // Simplified PnL
        } else {
            pnl = (current_position_entry_price - exit_price) * 100000;  // Simplified PnL
        }
        
        Print("[", Symbol(), "] [PAPER] SIMULATED CLOSE ", current_position_direction, 
              " @ ", DoubleToString(exit_price, 5),
              " PnL=", DoubleToString(pnl, 2),
              " | ", close_reason);
        
        is_position_open = false;
        current_position_ticket = 0;
        current_position_direction = "";
        
        return;
    }
    
    // ════════════════════════════════════════════════════════════════
    // LIVE TRADING MODE: Execute real close order
    // ════════════════════════════════════════════════════════════════
    
    MqlTradeRequest trade_request = {};
    MqlTradeResult trade_result = {};
    
    trade_request.action = TRADE_ACTION_DEAL;
    trade_request.symbol = Symbol();
    trade_request.volume = PositionGetDouble(POSITION_VOLUME);
    trade_request.price = SymbolInfoDouble(Symbol(), SYMBOL_BID);
    trade_request.comment = close_reason;
    
    if (current_position_direction == "BUY") {
        trade_request.type = ORDER_TYPE_SELL;
    } else {
        trade_request.type = ORDER_TYPE_BUY;
    }
    
    if (!OrderSend(trade_request, trade_result)) {
        Print("[", Symbol(), "] Close failed: ", GetLastError());
        return;
    }
    
    Print("[", Symbol(), "] ", current_position_direction, " closed: ", close_reason);
    
    is_position_open = false;
    current_position_ticket = 0;
    current_position_direction = "";
}

//+------------------------------------------------------------------+
// End of file
//+------------------------------------------------------------------+
