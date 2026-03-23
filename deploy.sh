#!/bin/bash
echo "🚀 Deploying Trading Services..."

# Copy service files to systemd user directory
mkdir -p ~/.config/systemd/user
cp smc-*.service ~/.config/systemd/user/
cp monitoring/*.service ~/.config/systemd/user/ 2>/dev/null || true

# Reload systemd
systemctl --user daemon-reload

# Enable and start core services
systemctl --user enable smc-signal-service.service
systemctl --user start smc-signal-service.service

systemctl --user enable smc-interactive-bot.service
systemctl --user start smc-interactive-bot.service

# Enable lingering so services run when evans logs out
sudo loginctl enable-linger evans

echo "✅ Deployment complete. Checking status..."
systemctl --user status smc-signal-service.service --no-pager | head -n 5
