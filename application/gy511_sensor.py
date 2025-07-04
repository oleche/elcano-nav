#!/usr/bin/env python3
"""
GY-511 Compass and Accelerometer Sensor Driver
==============================================
Driver for the GY-511 (LSM303DLHC) compass and accelerometer sensor
with enhanced calibration and heading calculation.
"""

import time
import math
import logging
import smbus
import threading
from collections import deque

logger = logging.getLogger(__name__)


class GY511:
    """GY-511 (LSM303DLHC) compass and accelerometer sensor driver"""

    # I2C addresses
    ACCEL_ADDRESS = 0x19  # Accelerometer
    MAG_ADDRESS = 0x1E  # Magnetometer

    # Accelerometer registers
    ACCEL_CTRL_REG1_A = 0x20
    ACCEL_CTRL_REG4_A = 0x23
    ACCEL_OUT_X_L_A = 0x28

    # Magnetometer registers
    MAG_CRA_REG_M = 0x00
    MAG_CRB_REG_M = 0x01
    MAG_MR_REG_M = 0x02
    MAG_OUT_X_H_M = 0x03

    def __init__(self, bus_number=1):
        self.bus_number = bus_number
        self.bus = None
        self.running = False
        self.thread = None

        # Sensor data
        self.accel_x = 0
        self.accel_y = 0
        self.accel_z = 0
        self.mag_x = 0
        self.mag_y = 0
        self.mag_z = 0

        # Heading calculation
        self.heading = 0.0
        self.tilt_compensated_heading = 0.0

        # Calibration data
        self.mag_offset_x = 0
        self.mag_offset_y = 0
        self.mag_offset_z = 0
        self.mag_scale_x = 1.0
        self.mag_scale_y = 1.0
        self.mag_scale_z = 1.0

        # Data smoothing
        self.heading_history = deque(maxlen=5)

        # Last update time
        self.last_update = 0

        logger.info("GY511 sensor initialized")

    def begin(self):
        """Initialize the GY-511 sensor"""
        try:
            self.bus = smbus.SMBus(self.bus_number)

            # Initialize accelerometer
            # Enable accelerometer, 50Hz, all axes
            self.bus.write_byte_data(self.ACCEL_ADDRESS, self.ACCEL_CTRL_REG1_A, 0x47)

            # Set accelerometer scale to ±2g
            self.bus.write_byte_data(self.ACCEL_ADDRESS, self.ACCEL_CTRL_REG4_A, 0x00)

            # Initialize magnetometer
            # Set data rate to 15Hz
            self.bus.write_byte_data(self.MAG_ADDRESS, self.MAG_CRA_REG_M, 0x10)

            # Set gain to ±1.3 gauss
            self.bus.write_byte_data(self.MAG_ADDRESS, self.MAG_CRB_REG_M, 0x20)

            # Set continuous measurement mode
            self.bus.write_byte_data(self.MAG_ADDRESS, self.MAG_MR_REG_M, 0x00)

            time.sleep(0.1)  # Allow sensors to stabilize

            # Start reading thread
            self.running = True
            self.thread = threading.Thread(target=self._read_loop)
            self.thread.daemon = True
            self.thread.start()

            logger.info("GY511 sensor initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize GY511 sensor: {e}")
            return False

    def _read_loop(self):
        """Main sensor reading loop"""
        while self.running:
            try:
                self._read_accelerometer()
                self._read_magnetometer()
                self._calculate_heading()
                self.last_update = time.time()
                time.sleep(0.1)  # 10Hz update rate

            except Exception as e:
                logger.debug(f"Error in GY511 read loop: {e}")
                time.sleep(0.5)

    def _read_accelerometer(self):
        """Read accelerometer data"""
        try:
            # Read 6 bytes starting from X low register
            data = self.bus.read_i2c_block_data(self.ACCEL_ADDRESS,
                                                self.ACCEL_OUT_X_L_A | 0x80, 6)

            # Convert to signed 16-bit values
            self.accel_x = self._to_signed_16(data[1] << 8 | data[0])
            self.accel_y = self._to_signed_16(data[3] << 8 | data[2])
            self.accel_z = self._to_signed_16(data[5] << 8 | data[4])

        except Exception as e:
            logger.debug(f"Error reading accelerometer: {e}")

    def _read_magnetometer(self):
        """Read magnetometer data"""
        try:
            # Read 6 bytes starting from X high register
            data = self.bus.read_i2c_block_data(self.MAG_ADDRESS, self.MAG_OUT_X_H_M, 6)

            # Convert to signed 16-bit values (magnetometer is big-endian)
            self.mag_x = self._to_signed_16(data[0] << 8 | data[1])
            self.mag_z = self._to_signed_16(data[2] << 8 | data[3])  # Z comes before Y
            self.mag_y = self._to_signed_16(data[4] << 8 | data[5])

            # Apply calibration
            self.mag_x = (self.mag_x - self.mag_offset_x) * self.mag_scale_x
            self.mag_y = (self.mag_y - self.mag_offset_y) * self.mag_scale_y
            self.mag_z = (self.mag_z - self.mag_offset_z) * self.mag_scale_z

        except Exception as e:
            logger.debug(f"Error reading magnetometer: {e}")

    def _to_signed_16(self, value):
        """Convert unsigned 16-bit to signed"""
        if value > 32767:
            return value - 65536
        return value

    def _calculate_heading(self):
        """Calculate compass heading with tilt compensation"""
        try:
            # Simple heading calculation (no tilt compensation)
            heading_rad = math.atan2(self.mag_y, self.mag_x)
            heading_deg = math.degrees(heading_rad)

            # Normalize to 0-360 degrees
            if heading_deg < 0:
                heading_deg += 360

            self.heading = heading_deg

            # Tilt-compensated heading calculation
            if self.accel_x != 0 or self.accel_y != 0 or self.accel_z != 0:
                # Normalize accelerometer readings
                accel_norm = math.sqrt(self.accel_x ** 2 + self.accel_y ** 2 + self.accel_z ** 2)
                if accel_norm > 0:
                    ax_norm = self.accel_x / accel_norm
                    ay_norm = self.accel_y / accel_norm
                    az_norm = self.accel_z / accel_norm

                    # Calculate roll and pitch
                    roll = math.atan2(ay_norm, az_norm)
                    pitch = math.atan2(-ax_norm, math.sqrt(ay_norm ** 2 + az_norm ** 2))

                    # Tilt compensation
                    mag_x_comp = (self.mag_x * math.cos(pitch) +
                                  self.mag_z * math.sin(pitch))
                    mag_y_comp = (self.mag_x * math.sin(roll) * math.sin(pitch) +
                                  self.mag_y * math.cos(roll) -
                                  self.mag_z * math.sin(roll) * math.cos(pitch))

                    # Calculate tilt-compensated heading
                    tilt_heading_rad = math.atan2(mag_y_comp, mag_x_comp)
                    tilt_heading_deg = math.degrees(tilt_heading_rad)

                    # Normalize to 0-360 degrees
                    if tilt_heading_deg < 0:
                        tilt_heading_deg += 360

                    self.tilt_compensated_heading = tilt_heading_deg
                else:
                    self.tilt_compensated_heading = self.heading
            else:
                self.tilt_compensated_heading = self.heading

            # Apply smoothing
            self.heading_history.append(self.tilt_compensated_heading)

        except Exception as e:
            logger.debug(f"Error calculating heading: {e}")

    def get_heading(self):
        """Get current compass heading (smoothed, tilt-compensated)"""
        if not self.heading_history:
            return None

        # Return smoothed heading
        return sum(self.heading_history) / len(self.heading_history)

    def get_raw_heading(self):
        """Get raw compass heading (no tilt compensation)"""
        return self.heading if self.last_update > 0 else None

    def get_accelerometer_data(self):
        """Get accelerometer readings"""
        return {
            'x': self.accel_x,
            'y': self.accel_y,
            'z': self.accel_z,
            'timestamp': self.last_update
        }

    def get_magnetometer_data(self):
        """Get magnetometer readings"""
        return {
            'x': self.mag_x,
            'y': self.mag_y,
            'z': self.mag_z,
            'timestamp': self.last_update
        }

    def calibrate_magnetometer(self, duration=30):
        """Calibrate magnetometer by collecting min/max values"""
        logger.info(f"Starting magnetometer calibration for {duration} seconds...")
        logger.info("Rotate the device in all directions during calibration")

        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')

        start_time = time.time()

        while time.time() - start_time < duration:
            # Update min/max values
            min_x = min(min_x, self.mag_x)
            max_x = max(max_x, self.mag_x)
            min_y = min(min_y, self.mag_y)
            max_y = max(max_y, self.mag_y)
            min_z = min(min_z, self.mag_z)
            max_z = max(max_z, self.mag_z)

            time.sleep(0.1)

        # Calculate offsets and scales
        self.mag_offset_x = (max_x + min_x) / 2
        self.mag_offset_y = (max_y + min_y) / 2
        self.mag_offset_z = (max_z + min_z) / 2

        range_x = max_x - min_x
        range_y = max_y - min_y
        range_z = max_z - min_z

        avg_range = (range_x + range_y + range_z) / 3

        self.mag_scale_x = avg_range / range_x if range_x > 0 else 1.0
        self.mag_scale_y = avg_range / range_y if range_y > 0 else 1.0
        self.mag_scale_z = avg_range / range_z if range_z > 0 else 1.0

        logger.info("Magnetometer calibration completed")
        logger.info(f"Offsets: X={self.mag_offset_x:.2f}, Y={self.mag_offset_y:.2f}, Z={self.mag_offset_z:.2f}")
        logger.info(f"Scales: X={self.mag_scale_x:.3f}, Y={self.mag_scale_y:.3f}, Z={self.mag_scale_z:.3f}")

    def is_data_valid(self):
        """Check if sensor data is valid and recent"""
        return (self.last_update > 0 and
                time.time() - self.last_update < 2.0)  # Data should be less than 2 seconds old

    def cleanup(self):
        """Stop sensor and cleanup"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

        if self.bus:
            try:
                self.bus.close()
            except:
                pass

        logger.info("GY511 sensor cleanup completed")


def main():
    """Test the GY511 sensor"""
    import sys

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Create sensor instance
        sensor = GY511()

        # Initialize sensor
        if not sensor.begin():
            print("Failed to initialize GY511 sensor")
            return 1

        print("GY511 sensor initialized successfully")
        print("Press Ctrl+C to stop")

        # Check if calibration is requested
        if len(sys.argv) > 1 and sys.argv[1] == 'calibrate':
            sensor.calibrate_magnetometer(30)

        # Main reading loop
        try:
            while True:
                if sensor.is_data_valid():
                    heading = sensor.get_heading()
                    raw_heading = sensor.get_raw_heading()
                    accel_data = sensor.get_accelerometer_data()
                    mag_data = sensor.get_magnetometer_data()

                    print(f"Heading: {heading:.1f}° (Raw: {raw_heading:.1f}°)")
                    print(f"Accel: X={accel_data['x']:6d}, Y={accel_data['y']:6d}, Z={accel_data['z']:6d}")
                    print(f"Mag:   X={mag_data['x']:6.1f}, Y={mag_data['y']:6.1f}, Z={mag_data['z']:6.1f}")
                    print("-" * 50)
                else:
                    print("Waiting for valid sensor data...")

                time.sleep(1)

        except KeyboardInterrupt:
            print("\nStopping sensor...")

        # Cleanup
        sensor.cleanup()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
