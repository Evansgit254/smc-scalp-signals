import time
import asyncio
import pandas as pd
import numpy as np
from indicators.calculations import IndicatorCalculator
from strategies.smc_strategy import SMCStrategy
from strategies.breakout_strategy import BreakoutStrategy
from strategies.price_action_strategy import PriceActionStrategy
from data.fetcher import DataFetcher

async def benchmark_indicators(df):
    start = time.perf_counter()
    IndicatorCalculator.add_indicators(df, "m5")
    end = time.perf_counter()
    return (end - start) * 1000 # ms

async def benchmark_strategy(strategy, symbol, data):
    start = time.perf_counter()
    await strategy.analyze(symbol, data, [], {})
    end = time.perf_counter()
    return (end - start) * 1000 # ms

async def run_benchmark():
    print("🚀 Starting System Performance Benchmark...")
    
    # 1. Generate Synthetic Data (5000 candles ~ 17 days of M5 data)
    print("\n[Gen] Generating 5,000 candles of synthetic data...")
    dates = pd.date_range(end=pd.Timestamp.now(), periods=5000, freq='5min')
    df = pd.DataFrame({
        'open': np.random.random(5000) * 100,
        'high': np.random.random(5000) * 100,
        'low': np.random.random(5000) * 100,
        'close': np.random.random(5000) * 100,
        'volume': np.random.random(5000) * 1000
    }, index=dates)
    
    # Ensure High is highest and Low is lowest
    df['high'] = df[['open', 'close']].max(axis=1) + df['high'] * 0.01
    df['low'] = df[['open', 'close']].min(axis=1) - df['low'] * 0.01
    
    # 2. Benchmark Indicators
    print("\n[1/3] Benchmarking Indicator Engine (TA-Lib/Pandas-TA)...")
    ind_times = []
    for _ in range(50):
        t = await benchmark_indicators(df.copy())
        ind_times.append(t)
    
    avg_ind = sum(ind_times) / len(ind_times)
    print(f"   ✅ Average Cost: {avg_ind:.2f}ms per 5000 candles")
    print(f"   ⚡ Throughput: {5000 / (avg_ind/1000):.0f} candles/sec")

    # Prepare data for strategies
    processed_df = IndicatorCalculator.add_indicators(df.copy(), "m5")
    data_pack = {
        'm5': processed_df,
        'm15': processed_df, # Reusing for speed
        'h1': processed_df,
        'h4': processed_df,
        'd1': processed_df
    }
    
    # 3. Benchmark Strategies
    print("\n[2/3] Benchmarking Strategy Logic (SMC, Breakout, PA)...")
    strategies = [SMCStrategy(), BreakoutStrategy(), PriceActionStrategy()]
    
    for strategy in strategies:
        strat_times = []
        for _ in range(50):
            t = await benchmark_strategy(strategy, "EURUSD=X", data_pack)
            strat_times.append(t)
        
        avg_strat = sum(strat_times) / len(strat_times)
        print(f"   🧩 {strategy.get_name()}: {avg_strat:.4f}ms per analysis")

    # 4. Total Pipeline Estimation
    total_latency = avg_ind + sum([sum(strat_times)/len(strat_times) for strategy in strategies])
    print(f"\n[3/3] Total Pipeline Latency Estimate (Single Threaded): {total_latency:.2f}ms")
    print(f"      (Excluding Network IO and AI API latency)")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
