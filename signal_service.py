#!/usr/bin/env python3
"""
Continuous Signal Service for Pure Quant Trading System.
Runs every 5 minutes, generates signals, and sends to Telegram.

Usage:
    python signal_service.py              # Normal mode
    python signal_service.py --test       # Test mode (one cycle)
"""
import asyncio
import signal
import sys
import hashlib
from datetime import datetime, timedelta
from typing import Set, Tuple

from app.generate_signals import generate_signals
from alerts.service import TelegramService
from core.signal_formatter import SignalFormatter

# Configuration
SIGNAL_INTERVAL = 300  # 5 minutes in seconds
DEDUP_WINDOW_HOURS = 4  # Don't resend same signal within this window
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds


class SignalService:
    """Continuous signal generation and Telegram delivery service."""
    
    def __init__(self):
        self.telegram = TelegramService()
        self.sent_signals: dict[str, datetime] = {}  # hash -> timestamp
        self.running = True
        self.cycle_count = 0
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n⏹️  Shutdown signal received. Completing current cycle...")
        self.running = False
    
    def _signal_hash(self, signal_data: dict) -> str:
        """Generate unique hash for a signal to detect duplicates."""
        key_parts = [
            signal_data.get('symbol', ''),
            signal_data.get('direction', ''),
            str(round(signal_data.get('entry_price', 0), 4)),
            signal_data.get('timeframe', '')
        ]
        return hashlib.md5('|'.join(key_parts).encode()).hexdigest()[:12]
    
    def _cleanup_old_signals(self):
        """Remove signals older than DEDUP_WINDOW from tracking."""
        cutoff = datetime.now() - timedelta(hours=DEDUP_WINDOW_HOURS)
        self.sent_signals = {
            h: ts for h, ts in self.sent_signals.items() 
            if ts > cutoff
        }
    
    def _is_duplicate(self, signal_data: dict) -> bool:
        """Check if signal was already sent recently."""
        sig_hash = self._signal_hash(signal_data)
        return sig_hash in self.sent_signals
    
    def _mark_sent(self, signal_data: dict):
        """Mark signal as sent to prevent duplicates."""
        sig_hash = self._signal_hash(signal_data)
        self.sent_signals[sig_hash] = datetime.now()
    
    async def run_cycle(self) -> Tuple[int, int]:
        """
        Run one signal generation cycle.
        Returns: (total_signals, sent_count)
        """
        self.cycle_count += 1
        print(f"\n{'='*60}")
        print(f"🔄 CYCLE #{self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        # Cleanup old tracked signals
        self._cleanup_old_signals()
        
        # Generate signals
        try:
            signals = await generate_signals()
        except Exception as e:
            print(f"❌ Error generating signals: {e}")
            return 0, 0
        
        if not signals:
            print("📭 No signals generated this cycle.")
            return 0, 0
        
        # Send to Telegram (with deduplication)
        sent_count = 0
        skipped = 0
        
        for signal_type, signal_data in signals:
            # Check for duplicates
            if self._is_duplicate(signal_data):
                skipped += 1
                print(f"⏭️  Skipped duplicate: {signal_data.get('symbol')} {signal_data.get('direction')}")
                continue
            
            # Format and send
            try:
                formatted = SignalFormatter.format_signal(signal_data)
                success = await self.telegram.send_signal(formatted)
                
                if success:
                    self._mark_sent(signal_data)
                    sent_count += 1
                    print(f"✅ Sent {signal_type}: {signal_data.get('symbol')} {signal_data.get('direction')}")
                else:
                    print(f"⚠️  Failed to send: {signal_data.get('symbol')}")
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Error sending signal: {e}")
        
        print(f"\n📊 Cycle summary: {sent_count} sent, {skipped} duplicates skipped")
        return len(signals), sent_count
    
    async def run(self, test_mode: bool = False):
        """
        Main service loop. Runs continuously until shutdown.
        
        Args:
            test_mode: If True, run only one cycle then exit
        """
        print("="*60)
        print("🚀 PURE QUANT SIGNAL SERVICE STARTED")
        print("="*60)
        print(f"📡 Interval: {SIGNAL_INTERVAL} seconds")
        print(f"🔄 Dedup window: {DEDUP_WINDOW_HOURS} hours")
        print(f"📱 Telegram: {'Configured' if self.telegram.bot else 'NOT CONFIGURED'}")
        print("="*60)
        
        if not self.telegram.bot:
            print("❌ FATAL: Telegram not configured. Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
            return
        
        while self.running:
            try:
                # Run signal cycle
                total, sent = await self.run_cycle()
                
                # Test mode: exit after one cycle
                if test_mode:
                    print("\n✅ Test cycle complete. Exiting.")
                    break
                
                # Calculate wait time (align to next 5-min mark if possible)
                now = datetime.now()
                next_run = now + timedelta(seconds=SIGNAL_INTERVAL)
                # Align to 5-minute candle close
                next_run = next_run.replace(second=15, microsecond=0)  # 15 sec after candle close
                wait_seconds = max(60, (next_run - now).total_seconds())
                
                print(f"\n⏳ Next cycle at {next_run.strftime('%H:%M:%S')} (waiting {int(wait_seconds)}s)")
                
                # Wait with graceful shutdown check
                for _ in range(int(wait_seconds)):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"❌ Cycle error: {e}")
                if not test_mode:
                    print(f"⏳ Retrying in {RETRY_DELAY} seconds...")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    break
        
        print("\n👋 Signal service stopped gracefully.")


async def main():
    test_mode = '--test' in sys.argv
    service = SignalService()
    await service.run(test_mode=test_mode)


if __name__ == "__main__":
    asyncio.run(main())
