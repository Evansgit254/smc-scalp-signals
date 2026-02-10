import asyncio
import pandas as pd
import os
from datetime import datetime, timedelta
from config.config import SYMBOLS, SPREAD_PIPS, SLIPPAGE_PIPS, ATR_MULTIPLIER
from data.fetcher import DataFetcher
from indicators.calculations import IndicatorCalculator
from strategies.quant_core_strategy import QuantCoreStrategy

async def run_quant_backtest(days=30):
    print(f"📊 PURE QUANT BACKTEST (Last {days} days)")
    strategy = QuantCoreStrategy()
    fetcher = DataFetcher()
    
    start_date = (datetime.now() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    all_data = {}
    for symbol in SYMBOLS:
        print(f"Fetching {symbol}...")
        df = fetcher.fetch_range(symbol, "5m", start_date, end_date)
        if df is None or df.empty: continue
        all_data[symbol] = IndicatorCalculator.add_indicators(df, "5m")

    trades = []
    # Simplified simulation
    for symbol, df in all_data.items():
        for i in range(200, len(df)-288): # Leave room for exit simulation
            state = df.iloc[:i+1]
            signal = await strategy.analyze(symbol, {'m5': state}, [], {})
            
            if signal:
                entry_p = signal['entry_price']
                sl = signal['sl']
                tp = signal['tp0']
                
                # High-fidelity exit (Spread aware)
                half_spread = (SPREAD_PIPS / 2.0) / 10000.0
                if "JPY" in symbol: half_spread = (SPREAD_PIPS / 2.0) / 100.0
                
                hit = None
                for j in range(i+1, i+288):
                    fut = df.iloc[j]
                    if signal['direction'] == "BUY":
                        if (fut['low'] - half_spread) <= sl: hit = "LOSS"; break
                        if (fut['high'] - half_spread) >= tp: hit = "WIN"; break
                    else:
                        if (fut['high'] + half_spread) >= sl: hit = "LOSS"; break
                        if (fut['low'] + half_spread) <= tp: hit = "WIN"; break
                
                if hit:
                    # Capture factor details for audit
                    factors = signal.get('score_details', {})
                    
                    r_val = 2.5 if hit == "WIN" else -1.0
                    trades.append({
                        't': df.index[i], 
                        'symbol': symbol, 
                        'res': hit, 
                        'r': r_val,
                        'velocity': factors.get('velocity', 0),
                        'zscore': factors.get('zscore', 0),
                        'signal': signal.get('confidence', 0)
                    })

    if not trades:
        print("No trades generated.")
        return
        
    df_trades = pd.DataFrame(trades)
    df_trades.to_csv("research/quant_audit_results.csv", index=False)
    print(f"📊 Forensic logs saved to research/quant_audit_results.csv")
    
    # 🧪 CALCULATE INSTITUTIONAL METRICS
    total_trades = len(df_trades)
    wins = len(df_trades[df_trades['res'] == 'WIN'])
    losses = len(df_trades[df_trades['res'] == 'LOSS'])
    win_rate = (wins / total_trades) * 100
    
    total_r = df_trades['r'].sum()
    expectancy = total_r / total_trades
    
    win_r = df_trades[df_trades['r'] > 0]['r'].sum()
    loss_r = abs(df_trades[df_trades['r'] < 0]['r'].sum())
    profit_factor = win_r / loss_r if loss_r != 0 else float('inf')
    
    # Max Drawdown (R-based)
    df_trades['cum_r'] = df_trades['r'].cumsum()
    df_trades['peak'] = df_trades['cum_r'].cummax()
    df_trades['dd'] = df_trades['cum_r'] - df_trades['peak']
    max_dd = df_trades['dd'].min()

    print("\n" + "="*55)
    print("📈 PURE QUANT INSTITUTIONAL PERFORMANCE REPORT")
    print("="*55)
    print(f"{'Performance Metric':<30} | {'Value':<15}")
    print("-" * 55)
    print(f"{'Total Execution Samples':<30} | {total_trades:<15}")
    print(f"{'Winning Trades':<30} | {wins:<15}")
    print(f"{'Losing Trades':<30} | {losses:<15}")
    print(f"{'Statistical Win Rate':<30} | {win_rate:>14.2f}%")
    print(f"{'Profit Factor (R)':<30} | {profit_factor:>15.2f}")
    print(f"{'Cumulative R-Multiple':<30} | {total_r:>14.2f}R")
    print(f"{'Expectancy (R per Trade)':<30} | {expectancy:>15.4f}")
    print(f"{'Max Peak-to-Valley DD':<30} | {max_dd:>14.2f}R")
    print("="*55)

if __name__ == "__main__":
    asyncio.run(run_quant_backtest())
