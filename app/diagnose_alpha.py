import asyncio
from datetime import datetime
from config.config import SYMBOLS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from core.alpha_factors import AlphaFactors
from core.alpha_combiner import AlphaCombiner

async def diagnose_alpha_levels():
    """
    Diagnostic tool to show current alpha levels across all symbols.
    """
    print("=" * 70)
    print("🔬 ALPHA FACTOR DIAGNOSTIC")
    print("=" * 70)
    
    fetcher = DataFetcher()
    results = []
    
    for symbol in SYMBOLS:
        try:
            m5_data = await fetcher.fetch_data_async(symbol, "5m", period="5d")
            h1_data = await fetcher.fetch_data_async(symbol, "1h", period="30d")
            
            if m5_data.empty or h1_data.empty:
                continue
                
            m5_df = IndicatorCalculator.add_indicators(m5_data, "5m")
            h1_df = IndicatorCalculator.add_indicators(h1_data, "1h")
            
            # M5 factors
            m5_factors = {
                'velocity': AlphaFactors.velocity_alpha(m5_df, period=20),
                'zscore': AlphaFactors.mean_reversion_zscore(m5_df, period=100)
            }
            m5_signal = AlphaCombiner.combine(m5_factors)
            
            # H1 factors
            h1_factors = {
                'velocity': AlphaFactors.velocity_alpha(h1_df, period=50),
                'zscore': AlphaFactors.mean_reversion_zscore(h1_df, period=200)
            }
            h1_signal = AlphaCombiner.combine(h1_factors)
            
            results.append({
                'symbol': symbol,
                'm5_signal': m5_signal,
                'h1_signal': h1_signal,
                'm5_vel': m5_factors['velocity'],
                'm5_z': m5_factors['zscore'],
                'h1_vel': h1_factors['velocity'],
                'h1_z': h1_factors['zscore']
            })
            
        except Exception as e:
            continue
    
    # Display results
    print(f"{'Symbol':<12} | {'M5 Signal':<10} | {'H1 Signal':<10} | {'M5 Status':<15} | {'H1 Status':<15}")
    print("-" * 70)
    
    for r in results:
        m5_status = "✅ ENTRY" if abs(r['m5_signal']) > 1.0 else "⏸️  Wait"
        h1_status = "✅ ENTRY" if abs(r['h1_signal']) > 1.3 else "⏸️  Wait"
        
        print(f"{r['symbol']:<12} | {r['m5_signal']:>10.3f} | {r['h1_signal']:>10.3f} | {m5_status:<15} | {h1_status:<15}")
    
    print("=" * 70)
    print(f"\nIntraday Threshold: |Signal| > 1.0")
    print(f"Swing Threshold: |Signal| > 1.3")
    
    # Stats
    m5_ready = sum(1 for r in results if abs(r['m5_signal']) > 1.0)
    h1_ready = sum(1 for r in results if abs(r['h1_signal']) > 1.3)
    
    print(f"\nCurrent State:")
    print(f"  Intraday Ready: {m5_ready}/{len(results)}")
    print(f"  Swing Ready: {h1_ready}/{len(results)}")

if __name__ == "__main__":
    asyncio.run(diagnose_alpha_levels())
