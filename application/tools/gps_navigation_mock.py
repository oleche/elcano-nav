#!/usr/bin/env python3
"""
GPS Navigation System with Mock GPS for Testing
===============================================
Version that works without GPS hardware for testing.
"""

import time
import math
import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import requests
import os
import random

# Import the original modules but with GPS mocking
from mbtiles_manager import MBTilesManager
from epaper_display import EPaperDisplay
from database_manager import DatabaseManager
from menu_system import MenuSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gps_navigation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MockGPSModule:
    """Mock GPS module for testing without hardware"""
    
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        
        # Mock GPS data - San Francisco Bay area
        self.latitude = 37.7749
        self.longitude = -122.4194
        self.altitude = 10.0
        self.speed = 0.0
        self.heading = 0.0
        self.satellites = 8
        self.fix_quality = 1
        self.last_update = datetime.now()
        
        # For simulation
        self.running = False
        self.thread = None
        self.simulation_time = 0
        
        # Change tracking
        self.prev_speed = 0.0
        self.prev_heading = 0.0
        self.speed_change_threshold = 2.0
        self.heading_change_threshold = 15.0
        
        logger.info("Mock GPS module initialized - will simulate GPS data")
    
    def connect(self):
        """Mock connection - always succeeds"""
        logger.info(f"Mock GPS: Simulating connection to {self.port}")
        return True
    
    def start_reading(self):
        """Start mock GPS simulation"""
        logger.info("Starting mock GPS simulation")
        self.running = True
        self.thread = threading.Thread(target=self._simulation_loop)
        self.thread.daemon = True
        self.thread.start()
        return True
    
    def _simulation_loop(self):
        """Simulate GPS movement"""
        while self.running:
            try:
                # Simulate slow movement around San Francisco Bay
                self.simulation_time += 1
                
                # Simulate circular movement
                radius = 0.01  # About 1km radius
                angle = (self.simulation_time * 0.1) % (2 * math.pi)
                
                self.latitude = 37.7749 + radius * math.sin(angle)
                self.longitude = -122.4194 + radius * math.cos(angle)
                
                # Simulate speed (0-10 km/h)
                self.speed = 5 + 3 * math.sin(self.simulation_time * 0.05)
                
                # Simulate heading
                self.heading = (angle * 180 / math.pi) % 360
                
                # Add some random variation
                self.latitude += random.uniform(-0.0001, 0.0001)
                self.longitude += random.uniform(-0.0001, 0.0001)
                self.speed += random.uniform(-0.5, 0.5)
                self.heading += random.uniform(-5, 5)
                
                # Keep values in valid ranges
                self.speed = max(0, self.speed)
                self.heading = self.heading % 360
                
                self.last_update = datetime.now()
                
                time.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Mock GPS simulation error: {e}")
                time.sleep(1)
    
    def has_significant_change(self):
        """Check for significant changes (for logbook entries)"""
        speed_change = abs(self.speed - self.prev_speed) >= self.speed_change_threshold
        heading_change = abs(self.heading - self.prev_heading) >= self.heading_change_threshold
        
        if speed_change or heading_change:
            self.prev_speed = self.speed
            self.prev_heading = self.heading
            return True
        
        return False
    
    def stop(self):
        """Stop mock GPS"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Mock GPS stopped")
    
    def get_status(self):
        """Get mock GPS status"""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'speed': self.speed,
            'heading': self.heading,
            'satellites': self.satellites,
            'fix_quality': self.fix_quality,
            'last_update': self.last_update
        }

# Import the rest of the navigation system but replace GPS module
def create_mock_navigation_system(assets_folder=None, config_file='navigation_config.json'):
    """Create navigation system with mock GPS"""
    
    # Import the original NavigationSystem class
    import gps_navigation
    
    # Create instance
    nav_system = gps_navigation.NavigationSystem(assets_folder, config_file)
    
    # Replace GPS module with mock
    nav_system.gps = MockGPSModule()
    
    logger.info("Created navigation system with mock GPS for testing")
    return nav_system

def main():
    """Main entry point for mock GPS testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GPS Navigation System with Mock GPS')
    parser.add_argument('assets_folder', nargs='?', 
                       help='Path to assets folder containing MBTiles files')
    parser.add_argument('--config', default='navigation_config.json',
                       help='Configuration file path')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    print("🧪 GPS Navigation System - Mock GPS Mode")
    print("=======================================")
    print("This version uses simulated GPS data for testing")
    print("Mock GPS will simulate movement around San Francisco Bay")
    print()
    
    # Create and run navigation system with mock GPS
    nav_system = create_mock_navigation_system(args.assets_folder, args.config)
    nav_system.run()

if __name__ == "__main__":
    main()
