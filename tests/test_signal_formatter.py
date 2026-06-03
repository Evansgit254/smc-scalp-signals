import pytest
from core.signal_formatter import SignalFormatter

@pytest.fixture
def base_signal():
    return {
        'symbol': 'EURUSD=X',
        'direction': 'BUY',
        'trade_type': 'CRT',
        'entry_price': 1.0850,
        'sl': 1.0830,
        'tp0': 1.0870,
        'tp1': 1.0890,
        'tp2': 1.0910,
        'confidence': 0.85,
        'quality_score': 8.5,
        'expected_hold': '4-8 hours',
        'risk_details': {'risk_percent': 2.0, 'lots': 0.1, 'risk_cash': 20.0},
        'regime': 'TRENDING'
    }

def test_advanced_pattern_styling(base_signal):
    """Verify Advanced Pattern signals use the pattern theme."""
    signal = base_signal.copy()
    signal['trade_type'] = 'ADVANCED_PATTERN'
    
    formatted = SignalFormatter.format_signal(signal)
    
    assert "⚡ ADVANCED PATTERN SIGNAL ⚡" in formatted
    assert "🏹" in formatted
    assert "≈" * 10 in formatted # Border check
    assert "• <b>Symbol:</b>" in formatted # Bullet check

def test_h1_crt_styling(base_signal):
    """Verify CRT signals use the structural theme."""
    signal = base_signal.copy()
    signal['timeframe'] = 'H1'
    signal['strategy_id'] = 'crt'
    
    formatted = SignalFormatter.format_signal(signal)
    
    assert "🏛️ CRT STRUCTURE SIGNAL 🏛️" in formatted
    assert "🏆" in formatted
    assert "█" * 10 in formatted # Border check
    assert "🧱 <b>Symbol:</b>" in formatted # Bullet check

def test_high_probability_intensity(base_signal):
    """Verify high quality signals show intensity emojis."""
    signal = base_signal.copy()
    signal['trade_type'] = 'ADVANCED_PATTERN'
    signal['quality_score'] = 9.5
    
    formatted = SignalFormatter.format_signal(signal)
    
    assert "🏎️💨 HIGH PROBABILITY 🏎️💨" in formatted
    
    signal['trade_type'] = 'CRT'
    formatted_crt = SignalFormatter.format_signal(signal)
    assert "💎💎💎 HIGH PROBABILITY 💎💎💎" in formatted_crt

def test_personalized_styling(base_signal):
    """Verify personalized signals retain the theme markers."""
    client = {
        'telegram_chat_id': '12345',
        'account_balance': 1000.0,
        'risk_percent': 1.0
    }
    signal = base_signal.copy()
    signal['timeframe'] = 'H1'
    
    formatted = SignalFormatter.format_personalized_signal(signal, client)
    
    assert "🏛️ CRT STRUCTURE SIGNAL 🏛️" in formatted
    assert "👤 <b>YOUR PERSONAL PLAN</b>" in formatted
    assert "💰 <b>Balance:</b> $1000.00" in formatted
