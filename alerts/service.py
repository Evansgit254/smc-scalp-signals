"""
Telegram Service for sending trading signals.
"""
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core.signal_formatter import SignalFormatter


class TelegramService:
    """
    Service for sending trading signals via Telegram.
    """
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.bot = None
        
        if self.bot_token and self.chat_id:
            try:
                self.bot = Bot(token=self.bot_token)
            except Exception as e:
                print(f"⚠️  Warning: Could not initialize Telegram bot: {e}")
    
    def format_signal(self, signal_data: dict) -> str:
        """
        Formats signal data into a Telegram message.
        Handles both simple signals and complex mock signals.
        """
        # If it's a simple signal (from generate_signals.py), use SignalFormatter
        if 'trade_type' in signal_data or 'timeframe' in signal_data:
            return SignalFormatter.format_signal(signal_data)
        
        # Otherwise, format as complex signal (from mock/test data)
        symbol = signal_data.get('symbol', 'UNKNOWN')
        direction = signal_data.get('direction', 'N/A')
        entry_tf = signal_data.get('entry_tf', signal_data.get('timeframe', 'N/A'))
        setup_quality = signal_data.get('setup_quality', 'STANDARD')
        session = signal_data.get('session', 'N/A')
        
        entry = signal_data.get('entry_price', signal_data.get('entry', 0))
        sl = signal_data.get('sl', signal_data.get('stop_loss', 0))
        tp0 = signal_data.get('tp0', 0)
        tp1 = signal_data.get('tp1', 0)
        tp2 = signal_data.get('tp2', 0)
        confidence = signal_data.get('confidence', 0)
        
        risk_details = signal_data.get('risk_details', {})
        layers = signal_data.get('layers', [])
        
        # Calculate pips
        pip_divisor = 10000.0
        if "JPY" in symbol:
            pip_divisor = 100.0
        elif "GC" in symbol or "BTC" in symbol or "CL" in symbol:
            pip_divisor = 10.0
        
        sl_pips = abs(entry - sl) * pip_divisor if entry and sl else 0
        tp0_pips = abs(tp0 - entry) * pip_divisor if tp0 and entry else 0
        tp1_pips = abs(tp1 - entry) * pip_divisor if tp1 and entry else 0
        tp2_pips = abs(tp2 - entry) * pip_divisor if tp2 and entry else 0
        
        # Build message
        message = f"""
{'='*60}
📊 TRADE SIGNAL - {setup_quality}
{'='*60}
Symbol:           {symbol}
Direction:        {direction}
Timeframe:        {entry_tf}
Session:          {session}
Entry Price:      {entry:.5f}
Stop Loss:        {sl:.5f} ({'-' if direction == 'BUY' else '+'}{sl_pips:.1f} pips)
──────────────────────────────────────────────────────────
TP0 (50% Exit):   {tp0:.5f} ({'+' if direction == 'BUY' else '-'}{tp0_pips:.1f} pips)
TP1 (30% Exit):   {tp1:.5f} ({'+' if direction == 'BUY' else '-'}{tp1_pips:.1f} pips)
TP2 (20% Exit):   {tp2:.5f} ({'+' if direction == 'BUY' else '-'}{tp2_pips:.1f} pips)
──────────────────────────────────────────────────────────
"""
        
        # Add layers if present
        if layers:
            message += "Entry Layers:\n"
            for layer in layers:
                message += f"  • {layer.get('label', 'Layer')}: {layer.get('lots', 0):.2f} lots @ {layer.get('price', 0):.5f}\n"
            message += "──────────────────────────────────────────────────────────\n"
        
        # Add risk details
        if risk_details:
            message += f"Position Size:    {risk_details.get('lots', risk_details.get('lot_size', 0))}\n"
            message += f"Risk Amount:      ${risk_details.get('risk_cash', risk_details.get('risk_amount', 0))}\n"
            message += f"Risk Percent:     {risk_details.get('risk_percent', 0)}%\n"
            if risk_details.get('warning'):
                message += f"⚠️  {risk_details.get('warning')}\n"
        
        # Add additional info
        if signal_data.get('liquidity_event'):
            message += f"\n💧 Liquidity: {signal_data.get('liquidity_event')}\n"
        if signal_data.get('ai_logic'):
            message += f"🧠 Logic: {signal_data.get('ai_logic')}\n"
        if signal_data.get('entry_zone'):
            message += f"📍 Entry Zone: {signal_data.get('entry_zone')}\n"
        
        message += f"Alpha Score:      {confidence:.2f} {'(STRONG)' if confidence > 1.5 else '(MODERATE)' if confidence > 1.0 else '(WEAK)'}\n"
        message += f"{'='*60}\n"
        
        return message
    
    async def send_signal(self, message: str) -> bool:
        """
        Sends a formatted signal message to Telegram.
        Returns True if successful, False otherwise.
        """
        if not self.bot or not self.chat_id:
            print("⚠️  Telegram not configured. Skipping send.")
            return False
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            return True
        except TelegramError as e:
            print(f"❌ Telegram error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False
    
    async def send_text(self, text: str, chat_id: str = None) -> bool:
        """
        Sends plain text message to Telegram.
        """
        target_id = chat_id if chat_id else self.chat_id
        if not self.bot or not target_id:
            return False
        
        try:
            await self.bot.send_message(chat_id=target_id, text=text)
            return True
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False

    async def broadcast_personalized_signal(self, signal_data: dict):
        """
        Broadcasts personalized signals to all active clients.
        """
        from core.client_manager import ClientManager
        from config.config import MULTI_CLIENT_MODE
        
        if not MULTI_CLIENT_MODE:
            # Fallback to single user
            message = self.format_signal(signal_data)
            await self.send_signal(message)
            return
            
        manager = ClientManager()
        clients = manager.get_all_active_clients()
        
        # V11.2 Auto-Register Primary Chat if Database is Empty
        if not clients and self.chat_id:
            from config.config import ACCOUNT_BALANCE
            print(f"⚙️ Auto-registering primary chat {self.chat_id} with ${ACCOUNT_BALANCE} balance...")
            manager.register_client(
                telegram_chat_id=self.chat_id,
                account_balance=ACCOUNT_BALANCE,
                risk_percent=2.0
            )
            clients = manager.get_all_active_clients()
            print(f"✅ Primary client registered successfully.")
        
        if not clients:
            print("⚠️ No active clients found. Signal not sent.")
            return
        
        success_count = 0
        for client in clients:
            try:
                formatted = SignalFormatter.format_personalized_signal(signal_data, client)
                if await self.send_text(formatted, chat_id=client['telegram_chat_id']):
                    success_count += 1
            except Exception as e:
                print(f"⚠️ Failed to send signal to {client['telegram_chat_id']}: {e}")
        
        print(f"📢 Broadcast complete. {success_count}/{len(clients)} clients reached.")
