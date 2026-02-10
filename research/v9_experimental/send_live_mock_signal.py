import asyncio
import os
from alerts.service import TelegramService

async def send_mock_signal():
    print("🚀 Preparing V6.1 Mock Signal for Telegram...")
    service = TelegramService()
    
    # Mock data mirroring V6.1 Liquid Shield logic
    mock_data = {
        'symbol': 'GC=F',
        'direction': 'BUY',
        'setup_quality': 'HIGH PROBABILITY',
        'entry_tf': 'M5',
        'session': 'London-NY Overlap',
        'layers': [
            {'label': 'Aggressive 1', 'lots': 0.10, 'price': 2025.50},
            {'label': 'Core 2', 'lots': 0.10, 'price': 2024.80},
            {'label': 'Deep 3', 'lots': 0.05, 'price': 2024.10}
        ],
        'sl': 2022.50,
        'tp0': 2027.50, # 20 pips for initial partial + BE
        'tp1': 2030.00,
        'tp2': 2035.00,
        'liquidity_event': 'M15_SWEEP at 2025.20 (21-bar lookback)',
        'ai_logic': 'Strong H1 Bullish trend confirmed. Price swept lower liquidity into the London overlap value zone.',
        'entry_zone': '2025.50 - 2024.10',
        'risk_details': {
            'lots': '0.25 (Total)',
            'risk_cash': '75.00',
            'risk_percent': '1.5',
            'pips': '30.0',
            'warning': '✅ RISK LEVEL: SAFE'
        },
        'atr_status': 'HIGH (Volatile)',
        'confidence': 8.8,
        'win_prob': 0.72,
        'asian_sweep': True,
        'asian_quality': True,
        'at_value': False,
        'ema_slope': 0.02,
        'adr_usage': 45,
        'adr_exhausted': False,
        'poc': 2025.10
    }

    message = service.format_signal(mock_data)
    await service.send_signal(message)
    print("✅ Full V6.1 Mock Signal sent to Telegram!")

if __name__ == "__main__":
    asyncio.run(send_mock_signal())
