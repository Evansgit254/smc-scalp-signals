# Monitoring & Alerting System - Deployment Guide

## Overview
The monitoring system is now fully implemented and ready for deployment. It consists of:

1. **Health Monitor** - Tracks signal counts, win rates, service status
2. **Alert Service** - Sends Telegram alerts for anomalies
3. **Daily Reports** - Automated performance summaries
4. **Watchdog** - Periodic health checks every 5 minutes

---

## Deployment Steps

### 1. Install Systemd Timers
```bash
cd /home/evans/Projects/TradingExpert/smc-scalp-signals

# Copy service files to systemd
sudo cp monitoring/smc-watchdog.service /etc/systemd/system/
sudo cp monitoring/smc-watchdog.timer /etc/systemd/system/
sudo cp monitoring/smc-daily-report.service /etc/systemd/system/
sudo cp monitoring/smc-daily-report.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timers
sudo systemctl enable smc-watchdog.timer
sudo systemctl start smc-watchdog.timer

sudo systemctl enable smc-daily-report.timer
sudo systemctl start smc-daily-report.timer

# Verify timers are running
sudo systemctl list-timers --all | grep smc
```

### 2. Test Components Manually
```bash
# Test health monitor
python3 monitoring/health_monitor.py

# Test alert service
python3 monitoring/watchdog.py

# Test daily report
python3 monitoring/daily_report.py
```

### 3. Monitor Logs
```bash
# Watch watchdog logs
sudo journalctl -u smc-watchdog -f

# Watch daily report logs
sudo journalctl -u smc-daily-report -f
```

---

## What Gets Monitored

### ✅ Automated Alerts (via Telegram)

| Alert Type | Trigger | Cool down |
|:-----------|:--------|:----------|
| Service Down | systemd service stops | 60 min |
| Signal Drought | No signals for 2+ hours | 60 min |
| Low Win Rate | 7-day win rate < 45% | 60 min |
| Low Signal Count | Today's signals < 100 | 60 min |

### 📊 Daily Report (Midnight UTC)

- Total signals (today vs yesterday)
- Win rate performance (24h, 7d, 30d)
- Service health status
- Last signal timestamp

---

## Configuration

### Adjust Alert Thresholds
Edit `monitoring/alert_service.py`:

```python
# Change signal drought threshold
await self.check_signal_drought(hours=4)  # Default: 2

# Change win rate threshold
await self.check_win_rate_anomaly(threshold=40.0)  # Default: 45.0

# Change signal count threshold (in method)
if today_count < 50:  # Default: 100
```

### Change Report Time
Edit `monitoring/smc-daily-report.timer`:

```ini
[Timer]
OnCalendar=*-*-* 06:00:00  # 6 AM UTC instead of midnight
```

Then reload: `sudo systemctl daemon-reload && sudo systemctl restart smc-daily-report.timer`

---

## Troubleshooting

### Alerts not sending?
```bash
# Check watchdog logs
sudo journalctl -u smc-watchdog -n 50

# Test alert manually
cd /home/evans/Projects/TradingExpert/smc-scalp-signals
source venv/bin/activate
python3 monitoring/watchdog.py
```

### Daily report not received?
```bash
# Check timer status
sudo systemctl status smc-daily-report.timer

# Check last execution
sudo systemctl list-timers --all | grep daily-report

# Manual test
python3 monitoring/daily_report.py
```

### Database errors?
```bash
# Ensure database exists and is writable
ls -la database/signals.db
ls -la monitoring/metrics.db

# Reset metrics database if needed
rm monitoring/metrics.db
python3 monitoring/health_monitor.py  # Will recreate
```

---

## Next Steps

1. ✅ Deploy systemd timers on production VM
2. ✅ Monitor Telegram for first daily report (midnight UTC)
3. ✅ Verify watchdog alerts work (can temporarily stop service to test)
4. 📊 Track metrics for 1 week to establish baseline

---

*Created: 2026-02-11 | Monitoring System V1.0*
