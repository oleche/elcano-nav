# Python Requirements Documentation

## Overview

This document describes all Python dependencies required for the GPS Navigation System and Boot Splash Screen, along with installation and troubleshooting information.

## Requirements Files

### 📄 **requirements.txt**
Contains all Python package dependencies with minimum version requirements.

### 🔧 **install_python_requirements.sh**
Automated installation script that:
- Updates system packages
- Installs system dependencies
- Installs Python packages
- Verifies installations
- Provides troubleshooting guidance

### 🔍 **check_requirements.py**
Comprehensive checker that:
- Verifies all package installations
- Checks version compatibility
- Tests hardware-specific packages
- Validates system configuration
- Provides installation guidance

## Required Packages

### 🖼️ **Image Processing**
\`\`\`
Pillow>=8.0.0          # Image manipulation and display rendering
numpy>=1.19.0          # Numerical operations for image processing
\`\`\`

### 🔌 **Hardware Communication**
\`\`\`
pyserial>=3.4          # Serial communication for GPS module
smbus2>=0.4.0          # I2C communication for sensors
spidev>=3.5            # SPI communication for e-paper display
RPi.GPIO>=0.7.0        # Low-level GPIO control
gpiozero>=1.6.0        # High-level GPIO interface
\`\`\`

### 🌐 **Network Communication**
\`\`\`
requests>=2.25.0       # HTTP requests for API synchronization
urllib3>=1.26.0        # HTTP client library
\`\`\`

### 🛠️ **System Utilities**
\`\`\`
psutil>=5.8.0          # System monitoring (optional)
\`\`\`

## Installation Methods

### 🚀 **Quick Installation**
\`\`\`bash
# Method 1: Using requirements.txt
pip3 install -r requirements.txt

# Method 2: Using installation script
chmod +x install_python_requirements.sh
./install_python_requirements.sh

# Method 3: Check and install
python3 check_requirements.py
\`\`\`

### 📋 **Manual Installation**
\`\`\`bash
# Core packages
pip3 install Pillow numpy pyserial requests gpiozero

# Hardware packages (Raspberry Pi only)
pip3 install RPi.GPIO spidev smbus2

# Optional packages
pip3 install psutil
\`\`\`

### 🏗️ **System Dependencies**
\`\`\`bash
# Install system packages first
sudo apt-get update
sudo apt-get install -y \
    python3-dev \
    python3-pip \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    i2c-tools \
    python3-smbus \
    python3-spidev \
    python3-rpi.gpio
\`\`\`

## Platform-Specific Notes

### 🥧 **Raspberry Pi**
- **Hardware packages required**: RPi.GPIO, spidev, smbus2
- **System interfaces needed**: SPI, I2C, Serial
- **User groups required**: gpio, spi, i2c
- **Enable interfaces**: `sudo raspi-config`

### 💻 **Development/Testing**
- **Hardware packages optional**: Will fail gracefully
- **Mock hardware**: Consider using mock libraries for testing
- **Limited functionality**: Display and GPS features won't work

## Version Requirements

### 📊 **Minimum Versions**
| Package | Version | Reason |
|---------|---------|---------|
| Pillow | 8.0.0 | Security fixes, performance improvements |
| numpy | 1.19.0 | Compatibility with Pillow |
| pyserial | 3.4 | Stable serial communication |
| requests | 2.25.0 | Security updates, HTTP/2 support |
| RPi.GPIO | 0.7.0 | Raspberry Pi 4 support |
| spidev | 3.5 | Improved SPI performance |
| smbus2 | 0.4.0 | Better I2C error handling |
| gpiozero | 1.6.0 | Enhanced button handling |

### 🔄 **Compatibility**
- **Python**: 3.7+ (Raspberry Pi OS default: 3.9+)
- **Raspberry Pi OS**: Bullseye or newer recommended
- **Hardware**: Raspberry Pi 3B+ or newer

## Troubleshooting

### ❌ **Common Installation Issues**

#### **Permission Errors**
\`\`\`bash
# Solution 1: Install for user only
pip3 install --user package_name

# Solution 2: Use system packages
sudo apt-get install python3-package-name

# Solution 3: Fix permissions
sudo chown -R $USER:$USER ~/.local
\`\`\`

#### **Compilation Errors**
\`\`\`bash
# Install build dependencies
sudo apt-get install build-essential python3-dev

# For Pillow specifically
sudo apt-get install libjpeg-dev zlib1g-dev libfreetype6-dev
\`\`\`

#### **Hardware Package Failures**
\`\`\`bash
# Enable hardware interfaces
sudo raspi-config
# → Interface Options → Enable SPI, I2C

# Add user to hardware groups
sudo usermod -a -G gpio,spi,i2c $USER

# Reboot after changes
sudo reboot
\`\`\`

### 🔍 **Verification Commands**

#### **Test Package Imports**
```python
# Test core packages
python3 -c "import PIL, numpy, serial, requests; print('Core packages OK')"

# Test hardware packages (Raspberry Pi only)
python3 -c "import RPi.GPIO, spidev, smbus; print('Hardware packages OK')"

# Test specific functionality
python3 -c "from PIL import Image; img=Image.new('RGB',(100,100)); print('Pillow OK')"
