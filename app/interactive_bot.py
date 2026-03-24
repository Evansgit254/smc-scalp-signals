"""
Interactive Telegram Bot for Multi-Client Management

Handles commands: /start, /register, /update_balance, /settings, /help
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config.config import TELEGRAM_BOT_TOKEN
from core.client_manager import ClientManager

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

class InteractiveBot:
    def __init__(self, token: str):
        self.token = token
        self.manager = ClientManager()
        self.application = None

    def _set_up_handlers(self, application):
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("register", self.register))
        application.add_handler(CommandHandler("subscribe", self.subscribe))
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("update_balance", self.update_balance))
        application.add_handler(CommandHandler("settings", self.settings))
        application.add_handler(CommandHandler("help", self.help))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        await update.message.reply_text(
            "🚀 Welcome to the Pure Quant Signal Service!\n\n"
            "To receive personalized signals based on your account size, please register through me.\n\n"
            "📝 Use /register <balance> to join.\n"
            "Example: /register 500"
        )

    async def register(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Register a new client with their balance."""
        chat_id = str(update.effective_chat.id)
        if not context.args:
            await update.message.reply_text("❌ Usage: /register <balance>\nExample: /register 500")
            return
        
        try:
            balance = float(context.args[0])
            res = self.manager.register_client(chat_id, balance)
            if res['status'] == 'registered':
                await update.message.reply_text(
                    f"✅ Registered successfully!\n"
                    f"💰 Account Balance: ${balance:.2f}\n"
                    f"You will now receive personalized signals."
                )
            else:
                await update.message.reply_text(
                    f"⚠️ {res['message']}.\n"
                    f"Use /update_balance if you need to adjust your size."
                )
        except ValueError:
            await update.message.reply_text("❌ Invalid balance. Please enter a numerical value.")

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show payment details for subscription."""
        await update.message.reply_html(
            "💎 <b>UPGRADE TO QUANT PREMIUM</b> 💎\n\n"
            "Get high-probability Institutional Swing and Intraday signals directly to your Telegram.\n\n"
            "💳 <b>PAYMENT METHODS:</b>\n"
            "• <b>M-Pesa:</b> +254 XXX XXX XXX (Evans)\n"
            "• <b>Bank:</b> KCB Bank - Acc: XXXXXXXX\n"
            "• <b>Crypto:</b> <code>[Your-USDT-TRC20-Address]</code>\n\n"
            "💵 <b>PRICING:</b>\n"
            "• 1 Month: $30\n"
            "• 3 Months: $75 (Save 15%)\n\n"
            "⚠️ <b>After payment:</b> Send a screenshot of the transaction to @YourAdminUsername for manual verification. We will activate your signals within 1 hour."
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check subscription status."""
        chat_id = str(update.effective_chat.id)
        # Use manager directly to get expiry since get_client only returns ACTIVE users
        client = self.manager.get_client(chat_id)
        
        if not client:
            await update.message.reply_text("❌ You are not registered. Use /register first.")
            return

        is_active = self.manager.is_subscription_active(chat_id)
        
        # Reload client to get expiry/tier as get_client might have filtered or not included them
        # Actually I need a method in manager to get RAW client data including inactive/expired
        conn = sqlite3.connect("database/clients.db")
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM clients WHERE telegram_chat_id = ?", (chat_id,)).fetchone()
        conn.close()
        
        expiry = row['subscription_expiry'] if row['subscription_expiry'] else 'N/A'
        tier = row['subscription_tier'] if row['subscription_tier'] else 'BASIC'
        
        status_text = "✅ ACTIVE" if is_active else "❌ EXPIRED"
        await update.message.reply_html(
            f"📊 <b>SUBSCRIPTION STATUS:</b> {status_text}\n"
            f"📅 <b>Expiry:</b> {expiry}\n"
            f"🏆 <b>Tier:</b> {tier}\n\n"
            "Use /subscribe to renew or upgrade your access."
        )

    async def update_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Update existing client's balance."""
        chat_id = str(update.effective_chat.id)
        if not context.args:
            await update.message.reply_text("❌ Usage: /update_balance <new_balance>\nExample: /update_balance 1200")
            return
            
        try:
            balance = float(context.args[0])
            res = self.manager.update_balance(chat_id, balance)
            if res['status'] == 'success':
                await update.message.reply_text(f"✅ Balance updated to ${balance:.2f}.")
            else:
                await update.message.reply_text(f"❌ Error: {res['message']}. Are you registered? Use /register first.")
        except ValueError:
            await update.message.reply_text("❌ Invalid balance format.")

    async def settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current client settings."""
        chat_id = str(update.effective_chat.id)
        client = self.manager.get_client(chat_id)
        if client:
            is_active = self.manager.is_subscription_active(chat_id)
            await update.message.reply_html(
                f"📊 <b>YOUR SETTINGS:</b>\n"
                f"────────────────────\n"
                f"💰 <b>Balance:</b> ${client['account_balance']:.2f}\n"
                f"📉 <b>Risk:</b> {client['risk_percent']:.1f}%\n"
                f"🗓️ <b>Sub Status:</b> {'✅ Active' if is_active else '❌ Expired'}\n"
                f"────────────────────\n"
                f"Use /update_balance to change your size."
            )
        else:
            await update.message.reply_text("❌ You are not registered yet. Use /register <balance>.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message."""
        await update.message.reply_text(
            "📚 COMMANDS:\n\n"
            "/register <bal> - Join the service\n"
            "/subscribe - Get payment details\n"
            "/status - Check your subscription expiry\n"
            "/settings - View your risk parameters\n"
            "/help - Show this message"
        )

    def run(self):
        """Run the bot in polling mode."""
        print("🤖 Starting Interactive Multi-Client Bot...")
        application = Application.builder().token(self.token).build()
        self._set_up_handlers(application)
        application.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment.")
    else:
        bot = InteractiveBot(TELEGRAM_BOT_TOKEN)
        bot.run()
