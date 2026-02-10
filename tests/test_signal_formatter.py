"""
Unit tests for Signal Formatter
100% coverage target
"""
import pytest
from core.signal_formatter import SignalFormatter

class TestSignalFormatter:
    """Test suite for signal formatting logic"""
    
    @pytest.fixture
    def sample_signal(self):
        """Create sample signal dict"""
        return {
            'symbol': 'EURUSD=X',
            'direction': 'BUY',
            'trade_type': 'SCALP',
            'timeframe': 'M5',
            'entry_price': 1.0850,
            'sl': 1.0830,
            'tp0': 1.0880,
            'tp1': 1.0920,
            'tp2': 1.0980,
            'confidence': 1.25,
            'expected_hold': '4-8 hours',
            'risk_details': {
                'lots': 0.5,
                'risk_cash': 100.0,
                'risk_percent': 2.0
            }
        }
    
    def test_format_signal_basic(self, sample_signal):
        """Test basic signal formatting returns string"""
        formatted = SignalFormatter.format_signal(sample_signal)
        
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        
    def test_format_signal_contains_key_info(self, sample_signal):
        """Test formatted signal contains critical information"""
        formatted = SignalFormatter.format_signal(sample_signal)
        
        assert 'EURUSD' in formatted
        assert 'BUY' in formatted
        assert 'SCALP' in formatted
        assert '1.0850' in formatted
        assert '1.0830' in formatted
        
    def test_format_signal_jpy_pair(self):
        """Test formatting for JPY pair (different pip calculation)"""
        signal = {
            'symbol': 'USDJPY=X',
            'direction': 'SELL',
            'trade_type': 'SWING',
            'timeframe': 'H1',
            'entry_price': 145.50,
            'sl': 146.00,
            'tp0': 145.00,
            'tp1': 144.50,
            'tp2': 144.00,
            'confidence': 0.95,
            'expected_hold': '1-3 days',
            'risk_details': {'lots': 0.2, 'risk_cash': 50.0, 'risk_percent': 1.0}
        }
        
        formatted = SignalFormatter.format_signal(signal)
        assert 'USDJPY' in formatted
        
    def test_format_signal_json_basic(self, sample_signal):
        """Test JSON formatting returns dict"""
        json_signal = SignalFormatter.format_signal_json(sample_signal)
        
        assert isinstance(json_signal, dict)
        assert 'symbol' in json_signal
        assert 'direction' in json_signal
        
    def test_format_signal_json_structure(self, sample_signal):
        """Test JSON formatting has correct structure"""
        json_signal = SignalFormatter.format_signal_json(sample_signal)
        
        assert json_signal['symbol'] == 'EURUSD=X'
        assert json_signal['direction'] == 'BUY'
        assert 'take_profits' in json_signal
        assert 'tp0' in json_signal['take_profits']
        
    def test_format_signal_json_tp_levels(self, sample_signal):
        """Test JSON formatting includes all TP levels with sizes"""
        json_signal = SignalFormatter.format_signal_json(sample_signal)
        
        assert json_signal['take_profits']['tp0']['size_pct'] == 50
        assert json_signal['take_profits']['tp1']['size_pct'] == 30
        assert json_signal['take_profits']['tp2']['size_pct'] == 20
