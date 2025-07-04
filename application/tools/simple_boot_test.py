#!/usr/bin/env python3
"""
Simple Boot Splash Test
=======================
Minimal test to verify e-paper display works for boot splash.
"""

import time
import logging
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_display_simple():
    """Simple display test without full EPaperDisplay class"""
    try:
        # Try to import hardware libraries
        import spidev
        import RPi.GPIO as GPIO
        
        print("✓ Hardware libraries imported")
        
        # Create a simple test image
        width, height = 800, 480
        image = Image.new('L', (width, height), 255)  # White background
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Draw "Elcano One" text
        title_text = "Elcano One"
        bbox = draw.textbbox((0, 0), title_text, font=font_large)
        title_width = bbox[2] - bbox[0]
        title_height = bbox[3] - bbox[1]
        
        title_x = (width - title_width) // 2
        title_y = (height - title_height) // 2 - 40
        
        draw.text((title_x, title_y), title_text, fill=0, font=font_large)
        
        # Draw subtitle
        subtitle_text = "GPS Navigation System"
        bbox = draw.textbbox((0, 0), subtitle_text, font=font_small)
        subtitle_width = bbox[2] - bbox[0]
        
        subtitle_x = (width - subtitle_width) // 2
        subtitle_y = title_y + title_height + 20
        
        draw.text((subtitle_x, subtitle_y), subtitle_text, fill=0, font=font_small)
        
        # Draw border
        draw.rectangle([50, 50, width-50, height-50], outline=0, width=3)
        
        print("✓ Test image created")
        
        # Save test image
        image.save("boot_splash_test.png")
        print("✓ Test image saved as boot_splash_test.png")
        
        # Try to initialize display (this might fail without hardware)
        try:
            from epaper_display import EPaperDisplay
            display = EPaperDisplay()
            
            if display.initialize():
                print("✓ E-paper display initialized")
                display.update(image)
                print("✓ Display updated with test image")
                time.sleep(5)
                display.cleanup()
                print("✓ Display test completed successfully")
                return True
            else:
                print("✗ Display initialization failed")
                return False
                
        except Exception as e:
            print(f"✗ Display test failed: {e}")
            print("This may be normal if e-paper display is not connected")
            return False
            
    except ImportError as e:
        print(f"✗ Hardware library import failed: {e}")
        print("Install missing libraries:")
        print("  sudo apt-get install python3-spidev python3-rpi.gpio")
        print("  pip3 install spidev RPi.GPIO")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def main():
    """Main test function"""
    print("Simple Boot Splash Test")
    print("======================")
    print()
    
    success = test_display_simple()
    
    print()
    if success:
        print("✅ Boot splash test PASSED")
        print("The e-paper display should work for boot splash")
    else:
        print("❌ Boot splash test FAILED")
        print("Check hardware connections and dependencies")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
