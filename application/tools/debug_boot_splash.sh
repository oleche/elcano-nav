#!/bin/bash
# Debug Boot Splash Screen Issues

echo "Boot Splash Screen Debugger"
echo "==========================="

# Get user info
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$USER_HOME/gps-navigation"

echo "User: $REAL_USER"
echo "Home: $USER_HOME"
echo "Project: $PROJECT_DIR"
echo ""

# Check if boot splash files exist
echo "1. Checking boot splash files..."
BOOT_SPLASH_FILES=(
    "boot_splash.py"
    "epaper_display.py"
)

for file in "${BOOT_SPLASH_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        echo "✓ Found: $PROJECT_DIR/$file"
        echo "  Permissions: $(ls -la "$PROJECT_DIR/$file")"
    else
        echo "✗ Missing: $PROJECT_DIR/$file"
    fi
done
echo ""

# Check systemd service
echo "2. Checking boot splash service..."
SERVICE_FILE="/etc/systemd/system/boot-splash.service"

if [ -f "$SERVICE_FILE" ]; then
    echo "✓ Service file exists: $SERVICE_FILE"
    echo "Contents:"
    cat "$SERVICE_FILE"
    echo ""
    
    # Check service status
    echo "Service status:"
    sudo systemctl status boot-splash.service --no-pager -l
    echo ""
    
    # Check if enabled
    if systemctl is-enabled boot-splash.service >/dev/null 2>&1; then
        echo "✓ Service is enabled"
    else
        echo "✗ Service is not enabled"
        echo "  Fix: sudo systemctl enable boot-splash.service"
    fi
else
    echo "✗ Service file missing: $SERVICE_FILE"
    echo "  Run: sudo ./setup_boot_splash.sh"
fi
echo ""

# Check recent boot logs
echo "3. Checking boot splash logs..."
echo "Recent boot-splash service logs:"
journalctl -u boot-splash.service -n 20 --no-pager
echo ""

# Check if service ran during last boot
echo "4. Checking if service ran during boot..."
LAST_BOOT=$(journalctl --list-boots -q | tail -1 | awk '{print $1}')
echo "Last boot ID: $LAST_BOOT"

if journalctl -b $LAST_BOOT -u boot-splash.service --no-pager | grep -q "boot_splash.py"; then
    echo "✓ Boot splash service ran during last boot"
    echo "Boot splash logs from last boot:"
    journalctl -b $LAST_BOOT -u boot-splash.service --no-pager
else
    echo "✗ Boot splash service did not run during last boot"
fi
echo ""

# Test manual execution
echo "5. Testing manual execution..."
cd "$PROJECT_DIR" 2>/dev/null || {
    echo "✗ Cannot change to project directory"
    exit 1
}

echo "Testing boot splash manually..."
if [ -f "boot_splash.py" ]; then
    echo "Running: python3 boot_splash.py"
    timeout 30 python3 boot_splash.py
    RESULT=$?
    
    if [ $RESULT -eq 0 ]; then
        echo "✓ Boot splash ran successfully"
    elif [ $RESULT -eq 124 ]; then
        echo "ℹ Boot splash timed out (normal - it runs for 5 seconds)"
    else
        echo "✗ Boot splash failed with exit code: $RESULT"
    fi
else
    echo "✗ boot_splash.py not found"
fi
echo ""

# Check display hardware
echo "6. Checking e-paper display hardware..."

# Check SPI
if [ -e /dev/spidev0.0 ]; then
    echo "✓ SPI interface available: /dev/spidev0.0"
else
    echo "✗ SPI interface not available"
    echo "  Enable with: sudo raspi-config → Interface Options → SPI"
fi

# Check GPIO permissions
if groups $USER | grep -q gpio; then
    echo "✓ User in gpio group"
else
    echo "✗ User not in gpio group"
    echo "  Fix: sudo usermod -a -G gpio $USER"
fi

# Check Python dependencies
echo ""
echo "7. Checking Python dependencies for boot splash..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR')

try:
    from PIL import Image, ImageDraw, ImageFont
    print('✓ PIL (Pillow) available')
except ImportError:
    print('✗ PIL (Pillow) not available - install with: pip3 install Pillow')

try:
    import spidev
    print('✓ spidev available')
except ImportError:
    print('✗ spidev not available - install with: pip3 install spidev')

try:
    import RPi.GPIO
    print('✓ RPi.GPIO available')
except ImportError:
    print('✗ RPi.GPIO not available - install with: pip3 install RPi.GPIO')

try:
    from epaper_display import EPaperDisplay
    print('✓ EPaperDisplay module imports successfully')
except Exception as e:
    print(f'✗ EPaperDisplay import error: {e}')

try:
    from boot_splash import BootSplash
    print('✓ BootSplash module imports successfully')
except Exception as e:
    print(f'✗ BootSplash import error: {e}')
"
echo ""

# Check boot timing
echo "8. Checking boot timing..."
echo "Boot splash should run early in boot process"
echo "Current service dependencies:"
if [ -f "$SERVICE_FILE" ]; then
    grep -E "(After|Before|Wants)" "$SERVICE_FILE" | sed 's/^/  /'
fi
echo ""

# Recommendations
echo "9. Recommendations..."

if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service not installed"
    echo "   Run: sudo ./setup_boot_splash.sh"
elif ! systemctl is-enabled boot-splash.service >/dev/null 2>&1; then
    echo "❌ Service not enabled"
    echo "   Run: sudo systemctl enable boot-splash.service"
elif [ ! -e /dev/spidev0.0 ]; then
    echo "❌ SPI not enabled"
    echo "   Run: sudo raspi-config → Interface Options → SPI → Yes"
    echo "   Then reboot"
elif ! groups $USER | grep -q gpio; then
    echo "❌ User not in gpio group"
    echo "   Run: sudo usermod -a -G gpio,spi $USER"
    echo "   Then log out and back in"
else
    echo "✅ Configuration looks good"
    echo "   Try: sudo systemctl start boot-splash.service"
    echo "   Or reboot to test: sudo reboot"
fi

echo ""
echo "Manual testing commands:"
echo "  Test service: sudo systemctl start boot-splash.service"
echo "  Check logs: journalctl -u boot-splash.service -f"
echo "  Test script: cd $PROJECT_DIR && python3 boot_splash.py"
echo "  Force reboot test: sudo reboot"
