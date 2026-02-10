import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, EMA_TREND
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator

async def quick_signal_count(days=10):
    """Quick signal counter for V6.1 logic verification"""
    print(f"🔍 V6.1 SIGNAL COUNTER (Last {days} days)")
    print(f"Testing symbols: {SYMBOLS}")
    
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    valid_symbols = []
    
    for symbol in SYMBOLS:
        h1 = DataFetcher.fetch_range(symbol, "1h", start=start_date, end=end_date)
        m15 = DataFetcher.fetch_range(symbol, "15m", start=start_date, end=end_date)
        
        if all(df is not None and not df.empty for df in [h1, m15]):
            all_data[symbol] = {
                'h1': IndicatorCalculator.add_indicators(h1, "h1"),
                'm15': IndicatorCalculator.add_indicators(m15, "15m")
            }
            valid_symbols.append(symbol)
    
    if not valid_symbols:
        print("❌ No valid data")
        return
    
    timeline = all_data[valid_symbols[0]]['m15'].index
    signal_count = 0
    signals_by_symbol = {s: 0 for s in valid_symbols}
    
    print(f"Scanning {len(timeline)} M15 bars...")
    
    for t in timeline:
        for symbol in valid_symbols:
            m15_df = all_data[symbol]['m15']
            h1_df = all_data[symbol]['h1']
            
            if t not in m15_df.index:
                continue
            
            idx = m15_df.index.get_loc(t)
            if idx < 100:
                continue
            
            state_m15 = m15_df.iloc[:idx+1]
            state_h1 = h1_df[h1_df.index <= t]
            
            if state_h1.empty or len(state_m15) < 22:
                continue
            
            # V6.1 Simple H1 Trend
            h1_close = state_h1.iloc[-1]['close']
            h1_ema = state_h1.iloc[-1][f'ema_{EMA_TREND}']
            
            # Skip if EMA not yet calculated
            if pd.isna(h1_ema) or pd.isna(h1_close):
                continue
            
            h1_trend_val = 1 if h1_close > h1_ema else -1
            
            # V6.1 Simple Sweep (21-bar lookback)
            prev_low = state_m15.iloc[-22:-1]['low'].min()
            prev_high = state_m15.iloc[-22:-1]['high'].max()
            latest = state_m15.iloc[-1]
            
            direction = None
            if h1_trend_val == 1 and latest['low'] < prev_low < latest['close']:
                direction = "BUY"
            elif h1_trend_val == -1 and latest['high'] > prev_high > latest['close']:
                direction = "SELL"
            
            if direction:
                signal_count += 1
                signals_by_symbol[symbol] += 1
    
    print("\n" + "="*40)
    print(f"📊 RESULTS ({days} days)")
    print(f"Total Signals: {signal_count}")
    print(f"Signals per day: {signal_count/days:.1f}")
    print("\nBy Symbol:")
    for symbol, count in signals_by_symbol.items():
        print(f"  • {symbol}: {count} signals")
    print("="*40)
    
    # Extrapolate to 58 days
    estimated_58d = int((signal_count / days) * 58)
    print(f"\n📈 Extrapolated to 58 days: ~{estimated_58d} signals")
    print(f"   (V6.1 baseline was 264 signals in 58 days)")

if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(quick_signal_count(days))
