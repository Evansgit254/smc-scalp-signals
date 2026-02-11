"""
Daily Report Generator
Sends comprehensive daily performance summary to Telegram.
"""
import asyncio
from datetime import datetime, timedelta
from telegram import Bot
from telegram.error import TelegramError

from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from monitoring.health_monitor import HealthMonitor


class DailyReportGenerator:
    """Generate and send daily performance reports."""
    
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
        self.chat_id = TELEGRAM_CHAT_ID
        self.monitor = HealthMonitor()
    
    def _format_win_rate(self, rate: float) -> str:
        """Format win rate with color indicators."""
        if rate is None:
            return "N/A"
        
        emoji = "✅" if rate >= 50 else "⚠️" if rate >= 45 else "❌"
        return f"{emoji} {rate:.2f}%"
    
    def _get_symbol_breakdown(self) -> str:
        """Get top performing symbols."""
        # This would query signals.db for symbol-specific performance
        # Placeholder for now
        return "Coming soon..."
    
    def generate_report(self) -> str:
        """Generate daily report message."""
        summary = self.monitor.get_health_summary()
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        yesterday_signals = self.monitor.get_daily_signal_count(yesterday)
        
        report = f"""
📊 <b>DAILY PERFORMANCE REPORT</b>
{'='*40}

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

<b>📈 Signal Activity</b>
  • Today: {summary['signals_today']} signals
  • Yesterday: {yesterday_signals} signals

<b>🎯 Win Rate Performance</b>
  • Last 24h: {self._format_win_rate(summary['win_rate_24h'])}
  • Last 7 days: {self._format_win_rate(summary['win_rate_7d'])}
  • Last 30 days: {self._format_win_rate(summary['win_rate_30d'])}

<b>⚙️ Service Health</b>
  • Status: {'✅ Running' if summary['service_status']['is_running'] else '❌ Stopped'}
  • Last Signal: {summary['last_signal'] or 'N/A'}

<b>📌 System Notes</b>
  • Target Win Rate: 51-52%
  • Expected Signals: 200-300/day
  • Profit Factor Target: 2.5+

{'='*40}
<i>Automated Report | Signal Service V11.2</i>
"""
        return report.strip()
    
    async def send_report(self):
        """Send daily report via Telegram."""
        if not self.bot or not self.chat_id:
            print("⚠️ Telegram not configured. Report not sent.")
            return False
        
        try:
            report = self.generate_report()
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=report,
                parse_mode='HTML'
            )
            print(f"✅ Daily report sent successfully at {datetime.now().isoformat()}")
            return True
            
        except TelegramError as e:
            print(f"❌ Failed to send daily report: {e}")
            return False


async def main():
    """Main entry point for daily report."""
    generator = DailyReportGenerator()
    await generator.send_report()


if __name__ == "__main__":
    asyncio.run(main())
