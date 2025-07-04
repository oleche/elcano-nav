#!/bin/bash
# Fix I2C Setup for MPU6050

echo "Fixing I2C Setup for MPU6050"
echo "============================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Running as root - some commands will be adjusted"
    REAL_USER=${SUDO_USER:-pi}
else
    REAL_USER=$USER
fi

echo "Setting up I2C for user: $REAL_USER"

# Enable I2C interface
echo "1. Enabling I2C interface..."
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_i2c 0
    echo "✅ I2C interface enabled"
else
    echo "⚠️  raspi-config not found - manually enabling I2C"

    # Add to config.txt if not present
    if ! grep -q "dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> /boot/config.txt
    fi
    if ! grep -q "dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
        echo "dtparam=i2c_arm=on" >> /boot/firmware/config.txt 2>/dev/null || true
    fi

    # Load I2C modules
    if ! grep -q "i2c-dev" /etc/modules; then
        echo "i2c-dev" >> /etc/modules
    fi
fi

# Install I2C tools
echo ""
echo "2. Installing I2C tools..."
apt-get update
apt-get install -y i2c-tools python3-smbus

# Add user to I2C group
echo ""
echo "3. Adding user to I2C group..."
usermod -a -G i2c $REAL_USER
echo "✅ User $REAL_USER added to i2c group"

# Set I2C permissions
echo ""
echo "4. Setting I2C permissions..."
if [ -e /dev/i2c-1 ]; then
    chmod 666 /dev/i2c-1
    echo "✅ I2C permissions set"
else
    echo "ℹ️  I2C device not yet available (will be created after reboot)"
fi

# Create udev rule for persistent I2C permissions
echo ""
echo "5. Creating udev rule for I2C permissions..."
cat > /etc/udev/rules.d/99-i2c.rules << EOF
SUBSYSTEM=="i2c-dev", GROUP="i2c", MODE="0666"
EOF
echo "✅ Udev rule created"

# Load I2C modules now
echo ""
echo "6. Loading I2C modules..."
modprobe i2c-dev 2>/dev/null || echo "ℹ️  i2c-dev module will load on reboot"
modprobe i2c-bcm2835 2>/dev/null || echo "ℹ️  i2c-bcm2835 module will load on reboot"

# Test I2C after setup
echo ""
echo "7. Testing I2C setup..."
if [ -e /dev/i2c-1 ]; then
    echo "✅ I2C device available: /dev/i2c-1"

    if command -v i2cdetect >/dev/null 2>&1; then
        echo "Scanning I2C bus..."
        i2cdetect -y 1
    fi
else
    echo "ℹ️  I2C device will be available after reboot"
fi

echo ""
echo "Setup completed!"
echo ""
echo "⚠️  REBOOT REQUIRED"
echo "Please reboot your Raspberry Pi to complete I2C setup:"
echo "  sudo reboot"
echo ""
echo "After reboot, test with:"
echo "  ./diagnose_i2c_mpu6050.sh"
echo "  python3 test_mpu6050_standalone.py"
