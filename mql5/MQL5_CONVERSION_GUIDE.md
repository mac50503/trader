# Guía de Conversión: Python → MQL5

Una guía completa para convertir estrategias de Python a MQL5 siguiendo las mejores prácticas aprendidas.

---

## 📋 Tabla de Contenidos

1. [Estructura Base](#estructura-base)
2. [Checklist de Conversión](#checklist-de-conversión)
3. [Errores Comunes a Evitar](#errores-comunes-a-evitar)
4. [Patrones de Código](#patrones-de-código)
5. [Validación Final](#validación-final)

---

## Estructura Base

### 1. Header y Propiedades

```mql5
//+------------------------------------------------------------------+
//| NombreEstrategia.mq5                                             |
//| Descripción breve de la estrategia                               |
//+------------------------------------------------------------------+
#property strict
#property version     "1.0"
#property description "Descripción completa"
#property copyright   "AlgoTrader Pro"
```

**Notas:**
- Siempre usar `#property strict` para validación de tipos
- Versión debe ser "1.0" para nuevas estrategias
- Copyright debe ser "AlgoTrader Pro"

---

### 2. Input Parameters

```mql5
//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+

// Strategy Parameters
input double   PARAM_NAME            = 0.01;    // Descripción
input int      PARAM_NAME            = 15;      // Descripción

// Risk Management
input double   RISK_PERCENT          = 1.0;     // Risk per trade (%)
input double   MAX_DAILY_LOSS_PCT    = 30.0;    // Max daily loss (%)
input int      MAX_OPEN_POSITIONS    = 1;       // Max concurrent positions

// Paper Trading Mode
input bool     PAPER_TRADING_MODE    = true;    // If true: only print signals
```

**Reglas:**
- Agrupar parámetros por categoría (Strategy, Risk Management, Paper Trading)
- Usar MAYÚSCULAS para nombres de parámetros
- Siempre incluir PAPER_TRADING_MODE
- Incluir comentarios descriptivos

---

### 3. Global Variables

```mql5
//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+

bool           is_position_open = false;
ulong          current_position_ticket = 0;      // ✅ SIEMPRE ulong, NUNCA int
string         current_position_direction = "";
double         current_position_entry_price = 0.0;
double         current_position_stop_loss = 0.0;
double         current_position_take_profit = 0.0;

datetime       last_tick_time = 0;
double         daily_pnl = 0.0;
bool           daily_loss_triggered = false;

MqlRates       rates[];                          // ✅ SIEMPRE agregar para CopyRates()
```

**Reglas Críticas:**
- ✅ Ticket SIEMPRE es `ulong`, NUNCA `int`
- ✅ SIEMPRE agregar `MqlRates rates[]` para CopyRates()
- Usar nombres descriptivos con prefijo (current_, is_, etc.)

---

### 4. Funciones Auxiliares Obligatorias

#### UpdateRates() - CRÍTICA

```mql5
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
```

**Notas:**
- ✅ OBLIGATORIA en OnTick()
- ✅ Usar `_Symbol` y `_Period` (no Symbol() ni Period())
- ✅ Validar que copied > 0
- ✅ Usar ArraySetAsSeries(rates, true) para acceso [0] = último

#### NormalizeVolume() - CRÍTICA

```mql5
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
```

**Notas:**
- ✅ OBLIGATORIA para calcular lot size
- ✅ Valida requisitos del símbolo
- ✅ Evita órdenes rechazadas

---

## Checklist de Conversión

### ✅ Antes de Empezar

- [ ] Leer la estrategia Python completamente
- [ ] Entender la lógica de entrada/salida
- [ ] Identificar todos los parámetros
- [ ] Documentar el flujo de señales

### ✅ Estructura Base

- [ ] Crear header con propiedades
- [ ] Definir input parameters
- [ ] Declarar global variables
- [ ] Agregar MqlRates rates[]
- [ ] Agregar UpdateRates()
- [ ] Agregar NormalizeVolume()

### ✅ Funciones Principales

- [ ] OnInit() - Inicializar handles de indicadores
- [ ] OnDeinit() - Liberar recursos
- [ ] OnTick() - Llamar UpdateRates() primero
- [ ] CheckEntrySignal() - Lógica de entrada
- [ ] CheckExitSignal() - Lógica de salida
- [ ] OpenPosition() - Abrir posición
- [ ] ClosePosition() - Cerrar posición

### ✅ Validaciones Críticas

- [ ] ✅ Usar `_Symbol` en lugar de `Symbol()`
- [ ] ✅ Usar `_Period` en lugar de `Period()`
- [ ] ✅ Usar `_Digits` en lugar de hardcoded 5
- [ ] ✅ Usar `rates[0]` en lugar de `Close[0]`
- [ ] ✅ Ticket es `ulong`, no `int`
- [ ] ✅ ZeroMemory() en structs MqlTradeRequest/Result
- [ ] ✅ Validar retcode en OrderSend()
- [ ] ✅ PositionSelect() antes de cerrar
- [ ] ✅ Deviation = 20 en OrderSend()
- [ ] ✅ Precios normalizados con NormalizeDouble()
- [ ] ✅ Usar NormalizeVolume() para lot size

---

## Errores Comunes a Evitar

### 🔴 ERROR 1: Acceso Directo a Close[0] sin CopyRates()

❌ **INCORRECTO:**
```mql5
void OnTick() {
    double close = Close[0];  // ❌ Datos inconsistentes
    // ...
}
```

✅ **CORRECTO:**
```mql5
void OnTick() {
    if(!UpdateRates())
        return;
    
    double close = rates[0].close;  // ✅ Datos consistentes
    // ...
}
```

---

### 🔴 ERROR 2: Ticket como int

❌ **INCORRECTO:**
```mql5
int current_position_ticket = 0;  // ❌ Pérdida de datos
```

✅ **CORRECTO:**
```mql5
ulong current_position_ticket = 0;  // ✅ Rango completo
```

---

### 🔴 ERROR 3: Inicialización de Structs

❌ **INCORRECTO:**
```mql5
MqlTradeRequest request = {};  // ❌ Valores basura en memoria
```

✅ **CORRECTO:**
```mql5
MqlTradeRequest request;
ZeroMemory(request);  // ✅ Limpia completamente
```

---

### 🔴 ERROR 4: Sin Validación de Retcode

❌ **INCORRECTO:**
```mql5
if (!OrderSend(request, result)) {
    Print("Order failed");
    return;
}
// ❌ Orden puede estar PLACED pero no DONE
```

✅ **CORRECTO:**
```mql5
if (!OrderSend(request, result)) {
    Print("OrderSend failed. Error=", GetLastError(),
          " retcode=", result.retcode);
    return;
}

if(result.retcode != TRADE_RETCODE_DONE && 
   result.retcode != TRADE_RETCODE_PLACED)
{
    Print("Order rejected. Retcode=", result.retcode);
    return;
}
```

---

### 🔴 ERROR 5: Cerrar sin PositionSelect()

❌ **INCORRECTO:**
```mql5
void ClosePosition() {
    request.volume = PositionGetDouble(POSITION_VOLUME);  // ❌ Falla si no existe
}
```

✅ **CORRECTO:**
```mql5
void ClosePosition() {
    if(!PositionSelect(_Symbol)) {
        Print("No position found");
        position_open = false;
        return;
    }
    
    request.volume = PositionGetDouble(POSITION_VOLUME);  // ✅ Seguro
}
```

---

### 🔴 ERROR 6: Hardcoded _Digits

❌ **INCORRECTO:**
```mql5
Print("Price: ", DoubleToString(price, 5));  // ❌ EURUSD tiene 4, XAUUSD tiene 2
```

✅ **CORRECTO:**
```mql5
Print("Price: ", DoubleToString(price, _Digits));  // ✅ Automático por símbolo
```

---

### 🔴 ERROR 7: Sin Deviation en OrderSend()

❌ **INCORRECTO:**
```mql5
request.action = TRADE_ACTION_DEAL;
request.symbol = _Symbol;
// ❌ Sin deviation → rechazada en mercados volátiles
```

✅ **CORRECTO:**
```mql5
request.action = TRADE_ACTION_DEAL;
request.symbol = _Symbol;
request.deviation = 20;  // ✅ Permite slippage
```

---

### 🔴 ERROR 8: Precios sin Normalizar

❌ **INCORRECTO:**
```mql5
request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);  // ❌ Puede tener decimales extra
```

✅ **CORRECTO:**
```mql5
request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
request.price = NormalizeDouble(request.price, _Digits);  // ✅ Normalizado
```

---

### 🔴 ERROR 9: Sin Ticket en Close

❌ **INCORRECTO:**
```mql5
request.action = TRADE_ACTION_DEAL;
request.symbol = _Symbol;
request.volume = PositionGetDouble(POSITION_VOLUME);
// ❌ Puede cerrar posición equivocada
```

✅ **CORRECTO:**
```mql5
request.action = TRADE_ACTION_DEAL;
request.symbol = _Symbol;
request.position = (ulong)PositionGetInteger(POSITION_TICKET);  // ✅ Especifica ticket
request.volume = PositionGetDouble(POSITION_VOLUME);
```

---

### 🔴 ERROR 10: Usar Symbol() en lugar de _Symbol

❌ **INCORRECTO:**
```mql5
ema_handle = iMA(Symbol(), Period(), EMA_FAST, 0, MODE_EMA, PRICE_CLOSE);
// ❌ Llamadas a función en cada tick
```

✅ **CORRECTO:**
```mql5
ema_handle = iMA(_Symbol, _Period, EMA_FAST, 0, MODE_EMA, PRICE_CLOSE);
// ✅ Variables predefinidas, más eficiente
```

---

## Patrones de Código

### Patrón 1: OnTick() Correcto

```mql5
void OnTick()
{
   // 1. SIEMPRE primero: actualizar datos
   if(!UpdateRates())
      return;

   // 2. Obtener precio actual
   double current_bid_price = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // 3. Si hay posición abierta: verificar salida
   if(is_position_open)
   {
      if(CheckExitSignal(current_bid_price))
         return;
   }
   else
   {
      // 4. Si no hay posición: verificar entrada
      CheckEntrySignal();
   }
}
```

---

### Patrón 2: OpenPosition() Correcto

```mql5
void OpenPosition(string direction, double stop_loss_price, double take_profit_price)
{
   if(is_position_open)
      return;  // Una posición a la vez

   // Calcular lot size
   double account_balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = account_balance * (RISK_PERCENT / 100.0);
   double stop_distance = MathAbs(rates[0].close - stop_loss_price);

   if(stop_distance <= 0.0)
   {
      Print("[", _Symbol, "] Invalid stop distance");
      return;
   }

   double calculated_lot_size = risk_amount / stop_distance;
   calculated_lot_size = NormalizeVolume(calculated_lot_size);

   // Preparar orden
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
   trade_request.comment = "Strategy Name";

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

   // Enviar orden
   if(!OrderSend(trade_request, trade_result))
   {
      Print("[", _Symbol, "] OrderSend failed. Error=", GetLastError(),
            " retcode=", trade_result.retcode);
      return;
   }

   if(trade_result.retcode != TRADE_RETCODE_DONE && 
      trade_result.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[", _Symbol, "] Order rejected. Retcode=", trade_result.retcode);
      return;
   }

   // Rastrear posición
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
```

---

### Patrón 3: ClosePosition() Correcto

```mql5
void ClosePosition(string close_reason)
{
   if(!is_position_open)
      return;

   // Verificar que la posición existe
   if(!PositionSelect(_Symbol))
   {
      Print("[", _Symbol, "] No live position found to close");
      is_position_open = false;
      current_position_ticket = 0;
      current_position_direction = "";
      return;
   }

   // Preparar orden de cierre
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

   // Enviar orden
   if(!OrderSend(trade_request, trade_result))
   {
      Print("[", _Symbol, "] Close failed. Error=", GetLastError(),
            " retcode=", trade_result.retcode);
      return;
   }

   if(trade_result.retcode != TRADE_RETCODE_DONE && 
      trade_result.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[", _Symbol, "] Close rejected. Retcode=", trade_result.retcode);
      return;
   }

   Print("[", _Symbol, "] ", current_position_direction, " closed: ", close_reason);

   is_position_open = false;
   current_position_ticket = 0;
   current_position_direction = "";
}
```

---

## Validación Final

### Checklist de Compilación

- [ ] Compila sin errores
- [ ] Compila sin warnings
- [ ] Todos los handles de indicadores validados
- [ ] Todos los structs inicializados con ZeroMemory()

### Checklist de Lógica

- [ ] UpdateRates() llamado en OnTick()
- [ ] Acceso a datos via rates[0], no Close[0]
- [ ] Validación de retcode en OrderSend()
- [ ] PositionSelect() antes de acceder a posición
- [ ] Normalización de precios y volumen
- [ ] Manejo de errores completo

### Checklist de Mejores Prácticas

- [ ] Usa _Symbol, _Period, _Digits
- [ ] Ticket es ulong
- [ ] Deviation = 20 en órdenes
- [ ] Comentarios descriptivos en logs
- [ ] Paper trading mode soportado
- [ ] Manejo de múltiples símbolos

---

## Ejemplo Completo: Plantilla Mínima

```mql5
//+------------------------------------------------------------------+
//| TemplateStrategy.mq5                                             |
//| Template for converting Python strategies to MQL5                |
//+------------------------------------------------------------------+
#property strict
#property version     "1.0"
#property description "Template Strategy"
#property copyright   "AlgoTrader Pro"

//+------------------------------------------------------------------+
//| Input Parameters                                                  |
//+------------------------------------------------------------------+

input double   RISK_PERCENT          = 1.0;
input bool     PAPER_TRADING_MODE    = true;

//+------------------------------------------------------------------+
//| Global Variables                                                  |
//+------------------------------------------------------------------+

bool           is_position_open = false;
ulong          current_position_ticket = 0;
string         current_position_direction = "";
double         current_position_entry_price = 0.0;
double         current_position_stop_loss = 0.0;

MqlRates       rates[];

//+------------------------------------------------------------------+
//| Load candle data                                                  |
//+------------------------------------------------------------------+
bool UpdateRates(const int candles = 100)
{
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, _Period, 0, candles, rates);
   if(copied <= 0) return false;
   return copied >= MathMin(candles, Bars(_Symbol, _Period));
}

//+------------------------------------------------------------------+
//| Normalize volume                                                  |
//+------------------------------------------------------------------+
double NormalizeVolume(double volume)
{
   double min_volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0.0) step = 0.01;
   volume = MathMax(min_volume, MathMin(volume, max_volume));
   volume = MathFloor(volume / step) * step;
   return NormalizeDouble(volume, 2);
}

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("[", _Symbol, "] Strategy initialized");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("[", _Symbol, "] Strategy deinitialized");
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!UpdateRates())
      return;

   if(is_position_open)
   {
      // Check exit
   }
   else
   {
      // Check entry
   }
}

//+------------------------------------------------------------------+
//| Open Position                                                     |
//+------------------------------------------------------------------+
void OpenPosition(string direction, double stop_loss_price)
{
   if(is_position_open) return;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RISK_PERCENT / 100.0);
   double stop_distance = MathAbs(rates[0].close - stop_loss_price);
   if(stop_distance <= 0.0) return;

   double lot_size = risk_amount / stop_distance;
   lot_size = NormalizeVolume(lot_size);

   MqlTradeRequest request;
   MqlTradeResult result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.volume = lot_size;
   request.sl = NormalizeDouble(stop_loss_price, _Digits);
   request.deviation = 20;
   request.comment = "Template";

   if(direction == "BUY")
   {
      request.type = ORDER_TYPE_BUY;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   }
   else
   {
      request.type = ORDER_TYPE_SELL;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   }

   request.price = NormalizeDouble(request.price, _Digits);

   if(!OrderSend(request, result)) return;
   if(result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED) return;

   is_position_open = true;
   current_position_ticket = result.deal;
   current_position_direction = direction;
   current_position_entry_price = result.price;
   current_position_stop_loss = stop_loss_price;

   Print("[", _Symbol, "] ", direction, " opened at ",
         DoubleToString(current_position_entry_price, _Digits));
}

//+------------------------------------------------------------------+
//| Close Position                                                    |
//+------------------------------------------------------------------+
void ClosePosition(string reason)
{
   if(!is_position_open) return;
   if(!PositionSelect(_Symbol)) { is_position_open = false; return; }

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

   if(current_position_direction == "BUY")
   {
      request.type = ORDER_TYPE_SELL;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   }
   else
   {
      request.type = ORDER_TYPE_BUY;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   }

   request.price = NormalizeDouble(request.price, _Digits);

   if(!OrderSend(request, result)) return;
   if(result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED) return;

   is_position_open = false;
   current_position_ticket = 0;
   current_position_direction = "";

   Print("[", _Symbol, "] closed: ", reason);
}

//+------------------------------------------------------------------+
// End of file
//+------------------------------------------------------------------+
```

---

## Resumen Rápido

| Aspecto | ❌ INCORRECTO | ✅ CORRECTO |
|---------|--------------|-----------|
| **Datos** | `Close[0]` | `rates[0].close` (con UpdateRates()) |
| **Ticket** | `int` | `ulong` |
| **Símbolo** | `Symbol()` | `_Symbol` |
| **Período** | `Period()` | `_Period` |
| **Decimales** | `5` (hardcoded) | `_Digits` |
| **Structs** | `MqlTradeRequest req = {}` | `ZeroMemory(req)` |
| **Retcode** | No validar | Validar DONE o PLACED |
| **Cierre** | Sin PositionSelect() | Con PositionSelect() |
| **Deviation** | No especificar | `deviation = 20` |
| **Precios** | Sin normalizar | `NormalizeDouble(price, _Digits)` |
| **Volumen** | Hardcoded | `NormalizeVolume()` |

---

## Recursos Adicionales

- **Estrategias Existentes:**
  - `Change_of_Direction.mq5` - Ejemplo completo
  - `EMA_Pullback_Pro.mq5` - Ejemplo con indicadores

- **Documentación:**
  - MQL5 Reference: https://www.mql5.com/en/docs
  - MetaTrader 5 Help: F1 en MetaEditor

---

**Última actualización:** Mayo 2026
**Versión:** 1.0
