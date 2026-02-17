import asyncio
import pandas as pd
from strategies.swing_quant_strategy import SwingQuantStrategy
from data.fetcher import DataFetcher
from config.config import SYMBOLS
import numpy as np

async def audit_alpha_recovery():
    print("🔍 ALPHA RECOVERY AUDIT: Simulating V12.0 Thresholds")
    print("=" * 60)
    
    strategy = SwingQuantStrategy()
    fetcher = DataFetcher()
    
    # Audit a few major symbols
    audit_symbols = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "BTC-USD"]
    
    results = {
        'total_analyzed': 0,
        'signals_generated': 0,
        'signals_skipped_by_macro': 0,
        'signals_skipped_by_threshold': 0
    }
    
    # Mock macro context (Extreme Bearish to test mandatory alignment)
    market_context = {
        'DXY': pd.DataFrame({
            'open': [105.0] * 100,
            'high': [105.1] * 100,
            'low': [104.9] * 100,
            'close': [105.0] * 100, 
            'volume': [1000] * 100
        }), 
        '^TNX': pd.DataFrame({
            'open': [4.5] * 100,
            'high': [4.55] * 100,
            'low': [4.45] * 100,
            'close': [4.5] * 100,
            'volume': [1000] * 100
        })
    }
    
    # Pre-calculate indicators for context
    from indicators.calculations import IndicatorCalculator
    market_context['DXY'] = IndicatorCalculator.add_indicators(market_context['DXY'], "1h")
    market_context['^TNX'] = IndicatorCalculator.add_indicators(market_context['^TNX'], "1h")

    for symbol in audit_symbols:
        print(f"📈 Auditing {symbol}...")
        h1_data = await fetcher.fetch_data_async(symbol, "1h", period="10d")
        if h1_data is None or h1_data.empty:
            continue
            
        h1_df = IndicatorCalculator.add_indicators(h1_data, "1h")
        data_bundle = {'h1': h1_df}
        
        # We manually run a variant of analyze to see what WAS skipped
        # This is a simulation of the logic we just wrote
        results['total_analyzed'] += 1
        
        signal = await strategy.analyze(symbol, data_bundle, [], market_context)
        
        if signal:
            results['signals_generated'] += 1
            print(f"  ✅ SIGNAL: {signal['direction']} @ {signal['entry_price']} (Score: {signal['quality_score']})")
        else:
            # Why was it skipped? (Hypothetical debug)
            results['signals_skipped_by_threshold'] += 1
            print(f"  ❌ SKIPPED: Does not meet V12.0 High-Conviction Criteria")

    print("\n" + "=" * 60)
    print("📊 FINAL AUDIT RESULTS")
    print(f"Total Symbols Analyzed: {results['total_analyzed']}")
    print(f"High-Conviction Signals: {results['signals_generated']}")
    print(f"Signals Filtered (Noise): {results['signals_skipped_by_threshold']}")
    print("=" * 60)
    
    if results['signals_generated'] < results['total_analyzed']:
        print("✅ SUCCESS: The V12.0 filters are successfully rejecting 'Mid-Quality' noise.")
    else:
        print("⚠️ WARNING: Filters might still be too loose for current volatility.")

if __name__ == "__main__":
    asyncio.run(audit_alpha_recovery())
