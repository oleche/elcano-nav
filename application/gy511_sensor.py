#!/usr/bin/env python3
"""
GY-511 (LSM303DLHC) Sensor Driver
================================
Driver for GY-511 module with LSM303DLHC accelerometer and magnetometer.
"""

import time
import math
import logging
import smbus

logger = logging.getLogger(__name__)


class GY511:
    """GY-511 (LSM303DLHC) accelerometer and magnetometer handler"""

    # I2C addresses
    ACCEL_ADDRESS = 0x19  # Accelerometer address
    MAG_ADDRESS = 0x1E  # Magnetometer address

    # Accelerometer registers
    ACCEL_CTRL_REG1_A = 0x20
    ACCEL_CTRL_REG4_A = 0x23
    ACCEL_OUT_X_L_A = 0x28

    # Magnetometer registers
    MAG_CRA_REG_M = 0x00
    MAG_CRB_REG_M = 0x01
    MAG_MR_REG_M = 0x02
    MAG_OUT_X_H_M = 0x03

    def __init__(self, bus=1):
        self.bus = smbus.SMBus(bus)
        self.compass_heading = 0.0
        self.accel_x = 0.0
        self.accel_y = 0.0
        self.accel_z = 0.0
        self.mag_x = 0.0
        self.mag_y = 0.0
        self.mag_z = 0.0
        self.available = False

    def initialize(self):
        """Initialize GY-511 (LSM303DLHC)"""
        try:
            # Check if devices exist first
            import subprocess
            result = subprocess.run(['i2cdetect', '-y', '1'], capture_output=True, text=True)

            accel_found = '19' in result.stdout
            mag_found = '1e' in result.stdout

            if not accel_found and not mag_found:
                logger.warning("GY-511 (LSM303DLHC) not detected on I2C bus - sensor disabled")
                return False

            if not accel_found:
                logger.warning("GY-511 accelerometer not found at address 0x19")
                return False

            if not mag_found:
                logger.warning("GY-511 magnetometer not found at address 0x1E")
                return False

            # Initialize accelerometer
            # Enable accelerometer, 50Hz, all axes
            self.bus.write_byte_data(self.ACCEL_ADDRESS, self.ACCEL_CTRL_REG1_A, 0x47)
            # Set scale to ±2g
            self.bus.write_byte_data(self.ACCEL_ADDRESS, self.ACCEL_CTRL_REG4_A, 0x00)

            # Initialize magnetometer
            # Set data rate to 15Hz
            self.bus.write_byte_data(self.MAG_ADDRESS, self.MAG_CRA_REG_M, 0x10)
            # Set gain to ±1.3 gauss
            self.bus.write_byte_data(self.MAG_ADDRESS, self.MAG_CRB_REG_M, 0x20)
            # Set continuous conversion mode
            self.bus.write_byte_data(self.MAG_ADDRESS, self.MAG_MR_REG_M, 0x00)

            # Test read to verify communication
            test_accel = self.bus.read_byte_data(self.ACCEL_ADDRESS, self.ACCEL_CTRL_REG1_A)
            test_mag = self.bus.read_byte_data(self.MAG_ADDRESS, self.MAG_MR_REG_M)

            self.available = True
            logger.info("GY-511 (LSM303DLHC) initialized successfully")
            return True

        except FileNotFoundError:
            logger.warning("i2cdetect command not found - cannot check for GY-511")
            return False
        except Exception as e:
            logger.warning(f"GY-511 not available: {e}")
            logger.info("Navigation will continue without compass sensor")
            return False

    def read_accel_raw(self):
        """Read raw accelerometer data"""
        try:
            # Read 6 bytes starting from X low register
            data = self.bus.read_i2c_block_data(self.ACCEL_ADDRESS, self.ACCEL_OUT_X_L_A | 0x80, 6)

            # Convert to signed 16-bit values
            x = (data[1] << 8) | data[0]
            y = (data[3] << 8) | data[2]
            z = (data[5] << 8) | data[4]

            # Convert to signed
            if x > 32767:
                x -= 65536
            if y > 32767:
                y -= 65536
            if z > 32767:
                z -= 65536

            return x, y, z
        except Exception as e:
            logger.error(f"Error reading accelerometer: {e}")
            return 0, 0, 0

    def read_mag_raw(self):
        """Read raw magnetometer data"""
        try:
            # Read 6 bytes starting from X high register
            data = self.bus.read_i2c_block_data(self.MAG_ADDRESS, self.MAG_OUT_X_H_M, 6)

            # Convert to signed 16-bit values (big endian)
            x = (data[0] << 8) | data[1]
            z = (data[2] << 8) | data[3]  # Note: Z comes before Y in LSM303
            y = (data[4] << 8) | data[5]

            # Convert to signed
            if x > 32767:
                x -= 65536
            if y > 32767:
                y -= 65536
            if z > 32767:
                z -= 65536

            return x, y, z
        except Exception as e:
            logger.error(f"Error reading magnetometer: {e}")
            return 0, 0, 0

    def update_readings(self):
        """Update sensor readings"""
        if not self.available:
            return

        try:
            # Read accelerometer
            accel_x_raw, accel_y_raw, accel_z_raw = self.read_accel_raw()

            # Convert to g (assuming ±2g scale)
            self.accel_x = accel_x_raw / 16384.0
            self.accel_y = accel_y_raw / 16384.0
            self.accel_z = accel_z_raw / 16384.0

            # Read magnetometer
            mag_x_raw, mag_y_raw, mag_z_raw = self.read_mag_raw()

            # Convert to gauss (assuming ±1.3 gauss scale)
            self.mag_x = mag_x_raw / 1100.0
            self.mag_y = mag_y_raw / 1100.0
            self.mag_z = mag_z_raw / 980.0  # Z axis has different sensitivity

            # Calculate compass heading with tilt compensation
            self.compass_heading = self._calculate_tilt_compensated_heading()

        except Exception as e:
            logger.error(f"Error updating GY-511 readings: {e}")

    def _calculate_tilt_compensated_heading(self):
        """Calculate tilt-compensated compass heading"""
        try:
            # Normalize accelerometer readings
            accel_norm = math.sqrt(self.accel_x ** 2 + self.accel_y ** 2 + self.accel_z ** 2)
            if accel_norm == 0:
                return self.compass_heading  # Return previous heading

            ax = self.accel_x / accel_norm
            ay = self.accel_y / accel_norm

            # Calculate pitch and roll
            pitch = math.asin(-ax)
            roll = math.asin(ay / math.cos(pitch))

            # Tilt compensation
            mag_x_comp = (self.mag_x * math.cos(pitch) +
                          self.mag_z * math.sin(pitch))

            mag_y_comp = (self.mag_x * math.sin(roll) * math.sin(pitch) +
                          self.mag_y * math.cos(roll) -
                          self.mag_z * math.sin(roll) * math.cos(pitch))

            # Calculate heading
            heading = math.atan2(mag_y_comp, mag_x_comp)

            # Convert to degrees and normalize to 0-360
            heading_deg = math.degrees(heading)
            if heading_deg < 0:
                heading_deg += 360

            return heading_deg

        except Exception as e:
            logger.error(f"Error calculating heading: {e}")
            # Fallback to simple 2D compass
            return self._calculate_simple_heading()

    def _calculate_simple_heading(self):
        """Calculate simple 2D compass heading (no tilt compensation)"""
        try:
            heading = math.atan2(self.mag_y, self.mag_x)
            heading_deg = math.degrees(heading)
            if heading_deg < 0:
                heading_deg += 360
            return heading_deg
        except:
            return 0.0

    def get_compass_heading(self):
        """Get compass heading in degrees"""
        if not self.available:
            return 0.0
        self.update_readings()
        return self.compass_heading

    def get_accelerometer_data(self):
        """Get accelerometer data in g"""
        if not self.available:
            return 0.0, 0.0, 0.0
        return self.accel_x, self.accel_y, self.accel_z

    def get_magnetometer_data(self):
        """Get magnetometer data in gauss"""
        if not self.available:
            return 0.0, 0.0, 0.0
        return self.mag_x, self.mag_y, self.mag_z

    def calibrate_magnetometer(self, duration=30):
        """Calibrate magnetometer by rotating device for specified duration"""
        if not self.available:
            logger.warning("GY-511 not available for calibration")
            return False

        logger.info(f"Starting magnetometer calibration - rotate device slowly for {duration} seconds")

        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')

        start_time = time.time()
        while time.time() - start_time < duration:
            self.update_readings()

            min_x = min(min_x, self.mag_x)
            max_x = max(max_x, self.mag_x)
            min_y = min(min_y, self.mag_y)
            max_y = max(max_y, self.mag_y)
            min_z = min(min_z, self.mag_z)
            max_z = max(max_z, self.mag_z)

            time.sleep(0.1)

        # Calculate offsets
        self.mag_offset_x = (max_x + min_x) / 2
        self.mag_offset_y = (max_y + min_y) / 2
        self.mag_offset_z = (max_z + min_z) / 2

        logger.info(f"Calibration complete - Offsets: X={self.mag_offset_x:.3f}, "
                    f"Y={self.mag_offset_y:.3f}, Z={self.mag_offset_z:.3f}")

        return True
