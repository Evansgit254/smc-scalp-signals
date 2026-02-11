"""
Alert Service for Signal Service Monitoring
Sends Telegram alerts when issues are detected.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from config.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from monitoring.health_monitor import HealthMonitor


class AlertService:
    """Send alerts via Telegram when service issues are detected."""
    
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
        self.chat_id = TELEGRAM_CHAT_ID
        self.monitor = HealthMonitor()
        self.alert_cooldown = {}  # Prevent alert spam
    
    def _should_send_alert(self, alert_type: str, cooldown_minutes: int = 60) -> bool:
        """Check if enough time has passed since last alert of this type."""
        last_sent = self.alert_cooldown.get(alert_type)
        
        if last_sent is None:
            return True
        
        time_since = datetime.now() - last_sent
        return time_since.total_seconds() > (cooldown_minutes * 60)
    
    def _mark_alert_sent(self, alert_type: str):
        """Record that an alert was sent."""
        self.alert_cooldown[alert_type] = datetime.now()
    
    async def send_alert(self, message: str, alert_type: str = "general"):
        """Send alert message via Telegram."""
        if not self.bot or not self.chat_id:
            print(f"⚠️ Alert (no Telegram configured): {message}")
            return False
        
        if not self._should_send_alert(alert_type):
            print(f"⏭️ Skipping alert (cooldown active): {alert_type}")
            return False
        
        try:
            full_message = f"🚨 <b>SIGNAL SERVICE ALERT</b>\n\n{message}"
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            self._mark_alert_sent(alert_type)
            print(f"✅ Alert sent: {alert_type}")
            return True
            
        except TelegramError as e:
            print(f"❌ Failed to send alert: {e}")
            return False
    
    async def check_service_down(self):
        """Alert if service is not running."""
        status = self.monitor.check_service_status()
        
        if not status['is_running']:
            message = (
                "⚠️ <b>Service Stopped</b>\n\n"
                f"The signal service is not running.\n"
                f"Last checked: {status['last_check']}\n\n"
                "Please investigate immediately."
            )
            await self.send_alert(message, alert_type="service_down")
    
    async def check_signal_drought(self, hours: int = 2):
        """Alert if no signals generated in N hours."""
        last_signal = self.monitor.get_last_signal_time()
        
        if last_signal is None:
            return  # No signals in database yet
        
        last_signal_dt = datetime.fromisoformat(last_signal)
        time_since = datetime.now() - last_signal_dt
        
        if time_since.total_seconds() > (hours * 3600):
            message = (
                f"⚠️ <b>No Signals Generated</b>\n\n"
                f"No signals have been generated in the last {hours} hours.\n"
                f"Last signal: {last_signal}\n\n"
                "Possible market closure or data feed issue."
            )
            await self.send_alert(message, alert_type="signal_drought")
    
    async def check_win_rate_anomaly(self, threshold: float = 45.0):
        """Alert if win rate drops below threshold."""
        win_rate_7d = self.monitor.get_win_rate(days=7)
        
        if win_rate_7d is None:
            return  # Not enough data
        
        if win_rate_7d < threshold:
            message = (
                f"⚠️ <b>Win Rate Alert</b>\n\n"
                f"7-day win rate has dropped to {win_rate_7d:.2f}%\n"
                f"Threshold: {threshold}%\n\n"
                "Review recent signals for quality issues."
            )
            await self.send_alert(message, alert_type="win_rate_low")
    
    async def check_signal_count_anomaly(self):
        """Alert if today's signal count is abnormally low."""
        today_count = self.monitor.get_daily_signal_count()
        
        # Expected range: 200-300 signals per day
        if today_count < 100:
            message = (
                f"⚠️ <b>Low Signal Count</b>\n\n"
                f"Only {today_count} signals generated today.\n"
                f"Expected: 200-300\n\n"
                "Possible data feed or strategy issue."
            )
            await self.send_alert(message, alert_type="signal_count_low")
    
    async def run_all_checks(self):
        """Run all health checks and send alerts as needed."""
        print(f"🔍 Running health checks at {datetime.now().isoformat()}")
        
        await self.check_service_down()
        await self.check_signal_drought(hours=2)
        await self.check_win_rate_anomaly(threshold=45.0)
        await self.check_signal_count_anomaly()
        
        print("✅ Health checks complete")


async def main():
    """Main entry point for alert service."""
    alert_service = AlertService()
    await alert_service.run_all_checks()


if __name__ == "__main__":
    asyncio.run(main())
