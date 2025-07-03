#!/bin/bash
# Fix GPS Serial Port Issues on Raspberry Pi

echo "GPS Serial Port Diagnostic and Fix"
echo "=================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: Not running on Raspberry Pi - GPS functionality will not work"
    exit 1
fi

echo "1. Checking available serial ports..."
echo "Available serial devices:"
ls -la /dev/tty* | grep -E "(ttyAMA|ttyS|ttyUSB)" || echo "No serial devices found"
echo ""

echo "2. Checking Raspberry Pi model..."
PI_MODEL=$(cat /proc/cpuinfo | grep "Revision" | cut -d' ' -f2)
echo "Pi Revision: $PI_MODEL"

# Determine correct serial port based on Pi model
if [[ "$PI_MODEL" =~ ^(a02082|a22082|a32082|a52082|a020d3) ]]; then
    # Pi 3/4/Zero W - Bluetooth uses ttyAMA0, GPIO serial is ttyS0
    SERIAL_PORT="/dev/ttyS0"
    echo "Pi 3/4/Zero W detected - GPIO serial should be: $SERIAL_PORT"
elif [[ "$PI_MODEL" =~ ^(0002|0003|0004|0005|0006|0007|0008|0009|000d|000e|000f|0010|0011|0012|0013|0014|0015) ]]; then
    # Pi 1/2 - GPIO serial is ttyAMA0
    SERIAL_PORT="/dev/ttyAMA0"
    echo "Pi 1/2 detected - GPIO serial should be: $SERIAL_PORT"
else
    echo "Unknown Pi model - will check both ports"
    SERIAL_PORT="/dev/ttyS0"
fi
echo ""

echo "3. Checking serial port configuration..."

# Check if serial is enabled in config
if grep -q "enable_uart=1" /boot/config.txt 2>/dev/null || grep -q "enable_uart=1" /boot/firmware/config.txt 2>/dev/null; then
    echo "✓ UART is enabled in config.txt"
else
    echo "✗ UART not enabled in config.txt"
    echo "  Fix: Add 'enable_uart=1' to /boot/config.txt"
fi

# Check if serial console is disabled
if grep -q "console=serial" /boot/cmdline.txt 2>/dev/null || grep -q "console=serial" /boot/firmware/cmdline.txt 2>/dev/null; then
    echo "✗ Serial console is enabled (conflicts with GPS)"
    echo "  Fix: Remove console=serial0,115200 from /boot/cmdline.txt"
else
    echo "✓ Serial console is disabled"
fi

# Check if Bluetooth is using the primary UART
if systemctl is-active --quiet hciuart; then
    echo "ℹ Bluetooth is using UART (may conflict on Pi 3/4)"
    echo "  Consider disabling Bluetooth or using mini UART"
else
    echo "✓ Bluetooth UART service not active"
fi
echo ""

echo "4. Testing available serial ports..."

# Test each potential port
for port in "/dev/ttyAMA0" "/dev/ttyS0" "/dev/ttyUSB0" "/dev/ttyUSB1"; do
    if [ -e "$port" ]; then
        echo "Testing $port..."

        # Check permissions
        if [ -r "$port" ] && [ -w "$port" ]; then
            echo "  ✓ Port exists and is accessible"

            # Try to read from port (timeout after 3 seconds)
            timeout 3 cat "$port" > /tmp/gps_test.txt 2>/dev/null &
            PID=$!
            sleep 3
            kill $PID 2>/dev/null

            if [ -s /tmp/gps_test.txt ]; then
                echo "  ✓ Data received from $port"
                echo "  Sample data:"
                head -3 /tmp/gps_test.txt | sed 's/^/    /'
                WORKING_PORT="$port"
            else
                echo "  ℹ No data received from $port (GPS may not be connected)"
            fi
            rm -f /tmp/gps_test.txt
        else
            echo "  ✗ Port exists but not accessible (permission issue)"
            echo "    Current permissions: $(ls -la $port)"
            echo "    Add user to dialout group: sudo usermod -a -G dialout $USER"
        fi
    else
        echo "  ✗ Port $port does not exist"
    fi
    echo ""
done

echo "5. Automatic fixes..."

# Fix 1: Enable UART
CONFIG_FILE="/boot/config.txt"
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
fi

if [ -f "$CONFIG_FILE" ]; then
    if ! grep -q "enable_uart=1" "$CONFIG_FILE"; then
        echo "Adding enable_uart=1 to $CONFIG_FILE..."
        echo "enable_uart=1" | sudo tee -a "$CONFIG_FILE" > /dev/null
        echo "✓ UART enabled in config"
        REBOOT_NEEDED=true
    fi
else
    echo "✗ Could not find config.txt file"
fi

# Fix 2: Disable serial console
CMDLINE_FILE="/boot/cmdline.txt"
if [ ! -f "$CMDLINE_FILE" ]; then
    CMDLINE_FILE="/boot/firmware/cmdline.txt"
fi

if [ -f "$CMDLINE_FILE" ]; then
    if grep -q "console=serial" "$CMDLINE_FILE"; then
        echo "Removing serial console from $CMDLINE_FILE..."
        sudo sed -i 's/console=serial0,115200 //g' "$CMDLINE_FILE"
        sudo sed -i 's/console=ttyAMA0,115200 //g' "$CMDLINE_FILE"
        echo "✓ Serial console disabled"
        REBOOT_NEEDED=true
    fi
fi

# Fix 3: Add user to dialout group
if ! groups $USER | grep -q dialout; then
    echo "Adding $USER to dialout group..."
    sudo usermod -a -G dialout $USER
    echo "✓ User added to dialout group"
    echo "  Note: You need to log out and back in for this to take effect"
fi

# Fix 4: Disable Bluetooth on primary UART (Pi 3/4 only)
if [[ "$PI_MODEL" =~ ^(a02082|a22082|a32082|a52082|a020d3) ]]; then
    echo ""
    echo "Pi 3/4 detected - Bluetooth may be using primary UART"
    echo "Options:"
    echo "1. Disable Bluetooth completely"
    echo "2. Move Bluetooth to mini UART (may be less reliable)"
    echo "3. Use mini UART for GPS (may have timing issues)"
    echo ""
    read -p "Choose option (1/2/3) or press Enter to skip: " choice

    case $choice in
        1)
            echo "Disabling Bluetooth..."
            echo "dtoverlay=disable-bt" | sudo tee -a "$CONFIG_FILE" > /dev/null
            sudo systemctl disable hciuart
            echo "✓ Bluetooth disabled"
            REBOOT_NEEDED=true
            ;;
        2)
            echo "Moving Bluetooth to mini UART..."
            echo "dtoverlay=pi3-miniuart-bt" | sudo tee -a "$CONFIG_FILE" > /dev/null
            echo "✓ Bluetooth moved to mini UART"
            REBOOT_NEEDED=true
            ;;
        3)
            echo "Using mini UART for GPS (less reliable)..."
            SERIAL_PORT="/dev/ttyS0"
            echo "✓ Will use $SERIAL_PORT for GPS"
            ;;
        *)
            echo "Skipping Bluetooth configuration"
            ;;
    esac
fi

echo ""
echo "6. Creating GPS configuration..."

# Update navigation config with correct port
CONFIG_FILE="navigation_config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "Updating $CONFIG_FILE with correct GPS port..."

    # Determine best port to use
    if [ -n "$WORKING_PORT" ]; then
        GPS_PORT="$WORKING_PORT"
    elif [ -e "/dev/ttyS0" ]; then
        GPS_PORT="/dev/ttyS0"
    elif [ -e "/dev/ttyAMA0" ]; then
        GPS_PORT="/dev/ttyAMA0"
    else
        GPS_PORT="/dev/ttyS0"  # Default fallback
    fi

    # Update config file
    python3 -c "
import json
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)

    if 'gps_settings' not in config:
        config['gps_settings'] = {}

    config['gps_settings']['port'] = '$GPS_PORT'
    config['gps_settings']['baudrate'] = 9600

    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)

    print('✓ Updated GPS port to $GPS_PORT')
except Exception as e:
    print(f'✗ Error updating config: {e}')
"
else
    echo "Creating new navigation_config.json..."
    cat > navigation_config.json << EOF
{
  "default_zoom": 14,
  "min_zoom": 8,
  "max_zoom": 18,
  "update_interval": 30,
  "button_pins": {
    "zoom_in": 16,
    "zoom_out": 20,
    "button3": 21,
    "button4": 26
  },
  "gps_settings": {
    "port": "$GPS_PORT",
    "baudrate": 9600,
    "speed_change_threshold": 2.0,
    "heading_change_threshold": 15.0
  },
  "assets_folder": "/opt/elcano/assets/"
}
EOF
    echo "✓ Created navigation_config.json with GPS port: $GPS_PORT"
fi

echo ""
echo "7. Summary and next steps..."

if [ -n "$WORKING_PORT" ]; then
    echo "✓ Found working GPS port: $WORKING_PORT"
else
    echo "ℹ No GPS data detected (GPS may not be connected or powered)"
fi

if [ "$REBOOT_NEEDED" = true ]; then
    echo ""
    echo "⚠️  REBOOT REQUIRED"
    echo "Changes have been made that require a reboot:"
    echo "  sudo reboot"
    echo ""
    echo "After reboot, test GPS with:"
    echo "  python3 gps_navigation.py"
else
    echo ""
    echo "Test GPS connection:"
    echo "  python3 gps_navigation.py"
fi

echo ""
echo "Manual testing commands:"
echo "  # Test serial port directly:"
echo "  cat $GPS_PORT"
echo "  # Should show NMEA sentences like: \$GPGGA,..."
echo ""
echo "  # Check port permissions:"
echo "  ls -la $GPS_PORT"
echo ""
echo "  # Monitor GPS data:"
echo "  timeout 10 cat $GPS_PORT"
