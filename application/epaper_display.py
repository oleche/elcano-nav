#!/usr/bin/env python3
"""
E-Paper Display Driver for Waveshare 7.5inch e-Paper HAT
========================================================
Simplified and robust driver for the Waveshare 7.5" e-paper display
with proper initialization and error handling.
"""

import time
import logging
import spidev
import RPi.GPIO as GPIO
from PIL import Image

logger = logging.getLogger(__name__)


class EPaperDisplay:
    """E-Paper Display Driver"""

    def __init__(self):
        # Display dimensions
        self.width = 800
        self.height = 480

        # GPIO pins
        self.RST_PIN = 17
        self.DC_PIN = 25
        self.CS_PIN = 8
        self.BUSY_PIN = 24

        # SPI interface
        self.spi = None

        # Initialization state
        self.initialized = False

        logger.info("EPaperDisplay instance created")

    def _gpio_setup(self):
        """Setup GPIO pins"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            GPIO.setup(self.RST_PIN, GPIO.OUT)
            GPIO.setup(self.DC_PIN, GPIO.OUT)
            GPIO.setup(self.CS_PIN, GPIO.OUT)
            GPIO.setup(self.BUSY_PIN, GPIO.IN)

            # Set initial states
            GPIO.output(self.CS_PIN, 1)
            GPIO.output(self.RST_PIN, 1)

            logger.debug("GPIO pins configured")
            return True

        except Exception as e:
            logger.error(f"GPIO setup failed: {e}")
            return False

    def _spi_setup(self):
        """Setup SPI interface"""
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(0, 0)  # Bus 0, Device 0
            self.spi.max_speed_hz = 4000000
            self.spi.mode = 0

            logger.debug("SPI interface configured")
            return True

        except Exception as e:
            logger.error(f"SPI setup failed: {e}")
            return False

    def _wait_until_idle(self, timeout=30):
        """Wait until the display is idle"""
        start_time = time.time()

        while GPIO.input(self.BUSY_PIN) == 1:
            if time.time() - start_time > timeout:
                logger.warning("Display busy timeout")
                return False
            time.sleep(0.1)

        logger.debug("Display is idle")
        return True

    def _send_command(self, command):
        """Send command to display"""
        try:
            GPIO.output(self.DC_PIN, 0)  # Command mode
            GPIO.output(self.CS_PIN, 0)
            self.spi.writebytes([command])
            GPIO.output(self.CS_PIN, 1)

        except Exception as e:
            logger.error(f"Failed to send command 0x{command:02X}: {e}")

    def _send_data(self, data):
        """Send data to display"""
        try:
            GPIO.output(self.DC_PIN, 1)  # Data mode
            GPIO.output(self.CS_PIN, 0)

            if isinstance(data, int):
                self.spi.writebytes([data])
            else:
                self.spi.writebytes(data)

            GPIO.output(self.CS_PIN, 1)

        except Exception as e:
            logger.error(f"Failed to send data: {e}")

    def _reset(self):
        """Reset the display"""
        logger.debug("Resetting display")

        GPIO.output(self.RST_PIN, 1)
        time.sleep(0.2)
        GPIO.output(self.RST_PIN, 0)
        time.sleep(0.01)
        GPIO.output(self.RST_PIN, 1)
        time.sleep(0.2)

    def initialize(self):
        """Initialize the e-paper display"""
        logger.info("Initializing e-paper display")

        try:
            # Setup hardware interfaces
            if not self._gpio_setup():
                return False

            if not self._spi_setup():
                return False

            # Reset display
            self._reset()

            # Wait for display to be ready
            if not self._wait_until_idle():
                logger.error("Display not ready after reset")
                return False

            # Initialize display with simplified sequence
            logger.debug("Sending initialization commands")

            # Power setting
            self._send_command(0x01)
            self._send_data(0x07)
            self._send_data(0x07)
            self._send_data(0x3f)
            self._send_data(0x3f)

            # Power on
            self._send_command(0x04)
            time.sleep(0.1)
            self._wait_until_idle()

            # Panel setting
            self._send_command(0x00)
            self._send_data(0x1F)  # KW-3f, KWR-2F, BWROTP-0f, BWOTP-1f

            # Resolution setting
            self._send_command(0x61)
            self._send_data(0x03)  # Width high byte
            self._send_data(0x20)  # Width low byte (800)
            self._send_data(0x01)  # Height high byte
            self._send_data(0xE0)  # Height low byte (480)

            # Dual SPI mode
            self._send_command(0x15)
            self._send_data(0x00)

            # VCOM and data interval setting
            self._send_command(0x50)
            self._send_data(0x11)
            self._send_data(0x07)

            # Tcon setting
            self._send_command(0x60)
            self._send_data(0x22)

            # Wait for initialization to complete
            self._wait_until_idle()

            self.initialized = True
            logger.info("E-paper display initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Display initialization failed: {e}")
            return False

    def _prepare_image_data(self, image):
        """Prepare image data for display"""
        try:
            # Ensure image is correct size
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)

            # Convert to grayscale if needed
            if image.mode != 'L':
                image = image.convert('L')

            # Convert to bytes
            image_data = []
            pixels = list(image.getdata())

            # Pack pixels into bytes (8 pixels per byte)
            for i in range(0, len(pixels), 8):
                byte_val = 0
                for j in range(8):
                    if i + j < len(pixels):
                        # Threshold: > 128 = white (1), <= 128 = black (0)
                        if pixels[i + j] > 128:
                            byte_val |= (1 << (7 - j))
                image_data.append(byte_val)

            logger.debug(f"Prepared {len(image_data)} bytes of image data")
            return image_data

        except Exception as e:
            logger.error(f"Image preparation failed: {e}")
            return None

    def update(self, image):
        """Update display with new image"""
        if not self.initialized:
            logger.error("Display not initialized")
            return False

        logger.info("Updating display")

        try:
            # Prepare image data
            image_data = self._prepare_image_data(image)
            if not image_data:
                return False

            # Send image data
            self._send_command(0x13)  # Start data transmission

            # Send data in chunks to avoid overwhelming SPI
            chunk_size = 1024
            for i in range(0, len(image_data), chunk_size):
                chunk = image_data[i:i + chunk_size]
                self._send_data(chunk)

                # Small delay between chunks
                if i % (chunk_size * 10) == 0:
                    time.sleep(0.01)

            # Refresh display
            self._send_command(0x12)  # Display refresh
            time.sleep(0.1)

            # Wait for refresh to complete
            if not self._wait_until_idle(timeout=60):
                logger.warning("Display refresh timeout")
                return False

            logger.info("Display updated successfully")
            return True

        except Exception as e:
            logger.error(f"Display update failed: {e}")
            return False

    def clear(self):
        """Clear display to white"""
        logger.info("Clearing display")

        try:
            # Create white image
            white_image = Image.new('L', (self.width, self.height), 255)
            return self.update(white_image)

        except Exception as e:
            logger.error(f"Display clear failed: {e}")
            return False

    def sleep(self):
        """Put display into sleep mode"""
        if not self.initialized:
            return

        logger.info("Putting display to sleep")

        try:
            self._send_command(0x02)  # Power off
            self._wait_until_idle()

            self._send_command(0x07)  # Deep sleep
            self._send_data(0xA5)

        except Exception as e:
            logger.error(f"Display sleep failed: {e}")

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up display resources")

        try:
            if self.initialized:
                self.sleep()

            if self.spi:
                self.spi.close()

            GPIO.cleanup()

        except Exception as e:
            logger.error(f"Display cleanup failed: {e}")


def main():
    """Test the display driver"""
    import sys

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Create display instance
        display = EPaperDisplay()

        # Initialize
        if not display.initialize():
            print("Failed to initialize display")
            return 1

        # Test with simple image
        test_image = Image.new('L', (800, 480), 255)
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(test_image)

        # Draw test pattern
        draw.rectangle([50, 50, 750, 430], outline=0, width=5)
        draw.text((400, 240), "E-Paper Display Test", fill=0, anchor="mm")
        draw.text((400, 280), f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}", fill=0, anchor="mm")

        # Update display
        if display.update(test_image):
            print("Display test successful")
        else:
            print("Display test failed")
            return 1

        # Cleanup
        display.cleanup()

    except KeyboardInterrupt:
        print("Test interrupted")
        return 1
    except Exception as e:
        print(f"Test failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
