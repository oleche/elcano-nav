#!/bin/bash
# Test Boot Splash Screen

echo "Testing Boot Splash Screen"
echo "========================="

# Get user info
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$USER_HOME/gps-navigation"

echo "Project directory: $PROJECT_DIR"

# Change to project directory
cd "$PROJECT_DIR" || {
    echo "Error: Cannot access project directory"
    exit 1
}

# Test 1: Check files exist
echo "1. Checking required files..."
if [ -f "boot_splash.py" ] && [ -f "epaper_display.py" ]; then
    echo "✓ Required files present"
else
    echo "✗ Missing required files"
    ls -la *.py
    exit 1
fi

# Test 2: Check Python imports
echo ""
echo "2. Testing Python imports..."
python3 -c "
import sys
sys.path.insert(0, '.')

try:
    from PIL import Image, ImageDraw, ImageFont
    print('✓ PIL imports OK')
except Exception as e:
    print(f'✗ PIL import error: {e}')

try:
    import spidev
    print('✓ spidev imports OK')
except Exception as e:
    print(f'✗ spidev import error: {e}')

try:
    import RPi.GPIO
    print('✓ RPi.GPIO imports OK')
except Exception as e:
    print(f'✗ RPi.GPIO import error: {e}')

try:
    from epaper_display import EPaperDisplay
    print('✓ EPaperDisplay imports OK')
except Exception as e:
    print(f'✗ EPaperDisplay import error: {e}')

try:
    from boot_splash import BootSplash
    print('✓ BootSplash imports OK')
except Exception as e:
    print(f'✗ BootSplash import error: {e}')
"

# Test 3: Check hardware interfaces
echo ""
echo "3. Checking hardware interfaces..."
if [ -e /dev/spidev0.0 ]; then
    echo "✓ SPI interface available"
else
    echo "✗ SPI interface not available"
    echo "  Enable with: sudo raspi-config"
fi

# Test 4: Check permissions
echo ""
echo "4. Checking permissions..."
if groups $USER | grep -q gpio; then
    echo "✓ User in gpio group"
else
    echo "✗ User not in gpio group"
fi

if groups $USER | grep -q spi; then
    echo "✓ User in spi group"
else
    echo "✗ User not in spi group"
fi

# Test 5: Run boot splash manually
echo ""
echo "5. Testing boot splash execution..."
echo "Running boot splash (will display for 5 seconds)..."

# Run with timeout to prevent hanging
timeout 30 python3 boot_splash.py
RESULT=$?

case $RESULT in
    0)
        echo "✓ Boot splash completed successfully"
        ;;
    124)
        echo "ℹ Boot splash timed out (this may be normal)"
        ;;
    *)
        echo "✗ Boot splash failed with exit code: $RESULT"
        ;;
esac

# Test 6: Check systemd service
echo ""
echo "6. Testing systemd service..."
if [ -f "/etc/systemd/system/boot-splash.service" ]; then
    echo "✓ Service file exists"
    
    if systemctl is-enabled boot-splash.service >/dev/null 2>&1; then
        echo "✓ Service is enabled"
    else
        echo "✗ Service is not enabled"
    fi
    
    echo "Testing service start..."
    sudo systemctl start boot-splash.service
    sleep 3
    
    if systemctl show boot-splash.service -p ExecMainStatus | grep -q "status=0"; then
        echo "✓ Service ran successfully"
    else
        echo "✗ Service failed"
        echo "Service logs:"
        journalctl -u boot-splash.service -n 5 --no-pager
    fi
else
    echo "✗ Service file not found"
fi

echo ""
echo "Test completed!"
echo ""
echo "If all tests pass, the boot splash should work on next reboot."
echo "To see it in action: sudo reboot"
