#!/bin/bash
# Install Python requirements for GPS Navigation System

echo "Installing Python requirements for GPS Navigation System"
echo "======================================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi"
    echo "Some hardware-specific libraries may not install correctly on other systems"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system packages first
echo "Updating system packages..."
sudo apt-get update

# Install system dependencies for Python packages
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libffi-dev \
    libssl-dev \
    i2c-tools \
    python3-smbus \
    python3-spidev \
    python3-rpi.gpio

# Upgrade pip
echo "Upgrading pip..."
python3 -m pip install --upgrade pip

# Install requirements from requirements.txt
if [ -f "requirements.txt" ]; then
    echo "Installing Python packages from requirements.txt..."
    python3 -m pip install -r requirements.txt
else
    echo "requirements.txt not found, installing packages individually..."
    
    # Core packages
    echo "Installing core packages..."
    python3 -m pip install \
        Pillow>=8.0.0 \
        numpy>=1.19.0 \
        pyserial>=3.4 \
        requests>=2.25.0 \
        gpiozero>=1.6.0 \
        psutil>=5.8.0
    
    # Try to install hardware-specific packages
    echo "Installing hardware-specific packages..."
    
    # smbus2 (alternative to system python3-smbus)
    python3 -m pip install smbus2>=0.4.0 || echo "Warning: smbus2 installation failed, using system package"
    
    # spidev (alternative to system python3-spidev)
    python3 -m pip install spidev>=3.5 || echo "Warning: spidev installation failed, using system package"
    
    # RPi.GPIO (alternative to system python3-rpi.gpio)
    python3 -m pip install RPi.GPIO>=0.7.0 || echo "Warning: RPi.GPIO installation failed, using system package"
fi

# Verify installations
echo ""
echo "Verifying installations..."
echo "========================="

# Test core packages
python3 -c "import PIL; print(f'✓ Pillow: {PIL.__version__}')" 2>/dev/null || echo "✗ Pillow installation failed"
python3 -c "import numpy; print(f'✓ NumPy: {numpy.__version__}')" 2>/dev/null || echo "✗ NumPy installation failed"
python3 -c "import serial; print(f'✓ PySerial: {serial.__version__}')" 2>/dev/null || echo "✗ PySerial installation failed"
python3 -c "import requests; print(f'✓ Requests: {requests.__version__}')" 2>/dev/null || echo "✗ Requests installation failed"

# Test hardware packages (only on Raspberry Pi)
if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    python3 -c "import RPi.GPIO; print('✓ RPi.GPIO: Available')" 2>/dev/null || echo "✗ RPi.GPIO not available"
    python3 -c "import spidev; print('✓ SpiDev: Available')" 2>/dev/null || echo "✗ SpiDev not available"
    python3 -c "import smbus; print('✓ SMBus: Available')" 2>/dev/null || echo "✗ SMBus not available"
    python3 -c "from gpiozero import Device; print('✓ GPIOZero: Available')" 2>/dev/null || echo "✗ GPIOZero not available"
else
    echo "ℹ Hardware-specific packages not tested (not on Raspberry Pi)"
fi

# Test optional packages
python3 -c "import psutil; print(f'✓ PSUtil: {psutil.__version__}')" 2>/dev/null || echo "ℹ PSUtil not installed (optional)"

echo ""
echo "Installation completed!"
echo ""
echo "If any packages failed to install, you can try:"
echo "  sudo apt-get install python3-<package-name>"
echo "  or"
echo "  pip3 install <package-name>"
echo ""
echo "For hardware-specific issues on Raspberry Pi:"
echo "  sudo raspi-config  # Enable SPI and I2C interfaces"
echo "  sudo usermod -a -G spi,gpio,i2c $USER  # Add user to hardware groups"
echo "  # Then reboot"
