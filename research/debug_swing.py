"""
Debug script to identify why swing strategy isn't generating signals
"""
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, DXY_SYMBOL, TNX_SYMBOL
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.swing_quant_strategy import SwingQuantStrategy
from core.alpha_factors import AlphaFactors
from core.alpha_combiner import AlphaCombiner
from core.filters.macro_filter import MacroFilter

async def debug_swing():
    print("="*80)
    print("🔍 SWING STRATEGY DEBUG")
    print("="*80)
    
    fetcher = DataFetcher()
    swing_strategy = SwingQuantStrategy()
    
    start_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch macro context
    print("\n📊 Fetching macro context...")
    market_context = {}
    try:
        dxy_df = fetcher.fetch_range(DXY_SYMBOL, "1h", start_date, end_date)
        tnx_df = fetcher.fetch_range(TNX_SYMBOL, "1h", start_date, end_date)
        
        if dxy_df is not None and not dxy_df.empty:
            market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_df, "1h")
            print(f"✅ DXY data: {len(market_context['DXY'])} bars")
        if tnx_df is not None and not tnx_df.empty:
            market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_df, "1h")
            print(f"✅ TNX data: {len(market_context['^TNX'])} bars")
    except Exception as e:
        print(f"❌ Error fetching macro: {e}")
    
    # Test first 3 symbols in detail
    for symbol in SYMBOLS[:3]:
        print(f"\n{'='*80}")
        print(f"🔍 Testing {symbol}")
        print(f"{'='*80}")
        
        h1_df = fetcher.fetch_range(symbol, "1h", start_date, end_date)
        if h1_df is None or h1_df.empty:
            print(f"❌ No data for {symbol}")
            continue
        
        h1_df = IndicatorCalculator.add_indicators(h1_df, "1h")
        print(f"✅ Data: {len(h1_df)} H1 bars")
        
        # Test at multiple points in time
        test_points = [len(h1_df)//4, len(h1_df)//2, len(h1_df)-100]
        
        for idx in test_points:
            if idx < 200:
                continue
                
            state = h1_df.iloc[:idx+1]
            
            # Calculate factors manually to see what's happening
            regime = IndicatorCalculator.get_market_regime(state)
            
            factors = {
                'velocity': AlphaFactors.velocity_alpha(state, period=50),
                'zscore': AlphaFactors.mean_reversion_zscore(state, period=200),
                'momentum': AlphaFactors.momentum_alpha(state, short_period=20, long_period=60),
                'volatility': AlphaFactors.volatility_regime_alpha(state, period=100)
            }
            
            alpha_signal = AlphaCombiner.combine(factors, regime=regime)
            quality_score = AlphaCombiner.calculate_quality_score(factors, alpha_signal)
            
            # Check thresholds
            thresholds = {
                "TRENDING": 0.3,
                "RANGING": 0.4,
                "CHOPPY": 0.5
            }
            threshold = thresholds.get(regime, 0.4)
            
            direction = None
            if alpha_signal > threshold:
                direction = "BUY"
            elif alpha_signal < -threshold:
                direction = "SELL"
            
            # Check macro filter
            macro_bias = MacroFilter.get_macro_bias(market_context)
            macro_safe = MacroFilter.is_macro_safe(symbol, direction, macro_bias) if direction else False
            
            print(f"\n  📍 Bar {idx}/{len(h1_df)} ({state.index[-1]}):")
            print(f"    Regime: {regime}")
            print(f"    Velocity: {factors['velocity']:.4f}")
            print(f"    Z-Score: {factors['zscore']:.4f}")
            print(f"    Momentum: {factors['momentum']:.4f}")
            print(f"    Volatility: {factors['volatility']:.4f}")
            print(f"    Alpha Signal: {alpha_signal:.4f} (threshold: {threshold})")
            print(f"    Quality Score: {quality_score:.2f} (min: 3.0)")
            print(f"    Direction: {direction if direction else 'NONE'}")
            print(f"    Macro Bias: {macro_bias}")
            print(f"    Macro Safe: {macro_safe if direction else 'N/A'}")
            
            # Check each filter
            if quality_score < 3.0:
                print(f"    ❌ BLOCKED by quality filter ({quality_score:.2f} < 3.0)")
            elif not direction:
                print(f"    ❌ BLOCKED by threshold ({abs(alpha_signal):.4f} < {threshold})")
            elif not macro_safe:
                print(f"    ❌ BLOCKED by macro filter")
            else:
                print(f"    ✅ SIGNAL WOULD GENERATE")
        
        # Now try with the actual strategy
        print(f"\n  🎯 Testing with actual strategy...")
        signal = await swing_strategy.analyze(symbol, {'h1': h1_df}, [], market_context)
        if signal:
            print(f"    ✅ SIGNAL GENERATED: {signal['direction']} @ {signal['entry_price']:.5f}")
        else:
            print(f"    ❌ NO SIGNAL GENERATED")

if __name__ == "__main__":
    asyncio.run(debug_swing())
