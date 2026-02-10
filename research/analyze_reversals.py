"""
Enhanced Backtest Analysis: Losing Trades Profit Reversal Study

Analyzes which losing trades were in profit before hitting SL.
This reveals the need for trailing stop mechanisms.
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS, SPREAD_PIPS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.quant_core_strategy import QuantCoreStrategy

async def analyze_profit_reversals(days=30):
    print(f"🔬 PROFIT REVERSAL ANALYSIS - Last {days} days")
    print("="*60)
    
    strategy = QuantCoreStrategy()
    fetcher = DataFetcher()
    
    start_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch data
    all_data = {}
    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        df = fetcher.fetch_range(symbol, "5m", start_date, end_date)
        if df is None or df.empty: continue
        all_data[symbol] = IndicatorCalculator.add_indicators(df, "5m")

    reversal_trades = []
    
    # Re-simulate with peak tracking
    for symbol, df in all_data.items():
        half_spread = (SPREAD_PIPS / 2.0) / 10000.0
        if "JPY" in symbol: 
            half_spread = (SPREAD_PIPS / 2.0) / 100.0
        
        for i in range(200, len(df)-288):
            state = df.iloc[:i+1]
            signal = await strategy.analyze(symbol, {'m5': state}, [], {})
            
            if not signal:
                continue
                
            entry_p = signal['entry_price']
            sl = signal['sl']
            tp = signal['tp0']
            direction = signal['direction']
            
            # Track peak profit during trade life
            peak_profit_pips = 0
            hit = None
            hit_bar = None
            
            for j in range(i+1, min(i+288, len(df))):
                fut = df.iloc[j]
                
                # Calculate current profit in pips
                if direction == "BUY":
                    current_profit = (fut['high'] - entry_p) * (10000 if "JPY" not in symbol else 100)
                    peak_profit_pips = max(peak_profit_pips, current_profit)
                    
                    if (fut['low'] - half_spread) <= sl:
                        hit = "LOSS"
                        hit_bar = j
                        break
                    if (fut['high'] - half_spread) >= tp:
                        hit = "WIN"
                        hit_bar = j
                        break
                else:  # SELL
                    current_profit = (entry_p - fut['low']) * (10000 if "JPY" not in symbol else 100)
                    peak_profit_pips = max(peak_profit_pips, current_profit)
                    
                    if (fut['high'] + half_spread) >= sl:
                        hit = "LOSS"
                        hit_bar = j
                        break
                    if (fut['low'] + half_spread) <= tp:
                        hit = "WIN"
                        hit_bar = j
                        break
            
            # Only record LOSSES that had profit
            if hit == "LOSS" and peak_profit_pips > 0:
                sl_pips = abs(entry_p - sl) * (10000 if "JPY" not in symbol else 100)
                reversal_trades.append({
                    'timestamp': df.index[i],
                    'symbol': symbol,
                    'direction': direction,
                    'entry': entry_p,
                    'sl': sl,
                    'tp': tp,
                    'sl_distance_pips': sl_pips,
                    'peak_profit_pips': peak_profit_pips,
                    'peak_profit_r': peak_profit_pips / sl_pips if sl_pips > 0 else 0,
                    'bars_to_peak': hit_bar - i if hit_bar else 0,
                    'confidence': signal.get('confidence', 0)
                })
    
    print(f"\n✅ Analysis complete!\n")
    
    if not reversal_trades:
        print("No profit reversals found.")
        return
    
    df_reversals = pd.DataFrame(reversal_trades)
    df_reversals.to_csv("research/profit_reversal_analysis.csv", index=False)
    
    # Calculate statistics
    print("="*60)
    print("📊 PROFIT REVERSAL STATISTICS")
    print("="*60)
    print(f"Total Reversals (Profit → Loss): {len(df_reversals)}")
    print(f"Average Peak Profit: {df_reversals['peak_profit_pips'].mean():.1f} pips")
    print(f"Median Peak Profit: {df_reversals['peak_profit_pips'].median():.1f} pips")
    print(f"Average Peak as R-Multiple: {df_reversals['peak_profit_r'].mean():.2f}R")
    print(f"Max Peak Profit: {df_reversals['peak_profit_pips'].max():.1f} pips")
    print()
    
    # Categorize by peak profit levels
    df_reversals['reversal_category'] = pd.cut(
        df_reversals['peak_profit_r'], 
        bins=[-np.inf, 0.25, 0.5, 1.0, 2.0, np.inf],
        labels=['Minor (0-0.25R)', 'Small (0.25-0.5R)', 'Medium (0.5-1R)', 'Large (1-2R)', 'Huge (>2R)']
    )
    
    print("Reversal Categories:")
    print(df_reversals['reversal_category'].value_counts().sort_index())
    print()
    
    print("Reversals by Symbol:")
    print(df_reversals['symbol'].value_counts())
    print()
    
    # Calculate potential savings with trailing stop
    potential_savings = df_reversals['peak_profit_r'].sum()
    print(f"💡 Potential R saved with trailing stops: {potential_savings:.2f}R")
    print(f"   (Assuming 50% capture of peak profits)")
    print(f"   Estimated improvement: {potential_savings * 0.5:.2f}R")
    print()
    
    print("="*60)
    print(f"📁 Detailed results saved to: research/profit_reversal_analysis.csv")
    print("="*60)
    
    # Sample of worst reversals
    print("\nTop 10 Worst Reversals (Highest Peak → Loss):")
    top_reversals = df_reversals.nlargest(10, 'peak_profit_pips')[
        ['timestamp', 'symbol', 'direction', 'peak_profit_pips', 'peak_profit_r', 'sl_distance_pips']
    ]
    print(top_reversals.to_string(index=False))

if __name__ == "__main__":
    asyncio.run(analyze_profit_reversals())
