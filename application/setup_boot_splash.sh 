#!/bin/bash
# Setup script for boot splash screen

echo "Setting up Elcano One boot splash screen..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the current user (the one who called sudo)
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)

# Define paths
PROJECT_DIR="$USER_HOME/gps-navigation"
SPLASH_SCRIPT="$PROJECT_DIR/boot_splash.py"
SERVICE_FILE="/etc/systemd/system/boot-splash.service"
LOG_DIR="/var/log"

echo "Project directory: $PROJECT_DIR"
echo "Real user: $REAL_USER"

# Create project directory if it doesn't exist
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Creating project directory..."
    mkdir -p "$PROJECT_DIR"
    chown $REAL_USER:$REAL_USER "$PROJECT_DIR"
fi

# Check if splash script exists
if [ ! -f "$SPLASH_SCRIPT" ]; then
    echo "Error: boot_splash.py not found in $PROJECT_DIR"
    echo "Please ensure all project files are in the correct location."
    exit 1
fi

# Make splash script executable
chmod +x "$SPLASH_SCRIPT"
chown $REAL_USER:$REAL_USER "$SPLASH_SCRIPT"

# Create systemd service file
echo "Creating systemd service..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Elcano One Boot Splash Screen
DefaultDependencies=false
After=local-fs.target
Before=graphical-session.target
Wants=local-fs.target

[Service]
Type=oneshot
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONPATH=$PROJECT_DIR
ExecStart=/usr/bin/python3 $SPLASH_SCRIPT
StandardOutput=journal
StandardError=journal
TimeoutStartSec=30
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Set correct permissions for service file
chmod 644 "$SERVICE_FILE"

# Create log directory and set permissions
touch "$LOG_DIR/boot_splash.log"
chown $REAL_USER:$REAL_USER "$LOG_DIR/boot_splash.log"

# Reload systemd and enable service
echo "Enabling boot splash service..."
systemctl daemon-reload
systemctl enable boot-splash.service

# Test the service
echo "Testing boot splash service..."
systemctl start boot-splash.service

# Check service status
if systemctl is-active --quiet boot-splash.service; then
    echo "✓ Boot splash service is running successfully"
else
    echo "✗ Boot splash service failed to start"
    echo "Check logs with: journalctl -u boot-splash.service"
    exit 1
fi

echo ""
echo "Boot splash setup completed successfully!"
echo ""
echo "The splash screen will now display during boot."
echo ""
echo "Useful commands:"
echo "  Check service status: sudo systemctl status boot-splash.service"
echo "  View logs: journalctl -u boot-splash.service"
echo "  Test manually: sudo systemctl start boot-splash.service"
echo "  Disable: sudo systemctl disable boot-splash.service"
echo ""
echo "Reboot to see the splash screen during boot!"
