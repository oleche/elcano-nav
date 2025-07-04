#!/usr/bin/env python3
"""
Boot Splash Screen for E-Paper Display
=====================================
Displays "Elcano One" splash screen during Raspberry Pi boot.
"""

import time
import logging
import sys
from PIL import Image, ImageDraw, ImageFont
from epaper_display import EPaperDisplay

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/boot_splash.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BootSplash:
    """Boot splash screen manager"""
    
    def __init__(self, width=800, height=480):
        self.width = width
        self.height = height
        self.display = None
        
        # Load fonts with multiple fallbacks
        self.font_title = self._load_font(72)  # Large title font
        self.font_subtitle = self._load_font(24)  # Smaller subtitle font
        
    def _load_font(self, size):
        """Load font with multiple fallbacks"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/droid/DroidSans-Bold.ttf"
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except (OSError, IOError):
                continue
        
        # Final fallback to default font
        try:
            return ImageFont.load_default()
        except:
            logger.warning(f"Could not load any font for size {size}")
            return None
    
    def initialize_display(self):
        """Initialize the e-paper display"""
        try:
            self.display = EPaperDisplay()
            success = self.display.initialize()
            if success:
                logger.info("E-paper display initialized successfully")
                return True
            else:
                logger.error("Failed to initialize e-paper display")
                return False
        except Exception as e:
            logger.error(f"Error initializing display: {e}")
            return False
    
    def create_splash_image(self):
        """Create the splash screen image"""
        try:
            # Create white background
            image = Image.new('L', (self.width, self.height), 255)
            draw = ImageDraw.Draw(image)
            
            # Main title: "Elcano One"
            title_text = "Elcano One"
            
            # Calculate title position (centered)
            if self.font_title:
                bbox = draw.textbbox((0, 0), title_text, font=self.font_title)
                title_width = bbox[2] - bbox[0]
                title_height = bbox[3] - bbox[1]
            else:
                # Fallback dimensions if font loading failed
                title_width = len(title_text) * 20
                title_height = 30
            
            title_x = (self.width - title_width) // 2
            title_y = (self.height - title_height) // 2 - 40  # Slightly above center
            
            # Draw title
            draw.text((title_x, title_y), title_text, fill=0, font=self.font_title)
            
            # Subtitle: "GPS Navigation System"
            subtitle_text = "GPS Navigation System"
            
            if self.font_subtitle:
                bbox = draw.textbbox((0, 0), subtitle_text, font=self.font_subtitle)
                subtitle_width = bbox[2] - bbox[0]
                subtitle_height = bbox[3] - bbox[1]
            else:
                subtitle_width = len(subtitle_text) * 8
                subtitle_height = 20
            
            subtitle_x = (self.width - subtitle_width) // 2
            subtitle_y = title_y + title_height + 20  # Below title
            
            # Draw subtitle
            draw.text((subtitle_x, subtitle_y), subtitle_text, fill=0, font=self.font_subtitle)
            
            # Add decorative elements
            self._add_decorative_elements(draw, title_x, title_y, title_width, title_height)
            
            # Add boot status
            status_text = "Initializing..."
            status_y = self.height - 60
            
            if self.font_subtitle:
                bbox = draw.textbbox((0, 0), status_text, font=self.font_subtitle)
                status_width = bbox[2] - bbox[0]
            else:
                status_width = len(status_text) * 8
            
            status_x = (self.width - status_width) // 2
            draw.text((status_x, status_y), status_text, fill=0, font=self.font_subtitle)
            
            logger.info("Splash screen image created successfully")
            return image
            
        except Exception as e:
            logger.error(f"Error creating splash image: {e}")
            return None
    
    def _add_decorative_elements(self, draw, title_x, title_y, title_width, title_height):
        """Add decorative elements around the title"""
        try:
            # Draw decorative lines above and below title
            line_y_top = title_y - 20
            line_y_bottom = title_y + title_height + 10
            line_start_x = title_x - 50
            line_end_x = title_x + title_width + 50
            
            # Top line
            draw.line([line_start_x, line_y_top, line_end_x, line_y_top], fill=0, width=3)
            
            # Bottom line
            draw.line([line_start_x, line_y_bottom, line_end_x, line_y_bottom], fill=0, width=3)
            
            # Corner decorations
            corner_size = 20
            
            # Top-left corner
            draw.line([line_start_x, line_y_top, line_start_x, line_y_top + corner_size], fill=0, width=3)
            draw.line([line_start_x, line_y_top, line_start_x + corner_size, line_y_top], fill=0, width=3)
            
            # Top-right corner
            draw.line([line_end_x, line_y_top, line_end_x, line_y_top + corner_size], fill=0, width=3)
            draw.line([line_end_x, line_y_top, line_end_x - corner_size, line_y_top], fill=0, width=3)
            
            # Bottom-left corner
            draw.line([line_start_x, line_y_bottom, line_start_x, line_y_bottom - corner_size], fill=0, width=3)
            draw.line([line_start_x, line_y_bottom, line_start_x + corner_size, line_y_bottom], fill=0, width=3)
            
            # Bottom-right corner
            draw.line([line_end_x, line_y_bottom, line_end_x, line_y_bottom - corner_size], fill=0, width=3)
            draw.line([line_end_x, line_y_bottom, line_end_x - corner_size, line_y_bottom], fill=0, width=3)
            
        except Exception as e:
            logger.warning(f"Error adding decorative elements: {e}")
    
    def display_splash(self):
        """Display the splash screen"""
        try:
            if not self.display:
                logger.error("Display not initialized")
                return False
            
            # Create splash image
            splash_image = self.create_splash_image()
            if not splash_image:
                logger.error("Failed to create splash image")
                return False
            
            # Update display
            logger.info("Updating e-paper display with splash screen...")
            self.display.update(splash_image)
            logger.info("Splash screen displayed successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Error displaying splash screen: {e}")
            return False
    
    def cleanup(self):
        """Cleanup display resources"""
        try:
            if self.display:
                self.display.cleanup()
                logger.info("Display cleanup completed")
        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

def main():
    """Main function"""
    logger.info("Starting boot splash screen...")
    
    splash = BootSplash()
    
    try:
        # Initialize display
        if not splash.initialize_display():
            logger.error("Failed to initialize display")
            sys.exit(1)
        
        # Display splash screen
        if not splash.display_splash():
            logger.error("Failed to display splash screen")
            sys.exit(1)
        
        # Keep splash visible for a few seconds
        logger.info("Splash screen active, waiting...")
        time.sleep(5)
        
        logger.info("Boot splash completed successfully")
        
    except KeyboardInterrupt:
        logger.info("Boot splash interrupted")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        splash.cleanup()

if __name__ == "__main__":
    main()
