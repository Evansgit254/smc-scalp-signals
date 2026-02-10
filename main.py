#!/usr/bin/env python3
"""
Main entry point for the Pure Quant Trading System.
Generates signals and sends them via Telegram if configured.
"""
import asyncio
import sys
from datetime import datetime
from app.generate_signals import generate_signals
from alerts.service import TelegramService
from core.signal_formatter import SignalFormatter


async def main():
    """
    Main execution function.
    Generates signals and optionally sends them via Telegram.
    """
    print("=" * 70)
    print("🚀 PURE QUANT TRADING SYSTEM - SIGNAL GENERATOR")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    
    try:
        # Generate signals
        signals = await generate_signals()
        
        if not signals:
            print("\n📭 No signals generated at this time.")
            return
        
        # Initialize Telegram service
        telegram_service = TelegramService()
        
        # Send signals via Telegram if configured
        if telegram_service.bot and telegram_service.chat_id:
            print(f"\n📤 Sending {len(signals)} signal(s) via Telegram...")
            sent_count = 0
            
            for signal_type, signal in signals:
                try:
                    # Format signal
                    formatted = SignalFormatter.format_signal(signal)
                    
                    # Send via Telegram
                    success = await telegram_service.send_signal(formatted)
                    if success:
                        sent_count += 1
                        print(f"✅ Sent {signal_type} signal for {signal.get('symbol', 'UNKNOWN')}")
                    else:
                        print(f"⚠️  Failed to send {signal_type} signal for {signal.get('symbol', 'UNKNOWN')}")
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Error processing signal: {e}")
                    continue
            
            print(f"\n📊 Summary: {sent_count}/{len(signals)} signals sent successfully")
        else:
            print("\n⚠️  Telegram not configured. Signals displayed above only.")
        
        print("\n✅ Signal generation complete!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
