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

# Create systemd service for auto-start
sudo tee /etc/systemd/system/gps-navigation.service > /dev/null <<EOF
[Unit]
Description=GPS Navigation System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/gps-navigation
Environment=ELCANONAV_SYNC_KEY=$SYNC_KEY
ExecStart=/usr/bin/python3 /home/pi/gps-navigation/gps_navigation.py /home/pi/gps-navigation/map.mbtiles
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
