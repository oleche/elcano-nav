#!/bin/bash
# Complete installation script for boot splash

echo "Installing Elcano One Boot Splash System"
echo "========================================"

# Update system packages
echo "Updating system packages..."
sudo apt-get update

# Install required Python packages if not already installed
echo "Installing Python dependencies..."
sudo apt-get install -y python3-pil python3-spidev python3-rpi.gpio

# Enable SPI if not already enabled
echo "Enabling SPI interface..."
sudo raspi-config nonint do_spi 0

# Copy files to project directory
PROJECT_DIR="$HOME/gps-navigation"
echo "Setting up project directory: $PROJECT_DIR"

mkdir -p "$PROJECT_DIR"

# Check if files exist in current directory
if [ ! -f "boot_splash.py" ]; then
    echo "Error: boot_splash.py not found in current directory"
    echo "Please run this script from the directory containing the project files."
    exit 1
fi

if [ ! -f "epaper_display.py" ]; then
    echo "Error: epaper_display.py not found in current directory"
    echo "Please ensure all project files are present."
    exit 1
fi

# Copy files
echo "Copying project files..."
cp boot_splash.py "$PROJECT_DIR/"
cp epaper_display.py "$PROJECT_DIR/"
cp setup_boot_splash.sh "$PROJECT_DIR/"

# Make scripts executable
chmod +x "$PROJECT_DIR/boot_splash.py"
chmod +x "$PROJECT_DIR/setup_boot_splash.sh"

# Run the setup script
echo "Running boot splash setup..."
cd "$PROJECT_DIR"
sudo ./setup_boot_splash.sh

echo ""
echo "Installation completed!"
echo "Reboot your Raspberry Pi to see the boot splash screen."
