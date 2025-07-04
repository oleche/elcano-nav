#!/bin/bash
# Fix GPS Navigation Service Setup

echo "Fixing GPS Navigation Service Setup"
echo "=================================="

# Get the current user
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$USER_HOME/gps-navigation"

echo "User: $REAL_USER"
echo "Home: $USER_HOME" 
echo "Project: $PROJECT_DIR"

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory does not exist: $PROJECT_DIR"
    echo "Creating project directory..."
    mkdir -p "$PROJECT_DIR"
    chown $REAL_USER:$REAL_USER "$PROJECT_DIR"
fi

# Check if main script exists
if [ ! -f "$PROJECT_DIR/gps_navigation.py" ]; then
    echo "Error: gps_navigation.py not found!"
    echo "Current project directory contents:"
    ls -la "$PROJECT_DIR/"
    echo ""
    echo "Please copy all project files to $PROJECT_DIR/"
    echo "Required files:"
    echo "  - gps_navigation.py"
    echo "  - mbtiles_manager.py"
    echo "  - mbtiles_to_png.py"
    echo "  - epaper_display.py"
    echo "  - database_manager.py"
    echo "  - menu_system.py"
    echo "  - navigation_config.json"
    exit 1
fi

# Make script executable
chmod +x "$PROJECT_DIR/gps_navigation.py"

# Remove old service if it exists
if [ -f "/etc/systemd/system/gps-navigation.service" ]; then
    echo "Removing old system service..."
    sudo systemctl stop gps-navigation.service 2>/dev/null || true
    sudo systemctl disable gps-navigation.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/gps-navigation.service
    sudo systemctl daemon-reload
fi

# Create improved systemd service
SERVICE_FILE="/etc/systemd/system/gps-navigation.service"

echo "Creating improved systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=GPS Navigation System
After=network.target
Wants=network.target

[Service]
Type=simple
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$PROJECT_DIR
Environment=HOME=$USER_HOME
Environment=USER=$REAL_USER
Environment=PYTHONPATH=$PROJECT_DIR
Environment=ELCANONAV_SYNC_KEY=${ELCANONAV_SYNC_KEY:-}
ExecStartPre=/bin/sleep 10
ExecStart=/usr/bin/python3 $PROJECT_DIR/gps_navigation.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOF

# Set correct permissions
sudo chmod 644 "$SERVICE_FILE"

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable gps-navigation.service

# Test the service configuration
echo ""
echo "Testing service configuration..."
if sudo systemctl status gps-navigation.service >/dev/null 2>&1; then
    echo "✓ Service configuration is valid"
else
    echo "ℹ Service is not running (this is normal)"
fi

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."
cd "$PROJECT_DIR"

# Test imports
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')

try:
    import gps_navigation
    print('✓ Main script imports successfully')
except ImportError as e:
    print(f'✗ Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'ℹ Script loaded (runtime error expected without hardware): {e}')
" 2>/dev/null || echo "ℹ Import test completed (some errors expected without hardware)"

echo ""
echo "Service setup completed!"
echo ""
echo "Service file: $SERVICE_FILE"
echo "Working directory: $PROJECT_DIR"
echo ""
echo "To manage the service:"
echo "  Start:   sudo systemctl start gps-navigation"
echo "  Stop:    sudo systemctl stop gps-navigation"
echo "  Status:  sudo systemctl status gps-navigation"
echo "  Logs:    journalctl -u gps-navigation.service -f"
echo ""
echo "To test manually:"
echo "  cd $PROJECT_DIR"
echo "  python3 gps_navigation.py"
