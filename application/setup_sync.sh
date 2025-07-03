#!/bin/bash
# Setup script for ElcanoNav synchronization

echo "ElcanoNav Sync Setup"
echo "===================="

# Check if sync key is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <your_sync_key>"
    echo "Example: $0 ABC1234567"
    exit 1
fi

SYNC_KEY=$1

# Validate sync key format (should be 10 characters)
if [ ${#SYNC_KEY} -ne 10 ]; then
    echo "Error: Sync key should be exactly 10 characters"
    exit 1
fi

echo "Setting up sync key: $SYNC_KEY"

# Add to environment
echo "export ELCANONAV_SYNC_KEY=$SYNC_KEY" >> ~/.bashrc

# Check if main script exists
if [ ! -f "/home/pi/gps-navigation/gps_navigation.py" ]; then
    echo "Error: gps_navigation.py not found in /home/pi/gps-navigation/"
    echo "Please ensure all project files are in the correct location."
    echo "Current directory contents:"
    ls -la /home/pi/gps-navigation/
    exit 1
fi

# Create systemd service for auto-start
sudo tee /etc/systemd/system/gps-navigation.service > /dev/null <<EOF
[Unit]
Description=GPS Navigation System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=%h/gps-navigation
Environment=HOME=%h
Environment=USER=%i
Environment=ELCANONAV_SYNC_KEY=$SYNC_KEY
ExecStart=/usr/bin/python3 %h/gps-navigation/gps_navigation.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
sudo systemctl daemon-reload
sudo systemctl enable gps-navigation.service

echo "Setup complete!"
echo "Sync key has been configured and service created."
echo "To start the service: sudo systemctl start gps-navigation"
echo "To check status: sudo systemctl status gps-navigation"
echo "Reboot or source ~/.bashrc to load the environment variable"

# Verify installation
echo "Verifying installation..."
if systemctl --user daemon-reload 2>/dev/null; then
    echo "Using user service (recommended)"
    systemctl --user enable gps-navigation.service
    echo "Service enabled. To start: systemctl --user start gps-navigation"
else
    echo "Using system service"
    echo "Service enabled. To start: sudo systemctl start gps-navigation"
fi
