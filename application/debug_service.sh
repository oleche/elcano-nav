#!/bin/bash
# Debug GPS Navigation Service Issues

echo "GPS Navigation Service Debugger"
echo "==============================="

# Get user info
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$USER_HOME/gps-navigation"

echo "User: $REAL_USER"
echo "Home: $USER_HOME"
echo "Project: $PROJECT_DIR"
echo ""

# Check project directory
echo "1. Checking project directory..."
if [ -d "$PROJECT_DIR" ]; then
    echo "✓ Project directory exists: $PROJECT_DIR"
    echo "Contents:"
    ls -la "$PROJECT_DIR/"
else
    echo "✗ Project directory missing: $PROJECT_DIR"
fi
echo ""

# Check main script
echo "2. Checking main script..."
if [ -f "$PROJECT_DIR/gps_navigation.py" ]; then
    echo "✓ Main script exists"
    echo "Permissions: $(ls -la "$PROJECT_DIR/gps_navigation.py")"

    # Test if executable
    if [ -x "$PROJECT_DIR/gps_navigation.py" ]; then
        echo "✓ Script is executable"
    else
        echo "ℹ Script not executable (fixing...)"
        chmod +x "$PROJECT_DIR/gps_navigation.py"
    fi
else
    echo "✗ Main script missing: $PROJECT_DIR/gps_navigation.py"
fi
echo ""

# Check Python
echo "3. Checking Python..."
if command -v python3 >/dev/null 2>&1; then
    echo "✓ Python3 available: $(which python3)"
    echo "Version: $(python3 --version)"
else
    echo "✗ Python3 not found"
fi
echo ""

# Check service file
echo "4. Checking service file..."
SERVICE_FILE="/etc/systemd/system/gps-navigation.service"
if [ -f "$SERVICE_FILE" ]; then
    echo "✓ Service file exists: $SERVICE_FILE"
    echo "Contents:"
    cat "$SERVICE_FILE"
else
    echo "✗ Service file missing: $SERVICE_FILE"
fi
echo ""

# Check service status
echo "5. Checking service status..."
if systemctl is-enabled gps-navigation.service >/dev/null 2>&1; then
    echo "✓ Service is enabled"
else
    echo "ℹ Service not enabled"
fi

echo "Service status:"
sudo systemctl status gps-navigation.service --no-pager -l
echo ""

# Check recent logs
echo "6. Recent service logs..."
echo "Last 20 log entries:"
journalctl -u gps-navigation.service -n 20 --no-pager
echo ""

# Test manual execution
echo "7. Testing manual execution..."
cd "$PROJECT_DIR" 2>/dev/null || {
    echo "✗ Cannot change to project directory"
    exit 1
}

echo "Testing Python import..."
python3 -c "
import sys
import os
sys.path.insert(0, '$PROJECT_DIR')
os.chdir('$PROJECT_DIR')

print('Python path:', sys.path[0])
print('Working directory:', os.getcwd())
print('Directory contents:', os.listdir('.'))

try:
    # Test basic imports
    from pathlib import Path
    import json
    print('✓ Basic imports work')

    # Test hardware imports (may fail on non-Pi systems)
    try:
        import serial
        print('✓ Serial library available')
    except ImportError:
        print('ℹ Serial library not available (install with: pip3 install pyserial)')

    try:
        import smbus
        print('✓ SMBus library available')
    except ImportError:
        print('ℹ SMBus library not available (install with: sudo apt-get install python3-smbus)')

    try:
        from gpiozero import Button
        print('✓ GPIO library available')
    except ImportError:
        print('ℹ GPIO library not available (install with: pip3 install gpiozero)')

    try:
        from PIL import Image
        print('✓ PIL library available')
    except ImportError:
        print('ℹ PIL library not available (install with: pip3 install Pillow)')

    # Test main script import
    try:
        import gps_navigation
        print('✓ Main script imports successfully')
    except Exception as e:
        print(f'ℹ Main script import issue: {e}')
        print('This may be normal without hardware connected')

except Exception as e:
    print(f'✗ Python test failed: {e}')
"

echo ""
echo "8. Recommendations..."

# Check if running on Raspberry Pi
if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "✓ Running on Raspberry Pi"

    # Check if interfaces are enabled
    if [ -e /dev/spidev0.0 ]; then
        echo "✓ SPI interface enabled"
    else
        echo "ℹ SPI interface not enabled (run: sudo raspi-config)"
    fi

    if [ -e /dev/i2c-1 ]; then
        echo "✓ I2C interface enabled"
    else
        echo "ℹ I2C interface not enabled (run: sudo raspi-config)"
    fi
else
    echo "ℹ Not running on Raspberry Pi (hardware features will not work)"
fi

echo ""
echo "To fix common issues:"
echo "1. Copy all project files to: $PROJECT_DIR/"
echo "2. Install dependencies: ./install_dependencies.sh"
echo "3. Enable hardware interfaces: sudo raspi-config"
echo "4. Recreate service: ./fix_service_setup.sh"
echo "5. Test manually: cd $PROJECT_DIR && python3 gps_navigation.py"
