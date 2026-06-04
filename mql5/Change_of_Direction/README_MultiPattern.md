# Change of Direction — MultiPattern EA

## 📋 Descripción

**Version:** 8.0  
**Base:** Change of Direction V6

Este EA implementa la estrategia **Pattern Priority** donde se rastrean **TODOS los patrones posibles simultáneamente** y el **primer patrón que se complete gana**.

## 🎯 Filosofía

### ❌ Estrategia Tradicional (V6)
- Rastrea **1 patrón SELL** y **1 patrón BUY** a la vez
- Si un patrón llega a PHASE3/4/5, espera a que se complete o se invalide
- Puede perder oportunidades mientras espera

### ✅ MultiPattern (V8)
- Rastrea **MÚLTIPLES patrones SELL y BUY** simultáneamente
- Cada vez que detecta velas rojas/verdes consecutivas → **inicia un nuevo patrón**
- **El primer patrón que llegue a generar señal de entrada → GANA**
- Cuando un patrón se completa → **TODOS los demás se descartan**

## 🔧 Cómo Funciona

### Detección Continua
```
Vela 1 (roja):     Pattern #1 inicia (SELL PHASE1)
Vela 2 (roja):     Pattern #1 continúa, Pattern #2 inicia (SELL PHASE1)
Vela 3 (verde):    Pattern #1 → PHASE2, Pattern #2 continúa
Vela 4 (verde):    Pattern #1 → PHASE3, Pattern #2 → PHASE2
Vela 5 (roja):     Pattern #1 → PHASE4, Pattern #2 → PHASE3, Pattern #3 inicia
...
Vela 12:           Pattern #2 completa PHASE5 → SEÑAL SELL
                   → Pattern #2 GANA, todos los demás se resetean
```

### Actualización Paralela
- **Cada vela**: actualiza TODOS los patrones activos
- **Patrones inválidos**: se eliminan automáticamente
- **Primer ganador**: ejecuta la operación y resetea todo

## 📊 Ejemplo de Logs

```
[XAUUSD] Pattern #1: SELL PHASE1 started, point_1=2614.50
[XAUUSD] Pattern #2: SELL PHASE1 started, point_1=2612.30
[XAUUSD] Pattern #1: → PHASE2
[XAUUSD] Pattern #3: BUY PHASE1 started, point_1=2615.00
[XAUUSD] Pattern #1: → PHASE3, waiting for break of 2614.50
[XAUUSD] Pattern #2: → PHASE2
[XAUUSD] Pattern #2: → PHASE3, waiting for break of 2612.30
[XAUUSD] Pattern #2: → PHASE4 (point_1 broken)
[XAUUSD] Pattern #1: → PHASE4 (point_1 broken)
[XAUUSD] Pattern #2: → PHASE5, waiting for entry at 2610.15
[XAUUSD] Pattern #2 SELL ENTRY: close=2610.00 SL=2618.50 TP=2593.00 risk=8.50
[XAUUSD] All patterns reset
```

## ⚙️ Parámetros

| Parámetro | Valor por Defecto | Descripción |
|-----------|-------------------|-------------|
| `MIN_RED_CANDLES` | 2 | Mínimo de velas rojas consecutivas |
| `MIN_GREEN_CANDLES` | 2 | Mínimo de velas verdes por pullback |
| `ALLOW_SHORT` | true | Permitir señales SELL |
| `ALLOW_LONG` | true | Permitir señales BUY |
| `RISK_PERCENT` | 1.0 | Riesgo por operación (% del balance) |
| `MAX_OPEN_POSITIONS` | 1 | Máximo de posiciones abiertas |
| `PAPER_TRADING_MODE` | false | Modo simulación (solo logs) |
| `DEBUG_LOGS` | false | Mostrar logs detallados de fases |

## 📈 Ventajas vs V6

### Mayor Reactividad
- No se queda "atascado" esperando que un patrón antiguo se complete
- Siempre está evaluando nuevas oportunidades

### Primera Oportunidad Gana
- El patrón más rápido en completarse es el que se ejecuta
- No importa si es el patrón más "fuerte", sino el más **completo**

### Sin Conflictos
- Cuando un patrón gana, todos los demás desaparecen automáticamente
- No hay confusión sobre cuál patrón seguir

## 🚀 Instalación

1. Copiar el archivo `Change_of_Direction_MultiPattern.mq5` a:
   ```
   C:\Users\[TU_USUARIO]\AppData\Roaming\MetaQuotes\Terminal\[ID_TERMINAL]\MQL5\Experts\
   ```

2. En MetaTrader 5:
   - Ir a **Herramientas → Editor MetaEditor**
   - Abrir el archivo
   - Presionar **F7** (compilar)
   - Arrastrar el EA al gráfico

3. Configurar parámetros según preferencia

## ⚠️ Recomendaciones

- **Timeframe**: M5 (el EA usa EMA40 M5 como filtro de tendencia)
- **Símbolo**: XAUUSD (optimizado para oro)
- **Modo Paper**: Prueba primero con `PAPER_TRADING_MODE = true`
- **DEBUG_LOGS**: Activa para ver todas las transiciones de fase

## 📝 Diferencias con V6

| Aspecto | V6 (Original) | V8 (MultiPattern) |
|---------|---------------|-------------------|
| Patrones rastreados | 1 SELL + 1 BUY | Múltiples SELL + múltiples BUY |
| Inicio de patrón | Solo si no hay patrón activo | Cada vela roja/verde |
| Selección | El único patrón | Primer patrón en completarse |
| Reset | Manual o por invalidación | Automático al completar |

## 🐛 Solución de Problemas

**No genera señales:**
- Verifica que `ALLOW_LONG` o `ALLOW_SHORT` estén en `true`
- Activa `DEBUG_LOGS = true` para ver el progreso de patrones
- Verifica que el filtro EMA40 M5 no esté bloqueando (price vs EMA40)

**Demasiados patrones activos:**
- Esto es normal, los patrones se limpian automáticamente
- Los patrones inválidos se eliminan en cada vela
- Solo el primero en completarse se ejecuta

## 📞 Soporte

Para preguntas o problemas, consulta el código fuente o la documentación del proyecto principal.

---

**Versión:** 8.0  
**Fecha:** 2026-06-04  
**Basado en:** Change of Direction V6  
**Autor:** AlgoTrader Pro
