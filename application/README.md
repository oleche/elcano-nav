# Raspberry Pi GPS Navigation System

A real-time GPS navigation system using a Waveshare 7.5" e-paper display, GPS module, and MPU6050 sensor.

## Hardware Requirements

### Components
- Raspberry Pi 4 (recommended) or Pi 3B+
- Waveshare 7.5" e-Paper Display (800x480)
- GY-NEO6MV2 GPS Module
- GY-511 (LSM303DLHC) Accelerometer/Magnetometer
- 4x Push buttons with 10kΩ pull-up resistors
- Breadboard and jumper wires

### Pinout Configuration

#### E-Paper Display (Waveshare 7.5")
| Display Pin | Pi Pin | GPIO | Function |
|-------------|--------|------|----------|
| VCC | 1 | 3.3V | Power |
| GND | 6 | GND | Ground |
| DIN | 19 | GPIO 10 | SPI MOSI |
| CLK | 23 | GPIO 11 | SPI SCLK |
| CS | 24 | GPIO 8 | SPI CE0 |
| DC | 22 | GPIO 25 | Data/Command |
| RST | 11 | GPIO 17 | Reset |
| BUSY | 18 | GPIO 24 | Busy Signal |

#### GPS Module (GY-NEO6MV2)
| GPS Pin | Pi Pin | GPIO | Function |
|---------|--------|------|----------|
| VCC | 2 | 5V | Power |
| GND | 14 | GND | Ground |
| TX | 10 | GPIO 15 | UART RX |
| RX | 8 | GPIO 14 | UART TX |

#### GY-511 (LSM303DLHC)
| GY-511 Pin | Pi Pin | GPIO | Function |
|------------|--------|------|----------|
| VCC | 1 | 3.3V | Power |
| GND | 6 | GND | Ground |
| SDA | 3 | GPIO 2 | I2C Data |
| SCL | 5 | GPIO 3 | I2C Clock |

**Note**: The GY-511 contains two I2C devices:
- LSM303DLHC Accelerometer at address 0x19
- LSM303DLHC Magnetometer at address 0x1e

#### Control Buttons
| Button | Pi Pin | GPIO | Function |
|--------|--------|------|----------|
| Zoom In | 36 | GPIO 16 | Increase zoom level |
| Zoom Out | 38 | GPIO 20 | Decrease zoom level |
| Button 3 | 40 | GPIO 21 | Reserved |
| Button 4 | 37 | GPIO 26 | Reserved |

All buttons connect between GPIO pin and GND with 10kΩ pull-up resistors.

## Software Installation

### 1. Enable Required Interfaces

\`\`\`bash
sudo raspi-config
\`\`\`

Enable:
- SPI (Interface Options → SPI → Yes)
- I2C (Interface Options → I2C → Yes)
- Serial Port (Interface Options → Serial Port → No to login shell, Yes to serial interface)

### 2. Install Dependencies

\`\`\`bash
chmod +x install_dependencies.sh
./install_dependencies.sh
\`\`\`

Or manually:

\`\`\`bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-numpy
sudo apt-get install -y python3-serial python3-smbus python3-spidev
sudo apt-get install -y python3-rpi.gpio
pip3 install gpiozero
\`\`\`

### 3. Reboot

\`\`\`bash
sudo reboot
\`\`\`

## Usage

### Basic Usage

\`\`\`bash
python3 gps_navigation.py /path/to/your/map.mbtiles
\`\`\`

### Command Line Options

\`\`\`bash
python3 gps_navigation.py map.mbtiles --config custom_config.json --log-level DEBUG
\`\`\`

### Configuration

Edit `navigation_config.json` to customize:

\`\`\`json
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
  }
}
\`\`\`

## Features

### Display Features
- **Real-time GPS tracking**: Updates every 30 seconds
- **Composite map rendering**: Combines multiple tiles for 800x480 resolution
- **Center crosshair**: Shows current GPS position
- **Compass rose**: Oriented using magnetometer data
- **Coordinate grid**: Graticule overlay for navigation
- **Information panel**: GPS coordinates, speed, heading, satellite count
- **E-paper optimized**: High contrast black and white rendering

### Navigation Features
- **Speed calculation**: Real-time speed in km/h
- **Heading calculation**: GPS-based heading with compass backup
- **Zoom controls**: Hardware buttons for zoom in/out (levels 8-18)
- **Fallback tile system**: Handles missing map tiles gracefully
- **Automatic GPS acquisition**: Waits for GPS fix before displaying maps

### Hardware Integration
- **GPS Module**: NMEA sentence parsing for position, speed, heading
- **MPU6050 Sensor**: Accelerometer/gyroscope for compass heading
- **E-Paper Display**: Optimized for outdoor readability
- **Physical Buttons**: Tactile zoom controls

## System Architecture

### Main Components

1. **NavigationSystem**: Main controller coordinating all components
2. **GPSModule**: Handles GPS communication and NMEA parsing
3. **MPU6050**: Manages accelerometer/gyroscope readings
4. **MapRenderer**: Generates composite maps with overlays
5. **EPaperDisplay**: Controls the e-paper display hardware

### Data Flow

\`\`\`
GPS Module → Position Data → Map Renderer → Composite Image → E-Paper Display
     ↓              ↓              ↓              ↓
MPU6050 → Compass → Navigation → Overlays → Display Update
     ↓         System      ↓
Buttons → Zoom Control → Force Update
\`\`\`

## Troubleshooting

### GPS Issues

**No GPS signal:**
- Check antenna connection
- Ensure clear sky view
- Verify UART is enabled: `ls /dev/ttyAMA0`
- Check GPS module power (red LED should be on)

**GPS not parsing:**
- Test with: `cat /dev/ttyAMA0` (should show NMEA sentences)
- Check baud rate (default 9600)
- Verify TX/RX connections

### Display Issues

**Display not updating:**
- Check SPI is enabled: `lsmod | grep spi`
- Verify display connections
- Check power supply (5V 2.5A minimum)

**Poor contrast:**
- Adjust `contrast_enhancement` in config
- Modify `threshold` value for black/white conversion

### Sensor Issues

**GY-511 not responding:**
- Check I2C is enabled: `i2cdetect -y 1`
- Should show device at address 0x19 and 0x1e
- Verify SDA/SCL connections

### Performance Issues

**Slow updates:**
- Reduce `update_interval` in config
- Use lower zoom levels for faster tile loading
- Ensure MBTiles file is on fast storage (SSD recommended)

## Development

### Adding New Features

The system is designed for extensibility:

1. **New overlays**: Add methods to `MapRenderer._add_overlays()`
2. **Button functions**: Modify button handlers in `NavigationSystem`
3. **Display modes**: Extend `MapRenderer.render_map()`
4. **Sensor integration**: Add new sensor classes following MPU6050 pattern

### Custom Map Styles

For better e-paper readability, consider:
- High contrast map tiles
- Simplified road networks
- Clear typography
- Minimal color usage (converts to grayscale)

### Logging

Logs are written to `gps_navigation.log` and console. Adjust log level:

\`\`\`bash
python3 gps_navigation.py map.mbtiles --log-level DEBUG
\`\`\`

## Performance Optimization

### Map Tiles
- Use optimized MBTiles files with appropriate zoom levels
- Store MBTiles on fast storage (SSD/USB 3.0)
- Pre-generate tiles for your area of interest

### System Performance
- Use Raspberry Pi 4 for better performance
- Ensure adequate cooling
- Use Class 10 SD card or better
- Consider overclocking for faster map rendering

### Power Management
- E-paper displays consume power only during updates
- GPS module can be put in power-save mode when stationary
- Consider adding sleep mode for battery operation

## License

This project is open source. See individual component licenses for details.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly on actual hardware
4. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs in `gps_navigation.log`
3. Test individual components separately
4. Create an issue with full error details and hardware setup
