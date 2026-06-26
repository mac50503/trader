# Continuous Mode Logic — Extracted from MultiPattern Continuo

## Concepto

Después de que una posición alcanza **Take Profit**, el EA entra en "modo continuo" donde:
- **NO** busca patrones completos (PHASE1-5)
- **SOLO** busca un pullback simple + break del punto de salida (PHASE3 simplificado)
- Si alcanza **Stop Loss**, sale del modo continuo y vuelve a buscar patrones completos

---

## Variables Globales Necesarias

```mql5
//+------------------------------------------------------------------+
//| Global Variables — Continuous Mode                                |
//+------------------------------------------------------------------+
bool           in_continuous_mode          = false;  // Active after TP hit
string         continuous_direction        = "";     // "SELL" or "BUY"
double         continuous_point_1          = 0.0;    // Reference level to break
double         continuous_pullback_high    = 0.0;    // For SELL continuous
double         continuous_pullback_low     = 0.0;    // For BUY continuous
int            continuous_entries          = 0;      // Counter of continuous entries
```

---

## Modificación en OnTick

```mql5
void OnTick()
{
   if(!UpdateRates()) return;

   static datetime last_candle_time = 0;
   if(rates[1].time == last_candle_time) return;
   last_candle_time = rates[1].time;

   MqlRates candle = rates[1];

   if(is_position_open)
      CheckExitSignal(candle);
   else if(in_continuous_mode)  // ← NUEVA SECCIÓN
   {
      // CONTINUOUS MODE: Only look for PHASE3 breaks
      if(continuous_direction == "SELL")
         CheckContinuousSellEntry(candle);
      else if(continuous_direction == "BUY")
         CheckContinuousBuyEntry(candle);
   }
   else
   {
      // NORMAL MODE: Look for complete patterns
      // ... (lógica normal de detección de patrones)
   }
}
```

---

## Modificación en CheckExitSignal

### Para SELL:

```mql5
void CheckExitSignal(MqlRates &c)
{
   if(!is_position_open) return;
   
   // ... verificación si la posición existe ...

   if(current_position_direction == "SELL")
   {
      // ────── STOP LOSS ──────
      if(c.close >= current_position_stop_loss)  
      { 
         // STOP LOSS HIT → Break continuous mode
         Print("[", _Symbol, "] STOP LOSS hit. Exiting continuous mode.");
         in_continuous_mode = false;
         continuous_direction = "";
         continuous_point_1 = 0.0;
         continuous_entries = 0;
         ClosePosition("Stop Loss hit"); 
         return; 
      }
      
      // ────── TAKE PROFIT ──────
      if(c.close <= current_position_take_profit) 
      { 
         // TAKE PROFIT HIT → Enter continuous mode
         Print("[", _Symbol, "] TAKE PROFIT hit. Entering CONTINUOUS MODE.");
         in_continuous_mode = true;
         continuous_direction = "SELL";
         continuous_point_1 = c.close;  // ← Exit price becomes new reference
         continuous_pullback_high = 0.0;  // Reset pullback tracker
         continuous_entries++;
         Print("[", _Symbol, "] CONTINUOUS SELL MODE: Entry #", continuous_entries, 
               " | Looking for break below ", DoubleToString(continuous_point_1, _Digits));
         ClosePosition("Take Profit hit"); 
         return; 
      }
   }
   // ... similar para BUY ...
}
```

### Para BUY:

```mql5
   else if(current_position_direction == "BUY")
   {
      // ────── STOP LOSS ──────
      if(c.close <= current_position_stop_loss)  
      { 
         // STOP LOSS HIT → Break continuous mode
         Print("[", _Symbol, "] STOP LOSS hit. Exiting continuous mode.");
         in_continuous_mode = false;
         continuous_direction = "";
         continuous_point_1 = 0.0;
         continuous_entries = 0;
         ClosePosition("Stop Loss hit"); 
         return; 
      }
      
      // ────── TAKE PROFIT ──────
      if(c.close >= current_position_take_profit) 
      { 
         // TAKE PROFIT HIT → Enter continuous mode
         Print("[", _Symbol, "] TAKE PROFIT hit. Entering CONTINUOUS MODE.");
         in_continuous_mode = true;
         continuous_direction = "BUY";
         continuous_point_1 = c.close;  // ← Exit price becomes new reference
         continuous_pullback_low = 0.0;  // Reset pullback tracker
         continuous_entries++;
         Print("[", _Symbol, "] CONTINUOUS BUY MODE: Entry #", continuous_entries, 
               " | Looking for break above ", DoubleToString(continuous_point_1, _Digits));
         ClosePosition("Take Profit hit"); 
         return; 
      }
   }
```

---

## Nueva Función: CheckContinuousSellEntry

```mql5
//+------------------------------------------------------------------+
//| Check Continuous SELL Entry (PHASE3 only)                         |
//+------------------------------------------------------------------+
void CheckContinuousSellEntry(MqlRates &c)
{
   bool is_green = c.close > c.open;
   bool is_red   = c.close < c.open;
   
   // Track pullback high
   if(is_green)
   {
      continuous_pullback_high = MathMax(continuous_pullback_high, c.high);
      Log("[" + _Symbol + "] CONTINUOUS SELL: Pullback green, high=" + 
          DoubleToString(continuous_pullback_high, _Digits));
   }
   
   // Check for break below continuous_point_1
   if(c.close < continuous_point_1)
   {
      double entry_price       = c.close;
      double stop_loss_price   = continuous_pullback_high > 0.0 ? continuous_pullback_high : c.high;
      double risk              = stop_loss_price - entry_price;
      double take_profit_price = entry_price - (risk * 2.0);
      
      Print("[", _Symbol, "] CONTINUOUS SELL ENTRY #", continuous_entries + 1, 
            ": close=", DoubleToString(entry_price, _Digits),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits),
            " risk=", DoubleToString(risk, _Digits));
      
      OpenPosition("SELL", stop_loss_price, take_profit_price);
   }
   
   // Reset if price goes too high (invalidates continuous mode)
   if(continuous_pullback_high > 0.0 && c.close > continuous_pullback_high + (continuous_pullback_high * 0.01))
   {
      Print("[", _Symbol, "] CONTINUOUS SELL INVALIDATED: Price too high. Exiting continuous mode.");
      in_continuous_mode = false;
      continuous_direction = "";
      continuous_point_1 = 0.0;
      continuous_entries = 0;
   }
}
```

---

## Nueva Función: CheckContinuousBuyEntry

```mql5
//+------------------------------------------------------------------+
//| Check Continuous BUY Entry (PHASE3 only)                          |
//+------------------------------------------------------------------+
void CheckContinuousBuyEntry(MqlRates &c)
{
   bool is_green = c.close > c.open;
   bool is_red   = c.close < c.open;
   
   // Track pullback low
   if(is_red)
   {
      continuous_pullback_low = continuous_pullback_low == 0.0 ? c.low : MathMin(continuous_pullback_low, c.low);
      Log("[" + _Symbol + "] CONTINUOUS BUY: Pullback red, low=" + 
          DoubleToString(continuous_pullback_low, _Digits));
   }
   
   // Check for break above continuous_point_1
   if(c.close > continuous_point_1)
   {
      double entry_price       = c.close;
      double stop_loss_price   = continuous_pullback_low > 0.0 ? continuous_pullback_low : c.low;
      double risk              = entry_price - stop_loss_price;
      double take_profit_price = entry_price + (risk * 2.0);
      
      Print("[", _Symbol, "] CONTINUOUS BUY ENTRY #", continuous_entries + 1, 
            ": close=", DoubleToString(entry_price, _Digits),
            " SL=", DoubleToString(stop_loss_price, _Digits),
            " TP=", DoubleToString(take_profit_price, _Digits),
            " risk=", DoubleToString(risk, _Digits));
      
      OpenPosition("BUY", stop_loss_price, take_profit_price);
   }
   
   // Reset if price goes too low (invalidates continuous mode)
   if(continuous_pullback_low > 0.0 && c.close < continuous_pullback_low - (continuous_pullback_low * 0.01))
   {
      Print("[", _Symbol, "] CONTINUOUS BUY INVALIDATED: Price too low. Exiting continuous mode.");
      in_continuous_mode = false;
      continuous_direction = "";
      continuous_point_1 = 0.0;
      continuous_entries = 0;
   }
}
```

---

## Flujo Completo

### Ejemplo SELL:

```
1. Patrón completo detectado → SELL entry @ 4500, SL=4520, TP=4460

2. Precio baja a 4460 → TP HIT
   ├─ Cerrar posición
   ├─ in_continuous_mode = true
   ├─ continuous_direction = "SELL"
   ├─ continuous_point_1 = 4460 (precio de salida)
   └─ continuous_pullback_high = 0.0

3. MODO CONTINUO ACTIVO
   ├─ Precio sube (pullback): 4465, 4470, 4475
   │  └─ continuous_pullback_high = 4475
   │
   ├─ Precio baja y rompe 4460: close = 4458 → ENTRADA
   │  ├─ Entry = 4458
   │  ├─ SL = 4475 (continuous_pullback_high)
   │  ├─ Risk = 17
   │  └─ TP = 4458 - (17 * 2) = 4424
   │
   └─ Precio alcanza 4424 → TP HIT (entry #2)
      └─ Vuelve a activar modo continuo con continuous_point_1 = 4424
      
4. Si en algún momento el SL se alcanza:
   ├─ in_continuous_mode = false
   └─ Vuelve a buscar patrones completos (PHASE1-5)
```

---

## Diferencias vs Patrón Normal

| Aspecto | Patrón Normal | Modo Continuo |
|---------|--------------|---------------|
| **Trigger** | Inicio | Después de TP |
| **Fases requeridas** | PHASE1-5 (completo) | Solo PHASE3 (pullback + break) |
| **Punto de referencia** | point_1 (mínimo PHASE1) | continuous_point_1 (precio de salida TP) |
| **Stop Loss** | pullback2_high | continuous_pullback_high |
| **Desactivación** | SL hit | SL hit |
| **Reinicio** | Nueva PHASE1 | TP hit → nuevo continuous_point_1 |

---

## Invalidación del Modo Continuo

### SELL:
- Si `close > continuous_pullback_high + 1%` → modo inválido (precio subió demasiado)

### BUY:
- Si `close < continuous_pullback_low - 1%` → modo inválido (precio bajó demasiado)

Esto previene que el EA se quede esperando indefinidamente en modo continuo cuando la tendencia claramente se revirtió.

---

## Resumen para Implementación en MultiPattern

1. ✅ Agregar variables globales de modo continuo
2. ✅ Modificar `OnTick()` para detectar `in_continuous_mode`
3. ✅ Modificar `CheckExitSignal()` para activar/desactivar modo continuo
4. ✅ Agregar funciones `CheckContinuousSellEntry()` y `CheckContinuousBuyEntry()`
5. ✅ Mantener toda la lógica MultiPattern existente (arrays, IDs, zona neutral)
