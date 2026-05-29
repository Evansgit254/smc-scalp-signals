import asyncio
import argparse
from datetime import datetime, timedelta
from core.backtest_engine import BacktestEngine
from version import get_system_banner

async def main():
    parser = argparse.ArgumentParser(description="Pure Quant Research Backtest Engine")
    parser.add_argument("--recent", action="store_true", 
                       help="Backtest last 30 days (where M5 data exists, CRT gets full representation)")
    parser.add_argument("--days", type=int, default=30,
                       help="Number of days to backtest (default: 30)")
    parser.add_argument("--start", type=str, default=None,
                       help="Custom start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None,
                       help="Custom end date (YYYY-MM-DD)")
    parser.add_argument("--include-smc-sweep", action="store_true",
                       help="Include quarantined SMC Sweep model in research backtests")
    args = parser.parse_args()

    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    elif args.recent:
        # V36.0: Default to last X days where ALL data (including M5) is available
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    else:
        # Standard: backtest the specified number of days
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    
    print(get_system_banner())
    print(f"🕵️  STARTING INSTITUTIONAL BACKTEST")
    print(f"📅 Range: {start_date} to {end_date}")
    active_models = "CRT + Session Clock + Advanced Patterns"
    if args.include_smc_sweep:
        active_models += " + SMC Sweep (quarantined research)"
    print(f"⚙️  Alpha Core: {active_models}")
    print("=" * 50)
    
    engine = BacktestEngine(start_date, end_date, include_smc_sweep=args.include_smc_sweep)
    
    def progress_bar(p):
        cols = 40
        done = int(p * cols)
        bar = "█" * done + "░" * (cols - done)
        print(f"\r🚀 Progress: |{bar}| {p*100:.1f}%", end="")

    results = await engine.run(progress_callback=progress_bar)
    
    print("\n" + "=" * 50)
    print("📊 BACKTEST RESULTS SUMMARY")
    print("=" * 50)
    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return

    print(f"✅ Total Trades: {results['total_trades']}")
    print(f"📈 Win Rate:    {results['win_rate']:.1f}%")
    print(f"💰 Net Profit:  {results['net_pips']:.1f}R")
    print("=" * 50)
    print(f"📂 Results saved to database/backtest_results.db (Run ID: {results['run_id']})")

if __name__ == "__main__":
    asyncio.run(main())
