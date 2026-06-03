import asyncio
from datetime import datetime
from config.manager import config_manager
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.crt_strategy import CRTStrategy
from strategies.advanced_pattern_strategy import AdvancedPatternStrategy
from core.signal_formatter import SignalFormatter
from core.market_status import MarketStatus


async def generate_signals():
    """
    Main signal generation engine.
    Runs the active research baseline: CRT and Advanced Pattern only.
    """
    print("=" * 60)
    print("🚀 CRT + ADVANCED PATTERN SIGNAL GENERATOR")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    settings = config_manager.refresh()
    print(f"Symbols: {len(settings.symbols)} pairs")
    print("=" * 60)
    
    from data.news_fetcher import NewsFetcher
    from core.client_manager import ClientManager
    
    fetcher = DataFetcher()
    client_manager = ClientManager()
    crt_strategy = CRTStrategy()
    advanced_strategy = AdvancedPatternStrategy()
    
    # Fetch macro context (DXY, TNX) for all symbols
    print("📊 Fetching macro context...")
    market_context = {}
    try:
        dxy_data = await fetcher.fetch_data_async(settings.dxy_symbol, "1h", period="60d")
        tnx_data = await fetcher.fetch_data_async(settings.tnx_symbol, "1h", period="60d")
        
        if dxy_data is not None and not dxy_data.empty:
            market_context['DXY'] = IndicatorCalculator.add_indicators(dxy_data, "1h")
        if tnx_data is not None and not tnx_data.empty:
            market_context['^TNX'] = IndicatorCalculator.add_indicators(tnx_data, "1h")
    except Exception as e:
        print(f"⚠️  Warning: Could not fetch macro context: {e}")
    
    # Fetch news events (optional, can be empty)
    news_events = []
    try:
        news_fetcher = NewsFetcher()
        news_events = news_fetcher.get_upcoming_events() if hasattr(news_fetcher, 'get_upcoming_events') else []
    except Exception as e:
        # News fetching is optional
        pass
    
    all_signals = []
    symbol_data = {}

    async def fetch_symbol_bundle(symbol: str):
        sem = fetch_symbol_bundle.sem
        async with sem:
            m5_data, h1_data, d1_data = await asyncio.gather(
                fetcher.fetch_data_async(symbol, "5m", period="5d"),
                fetcher.fetch_data_async(symbol, "1h", period="30d"),
                fetcher.fetch_data_async(symbol, "1d", period="365d"),
            )
            return symbol, m5_data, h1_data, d1_data

    fetch_symbol_bundle.sem = asyncio.Semaphore(8)
    try:
        fetched = await asyncio.gather(*(fetch_symbol_bundle(symbol) for symbol in settings.symbols))
        symbol_data = {symbol: (m5, h1, d1) for symbol, m5, h1, d1 in fetched}
    except Exception as e:
        print(f"⚠️  Warning: Concurrent symbol fetch failed: {e}")
    
    for symbol in settings.symbols:
        try:
            # Fetch multi-timeframe data
            m5_data, h1_data, d1_data = symbol_data.get(symbol, (None, None, None))
            
            
            # V16.1: Market Status Check (Prevent stale data processing)
            if not MarketStatus.is_market_open(symbol):
                # Only log once per hour or if debug mode to avoid spam
                # For now, just skip silently or print if verbose
                # print(f"zzz Market Closed for {symbol}")
                continue

            if m5_data is None or h1_data is None or d1_data is None or m5_data.empty or h1_data.empty or d1_data.empty:
                continue
                
            # Add indicators
            m5_df = IndicatorCalculator.add_indicators(m5_data, "5m")
            h1_df = IndicatorCalculator.add_indicators(h1_data, "1h")
            d1_df = IndicatorCalculator.add_indicators(d1_data, "1d")
            
            data_bundle = {
                'm5': m5_df,
                'h1': h1_df,
                'd1': d1_df
            }
            
            # V28.0: CRT Strategy — ALWAYS ON (locked)
            crt_signal = await crt_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if crt_signal:
                all_signals.append(('CRT', crt_signal))

            # V23: Advanced Patterns — ALWAYS ON (locked)
            advanced_signal = await advanced_strategy.analyze(symbol, data_bundle, news_events, market_context)
            if advanced_signal:
                all_signals.append(('ADVANCED', advanced_signal))

                
        except Exception as e:
            print(f"⚠️  Error processing {symbol}: {str(e)}")
            continue
    
    # Display all signals
    print(f"\n📊 Total Base Signals Generated: {len(all_signals)}")
    print("=" * 60)
    
    # V11.0: Multi-Client Delivery Logic
    if settings.multi_client_mode:
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
