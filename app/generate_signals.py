import asyncio
from datetime import datetime
from config.config import SYMBOLS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from strategies.swing_quant_strategy import SwingQuantStrategy
from core.signal_formatter import SignalFormatter

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
    swing_strategy = SwingQuantStrategy()
    
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
            
            if m5_data.empty or h1_data.empty:
                continue
                
            # Add indicators
            m5_df = IndicatorCalculator.add_indicators(m5_data, "5m")
            h1_df = IndicatorCalculator.add_indicators(h1_data, "1h")
            
            data_bundle = {
                'm5': m5_df,
                'h1': h1_df
            }
            
            # Generate intraday signal with context
            intraday_signal = await intraday_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if intraday_signal:
                all_signals.append(('INTRADAY', intraday_signal))
            
            # Generate swing signal with context
            swing_signal = await swing_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if swing_signal:
                all_signals.append(('SWING', swing_signal))
                
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
