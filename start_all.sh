#!/bin/bash
# Manual Startup Script for SMC Scalp Signals
# Use this when systemctl --user is failing to connect to the bus.

BASE_DIR="/home/evans/smc-scalp-signals"
cd $BASE_DIR

echo "🚀 Starting SMC Scalp Signals System..."

# 1. Kill any existing processes (forceful) to start clean
echo "🧹 Cleaning up old processes..."
pkill -9 -f "signal_service.py"
pkill -9 -f "signal_tracker.py"
pkill -9 -f "admin_server.py"
pkill -9 -f "interactive_bot.py"
pkill -9 -f "smc-scalp-signals"

sleep 2

# 2. Start all components in the background
echo "📡 Starting Signal Service..."
nohup python3 signal_service.py >> signals.log 2>&1 &

echo "🎯 Starting Signal Tracker..."
nohup python3 signal_tracker.py >> tracker.log 2>&1 &

echo "📊 Starting Admin Dashboard..."
nohup python3 admin_server.py >> admin.log 2>&1 &

echo "🤖 Starting Telegram Bot..."
nohup python3 app/interactive_bot.py >> bot.log 2>&1 &

echo "✅ All services started manually!"
echo "Use 'ps aux | grep python3' to verify or check the .log files."
