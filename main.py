#!/usr/bin/env python3
"""
Main entry point for the CRT + Advanced Pattern signal system.
Runs one guarded signal-service cycle.
"""
import asyncio
import sys
from datetime import datetime
from signal_service import SignalService


async def main():
    """
    Main execution function.
    Runs the same guarded path used by the continuous service.
    """
    print("=" * 70)
    print("🚀 CRT + ADVANCED PATTERN SIGNAL SERVICE")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    
    try:
        total_signals, sent_count = await SignalService().run_cycle()
        print(f"\n📊 Summary: {sent_count}/{total_signals} signals sent")
        print("\n✅ Signal service cycle complete!")
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
