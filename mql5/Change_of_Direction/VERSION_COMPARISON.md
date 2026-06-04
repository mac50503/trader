# Change of Direction — Version Comparison

Detailed comparison of all MQL5 Expert Advisor versions and their Python equivalents.

---

## Overview Table

| Aspect | V6 | V7 | V8 (MultiPattern) |
|--------|----|----|-------------------|
| **Status** | ✅ Production | ⚠️ Experimental | ✅ Production |
| **Python Equivalent** | `change_of_direction_strategy.py` | *(none)* | `pattern_priority_strategy.py` |
| **Patterns Tracked** | 1 SELL + 1 BUY | 1 SELL + 1 BUY | Multiple SELL + Multiple BUY |
| **Pattern Init** | Only when IDLE | Only when IDLE | Every red/green candle |
| **Pattern Selection** | The only pattern | The only pattern | First to complete |
| **Reset Logic** | Manual/Invalidation | Manual/Invalidation | Auto on completion |
| **Trend Filter** | EMA40 M5 | EMA40 M5 | EMA40 M5 |
| **Risk/Reward** | 1:2 | 1:2 | 1:2 |

---

## Version 6 (V6) — Base Version

### File
`Change_of_Direction_V6.mq5`

### Python Equivalent
`strategies/change_of_direction_strategy.py`

### Description
The **base implementation** of the Change of Direction strategy. Tracks a single SELL pattern and a single BUY pattern at a time.

### How It Works

1. **IDLE State**: No pattern is being tracked
2. **Pattern Detection**: 
   - Sees 2+ consecutive RED candles → starts SELL pattern
   - Sees 2+ consecutive GREEN candles → starts BUY pattern
3. **Phase Progression**: Pattern progresses through PHASE1 → PHASE2 → PHASE3 → PHASE4 → PHASE5
4. **Entry**: When pattern completes PHASE5 and entry conditions met → opens position
5. **Reset**: Pattern resets if invalidated or after position opens

### State Machine

```
SELL Pattern:
├── IDLE
├── PHASE1_DROP       (2+ consecutive reds)
├── PHASE2_PULLBACK1  (2+ greens, not consecutive)
├── PHASE3_BREAK      (close < point_1)
├── PHASE4_PULLBACK2  (2+ greens, not consecutive)
└── PHASE5_ENTRY      (close <= point_2) → SELL

BUY Pattern:
├── IDLE
├── PHASE1_DROP       (2+ consecutive greens)
├── PHASE2_PULLBACK1  (2+ reds, not consecutive)
├── PHASE3_BREAK      (close > point_1)
├── PHASE4_PULLBACK2  (2+ reds, not consecutive)
└── PHASE5_ENTRY      (close >= point_2) → BUY
```

### Validation Rules

**PHASE2 Validation:**
- From 2nd pullback candle onwards, close must NOT cross point_1
- SELL PHASE2: if green candle close < point_1 → INVALID
- BUY PHASE2: if red candle close > point_1 → INVALID

**PHASE4 Validation:**
- From 2nd pullback candle onwards, close must NOT cross point_1
- SELL PHASE4: if green candle close < point_1 → INVALID
- BUY PHASE4: if red candle close > point_1 → INVALID

**PHASE4/PHASE5 Reset:**
- SELL: if close > pullback1_high → RESET
- BUY: if close < pullback1_low → RESET

### Pros
✅ Proven and stable  
✅ Clear state machine logic  
✅ Direct Python equivalent  
✅ Easier to debug  
✅ Lower false signal rate  

### Cons
❌ Can miss opportunities while waiting for pattern completion  
❌ If pattern invalidates in PHASE4, must start from scratch  
❌ Only tracks one pattern per direction  

### Use When
- You want **stability** over aggressiveness
- You prefer **fewer but higher-quality** signals
- You're **new** to the strategy
- You want **1:1 parity** with Python base version

---

## Version 7 (V7) — Experimental

### File
`Change_of_Direction_V7.mq5`

### Python Equivalent
*(None — testing only)*

### Description
**Experimental version** with additional validation rules. Adds stricter invalidation conditions during pullback phases.

### Additional Validation

**New Rule**: ANY candle BETWEEN 1st and 2nd pullback candle that crosses point_1 invalidates the pattern.

**SELL Example:**
```
PHASE2: green1, RED, green2
        ↑       ↑
        OK      If this RED close < point_1 → INVALID
```

**BUY Example:**
```
PHASE2: red1, GREEN, red2
        ↑     ↑
        OK    If this GREEN close > point_1 → INVALID
```

### Rationale
Attempting to filter out "weak" patterns where price action shows indecision before completing the required pullback candles.

### Issues
⚠️ **Too strict** — invalidates many valid patterns  
⚠️ **Lower signal frequency** — fewer entries  
⚠️ **Not production-tested** — limited real-world validation  

### Status
**Not recommended for production.** This was an experimental test to see if additional filtering would improve win rate, but results were inconclusive.

### Use When
- You're **testing** stricter validation rules
- You want to **compare** with V6
- **Do NOT use** for live trading

---

## Version 8 (V8) — MultiPattern

### File
`Change_of_Direction_MultiPattern.mq5`

### Python Equivalent
`strategies/pattern_priority_strategy.py`

### Description
**Multi-pattern tracking version**. Tracks ALL possible patterns simultaneously. The **first pattern to complete** wins, and all others are discarded.

### How It Works

1. **Continuous Detection**:
   - Every RED candle → starts a new SELL pattern
   - Every GREEN candle → starts a new BUY pattern
   - Patterns are added to arrays: `sell_patterns[]`, `buy_patterns[]`

2. **Parallel Updates**:
   - On each new candle, update ALL active patterns
   - Each pattern has its own state and progression

3. **First Winner**:
   - First pattern to reach PHASE5 and generate entry → **WINS**
   - All other patterns (SELL + BUY) are immediately reset

4. **Cleanup**:
   - Invalid patterns are removed automatically
   - Only valid, progressing patterns remain

### Data Structure

```mql5
struct Pattern
{
   int      id;                // Unique pattern ID
   string   direction;         // "SELL" or "BUY"
   int      phase;             // Current phase (0-5)
   
   // State variables
   double   point_1;
   double   point_2;
   double   pullback1_high;    // SELL
   double   pullback2_high;    // SELL
   double   pullback1_low;     // BUY
   double   pullback2_low;     // BUY
   int      red_count;
   int      green_count;
   // ...
};

Pattern  sell_patterns[];      // Array of SELL patterns
Pattern  buy_patterns[];       // Array of BUY patterns
```

### Example Flow

```
Candle 1 (RED):    Pattern #1 starts (SELL PHASE1)
Candle 2 (RED):    Pattern #1 continues, Pattern #2 starts (SELL PHASE1)
Candle 3 (GREEN):  Pattern #1 → PHASE2, Pattern #2 continues
Candle 4 (GREEN):  Pattern #1 → PHASE3, Pattern #2 → PHASE2
Candle 5 (RED):    Pattern #1 → PHASE4, Pattern #2 → PHASE3, Pattern #3 starts
Candle 6 (GREEN):  Pattern #1 accumulates pullback2, Pattern #2 → PHASE4
Candle 7 (GREEN):  Pattern #1 accumulates pullback2, Pattern #2 accumulates pullback2
Candle 8 (RED):    Pattern #1 → PHASE5, Pattern #2 → PHASE5
Candle 9 (RED):    Pattern #2 completes entry condition → WINS!
                   → All patterns reset (Pattern #1, #2, #3 cleared)
```

### Validation Rules

**Same as V6:**
- PHASE2/PHASE4: pullback candles must not cross point_1
- PHASE4/PHASE5: must not exceed pullback1_high/low

**Additional:**
- Invalid patterns removed from array each candle
- Pattern ID counter increments for each new pattern

### Pros
✅ **More opportunities** — tracks all possible patterns  
✅ **First to complete wins** — no waiting for old patterns  
✅ **Auto-cleanup** — invalid patterns removed automatically  
✅ **Python equivalent** available for backtesting  
✅ **More reactive** — adapts quickly to new patterns  

### Cons
❌ **More complex** — harder to debug  
❌ **More CPU usage** — updates many patterns per candle  
❌ **Log spam** — many pattern start/stop messages (if DEBUG_LOGS=true)  
❌ **Less predictable** — pattern #5 might win over pattern #2  

### Use When
- You want **maximum opportunities**
- You don't mind **more complexity**
- You're **comfortable** with the strategy
- You want to **match** Python `pattern_priority_strategy.py`

---

## Performance Comparison

| Metric | V6 | V7 | V8 |
|--------|----|----|-----|
| **Signal Frequency** | Medium | Low | High |
| **False Signals** | Low | Very Low | Medium |
| **CPU Usage** | Low | Low | Medium |
| **Ease of Debug** | Easy | Easy | Hard |
| **Missed Opportunities** | Some | Many | Few |
| **Pattern Count (active)** | 2 (1 SELL + 1 BUY) | 2 (1 SELL + 1 BUY) | Variable (5-20+) |

---

## Python Equivalents

### V6 ↔ `change_of_direction_strategy.py`

**Identical Logic:**
- Single SELL pattern tracked in `_sell_*` variables
- Single BUY pattern tracked in `_buy_*` variables
- Same phase progression
- Same validation rules

**File:** `strategies/change_of_direction_strategy.py`

### V8 ↔ `pattern_priority_strategy.py`

**Identical Logic:**
- Multiple patterns in `_sell_patterns[]` and `_buy_patterns[]`
- Each pattern is a `PatternState` object
- First completed pattern wins
- Auto-reset all patterns on completion

**File:** `strategies/pattern_priority_strategy.py`

---

## Migration Guide

### From V6 to V8

**What Changes:**
- More signals will be generated
- Logs will show multiple patterns being tracked
- First completed pattern wins (not necessarily the first detected)

**Parameters:** Same parameters work for both

**Recommended Approach:**
1. Test V8 in PAPER_TRADING_MODE first
2. Compare signal frequency with V6
3. If too aggressive, increase `MIN_RED_CANDLES` and `MIN_GREEN_CANDLES`

### From V7 to V6 or V8

**V7 → V6:**
- More signals (V7 is stricter)
- Same structure, just remove extra validation

**V7 → V8:**
- Much more signals
- Different tracking mechanism

---

## Which Version Should I Use?

### Choose V6 if:
- ✅ You want proven stability
- ✅ You're new to the strategy
- ✅ You want 1:1 parity with Python base
- ✅ You prefer quality over quantity

### Choose V8 if:
- ✅ You want maximum opportunities
- ✅ You're comfortable with more complexity
- ✅ You want to match Python `pattern_priority_strategy.py`
- ✅ You don't mind more log output

### Avoid V7:
- ❌ Not recommended for production
- ❌ Too strict validation
- ❌ No Python equivalent

---

## Testing Recommendations

### Backtest Setup
1. **Timeframe**: M5 (recommended)
2. **Symbol**: XAUUSD
3. **Period**: 3-6 months minimum
4. **Model**: Every tick (most accurate)

### Compare Versions
Run backtest on same data:
- V6: Track signal count, win rate, profit
- V8: Track signal count, win rate, profit
- Compare: Did V8 catch more winners? More losers?

### Forward Test
1. Start with PAPER_TRADING_MODE = true
2. Run both V6 and V8 simultaneously on demo accounts
3. Compare for 2-4 weeks
4. Choose the one that matches your risk profile

---

## Summary

| Version | Best For | Python Match |
|---------|----------|--------------|
| **V6** | Stability, beginners | `change_of_direction_strategy.py` |
| **V7** | Testing only | *(none)* |
| **V8** | Max opportunities, advanced | `pattern_priority_strategy.py` |

**Recommendation**: Start with **V6**, migrate to **V8** if you want more signals.
