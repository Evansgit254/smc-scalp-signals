import asyncio
import pandas as pd
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector

async def diagnose_logic():
    print("🔍 DIAGNOSTIC MODE: Checking Logic Components...")
    fetcher = DataFetcher()
    market_data = fetcher.get_latest_data()
    
    for symbol, data in market_data.items():
        print(f"\n--- Testing {symbol} ---")
        m5 = IndicatorCalculator.add_indicators(data['m5'], "m5")
        m1 = IndicatorCalculator.add_indicators(data['m1'], "m1")
        
        # Check current bias
        bias = BiasAnalyzer.get_bias(m5)
        print(f"Current M5 Bias: {bias}")
        
        # List last 3 bias changes
        print("Last 3 M5 EMA values (to check for crosses):")
        print(m5[[f'ema_20', f'ema_50', 'close']].tail(3))
        
        # Check for ANY sweep in the last 100 bars
        sweeps_found = 0
        for i in range(len(m1)-100, len(m1)):
            current_m1 = m1.iloc[:i+1]
            # Test sweep against BOTH biases to see if detection works
            for test_bias in ["BULLISH", "BEARISH"]:
                sweep = LiquidityDetector.detect_sweep(current_m1, test_bias)
                if sweep:
                    print(f"Found {test_bias} sweep at {current_m1.index[-1]}: {sweep['description']}")
                    sweeps_found += 1
        
        if sweeps_found == 0:
            print("No sweeps detected in the last 100 M1 bars.")

if __name__ == "__main__":
    asyncio.run(diagnose_logic())
