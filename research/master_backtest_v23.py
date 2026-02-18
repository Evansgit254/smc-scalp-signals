import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config.config import SYMBOLS, SPREAD_PIPS
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.intraday_quant_strategy import IntradayQuantStrategy
from strategies.swing_quant_strategy import SwingQuantStrategy
from strategies.session_clock_strategy import SessionClockStrategy
from strategies.advanced_pattern_strategy import AdvancedPatternStrategy

async def run_master_backtest(days=30):
    print(f"🚀 MASTER BACKTEST V23 (Last {days} days)")
    print("="*80)
    
    fetcher = DataFetcher()
    strategies = {
        'INTRADAY': IntradayQuantStrategy(),
        'SWING':    SwingQuantStrategy(),
        'CLOCK':    SessionClockStrategy(),
        'ADVANCED': AdvancedPatternStrategy()
    }
    
    start_date = (datetime.now() - timedelta(days=days + 15)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    for symbol in SYMBOLS:
        print(f"  Fetching {symbol}...")
        m5_df = fetcher.fetch_range(symbol, "5m", start_date, end_date)
        h1_df = fetcher.fetch_range(symbol, "1h", start_date, end_date)
        
        if m5_df is None or m5_df.empty or h1_df is None or h1_df.empty:
            continue
            
        all_data[symbol] = {
            'm5': IndicatorCalculator.add_indicators(m5_df, "5m"),
            'h1': IndicatorCalculator.add_indicators(h1_df, "1h")
        }

    if not all_data:
        print("❌ No data loaded.")
        return

    trades = []

    for symbol, data in all_data.items():
        print(f"  Testing {symbol}...")
        h1_df = data['h1']
        m5_df = data['m5']
        
        for i in range(200, len(h1_df) - 1):
            ts = h1_df.index[i]
            h1_state = h1_df.iloc[:i+1]
            m5_i = m5_df.index.get_indexer([ts], method='ffill')[0]
            m5_state = m5_df.iloc[:m5_i+1]
            
            data_bundle = {'h1': h1_state, 'm5': m5_state}
            
            for name, strat in strategies.items():
                signal = await strat.analyze(symbol, data_bundle, [], {})
                
                if signal:
                    entry = signal['entry_price']
                    sl = signal['sl']
                    tp = signal['tp0']
                    trade_type = signal.get('trade_type', 'QUANT')
                    sl_dist = abs(entry - sl)
                    if sl_dist == 0: continue
                    
                    hit = None
                    pnl_r = 0.0
                    
                    if trade_type in ['SESSION_CLOCK', 'ADVANCED_PATTERN'] and 'expected_hold' in signal and '1 hour' in signal['expected_hold']:
                        if i+1 < len(h1_df):
                            next_bar = h1_df.iloc[i+1]
                            exit_p = next_bar['close']
                            dist_hit = False
                            if signal['direction'] == "BUY":
                                if next_bar['low'] <= sl: dist_hit = True
                            else:
                                if next_bar['high'] >= sl: dist_hit = True
                                
                            if dist_hit:
                                hit = "LOSS"; pnl_r = -1.0
                            else:
                                if signal['direction'] == "BUY":
                                    pnl_r = (exit_p - entry) / sl_dist
                                else:
                                    pnl_r = (entry - exit_p) / sl_dist
                                hit = "WIN" if pnl_r > 0 else "LOSS"
                                
                            trades.append({'t': ts, 'symbol': symbol, 'strategy': name, 'res': hit, 'r': pnl_r})
                    else:
                        lookahead = 576 
                        for j in range(m5_i+1, min(m5_i+lookahead, len(m5_df))):
                            fut = m5_df.iloc[j]
                            if signal['direction'] == "BUY":
                                if fut['low'] <= sl: hit = "LOSS"; pnl_r = -1.0; break
                                if fut['high'] >= tp: hit = "WIN"; pnl_r = (tp - entry) / sl_dist; break
                            else:
                                if fut['high'] >= sl: hit = "LOSS"; pnl_r = -1.0; break
                                if fut['low'] <= tp: hit = "WIN"; pnl_r = (entry - tp) / sl_dist; break
                        
                        if hit:
                            trades.append({'t': ts, 'symbol': symbol, 'strategy': name, 'res': hit, 'r': pnl_r})

    if not trades:
        print("No trades found.")
        return
        
    df_results = pd.DataFrame(trades)
    print("\n" + "="*80)
    print(f"{'STRATEGY':<15} | {'N':>5} | {'WIN%':>8} | {'PF':>6} | {'EXP':>8}")
    print("-" * 80)
    
    for name in strategies.keys():
        sub = df_results[df_results['strategy'] == name]
        if sub.empty: continue
        wr = (sub['res'] == 'WIN').mean() * 100
        win_r = sub[sub['r'] > 0]['r'].sum()
        loss_r = abs(sub[sub['r'] < 0]['r'].sum())
        pf = win_r / loss_r if loss_r > 0 else float('inf')
        print(f"{name:<15} | {len(sub):>5} | {wr:>7.1f}% | {pf:>6.2f} | {sub['r'].mean():>7.3f}R")
        
    total_r = df_results['r'].sum()
    print("-" * 80)
    print(f"Total Trades: {len(df_results)}  |  Total Profit: {total_r:.1f}R")
    print("="*80)

if __name__ == "__main__":
    import sys
    d = 30
    if len(sys.argv) > 1: d = int(sys.argv[1])
    asyncio.run(run_master_backtest(d))
