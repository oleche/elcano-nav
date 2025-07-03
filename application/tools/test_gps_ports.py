#!/usr/bin/env python3
"""
GPS Port Tester
===============
Tests different serial ports to find GPS module.
"""

import serial
import time
import sys
from pathlib import Path


def test_port(port_path, baudrate=9600, timeout=5):
    """Test a serial port for GPS data"""
    print(f"Testing {port_path}...")

    if not Path(port_path).exists():
        print(f"  ✗ Port does not exist")
        return False, None

    try:
        # Try to open the port
        ser = serial.Serial(port_path, baudrate, timeout=1)
        print(f"  ✓ Port opened successfully")

        # Read data for a few seconds
        start_time = time.time()
        nmea_sentences = []

        while time.time() - start_time < timeout:
            try:
                line = ser.readline().decode('ascii', errors='ignore').strip()
                if line.startswith('$'):
                    nmea_sentences.append(line)
                    print(f"  📡 {line}")

                    # If we get GPS data, that's good enough
                    if len(nmea_sentences) >= 3:
                        break

            except Exception as e:
                print(f"  ⚠️  Read error: {e}")
                break

        ser.close()

        if nmea_sentences:
            print(f"  ✓ Received {len(nmea_sentences)} NMEA sentences")
            return True, nmea_sentences
        else:
            print(f"  ℹ  No NMEA data received (GPS may not be connected)")
            return False, None

    except serial.SerialException as e:
        print(f"  ✗ Serial error: {e}")
        return False, None
    except PermissionError:
        print(f"  ✗ Permission denied (add user to dialout group)")
        return False, None
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False, None


def main():
    """Test common GPS ports"""
    print("GPS Port Tester")
    print("===============")
    print()

    # Common GPS ports on Raspberry Pi
    ports_to_test = [
        "/dev/ttyAMA0",  # Pi 1/2 primary UART
        "/dev/ttyS0",  # Pi 3/4 mini UART (when Bluetooth uses primary)
        "/dev/ttyUSB0",  # USB GPS modules
        "/dev/ttyUSB1",  # Additional USB ports
        "/dev/ttyACM0",  # Some USB GPS modules
    ]

    working_ports = []

    for port in ports_to_test:
        success, data = test_port(port, timeout=3)
        if success:
            working_ports.append((port, data))
        print()

    print("Results:")
    print("========")

    if working_ports:
        print(f"✓ Found {len(working_ports)} working GPS port(s):")
        for port, data in working_ports:
            print(f"  {port} - {len(data)} NMEA sentences")
            print(f"    Sample: {data[0] if data else 'No data'}")

        # Recommend the first working port
        recommended_port = working_ports[0][0]
        print(f"\n🎯 Recommended port: {recommended_port}")

        # Update config file if it exists
        config_file = Path("navigation_config.json")
        if config_file.exists():
            import json
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)

                if 'gps_settings' not in config:
                    config['gps_settings'] = {}

                config['gps_settings']['port'] = recommended_port

                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)

                print(f"✓ Updated {config_file} with port: {recommended_port}")

            except Exception as e:
                print(f"✗ Could not update config file: {e}")
    else:
        print("✗ No working GPS ports found")
        print("\nTroubleshooting:")
        print("1. Check GPS module is connected and powered")
        print("2. Verify UART is enabled: sudo raspi-config")
        print("3. Check user permissions: sudo usermod -a -G dialout $USER")
        print("4. On Pi 3/4, Bluetooth may be using the primary UART")
        print("5. Try USB GPS module if GPIO GPS doesn't work")

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
