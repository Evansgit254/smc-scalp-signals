#!/bin/bash

# TradingExpert VM Setup Script (v22.0)
# This script automates the installation of dependencies and systemd services.

set -e

# 1. Project and User Detection
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." \u0026\u0026 pwd)"
VIRTUAL_USER="evans" # The user the services should run as
VENV_PATH="$PROJECT_DIR/venv"
LOCAL_DEV_PATH="/home/evans/Projects/TradingExpert/smc-scalp-signals"

echo "🚀 Starting TradingExpert Deployment..."

# 1. Update System & Install Dependencies
echo "📦 Installing system dependencies..."
sudo apt update && sudo apt install -y python3.12 python3.12-venv python3-pip git ufw

# 2. Create Project Directory (if not exists)
mkdir -p "$PROJECT_DIR"

# 3. Setup Virtual Environment
echo "🐍 Setting up Python virtual environment..."
python3.12 -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"

# 4. Install Python Requirements
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "📜 Installing Python packages..."
    pip install --upgrade pip
    pip install -r "$PROJECT_DIR/requirements.txt"
else
    echo "⚠️ requirements.txt not found in $PROJECT_DIR. Skipping pip install."
fi

# 5. Configure Firewall
echo "🛡️ Configuring Firewall..."
sudo ufw allow 5000/tcp  # Admin Dashboard
sudo ufw allow 22/tcp    # SSH
sudo ufw --force enable

# 6. Install Systemd Services
echo "⚙️ Registering systemd services..."
SERVICES=("smc-admin-dashboard" "smc-signal-service" "smc-interactive-bot" "smc-signal-tracker")

for SERVICE in "${SERVICES[@]}"; do
    if [ -f "$PROJECT_DIR/$SERVICE.service" ]; then
        echo "   🔹 Installing $SERVICE.service"
        # Update paths in service file to current user/dir
        sed -i "s|$LOCAL_DEV_PATH|$PROJECT_DIR|g" "$PROJECT_DIR/$SERVICE.service"
        sed -i "s|User=evans|User=$VIRTUAL_USER|g" "$PROJECT_DIR/$SERVICE.service"
        
        sudo cp "$PROJECT_DIR/$SERVICE.service" "/etc/systemd/system/$SERVICE.service"
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE.service"
        sudo systemctl restart "$SERVICE.service"
    else
        echo "   ⚠️ $SERVICE.service not found in $PROJECT_DIR"
    fi
done

echo "✅ Deployment Complete!"
echo "📡 Admin Dashboard should be live at: http://$(curl -s ifconfig.me):5000"
echo "📊 Check service status with: sudo systemctl status smc-*"
