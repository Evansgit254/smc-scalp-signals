import asyncio
from datetime import datetime
from config.config import SYMBOLS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from strategies.swing_quant_strategy import SwingQuantStrategy
from strategies.session_clock_strategy import SessionClockStrategy
from strategies.advanced_pattern_strategy import AdvancedPatternStrategy
from strategies.gold_quant_strategy import GoldQuantStrategy
from strategies.statistical_arbitrage_strategy import StatisticalArbitrageStrategy
from strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy
from strategies.anchored_poc_strategy import AnchoredPOCStrategy
from strategies.pre_news_quant_strategy import PreNewsQuantStrategy
from core.signal_formatter import SignalFormatter
from core.market_status import MarketStatus

async def generate_signals():
    """
    Main signal generation engine.
    Runs both intraday (M5) and swing (H1) strategies concurrently.
    """
    print("=" * 60)
    print("🚀 DUAL-TIMEFRAME QUANT SIGNAL GENERATOR")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Symbols: {len(SYMBOLS)} pairs")
    print("=" * 60)
    
    from config.config import DXY_SYMBOL, TNX_SYMBOL, MULTI_CLIENT_MODE
    from data.news_fetcher import NewsFetcher
    from core.client_manager import ClientManager
    
    fetcher = DataFetcher()
    client_manager = ClientManager()
    intraday_strategy = IntradayQuantStrategy()
    # V25.0: SWING disabled — 6.9% WR, 93% SL rate in backtest. Re-enable after Pillar 1 (entry fix).
    # swing_strategy = SwingQuantStrategy()
    clock_strategy = SessionClockStrategy()
    advanced_strategy = AdvancedPatternStrategy()
    gold_strategy = GoldQuantStrategy()
    stat_arb_strategy = StatisticalArbitrageStrategy()
    smc_sweep_strategy = SMCLiquiditySweepStrategy()
    poc_edge_strategy = AnchoredPOCStrategy()
    pre_news_strategy = PreNewsQuantStrategy()
    
    # Fetch macro context (DXY, TNX) for all symbols
    print("📊 Fetching macro context...")
    market_context = {}
    try:
        dxy_data = await fetcher.fetch_data_async(DXY_SYMBOL, "1h", period="10d")
        tnx_data = await fetcher.fetch_data_async(TNX_SYMBOL, "1h", period="10d")
        
        if not dxy_data.empty:
            market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_data, "1h")
        if not tnx_data.empty:
            market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_data, "1h")
    except Exception as e:
        print(f"⚠️  Warning: Could not fetch macro context: {e}")
    
    # Fetch news events (optional, can be empty)
    news_events = []
    try:
        news_fetcher = NewsFetcher()
        news_events = await news_fetcher.get_upcoming_events() if hasattr(news_fetcher, 'get_upcoming_events') else []
    except Exception as e:
        # News fetching is optional
        pass
    
    all_signals = []
    
    for symbol in SYMBOLS:
        try:
            # Fetch multi-timeframe data
            m5_data = await fetcher.fetch_data_async(symbol, "5m", period="5d")
            h1_data = await fetcher.fetch_data_async(symbol, "1h", period="30d")
            
            
            # V16.1: Market Status Check (Prevent stale data processing)
            if not MarketStatus.is_market_open(symbol):
                # Only log once per hour or if debug mode to avoid spam
                # For now, just skip silently or print if verbose
                # print(f"zzz Market Closed for {symbol}")
                continue

            if m5_data.empty or h1_data.empty:
                continue
                
            # Add indicators
            m5_df = IndicatorCalculator.add_indicators(m5_data, "5m")
            h1_df = IndicatorCalculator.add_indicators(h1_data, "1h")
            
            data_bundle = {
                'm5': m5_df,
                'h1': h1_df
            }
            
            # V25.1: Gold-Specific Specialized Engine Bypass
            if symbol == "GC=F":
                gold_signal = await gold_strategy.analyze(symbol, data_bundle, news_events, market_context)
                if gold_signal:
                    all_signals.append(('GOLD_QUANT', gold_signal))
                continue  # Skip all forex strategies for GC=F
            
            # Generate intraday signal with context
            intraday_signal = await intraday_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if intraday_signal:
                all_signals.append(('INTRADAY', intraday_signal))
            
            # V25.0: SWING disabled — re-enable after Pillar 1 (entry fix)
            # swing_signal = await swing_strategy.analyze(symbol, data_bundle, news_events, market_context)
            # if swing_signal:
            #     all_signals.append(('SWING', swing_signal))

            # V22.4: Session Clock Strategy (Time-Based Edge)
            clock_signal = await clock_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if clock_signal:
                all_signals.append(('SESSION_CLOCK', clock_signal))

            # V23: Advanced Patterns (DOW + PA)
            advanced_signal = await advanced_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if advanced_signal:
                all_signals.append(('ADVANCED', advanced_signal))
                
            # Triple-Edge Suite
            stat_arb_signal = await stat_arb_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if stat_arb_signal:
                all_signals.append(('STAT_ARB', stat_arb_signal))
                
            smc_signal = await smc_sweep_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if smc_signal:
                all_signals.append(('SMC_SWEEP', smc_signal))
                
            poc_signal = await poc_edge_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if poc_signal:
                all_signals.append(('POC_EDGE', poc_signal))

            # V26.3: Pre-News Quant (Rubber Band Z-Score + DXY Divergence)
            pre_news_signal = await pre_news_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if pre_news_signal:
                all_signals.append(('PRE_NEWS', pre_news_signal))
                
        except Exception as e:
            print(f"⚠️  Error processing {symbol}: {str(e)}")
            continue
    
    # Display all signals
    print(f"\n📊 Total Base Signals Generated: {len(all_signals)}")
    print("=" * 60)
    
    # V11.0: Multi-Client Delivery Logic
    if MULTI_CLIENT_MODE:
        clients = client_manager.get_all_active_clients()
        print(f"👥 Broadcasting to {len(clients)} active clients...")
        
        for client in clients:
            print(f"\n📱 Delivery for Client: {client['telegram_chat_id']} (Bal: ${client['account_balance']})")
            for signal_type, signal in all_signals:
                formatted = SignalFormatter.format_personalized_signal(signal, client)
                print(formatted)
    else:
        # Standard single-user mode
        for signal_type, signal in all_signals:
            formatted = SignalFormatter.format_signal(signal)
            print(formatted)
    
    return all_signals

if __name__ == "__main__":
    signals = asyncio.run(generate_signals())
    print(f"\n✅ Signal generation complete. Generated {len(signals)} total signals.")
