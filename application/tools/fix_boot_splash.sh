#!/bin/bash
# Fix Boot Splash Screen Issues

echo "Fixing Boot Splash Screen"
echo "========================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

# Get the real user
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$USER_HOME/gps-navigation"

echo "User: $REAL_USER"
echo "Project directory: $PROJECT_DIR"

# Ensure project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Creating project directory..."
    mkdir -p "$PROJECT_DIR"
    chown $REAL_USER:$REAL_USER "$PROJECT_DIR"
fi

# Check required files
REQUIRED_FILES=("boot_splash.py" "epaper_display.py")
MISSING_FILES=()

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$PROJECT_DIR/$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "Missing required files:"
    printf '  %s\n' "${MISSING_FILES[@]}"
    echo ""
    echo "Please copy these files to $PROJECT_DIR/"
    exit 1
fi

# Make scripts executable
chmod +x "$PROJECT_DIR/boot_splash.py"
chmod +x "$PROJECT_DIR/epaper_display.py"
chown $REAL_USER:$REAL_USER "$PROJECT_DIR"/*

# Enable SPI if not already enabled
echo "Enabling SPI interface..."
raspi-config nonint do_spi 0

# Add user to required groups
echo "Adding user to hardware groups..."
usermod -a -G gpio,spi,dialout $REAL_USER

# Remove old service if exists
if [ -f "/etc/systemd/system/boot-splash.service" ]; then
    echo "Removing old boot splash service..."
    systemctl stop boot-splash.service 2>/dev/null || true
    systemctl disable boot-splash.service 2>/dev/null || true
    rm -f /etc/systemd/system/boot-splash.service
fi

# Create improved systemd service
SERVICE_FILE="/etc/systemd/system/boot-splash.service"
echo "Creating boot splash service..."

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Elcano One Boot Splash Screen
DefaultDependencies=false
After=local-fs.target
Before=multi-user.target
Wants=local-fs.target

[Service]
Type=oneshot
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$PROJECT_DIR
Environment=HOME=$USER_HOME
Environment=USER=$REAL_USER
Environment=PYTHONPATH=$PROJECT_DIR
ExecStartPre=/bin/sleep 2
ExecStart=/usr/bin/python3 $PROJECT_DIR/boot_splash.py
StandardOutput=journal
StandardError=journal
TimeoutStartSec=30
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Set correct permissions
chmod 644 "$SERVICE_FILE"

# Create log file with correct permissions
LOG_FILE="/var/log/boot_splash.log"
touch "$LOG_FILE"
chown $REAL_USER:$REAL_USER "$LOG_FILE"

# Reload systemd and enable service
echo "Enabling boot splash service..."
systemctl daemon-reload
systemctl enable boot-splash.service

# Test the service
echo "Testing boot splash service..."
systemctl start boot-splash.service

# Check if it worked
sleep 3
if systemctl is-active --quiet boot-splash.service; then
    echo "✓ Boot splash service started successfully"
elif systemctl show boot-splash.service -p ExecMainStatus | grep -q "status=0"; then
    echo "✓ Boot splash service completed successfully"
else
    echo "✗ Boot splash service failed"
    echo "Checking logs..."
    journalctl -u boot-splash.service -n 10 --no-pager
fi

echo ""
echo "Boot splash setup completed!"
echo ""
echo "Service file: $SERVICE_FILE"
echo "Log file: $LOG_FILE"
echo ""
echo "To test:"
echo "  sudo systemctl start boot-splash.service"
echo "  journalctl -u boot-splash.service -f"
echo ""
echo "To see on next boot:"
echo "  sudo reboot"
echo ""
echo "The splash screen should appear early in the boot process"
echo "and display 'Elcano One' for about 5 seconds."
