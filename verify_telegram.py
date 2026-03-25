import os
import telebot
from dotenv import load_dotenv

def verify():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not found in .env")
        return

    print(f"🤖 Initializing bot with token: {token[:10]}...{token[-5:]}")
    try:
        bot = telebot.TeleBot(token)
        me = bot.get_me()
        print(f"✅ Bot connected! Name: @{me.username}")
    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")
        return

    print("\n---------------------------------------------------------")
    print("👉 ACTION REQUIRED: Send a message to your bot on Telegram.")
    print("I am waiting to catch your Chat ID...")
    print("---------------------------------------------------------")

    @bot.message_handler(func=lambda msg: True)
    def catch_id(message):
        print("\n🎉 GOT IT!")
        print(f"👤 User: {message.from_user.first_name} (@{message.from_user.username})")
        print(f"🆔 YOUR PERSONAL CHAT ID: {message.chat.id}")
        print("\n---------------------------------------------------------")
        print("1. Copy this number.")
        print("2. Put it in your .env for TELEGRAM_CHAT_ID.")
        print("3. Restart your services.")
        print("---------------------------------------------------------")
        os._exit(0)

    bot.polling()

if __name__ == "__main__":
    verify()
