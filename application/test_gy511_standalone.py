#!/usr/bin/env python3
"""
Standalone GY-511 (LSM303DLHC) Test
===================================
Test the GY-511 sensor independently to verify it's working.
"""

import time
import logging
from gy511_sensor import GY511

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_gy511():
    """Test GY-511 sensor functionality"""
    print("GY-511 (LSM303DLHC) Sensor Test")
    print("=" * 40)

    # Initialize sensor
    gy511 = GY511()

    if not gy511.initialize():
        print("❌ Failed to initialize GY-511 sensor")
        print("\nTroubleshooting:")
        print("1. Check I2C is enabled: sudo raspi-config")
        print("2. Check connections:")
        print("   VCC → 3.3V (Pin 1)")
        print("   GND → GND (Pin 6)")
        print("   SDA → GPIO 2 (Pin 3)")
        print("   SCL → GPIO 3 (Pin 5)")
        print("3. Check I2C devices: i2cdetect -y 1")
        print("   Should show devices at 0x19 and 0x1e")
        return False

    print("✅ GY-511 sensor initialized successfully")
    print("\nReading sensor data for 10 seconds...")
    print("(Rotate the device to see compass changes)")
    print()

    try:
        for i in range(20):  # 10 seconds at 0.5s intervals
            gy511.update_readings()

            # Get all sensor data
            accel_x, accel_y, accel_z = gy511.get_accelerometer_data()
            mag_x, mag_y, mag_z = gy511.get_magnetometer_data()
            heading = gy511.get_compass_heading()

            print(f"Reading {i + 1:2d}/20:")
            print(f"  Accelerometer: X={accel_x:6.3f}g, Y={accel_y:6.3f}g, Z={accel_z:6.3f}g")
            print(f"  Magnetometer:  X={mag_x:6.3f}G, Y={mag_y:6.3f}G, Z={mag_z:6.3f}G")
            print(f"  Compass:       {heading:6.1f}°")
            print()

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")

    print("✅ GY-511 test completed successfully")
    return True


def main():
    """Main test function"""
    success = test_gy511()

    if success:
        print("\n🎉 GY-511 sensor is working correctly!")
        print("The navigation system should now work with compass functionality.")
    else:
        print("\n⚠️  GY-511 sensor test failed")
        print("The navigation system will work without compass (GPS heading only).")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
