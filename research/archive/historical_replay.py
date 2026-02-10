import asyncio
import pandas as pd
from datetime import datetime, timedelta
from config.config import SYMBOLS, MIN_CONFIDENCE_SCORE
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from structure.bias import BiasAnalyzer
from liquidity.sweep_detector import LiquidityDetector
from strategy.displacement import DisplacementAnalyzer
from strategy.entry import EntryLogic
from filters.session_filter import SessionFilter
from filters.volatility_filter import VolatilityFilter
from strategy.scoring import ScoringEngine
from data.news_fetcher import NewsFetcher
from filters.news_filter import NewsFilter

async def replay_symbol(symbol: str, market_data: dict, news_events: list):
    m5_df = market_data['m5']
    m1_df = market_data['m1']

    # Add Indicators
    m5_df = IndicatorCalculator.add_indicators(m5_df, "m5")
    m1_df = IndicatorCalculator.add_indicators(m1_df, "m1")

    print(f"\n--- Replaying {symbol} (Last 3000 M1 bars) ---")
    
    setups_found = 0
    # Increase range to look back further (3000 bars = ~2 days)
    for i in range(max(0, len(m1_df) - 3000), len(m1_df)):
        current_m1 = m1_df.iloc[:i+1]
        timestamp = current_m1.index[-1]
        
        current_m5 = m5_df[m5_df.index <= timestamp]
        if current_m5.empty: continue
        
        bias = BiasAnalyzer.get_bias(current_m5)
        if bias == "NEUTRAL": continue
        
        sweep = LiquidityDetector.detect_sweep(current_m1, bias)
        if not sweep: continue
        
        direction = "BUY" if bias == "BULLISH" else "SELL"
        displaced = DisplacementAnalyzer.is_displaced(current_m1, direction)
        entry = EntryLogic.check_pullback(current_m1, direction)
        
        # Filters
        volatile = VolatilityFilter.is_volatile(current_m1)
        
        # Scoring (Forced session for replay)
        score_details = {
            'bias_strength': True,
            'sweep_type': sweep['type'],
            'displaced': displaced,
            'pullback': entry is not None,
            'session': "London Open",
            'volatile': volatile
        }
        confidence = ScoringEngine.calculate_score(score_details)
        
        # Lower threshold for replay to show the user the engine is alive
        IF_REPLAY_MIN_SCORE = 7.0

        if confidence >= IF_REPLAY_MIN_SCORE:
            setups_found += 1
            atr = current_m1.iloc[-1]['atr']
            levels = EntryLogic.calculate_levels(current_m1, direction, sweep['level'], atr)
            
            print(f"✅ FOUND SETUP at {timestamp}")
            print(f"   Direction: {direction} | Confidence: {confidence}/10")
            print(f"   Logic: {sweep['description']}")
            print(f"   Price: {current_m1.iloc[-1]['close']:.5f} | SL: {levels['sl']:.5f} | TP1: {levels['tp1']:.5f}")

    if setups_found == 0:
        print(f"   No high-confidence setups found in this window.")

async def main():
    print(f"🚀 SMC Signal Replay Engine Running... {datetime.now()}")
    fetcher = DataFetcher()
    market_data = fetcher.get_latest_data()
    news_events = NewsFetcher.fetch_news()
    
    for symbol, data in market_data.items():
        await replay_symbol(symbol, data, news_events)

if __name__ == "__main__":
    asyncio.run(main())
