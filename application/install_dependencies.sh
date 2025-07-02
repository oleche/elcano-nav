#!/bin/bash
# Installation script for GPS Navigation System with Database Support

echo "Installing GPS Navigation System dependencies..."

# Update system
sudo apt-get update

# Install Python packages
sudo apt-get install -y python3-pip python3-pil python3-numpy
sudo apt-get install -y python3-serial python3-smbus python3-spidev
sudo apt-get install -y python3-rpi.gpio python3-requests

# Install SQLite3 (usually pre-installed on Raspberry Pi OS)
sudo apt-get install -y sqlite3 libsqlite3-dev

# Install wireless tools for WiFi monitoring
sudo apt-get install -y wireless-tools

# Install additional Python packages via pip
pip3 install gpiozero requests

# Enable SPI and I2C
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0

# Enable UART for GPS
sudo raspi-config nonint do_serial 0

# Add user to dialout group for serial access
sudo usermod -a -G dialout $USER

echo "Installation complete!"
echo "Please reboot your Raspberry Pi to enable all interfaces."
echo ""
echo "Database will be automatically created on first run."
echo ""
echo "Don't forget to set your sync key:"
echo "export ELCANONAV_SYNC_KEY=your_sync_key_here"
echo "Add this to ~/.bashrc to make it permanent"
echo ""
echo "Usage:"
echo "python3 gps_navigation.py /path/to/your/map.mbtiles"
