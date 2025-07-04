#!/usr/bin/env python3
"""
E-Paper Display Driver for Waveshare 7.5inch e-Paper HAT
========================================================
Driver for the Waveshare 7.5" e-paper display with optimized refresh rates
and proper initialization sequence.
"""

import time
import logging
import spidev
import RPi.GPIO as GPIO
from PIL import Image

logger = logging.getLogger(__name__)


class EPaperDisplay:
    """E-Paper Display Driver for 7.5inch Waveshare display"""

    # Display resolution
    WIDTH = 800
    HEIGHT = 480

    # GPIO pin definitions
    RST_PIN = 12
    DC_PIN = 6
    CS_PIN = 8
    BUSY_PIN = 5

    def __init__(self):
        self.width = self.WIDTH
        self.height = self.HEIGHT
        self.spi = None
        self.initialized = False

        logger.info("E-Paper Display driver initialized")

    def initialize(self):
        """Initialize the e-paper display"""
        try:
            # Setup GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Configure GPIO pins
            GPIO.setup(self.RST_PIN, GPIO.OUT)
            GPIO.setup(self.DC_PIN, GPIO.OUT)
            GPIO.setup(self.CS_PIN, GPIO.OUT)
            GPIO.setup(self.BUSY_PIN, GPIO.IN)

            # Initialize SPI
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)  # Bus 0, Device 0
            self.spi.max_speed_hz = 4000000
            self.spi.mode = 0

            # Hardware reset
            self._reset()

            # Wait for ready
            self._wait_until_idle()

            # Send initialization commands
            self._send_command(0x01)  # POWER_SETTING
            self._send_data([0x07, 0x07, 0x3f, 0x3f])

            self._send_command(0x04)  # POWER_ON
            time.sleep(0.1)
            self._wait_until_idle()

            self._send_command(0x00)  # PANEL_SETTING
            self._send_data([0x1F])  # KW-3f   KWR-2F	BWROTP 0f	BWOTP 1f

            self._send_command(0x61)  # RESOLUTION_SETTING
            self._send_data([0x03, 0x20, 0x01, 0xE0])  # 800x480

            self._send_command(0x15)  # SPI_FLASH_CONTROL
            self._send_data([0x00])

            self._send_command(0x50)  # VCOM_AND_DATA_INTERVAL_SETTING
            self._send_data([0x11, 0x07])

            self._send_command(0x60)  # TCON_SETTING
            self._send_data([0x22])

            self.initialized = True
            logger.info("E-Paper display initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize e-paper display: {e}")
            return False

    def _reset(self):
        """Hardware reset the display"""
        GPIO.output(self.RST_PIN, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(self.RST_PIN, GPIO.LOW)
        time.sleep(0.2)
        GPIO.output(self.RST_PIN, GPIO.HIGH)
        time.sleep(0.2)

    def _send_command(self, command):
        """Send command to display"""
        GPIO.output(self.DC_PIN, GPIO.LOW)
        GPIO.output(self.CS_PIN, GPIO.LOW)
        self.spi.writebytes([command])
        GPIO.output(self.CS_PIN, GPIO.HIGH)

    def _send_data(self, data):
        """Send data to display"""
        GPIO.output(self.DC_PIN, GPIO.HIGH)
        GPIO.output(self.CS_PIN, GPIO.LOW)
        if isinstance(data, list):
            self.spi.writebytes(data)
        else:
            self.spi.writebytes([data])
        GPIO.output(self.CS_PIN, GPIO.HIGH)

    def _wait_until_idle(self):
        """Wait until display is ready"""
        timeout = time.time() + 30  # 30 second timeout
        while GPIO.input(self.BUSY_PIN) == GPIO.HIGH:
            if time.time() > timeout:
                logger.warning("Display busy timeout")
                break
            time.sleep(0.01)

    def update(self, image):
        """Update the display with new image"""
        if not self.initialized:
            logger.error("Display not initialized")
            return False

        try:
            # Ensure image is correct size and mode
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height))

            if image.mode != 'L':
                image = image.convert('L')

            # Convert image to display format
            buf = self._image_to_buffer(image)

            # Send image data
            self._send_command(0x13)  # DATA_START_TRANSMISSION_2

            # Send data in chunks to avoid SPI buffer overflow
            chunk_size = 4096
            for i in range(0, len(buf), chunk_size):
                chunk = buf[i:i + chunk_size]
                self._send_data(chunk)

            # Refresh display
            self._send_command(0x12)  # DISPLAY_REFRESH
            time.sleep(0.1)
            self._wait_until_idle()

            logger.debug("Display updated successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to update display: {e}")
            return False

    def _image_to_buffer(self, image):
        """Convert PIL image to display buffer"""
        buf = []
        image_array = list(image.getdata())

        for i in range(0, len(image_array), 2):
            # Pack two pixels into one byte
            pixel1 = 0x00 if image_array[i] < 128 else 0x03
            pixel2 = 0x00 if (i + 1 < len(image_array) and image_array[i + 1] < 128) else 0x03
            buf.append((pixel1 << 4) | pixel2)

        return buf

    def clear(self):
        """Clear the display"""
        if not self.initialized:
            return False

        try:
            # Create white image
            white_image = Image.new('L', (self.width, self.height), 255)
            return self.update(white_image)
        except Exception as e:
            logger.error(f"Failed to clear display: {e}")
            return False

    def sleep(self):
        """Put display into sleep mode"""
        if not self.initialized:
            return

        try:
            self._send_command(0x02)  # POWER_OFF
            self._wait_until_idle()
            self._send_command(0x07)  # DEEP_SLEEP
            self._send_data([0xA5])
            logger.info("Display entered sleep mode")
        except Exception as e:
            logger.error(f"Failed to put display to sleep: {e}")

    def cleanup(self):
        """Cleanup GPIO and SPI"""
        try:
            if self.initialized:
                self.sleep()

            if self.spi:
                self.spi.close()

            GPIO.cleanup()
            logger.info("Display cleanup completed")
        except Exception as e:
            logger.error(f"Error during display cleanup: {e}")


def main():
    """Test the e-paper display"""
    import sys

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Create display instance
        display = EPaperDisplay()

        # Initialize display
        if not display.initialize():
            print("Failed to initialize display")
            return 1

        print("Display initialized successfully")

        # Create test image
        test_image = Image.new('L', (display.width, display.height), 255)
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(test_image)

        # Draw test pattern
        draw.rectangle([50, 50, display.width - 50, display.height - 50], outline=0, width=3)
        draw.text((100, 100), "E-Paper Display Test", fill=0)
        draw.text((100, 150), f"Resolution: {display.width}x{display.height}", fill=0)
        draw.text((100, 200), "Display working correctly!", fill=0)

        # Update display
        print("Updating display...")
        if display.update(test_image):
            print("Display updated successfully")
        else:
            print("Failed to update display")
            return 1

        # Cleanup
        display.cleanup()

    except KeyboardInterrupt:
        print("\nTest interrupted")
        if 'display' in locals():
            display.cleanup()
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
