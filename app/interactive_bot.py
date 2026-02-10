"""
Interactive Telegram Bot for Multi-Client Management

Handles commands: /start, /register, /update_balance, /settings, /help
"""
import logging
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
            await update.message.reply_text(
                f"📊 YOUR SETTINGS:\n"
                f"────────────────────\n"
                f"💰 Balance: ${client['account_balance']:.2f}\n"
                f"📉 Risk: {client['risk_percent']:.1f}%\n"
                f"🔥 Max concurrent: {client['max_concurrent_trades']}\n"
                f"────────────────────\n"
                f"Use /update_balance to change your size."
            )
        else:
            await update.message.reply_text("❌ You are not registered yet. Use /register <balance>.")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message."""
        await update.message.reply_text(
            "📚 COMMANDS:\n\n"
            "/register <balance> - Join the signal service\n"
            "/update_balance <val> - Update your account size\n"
            "/settings - View your current risk parameters\n"
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
