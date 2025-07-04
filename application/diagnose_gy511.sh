#!/bin/bash
# Diagnostic script for GY-511 (LSM303DLHC) sensor

echo "GY-511 (LSM303DLHC) Sensor Diagnostic"
echo "====================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "❌ Not running on Raspberry Pi - GY-511 will not work"
    exit 1
fi

echo "✅ Running on Raspberry Pi"
echo ""

# Check I2C interface
echo "1. Checking I2C interface..."
if [ -e /dev/i2c-1 ]; then
    echo "✅ I2C interface is enabled (/dev/i2c-1 exists)"
else
    echo "❌ I2C interface not enabled"
    echo "   Fix: sudo raspi-config → Interface Options → I2C → Yes"
    echo "   Then reboot"
    exit 1
fi

# Check user permissions
echo ""
echo "2. Checking user permissions..."
if groups $USER | grep -q i2c; then
    echo "✅ User $USER is in i2c group"
else
    echo "⚠️  User $USER not in i2c group"
    echo "   Fix: sudo usermod -a -G i2c $USER"
    echo "   Then log out and back in"
fi

# Check for i2c-tools
echo ""
echo "3. Checking I2C tools..."
if command -v i2cdetect >/dev/null 2>&1; then
    echo "✅ i2c-tools installed"
else
    echo "❌ i2c-tools not installed"
    echo "   Fix: sudo apt-get install i2c-tools"
    exit 1
fi

# Scan I2C bus
echo ""
echo "4. Scanning I2C bus for GY-511 devices..."
echo "Expected devices:"
echo "  - 0x19: LSM303DLHC Accelerometer"
echo "  - 0x1e: LSM303DLHC Magnetometer"
echo ""

I2C_SCAN=$(i2cdetect -y 1 2>/dev/null)
echo "$I2C_SCAN"

# Check for accelerometer (0x19)
if echo "$I2C_SCAN" | grep -q " 19 "; then
    echo "✅ Found accelerometer at address 0x19"
    ACCEL_FOUND=true
else
    echo "❌ Accelerometer not found at address 0x19"
    ACCEL_FOUND=false
fi

# Check for magnetometer (0x1e)
if echo "$I2C_SCAN" | grep -q " 1e "; then
    echo "✅ Found magnetometer at address 0x1e"
    MAG_FOUND=true
else
    echo "❌ Magnetometer not found at address 0x1e"
    MAG_FOUND=false
fi

echo ""
echo "5. Hardware connection check..."
echo "GY-511 should be connected as follows:"
echo "  VCC → Pin 1  (3.3V)"
echo "  GND → Pin 6  (Ground)"
echo "  SDA → Pin 3  (GPIO 2)"
echo "  SCL → Pin 5  (GPIO 3)"
echo ""

# Test Python imports
echo "6. Testing Python libraries..."
python3 -c "
try:
    import smbus
    print('✅ smbus library available')
except ImportError:
    print('❌ smbus library not available')
    print('   Fix: sudo apt-get install python3-smbus')

try:
    import time, math
    print('✅ Standard libraries available')
except ImportError:
    print('❌ Standard libraries missing')
"

echo ""
echo "7. Testing GY-511 sensor class..."
if [ -f "gy511_sensor.py" ]; then
    echo "✅ gy511_sensor.py found"
    
    python3 -c "
try:
    from gy511_sensor import GY511
    print('✅ GY511 class imports successfully')
except Exception as e:
    print(f'❌ GY511 import error: {e}')
"
else
    echo "❌ gy511_sensor.py not found in current directory"
fi

echo ""
echo "8. Summary and recommendations..."

if [ "$ACCEL_FOUND" = true ] && [ "$MAG_FOUND" = true ]; then
    echo "🎉 GY-511 sensor detected successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Test the sensor: python3 test_gy511_standalone.py"
    echo "2. Run navigation system: python3 gps_navigation.py"
    
elif [ "$ACCEL_FOUND" = true ] || [ "$MAG_FOUND" = true ]; then
    echo "⚠️  Partial GY-511 detection"
    if [ "$ACCEL_FOUND" = false ]; then
        echo "   Missing: Accelerometer (0x19)"
    fi
    if [ "$MAG_FOUND" = false ]; then
        echo "   Missing: Magnetometer (0x1e)"
    fi
    echo ""
    echo "Possible issues:"
    echo "- Loose connections"
    echo "- Wrong module (not LSM303DLHC)"
    echo "- Faulty sensor"
    
else
    echo "❌ GY-511 sensor not detected"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Check all connections are secure"
    echo "2. Verify you have a GY-511 with LSM303DLHC chip"
    echo "3. Try a different I2C address scan: i2cdetect -y 1"
    echo "4. Check power supply (3.3V, not 5V)"
    echo "5. Test with a multimeter"
fi

echo ""
echo "The navigation system will work without GY-511 (GPS heading only)"
