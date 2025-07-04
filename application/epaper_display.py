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
    """Waveshare 7.5" e-Paper display driver"""
    
    def __init__(self):
        # Pin definitions
        self.RST_PIN = 17
        self.DC_PIN = 25
        self.CS_PIN = 8
        self.BUSY_PIN = 24
        
        # Display dimensions
        self.width = 800
        self.height = 480
        
        # SPI setup
        self.spi = spidev.SpiDev()
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.RST_PIN, GPIO.OUT)
        GPIO.setup(self.DC_PIN, GPIO.OUT)
        GPIO.setup(self.CS_PIN, GPIO.OUT)
        GPIO.setup(self.BUSY_PIN, GPIO.IN)
        
        logger.info("EPaperDisplay instance created")
    
    def initialize(self):
        """Initialize the e-Paper display"""
        try:
            # Initialize SPI
            self.spi.open(0, 0)  # Bus 0, Device 0
            self.spi.max_speed_hz = 4000000
            self.spi.mode = 0
            
            # Hardware reset
            self._reset()
            
            # Send initialization commands
            self._send_command(0x01)  # POWER_SETTING
            self._send_data(0x07)
            self._send_data(0x07)
            self._send_data(0x3f)
            self._send_data(0x3f)
            
            self._send_command(0x04)  # POWER_ON
            self._wait_until_idle()
            
            self._send_command(0x00)  # PANEL_SETTING
            self._send_data(0x1F)     # KW-3f   KWR-2F	BWROTP 0f	BWOTP 1f
            
            self._send_command(0x61)  # RESOLUTION_SETTING
            self._send_data(0x03)     # source 800
            self._send_data(0x20)
            self._send_data(0x01)     # gate 480
            self._send_data(0xE0)
            
            self._send_command(0x15)
            self._send_data(0x00)
            
            self._send_command(0x50)  # VCOM_AND_DATA_INTERVAL_SETTING
            self._send_data(0x11)
            self._send_data(0x07)
            
            self._send_command(0x60)  # TCON_SETTING
            self._send_data(0x22)
            
            logger.info("E-Paper display initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize e-Paper display: {e}")
            return False
    
    def _reset(self):
        """Hardware reset"""
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
        self.spi.writebytes([data])
        GPIO.output(self.CS_PIN, GPIO.HIGH)
    
    def _wait_until_idle(self):
        """Wait until display is ready"""
        while GPIO.input(self.BUSY_PIN) == 1:
            time.sleep(0.01)
    
    def update(self, image):
        """Update display with new image"""
        try:
            # Ensure image is correct size and format
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height))
            
            if image.mode != 'L':
                image = image.convert('L')
            
            # Convert to 1-bit
            image = image.point(lambda x: 0 if x < 128 else 255, '1')
            
            # Send image data
            self._send_command(0x13)  # DATA_START_TRANSMISSION_2
            
            # Convert image to bytes
            buf = []
            for y in range(self.height):
                for x in range(0, self.width, 8):
                    byte = 0
                    for bit in range(8):
                        if x + bit < self.width:
                            pixel = image.getpixel((x + bit, y))
                            if pixel == 0:  # Black pixel
                                byte |= (1 << (7 - bit))
                    buf.append(byte)
            
            # Send data in chunks
            chunk_size = 4096
            for i in range(0, len(buf), chunk_size):
                chunk = buf[i:i + chunk_size]
                GPIO.output(self.DC_PIN, GPIO.HIGH)
                GPIO.output(self.CS_PIN, GPIO.LOW)
                self.spi.writebytes(chunk)
                GPIO.output(self.CS_PIN, GPIO.HIGH)
            
            # Refresh display
            self._send_command(0x12)  # DISPLAY_REFRESH
            self._wait_until_idle()
            
            logger.info("Display updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")
    
    def clear(self):
        """Clear the display"""
        try:
            # Create white image
            white_image = Image.new('L', (self.width, self.height), 255)
            self.update(white_image)
            logger.info("Display cleared")
        except Exception as e:
            logger.error(f"Error clearing display: {e}")
    
    def sleep(self):
        """Put display to sleep"""
        self._send_command(0x02)  # POWER_OFF
        self._wait_until_idle()
        self._send_command(0x07)  # DEEP_SLEEP
        self._send_data(0xA5)
    
    def cleanup(self):
        """Cleanup GPIO and SPI"""
        try:
            self.spi.close()
            GPIO.cleanup()
        except:
            pass

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
