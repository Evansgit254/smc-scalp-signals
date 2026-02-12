import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio
import sqlite3

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from signal_service import SignalService

class TestReasoningFix(unittest.TestCase):
    
    @patch('signal_service.TelegramService')
    @patch('signal_service.generate_signals', new_callable=AsyncMock)
    @patch('sqlite3.connect')
    def test_reasoning_generation_and_logging(self, mock_sqlite, mock_generate, mock_telegram_cls):
        # Setup mocks
        mock_telegram = mock_telegram_cls.return_value
        mock_telegram.broadcast_personalized_signal = AsyncMock()
        mock_telegram.bot = MagicMock() # Ensure bot is configured
        
        # Create a sample signal WITHOUT reasoning
        sample_signal = {
            'symbol': 'EURUSD',
            'direction': 'BUY',
            'entry_price': 1.1000,
            'sl': 1.0950,
            'tp0': 1.1020,
            'tp1': 1.1050,
            'tp2': 1.1100,
            'timeframe': 'M5',
            'confidence': 0.85,
            'score_details': {
                'velocity': 1.2,
                'zscore': -2.0,
                'momentum': 0.8
            },
            'regime': 'TRENDING'
        }
        
        # generate_signals returns a list of tuples (type, data)
        mock_generate.return_value = [('INTRADAY', sample_signal)]
        
        # Setup database mock
        mock_conn = MagicMock()
        mock_sqlite.return_value = mock_conn
        
        # Initialize service - mocks handle __init__ logic
        service = SignalService()
        service.telegram = mock_telegram
        service.sent_signals = {}
        service.cycle_count = 0
        service._is_duplicate = lambda x: False
        service._mark_sent = lambda x: None
        service._cleanup_old_signals = lambda: None
        
        # Run one cycle
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.run_cycle())
        
        # VERIFICATION 1: reasoning field should be populated in the signal dictionary
        if 'reasoning' in sample_signal:
            print(f"\n✅ Reasoning generated: {sample_signal['reasoning'][:50]}...")
        else:
            self.fail("❌ Reasoning field missing from signal data!")
            
        # VERIFICATION 2: broadcast_personalized_signal called with signal containing reasoning
        calls = mock_telegram.broadcast_personalized_signal.call_args_list
        if not calls:
            self.fail("❌ broadcast_personalized_signal not called!")
            
        args = calls[0][0]
        self.assertIn('reasoning', args[0], "Reasoning missing from broadcast call")
        
        # VERIFICATION 3: Database insert called with reasoning
        # Check that execute was called
        # mock_conn.execute is called within _log_to_database which creates a NEW connection
        # Wait, the patch is on sqlite3.connect, so it returns mock_conn
        if not mock_conn.execute.called:
             # Check if context manager was used: with sqlite3.connect(...) as conn:
             pass
        
        # Find the INSERT call
        insert_found = False
        for call in mock_conn.execute.call_args_list:
            sql = call[0][0]
            if "INSERT INTO signals" in sql:
                insert_found = True
                params = call[0][1]
                # reasoning is stored
                print(f"✅ INSERT params found: {params}")
                # The reasoning index depends on schema, but logic puts it at index 8 (9th param)
                # (timestamp, symbol, direction, entry_price, sl, tp0, tp1, tp2, reasoning, timeframe, confidence)
                reasoning_param = params[8]
                self.assertTrue(len(reasoning_param) > 0, "Empty reasoning in INSERT")
                
        if not insert_found:
             self.fail("❌ INSERT INTO signals statement not found in mock calls")
        else:
             print("✅ Database logging verified successfully")

if __name__ == '__main__':
    unittest.main()
