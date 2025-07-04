#!/bin/bash
# Diagnose I2C and MPU6050 Issues

echo "I2C and MPU6050 Diagnostic Tool"
echo "==============================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "❌ Not running on Raspberry Pi - I2C sensors not supported"
    exit 1
fi

echo "✅ Running on Raspberry Pi"
echo ""

# Check if I2C is enabled
echo "1. Checking I2C interface..."
if [ -e /dev/i2c-1 ]; then
    echo "✅ I2C interface is enabled (/dev/i2c-1 exists)"
else
    echo "❌ I2C interface is NOT enabled"
    echo "   Fix: sudo raspi-config → Interface Options → I2C → Yes"
    echo "   Then reboot"
fi

# Check I2C tools
echo ""
echo "2. Checking I2C tools..."
if command -v i2cdetect >/dev/null 2>&1; then
    echo "✅ i2c-tools installed"
else
    echo "❌ i2c-tools not installed"
    echo "   Fix: sudo apt-get install i2c-tools"
fi

# Check user permissions
echo ""
echo "3. Checking user permissions..."
if groups $USER | grep -q i2c; then
    echo "✅ User $USER is in i2c group"
else
    echo "❌ User $USER is NOT in i2c group"
    echo "   Fix: sudo usermod -a -G i2c $USER"
    echo "   Then log out and back in"
fi

# Scan I2C bus
echo ""
echo "4. Scanning I2C bus..."
if command -v i2cdetect >/dev/null 2>&1 && [ -e /dev/i2c-1 ]; then
    echo "I2C devices found:"
    i2cdetect -y 1
    echo ""

    # Check specifically for MPU6050
    if i2cdetect -y 1 | grep -q " 68 "; then
        echo "✅ MPU6050 detected at address 0x68"
    else
        echo "❌ MPU6050 NOT detected at address 0x68"
        echo "   Check wiring:"
        echo "   - VCC → 3.3V (Pin 17)"
        echo "   - GND → GND (Pin 20)"
        echo "   - SDA → GPIO 2 (Pin 3)"
        echo "   - SCL → GPIO 3 (Pin 5)"
    fi
else
    echo "❌ Cannot scan I2C bus (interface not available)"
fi

# Test Python I2C access
echo ""
echo "5. Testing Python I2C access..."
python3 -c "
import sys
try:
    import smbus
    print('✅ smbus library available')

    try:
        bus = smbus.SMBus(1)
        print('✅ I2C bus accessible from Python')

        # Try to read from MPU6050
        try:
            who_am_i = bus.read_byte_data(0x68, 0x75)
            print(f'✅ MPU6050 WHO_AM_I register: 0x{who_am_i:02x}')
            if who_am_i in [0x68, 0x70, 0x71, 0x72, 0x73, 0x74]:
                print('✅ MPU6050 responding correctly')
            else:
                print(f'⚠️  Unexpected WHO_AM_I value: 0x{who_am_i:02x}')
        except Exception as e:
            print(f'❌ Cannot communicate with MPU6050: {e}')

    except Exception as e:
        print(f'❌ Cannot access I2C bus: {e}')

except ImportError:
    print('❌ smbus library not available')
    print('   Fix: sudo apt-get install python3-smbus')
    sys.exit(1)
" 2>/dev/null || echo "❌ Python I2C test failed"

# Check hardware connections
echo ""
echo "6. Hardware connection guide..."
echo "MPU6050 → Raspberry Pi connections:"
echo "┌─────────┬──────────────┬─────────┐"
echo "│ MPU6050 │ Raspberry Pi │ Pin #   │"
echo "├─────────┼──────────────┼─────────┤"
echo "│ VCC     │ 3.3V         │ Pin 17  │"
echo "│ GND     │ GND          │ Pin 20  │"
echo "│ SDA     │ GPIO 2       │ Pin 3   │"
echo "│ SCL     │ GPIO 3       │ Pin 5   │"
echo "└─────────┴──────────────┴─────────┘"

echo ""
echo "7. Troubleshooting steps..."
echo "If MPU6050 is not detected:"
echo "1. Check all wire connections"
echo "2. Verify MPU6050 power (3.3V, not 5V)"
echo "3. Try different jumper wires"
echo "4. Check for loose connections"
echo "5. Verify MPU6050 module is not damaged"
echo "6. Try connecting to different I2C address (some modules use 0x69)"

echo ""
echo "8. Alternative solutions..."
echo "If MPU6050 continues to fail:"
echo "- Navigation system will work without compass"
echo "- GPS heading will be used instead"
echo "- Consider using a different MPU6050 module"
echo "- Or disable compass functionality entirely"

echo ""
echo "To disable MPU6050 in the navigation system:"
echo "Edit gps_navigation.py and comment out MPU6050 initialization"
