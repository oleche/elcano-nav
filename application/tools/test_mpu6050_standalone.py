#!/usr/bin/env python3
"""
Standalone MPU6050 Test
======================
Test MPU6050 sensor independently of the main navigation system.
"""

import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_mpu6050():
    """Test MPU6050 sensor functionality"""
    print("MPU6050 Standalone Test")
    print("======================")

    try:
        import smbus
        print("✅ smbus library imported successfully")
    except ImportError:
        print("❌ smbus library not available")
        print("Install with: sudo apt-get install python3-smbus")
        return False

    try:
        # Initialize I2C bus
        bus = smbus.SMBus(1)
        address = 0x68
        print(f"✅ I2C bus initialized, testing address 0x{address:02x}")

        # Test WHO_AM_I register
        try:
            who_am_i = bus.read_byte_data(address, 0x75)
            print(f"✅ WHO_AM_I register: 0x{who_am_i:02x}")

            if who_am_i in [0x68, 0x70, 0x71, 0x72, 0x73, 0x74]:
                print("✅ Valid MPU6050/MPU9250 device detected")
            else:
                print(f"⚠️  Unexpected device ID: 0x{who_am_i:02x}")

        except Exception as e:
            print(f"❌ Cannot read WHO_AM_I register: {e}")
            return False

        # Wake up the device
        try:
            bus.write_byte_data(address, 0x6B, 0)
            print("✅ Device wake-up command sent")
            time.sleep(0.1)
        except Exception as e:
            print(f"❌ Cannot wake up device: {e}")
            return False

        # Test reading accelerometer data
        try:
            # Read accelerometer X-axis (high and low bytes)
            accel_x_h = bus.read_byte_data(address, 0x3B)
            accel_x_l = bus.read_byte_data(address, 0x3C)
            accel_x = (accel_x_h << 8) | accel_x_l
            if accel_x > 32768:
                accel_x -= 65536

            accel_x_g = accel_x / 16384.0
            print(f"✅ Accelerometer X-axis: {accel_x_g:.3f} g")

        except Exception as e:
            print(f"❌ Cannot read accelerometer data: {e}")
            return False

        # Test continuous reading
        print("\n📊 Testing continuous readings (5 seconds)...")
        start_time = time.time()
        reading_count = 0

        while time.time() - start_time < 5:
            try:
                # Read accelerometer data
                accel_x_h = bus.read_byte_data(address, 0x3B)
                accel_x_l = bus.read_byte_data(address, 0x3C)
                accel_y_h = bus.read_byte_data(address, 0x3D)
                accel_y_l = bus.read_byte_data(address, 0x3E)
                accel_z_h = bus.read_byte_data(address, 0x3F)
                accel_z_l = bus.read_byte_data(address, 0x40)

                # Convert to signed values
                accel_x = ((accel_x_h << 8) | accel_x_l)
                if accel_x > 32768: accel_x -= 65536
                accel_y = ((accel_y_h << 8) | accel_y_l)
                if accel_y > 32768: accel_y -= 65536
                accel_z = ((accel_z_h << 8) | accel_z_l)
                if accel_z > 32768: accel_z -= 65536

                # Convert to g-force
                accel_x_g = accel_x / 16384.0
                accel_y_g = accel_y / 16384.0
                accel_z_g = accel_z / 16384.0

                reading_count += 1
                if reading_count % 10 == 0:  # Print every 10th reading
                    print(f"Reading {reading_count}: X={accel_x_g:.3f}g, Y={accel_y_g:.3f}g, Z={accel_z_g:.3f}g")

                time.sleep(0.1)

            except Exception as e:
                print(f"❌ Reading failed: {e}")
                return False

        print(f"✅ Successfully completed {reading_count} readings")
        print("✅ MPU6050 is working correctly!")
        return True

    except Exception as e:
        print(f"❌ MPU6050 test failed: {e}")
        return False


def main():
    """Main test function"""
    success = test_mpu6050()

    print("\n" + "=" * 50)
    if success:
        print("🎉 MPU6050 TEST PASSED")
        print("The sensor is working correctly and can be used in the navigation system.")
    else:
        print("❌ MPU6050 TEST FAILED")
        print("\nTroubleshooting steps:")
        print("1. Run the diagnostic script: ./diagnose_i2c_mpu6050.sh")
        print("2. Check I2C is enabled: sudo raspi-config")
        print("3. Check wiring connections")
        print("4. Install I2C tools: sudo apt-get install i2c-tools")
        print("5. Add user to i2c group: sudo usermod -a -G i2c $USER")
        print("\nThe navigation system will work without the compass sensor.")

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
