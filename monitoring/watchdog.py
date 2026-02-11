"""
Service Watchdog
Monitors the signal service and sends alerts if it stops.
Run this via systemd timer every 5 minutes.
"""
import asyncio
import sys
from monitoring.alert_service import AlertService


async def main():
    """Run health checks and send alerts if needed."""
    alert_service = AlertService()
    
    try:
        await alert_service.run_all_checks()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Watchdog error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
