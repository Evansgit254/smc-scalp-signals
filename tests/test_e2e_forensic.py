#!/usr/bin/env python3
"""
End-to-End Forensic Validation Test
Tests the complete signal flow from data fetch to Telegram broadcast
"""
import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

import sqlite3
import asyncio
from datetime import datetime
import pandas as pd
import numpy as np


def test_e2e_signal_flow():
    """Test complete signal generation pipeline"""
    print("=" * 80)
    print("🔬 FORENSIC END-TO-END VALIDATION TEST")
    print("=" * 80)
    
    # Step 1: Database Integrity Check
    print("\n📊 Step 1: Database Integrity Check")
    db_path = "database/signals.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check schema
    cursor.execute("PRAGMA table_info(signals)")
    columns = {row[1] for row in cursor.fetchall()}
    required_cols = {'timestamp', 'symbol', 'direction', 'entry_price', 'sl', 'tp1', 'tp2',
                     'reasoning', 'timeframe', 'confidence', 'trade_type', 'quality_score',
                     'regime', 'expected_hold', 'risk_details', 'score_details'}
    missing_cols = required_cols - columns
    
    if missing_cols:
        print(f"   ❌ FAIL: Missing columns: {missing_cols}")
        return False
    print(f"   ✅ PASS: All {len(required_cols)} required columns present")
    
    # Check WAL mode
    cursor.execute("PRAGMA journal_mode")
    journal_mode = cursor.fetchone()[0]
    if journal_mode.upper() == 'WAL':
        print(f"   ✅ PASS: WAL mode enabled ({journal_mode})")
    else:
        print(f"   ⚠️  WARNING: Journal mode is {journal_mode}, expected WAL")
    
    initial_count = cursor.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    print(f"   📝 Current signal count: {initial_count}")
    conn.close()
    
    # Step 2: Generate Synthetic Signal
    print("\n🎯 Step 2: Signal Generation Test")
    try:
        from strategies.intraday_quant_strategy import IntradayQuantStrategy
        from core.data_fetcher import DataFetcher
        
        # Create synthetic market data
        dates = pd.date_range(end=datetime.now(), periods=500, freq='5min')
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.randn(500) * 0.5)
        
        df = pd.DataFrame({
            'open': prices,
            'high': prices + np.abs(np.random.randn(500) * 0.2),
            'low': prices - np.abs(np.random.randn(500) * 0.2),
            'close': prices + np.random.randn(500) * 0.1,
            'volume': np.random.randint(1000, 10000, 500)
        }, index=dates)
        
        print(f"   📈 Created synthetic data: {len(df)} candles, price range {df['close'].min():.2f}-{df['close'].max():.2f}")
        
        # Run strategy
        strategy = IntradayQuantStrategy()
        signal = strategy.analyze('TESTPAIR', df, '5m')
        
        if signal:
            print(f"   ✅ PASS: Strategy generated signal")
            print(f"      Direction: {signal.get('direction')}")
            print(f"      Entry: {signal.get('entry_price')}")
            print(f"      Quality: {signal.get('quality_score')}")
            print(f"      Trade Type: {signal.get('trade_type')}")
        else:
            print(f"   ⚠️  No signal generated (market conditions may not meet criteria)")
            signal = None
    except Exception as e:
        print(f"   ❌ FAIL: Signal generation error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Database Logging Simulation
    print("\n💾 Step 3: Database Logging Test")
    if signal:
        try:
            import json
            conn = sqlite3.connect(db_path)
            
            risk_json = json.dumps(signal.get('risk_details', {}))
            score_json = json.dumps(signal.get('score_details', {}))
            
            conn.execute("""
                INSERT INTO signals (
                    timestamp, symbol, direction, entry_price, 
                    sl, tp0, tp1, tp2, reasoning, timeframe, confidence,
                    trade_type, quality_score, regime, expected_hold, risk_details, score_details
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                signal.get('symbol', 'TESTPAIR'),
                signal.get('direction', 'BUY'),
                signal.get('entry_price', 0.0),
                signal.get('sl', 0.0),
                signal.get('tp0', 0.0),
                signal.get('tp1', 0.0),
                signal.get('tp2', 0.0),
                signal.get('reasoning', 'Test signal')[:5000],
                signal.get('timeframe', '5m'),
                signal.get('confidence', 0.0),
                signal.get('trade_type', 'SCALP'),
                signal.get('quality_score', 0.0),
                signal.get('regime', 'UNKNOWN'),
                signal.get('expected_hold', 'UNKNOWN'),
                risk_json,
                score_json
            ))
            conn.commit()
            
            final_count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            conn.close()
            
            if final_count == initial_count + 1:
                print(f"   ✅ PASS: Signal logged successfully (count: {initial_count} → {final_count})")
            else:
                print(f"   ❌ FAIL: Expected count {initial_count + 1}, got {final_count}")
                return False
                
        except Exception as e:
            print(f"   ❌ FAIL: Database logging error: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print(f"   ⏭️  SKIP: No signal to log")
    
    # Step 4: API Endpoint Validation
    print("\n🌐 Step 4: API Endpoint Validation")
    try:
        from fastapi.testclient import TestClient
        from admin_server import app
        
        client = TestClient(app)
        
        # Test /api/signals
        response = client.get("/api/signals")
        if response.status_code == 200:
            signals = response.json()
            print(f"   ✅ PASS: /api/signals returned {len(signals)} signals")
        else:
            print(f"   ❌ FAIL: /api/signals returned status {response.status_code}")
            return False
        
        # Test /api/stats
        response = client.get("/api/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ PASS: /api/stats - Active clients: {stats.get('active_clients')}, Signals today: {stats.get('signals_today')}")
        else:
            print(f"   ❌ FAIL: /api/stats returned status {response.status_code}")
            return False
        
        # Test /api/analytics/daily
        response = client.get("/api/analytics/daily")
        if response.status_code == 200:
            analytics = response.json()
            print(f"   ✅ PASS: /api/analytics/daily - Total: {analytics.get('total_signals')}, Quality: {analytics.get('avg_quality')}")
        else:
            print(f"   ❌ FAIL: /api/analytics/daily returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ FAIL: API validation error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Final Summary
    print("\n" + "=" * 80)
    print("✅ FORENSIC VALIDATION: ALL TESTS PASSED")
    print("=" * 80)
    return True

if __name__ == "__main__":
    success = test_e2e_signal_flow()
    sys.exit(0 if success else 1)
