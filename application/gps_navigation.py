#!/usr/bin/env python3
"""
Raspberry Pi GPS Navigation System
==================================
A real-time GPS navigation system using e-paper display, GPS module, and GY-511 sensor.
Enhanced with database storage, trip management, menu system, and multi-regional MBTiles support.
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
import queue

# Hardware libraries
import serial
import smbus
from gpiozero import Button
from PIL import Image, ImageDraw, ImageFont

# Custom imports
from mbtiles_manager import MBTilesManager
from epaper_display import EPaperDisplay
from database_manager import DatabaseManager
from menu_system import MenuSystem
from gy511_sensor import GY511

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


class GPSModule:
    """GPS module handler for GY-NEO6MV2"""

    def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0
        self.speed = 0.0  # Speed in km/h
        self.heading = 0.0  # Heading in degrees
        self.satellites = 0
        self.fix_quality = 0
        self.last_update = None
        self.running = False
        self.thread = None

        # For speed calculation and change detection
        self.prev_lat = None
        self.prev_lon = None
        self.prev_time = None
        self.prev_speed = 0.0
        self.prev_heading = 0.0

        # Change thresholds for logbook entries
        self.speed_change_threshold = 2.0  # km/h
        self.heading_change_threshold = 15.0  # degrees

    def connect(self):
        """Connect to GPS module"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            logger.info(f"Connected to GPS module on {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to GPS: {e}")
            return False

    def parse_nmea(self, sentence):
        """Parse NMEA sentence"""
        try:
            if sentence.startswith('$GPGGA'):
                # Global Positioning System Fix Data
                parts = sentence.split(',')
                if len(parts) >= 15 and parts[2] and parts[4]:
                    # Latitude
                    lat_deg = float(parts[2][:2])
                    lat_min = float(parts[2][2:])
                    self.latitude = lat_deg + lat_min / 60
                    if parts[3] == 'S':
                        self.latitude = -self.latitude

                    # Longitude
                    lon_deg = float(parts[4][:3])
                    lon_min = float(parts[4][3:])
                    self.longitude = lon_deg + lon_min / 60
                    if parts[5] == 'W':
                        self.longitude = -self.longitude

                    # Other data
                    self.fix_quality = int(parts[6]) if parts[6] else 0
                    self.satellites = int(parts[7]) if parts[7] else 0
                    self.altitude = float(parts[9]) if parts[9] else 0.0

                    self.last_update = datetime.now()
                    self._calculate_speed_heading()

            elif sentence.startswith('$GPRMC'):
                # Recommended Minimum Course
                parts = sentence.split(',')
                if len(parts) >= 10 and parts[7]:
                    # Speed in knots, convert to km/h
                    speed_knots = float(parts[7])
                    self.speed = speed_knots * 1.852

                if len(parts) >= 9 and parts[8]:
                    # True course
                    self.heading = float(parts[8])

        except Exception as e:
            logger.debug(f"Error parsing NMEA: {e}")

    def _calculate_speed_heading(self):
        """Calculate speed and heading from position changes"""
        if self.prev_lat is not None and self.prev_lon is not None and self.prev_time is not None:
            current_time = time.time()
            time_diff = current_time - self.prev_time

            if time_diff > 0:
                # Calculate distance using Haversine formula
                distance = self._haversine_distance(
                    self.prev_lat, self.prev_lon,
                    self.latitude, self.longitude
                )

                # Calculate speed in km/h
                speed_ms = distance / time_diff
                self.speed = speed_ms * 3.6

                # Calculate heading
                self.heading = self._calculate_bearing(
                    self.prev_lat, self.prev_lon,
                    self.latitude, self.longitude
                )

        # Update previous values
        self.prev_lat = self.latitude
        self.prev_lon = self.longitude
        self.prev_time = time.time()

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        R = 6371000  # Earth's radius in meters

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        """Calculate bearing between two points"""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360

    def has_significant_change(self):
        """Check if there's been a significant change in speed or heading"""
        speed_change = abs(self.speed - self.prev_speed) >= self.speed_change_threshold
        heading_change = abs(self.heading - self.prev_heading) >= self.heading_change_threshold

        if speed_change or heading_change:
            self.prev_speed = self.speed
            self.prev_heading = self.heading
            return True

        return False

    def start_reading(self):
        """Start reading GPS data in background thread"""
        if not self.connect():
            return False

        self.running = True
        self.thread = threading.Thread(target=self._read_loop)
        self.thread.daemon = True
        self.thread.start()
        return True

    def _read_loop(self):
        """Main GPS reading loop"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('ascii', errors='ignore').strip()
                    if line.startswith('$'):
                        self.parse_nmea(line)
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"GPS reading error: {e}")
                time.sleep(1)

    def stop(self):
        """Stop GPS reading"""
        self.running = False
        if self.thread:
            self.thread.join()
        if self.serial:
            self.serial.close()

    def get_status(self):
        """Get current GPS status"""
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


class WiFiManager:
    """WiFi status monitoring and management"""

    def __init__(self):
        self.is_connected = False
        self.ssid = None
        self.signal_strength = 0
        self.ip_address = None

    def check_wifi_status(self):
        """Check current WiFi connection status"""
        try:
            # Check if WiFi interface is up
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5)
            wifi_info = result.stdout

            # Check for connection
            if 'ESSID:' in wifi_info and 'Not-Associated' not in wifi_info:
                # Extract SSID
                for line in wifi_info.split('\n'):
                    if 'ESSID:' in line:
                        self.ssid = line.split('ESSID:')[1].strip().strip('"')
                        break

                # Get IP address
                ip_result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
                self.ip_address = ip_result.stdout.strip().split()[0] if ip_result.stdout.strip() else None

                self.is_connected = True
            else:
                self.is_connected = False
                self.ssid = None
                self.ip_address = None

        except Exception as e:
            logger.debug(f"Error checking WiFi status: {e}")
            self.is_connected = False

        return self.is_connected

    def get_status(self):
        """Get current WiFi status"""
        return {
            'connected': self.is_connected,
            'ssid': self.ssid,
            'ip_address': self.ip_address,
            'signal_strength': self.signal_strength
        }


class SyncManager:
    """API synchronization manager with enhanced trip management"""

    def _read_sync_key(self):
        """Read sync key from settings file"""
        try:
            with open('/opt/elcano/settings.ini', 'r') as f:
                setting = f.read().strip()
                return setting.replace('token=', '')
        except Exception as e:
            logger.warning(f"Could not read sync key from settings file: {e}")
            return None

    def __init__(self, database_manager, sync_key=None, api_base_url="https://api.elcanonav.com"):
        self.db = database_manager
        self.sync_key = sync_key or self._read_sync_key() or os.getenv('ELCANONAV_SYNC_KEY')
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.session.timeout = 30

        # Ping timer
        self.last_ping_time = None
        self.ping_interval = 60  # 1 minute

        if not self.sync_key:
            logger.warning("No sync key provided. Sync functionality disabled.")

    def is_enabled(self):
        """Check if sync is enabled (has sync key)"""
        return self.sync_key is not None

    def is_valid_sync_key(self):
        """Check if sync key is valid (not default/placeholder)"""
        if not self.sync_key:
            return False
        # Check for default/placeholder sync keys
        invalid_keys = ['ABC1234567', 'PLACEHOLDER', 'DEFAULT', 'TEST123456']
        return self.sync_key not in invalid_keys and len(self.sync_key) >= 10

    def should_ping(self):
        """Check if it's time to ping"""
        if not self.last_ping_time:
            return True
        return (time.time() - self.last_ping_time) >= self.ping_interval

    def ping_device(self, gps_status=None):
        """Send ping to update device last sync time with optional position data"""
        if not self.sync_key:
            return False, "No sync key configured"

        try:
            url = f"{self.api_base_url}/api/sync/device/{self.sync_key}/ping"

            # Prepare payload with position data if available
            payload = {}
            if gps_status and gps_status.get('fix_quality', 0) > 0:
                payload = {
                    "lastLatitude": gps_status.get('latitude'),
                    "lastLongitude": gps_status.get('longitude'),
                    "lastHeading": gps_status.get('heading', 0),
                    "lastCourse": gps_status.get('heading', 0)  # Using heading as course
                }

            # Send POST request with or without payload
            if payload:
                response = self.session.post(url, json=payload)
            else:
                response = self.session.post(url)

            if response.status_code == 200:
                self.last_ping_time = time.time()
                self.db.set_sync_status('last_ping', datetime.now().isoformat())

                # Store response data if available
                response_data = response.json()
                if 'lastLatitude' in response_data:
                    self.db.set_sync_status('last_ping_position', json.dumps({
                        'latitude': response_data.get('lastLatitude'),
                        'longitude': response_data.get('longitude'),
                        'heading': response_data.get('heading'),
                        'course': response_data.get('lastCourse'),
                        'timestamp': response_data.get('lastUpdate')
                    }))

                logger.info("Device ping successful with position data" if payload else "Device ping successful")
                return True, "Ping successful"
            else:
                logger.error(f"Ping failed: {response.status_code} - {response.text}")
                return False, f"Ping failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Ping error: {e}")
            return False, f"Ping error: {str(e)}"

    def sync_device_data(self):
        """Sync device data and trips from API"""
        if not self.sync_key:
            return False, "No sync key configured"

        try:
            url = f"{self.api_base_url}/api/sync/device/{self.sync_key}"
            response = self.session.get(url)

            if response.status_code == 200:
                sync_data = response.json()
                success = self.db.store_device_sync_data(sync_data)

                if success:
                    self.db.set_sync_status('last_full_sync', datetime.now().isoformat())
                    logger.info(f"Synced device data with {len(sync_data.get('trips', []))} trips")
                    return True, f"Synced {len(sync_data.get('trips', []))} trips"
                else:
                    return False, "Failed to store sync data"
            else:
                logger.error(f"Sync failed: {response.status_code}")
                return False, f"Sync failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False, f"Sync error: {str(e)}"

    def update_trip_status(self, trip_id, status):
        """Update trip status via API"""
        if not self.sync_key:
            return False, "No sync key configured"

        try:
            url = f"{self.api_base_url}/api/sync/device/{self.sync_key}/trip/{trip_id}"
            payload = {"status": status}
            response = self.session.put(url, json=payload)

            if response.status_code == 200:
                logger.info(f"Updated trip {trip_id} status to {status}")
                return True, "Trip status updated"
            else:
                logger.error(f"Trip status update failed: {response.status_code} - {response.text}")
                return False, f"Update failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Trip status update error: {e}")
            return False, f"Update error: {str(e)}"

    def sync_logbook_entries(self, entries):
        """Sync logbook entries to API"""
        if not self.sync_key or not entries:
            return False, "No sync key or no entries"

        try:
            url = f"{self.api_base_url}/api/logbook/sync/{self.sync_key}/bulk"

            # Format entries for API
            formatted_entries = []
            for entry in entries:
                formatted_entry = {
                    "timestamp": entry['timestamp'],
                    "location": {
                        "longitude": entry['longitude'],
                        "latitude": entry['latitude']
                    },
                    "vessel": {
                        "speed": entry.get('speed', 0),
                        "course": entry.get('heading', 0)
                    },
                    "content": entry.get('content', 'GPS tracker entry')
                }

                # Add trip ID if available
                if entry.get('trip_id'):
                    formatted_entry['trip'] = entry['trip_id']

                formatted_entries.append(formatted_entry)

            payload = {"entries": formatted_entries}
            response = self.session.post(url, json=payload)

            if response.status_code in [200, 201]:
                logger.info(f"Synced {len(entries)} logbook entries")
                return True, f"Synced {len(entries)} entries"
            else:
                logger.error(f"Logbook sync failed: {response.status_code} - {response.text}")
                return False, f"Sync failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Logbook sync error: {e}")
            return False, f"Sync error: {str(e)}"

    def sync_pending_data(self):
        """Sync all pending data (trips and logbook entries)"""
        results = []

        # Sync trip status updates
        trips_needing_sync = self.db.get_trips_needing_sync()
        for trip in trips_needing_sync:
            status = trip.get('local_status')
            if status:
                success, message = self.update_trip_status(trip['id'], status)
                if success:
                    self.db.mark_trip_synced(trip['id'])
                    results.append(f"Trip {trip['title']}: {message}")
                else:
                    results.append(f"Trip {trip['title']}: {message}")

        # Sync logbook entries
        unsynced_entries = self.db.get_unsynced_logbook_entries()
        if unsynced_entries:
            success, message = self.sync_logbook_entries(unsynced_entries)
            if success:
                entry_ids = [entry['id'] for entry in unsynced_entries]
                self.db.mark_logbook_entries_synced(entry_ids)
            results.append(f"Logbook: {message}")

        return results


class MapRenderer:
    """Map rendering with overlays for e-paper display using MBTilesManager"""

    def __init__(self, mbtiles_manager, width=800, height=480):
        self.width = width
        self.height = height
        self.mbtiles_manager = mbtiles_manager

        # Try to load fonts
        self.font_small = self._load_font(12)
        self.font_medium = self._load_font(16)
        self.font_large = self._load_font(20)
        self.font_title = self._load_font(24)

    def _load_font(self, size):
        """Load font with fallback"""
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", size)
            except:
                return ImageFont.load_default()

    def render_sync_setup_screen(self):
        """Render sync setup configuration screen"""
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Title
        title = "Device Configuration Required"
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, 50), title, fill=0, font=self.font_title)

        # Main message
        y_pos = 120
        messages = [
            "This device needs to be configured with a",
            "synchronization key to connect to ElcanoNav.",
            "",
            "To configure this device:",
            "",
            "1. Connect to WiFi network: 'elcano_nav'",
            "",
            "2. Open web browser and go to:",
            "   http://192.168.4.1",
            "",
            "3. Configure WiFi settings and device key",
            "",
            "4. The device will restart after configuration"
        ]

        for message in messages:
            if message:  # Skip empty lines for spacing
                bbox = draw.textbbox((0, 0), message, font=self.font_medium)
                text_width = bbox[2] - bbox[0]
                text_x = (self.width - text_width) // 2
                draw.text((text_x, y_pos), message, fill=0, font=self.font_medium)
            y_pos += 25

        # Bottom instruction
        bottom_text = "Press any button to retry sync key detection"
        bbox = draw.textbbox((0, 0), bottom_text, font=self.font_small)
        text_width = bbox[2] - bbox[0]
        text_x = (self.width - text_width) // 2
        draw.text((text_x, self.height - 40), bottom_text, fill=0, font=self.font_small)

        # Draw border
        draw.rectangle([20, 20, self.width - 20, self.height - 20], outline=0, width=2)

        return image

    def render_map(self, lat, lon, zoom, heading=0, wifi_status=None, gps_status=None, map_points=None):
        """Render map with overlays using appropriate regional MBTiles file"""
        try:
            # Get appropriate MBTiles reader for coordinates
            reader = self.mbtiles_manager.get_reader_for_coordinates(lat, lon)

            if not reader:
                # No map available for coordinates
                return self._render_no_map_available(lat, lon, wifi_status, gps_status)

            # Generate base map using the selected reader
            image_data, metadata = reader.generate_composite_image(
                lat, lon, zoom, self.width, self.height,
                use_fallback=True, crop_to_size=True
            )

            # Convert to PIL Image
            from io import BytesIO
            base_image = Image.open(BytesIO(image_data))

            # Convert to grayscale for e-paper
            base_image = base_image.convert('L')

            # Enhance contrast for e-paper
            base_image = self._enhance_for_epaper(base_image)

            # Add current file info to metadata
            current_file_info = self.mbtiles_manager.get_current_file_info()
            if current_file_info:
                metadata['current_file'] = current_file_info['filename']
                metadata['region_name'] = current_file_info.get('name', 'Unknown Region')

            # Add overlays with status information
            self._add_overlays(base_image, lat, lon, zoom, heading, metadata, wifi_status, gps_status, map_points)

            return base_image, metadata

        except Exception as e:
            logger.error(f"Error rendering map: {e}")
            # Return error screen
            return self._render_map_error(str(e), lat, lon, wifi_status, gps_status)

    def _render_no_map_available(self, lat, lon, wifi_status, gps_status):
        """Render screen when no map is available for coordinates"""
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Draw status bar
        self._draw_status_bar(draw, wifi_status, gps_status, lat, lon)

        # Title
        draw.text((self.width // 2, 150), "No Map Available",
                  fill=0, font=self.font_large, anchor="mm")

        # Coordinates
        coord_text = f"Position: {lat:.4f}, {lon:.4f}"
        draw.text((self.width // 2, 200), coord_text,
                  fill=0, font=self.font_medium, anchor="mm")

        # Available regions
        available_files = self.mbtiles_manager.get_available_files()
        if available_files:
            draw.text((self.width // 2, 250), "Available Regions:",
                      fill=0, font=self.font_medium, anchor="mm")

            y_pos = 280
            for filename, file_info in list(available_files.items())[:5]:  # Show first 5
                region_name = file_info.get('name', filename)
                draw.text((self.width // 2, y_pos), f"• {region_name}",
                          fill=0, font=self.font_small, anchor="mm")
                y_pos += 25
        else:
            draw.text((self.width // 2, 250), "No map files available",
                      fill=0, font=self.font_medium, anchor="mm")

        return image, {'error': 'no_map_available'}

    def _render_map_error(self, error_msg, lat, lon, wifi_status, gps_status):
        """Render screen when map rendering fails"""
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Draw status bar
        self._draw_status_bar(draw, wifi_status, gps_status, lat, lon)

        # Error message
        draw.text((self.width // 2, 200), "Map Rendering Error",
                  fill=0, font=self.font_large, anchor="mm")

        # Error details (truncated)
        error_text = error_msg[:50] + "..." if len(error_msg) > 50 else error_msg
        draw.text((self.width // 2, 250), error_text,
                  fill=0, font=self.font_small, anchor="mm")

        return image, {'error': 'rendering_error', 'error_message': error_msg}

    def _enhance_for_epaper(self, image):
        """Enhance image contrast for e-paper display with inverted colors"""
        # Convert to grayscale if not already
        if image.mode != 'L':
            image = image.convert('L')

        # Invert colors first (make light areas dark and vice versa)
        import numpy as np
        img_array = np.array(image)
        img_array = 255 - img_array  # Invert: white becomes black, black becomes white

        # Apply threshold to make it more black and white
        # Use a lower threshold since we inverted (lighter areas become white)
        img_array = np.where(img_array > 100, 255, 0)

        # Increase contrast on the inverted image
        inverted_image = Image.fromarray(img_array.astype('uint8'))
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(inverted_image)
        final_image = enhancer.enhance(1.2)  # Reduced contrast enhancement

        return final_image

    def _add_overlays(self, image, lat, lon, zoom, heading, metadata, wifi_status=None, gps_status=None,
                      map_points=None):
        """Add overlays to the map"""
        draw = ImageDraw.Draw(image)

        # Draw status bar first (at top)
        self._draw_status_bar(draw, wifi_status, gps_status, lat, lon)

        # Draw map points if provided
        if map_points:
            self._draw_map_points(draw, map_points, lat, lon, zoom)

        # Draw center crosshair
        self._draw_crosshair(draw)

        # Draw graticule
        self._draw_graticule(draw, lat, lon, zoom)

        # Draw compass rose - force show if we have GY-511 data
        has_gy511_data = hasattr(self, '_last_gy511_heading') or heading != 0
        self._draw_compass_rose(draw, heading, force_show=has_gy511_data)

        # Draw info panel (moved down to accommodate status bar)
        self._draw_info_panel(draw, lat, lon, zoom, metadata)

    def _draw_map_points(self, draw, map_points, center_lat, center_lon, zoom):
        """Draw map points as route overlay"""
        if not map_points or len(map_points) < 2:
            return

        # Convert map points to screen coordinates
        screen_points = []
        for point in map_points:
            screen_x, screen_y = self._geo_to_screen(
                point['latitude'], point['longitude'],
                center_lat, center_lon, zoom
            )
            if 0 <= screen_x <= self.width and 0 <= screen_y <= self.height:
                screen_points.append((screen_x, screen_y))

        # Draw route line
        if len(screen_points) > 1:
            for i in range(len(screen_points) - 1):
                draw.line([screen_points[i], screen_points[i + 1]], fill=0, width=3)

        # Draw points
        for point in screen_points:
            draw.ellipse([point[0] - 3, point[1] - 3, point[0] + 3, point[1] + 3], fill=0)

    def _geo_to_screen(self, lat, lon, center_lat, center_lon, zoom):
        """Convert geographic coordinates to screen coordinates"""
        # Get current reader for coordinate conversion
        reader = self.mbtiles_manager.current_reader
        if not reader:
            return self.width // 2, self.height // 2

        center_x, center_y = reader.deg2num(center_lat, center_lon, zoom)
        point_x, point_y = reader.deg2num(lat, lon, zoom)

        # Calculate offset in tiles
        tile_offset_x = point_x - center_x
        tile_offset_y = point_y - center_y

        # Convert to screen coordinates (256 pixels per tile)
        screen_x = self.width // 2 + int(tile_offset_x * 256)
        screen_y = self.height // 2 + int(tile_offset_y * 256)

        return screen_x, screen_y

    def _draw_status_bar(self, draw, wifi_status, gps_status, lat, lon):
        """Draw status bar at top of screen"""
        # Background for status bar
        draw.rectangle([0, 0, self.width, 30], fill=255, outline=0)

        # GPS status
        gps_text = "GPS: "
        if gps_status and gps_status.get('fix_quality', 0) > 0:
            sats = gps_status.get('satellites', 0)
            gps_text += f"✓ {sats} sats"
        else:
            gps_text += "✗ No fix"

        draw.text((10, 5), gps_text, fill=0, font=self.font_small)

        # WiFi status
        wifi_text = "WiFi: "
        if wifi_status and wifi_status.get('connected', False):
            ssid = wifi_status.get('ssid', 'Unknown')
            wifi_text += f"✓ {ssid}"
        else:
            wifi_text += "✗ Disconnected"

        # Position WiFi text in center
        bbox = draw.textbbox((0, 0), wifi_text, font=self.font_small)
        wifi_width = bbox[2] - bbox[0]
        wifi_x = (self.width - wifi_width) // 2
        draw.text((wifi_x, 5), wifi_text, fill=0, font=self.font_small)

        # Time
        current_time = datetime.now().strftime("%H:%M")
        bbox = draw.textbbox((0, 0), current_time, font=self.font_small)
        time_width = bbox[2] - bbox[0]
        draw.text((self.width - time_width - 10, 5), current_time, fill=0, font=self.font_small)

        # Draw separator line
        draw.line([0, 30, self.width, 30], fill=0, width=1)

    def _draw_crosshair(self, draw):
        """Draw center crosshair"""
        center_x = self.width // 2
        center_y = self.height // 2

        # Draw crosshair
        draw.line([center_x - 15, center_y, center_x + 15, center_y], fill=0, width=2)
        draw.line([center_x, center_y - 15, center_x, center_y + 15], fill=0, width=2)

        # Draw center dot
        draw.ellipse([center_x - 2, center_y - 2, center_x + 2, center_y + 2], fill=0)

    def _draw_graticule(self, draw, lat, lon, zoom):
        """Draw coordinate grid lines"""
        # Skip graticule for now to keep display clean
        pass

    def _draw_compass_rose(self, draw, heading, force_show=False):
        """Draw compass rose in lower left corner"""
        # Position in lower left corner
        rose_x = 60
        rose_y = self.height - 60
        rose_radius = 40

        # Background circle
        draw.ellipse([rose_x - rose_radius, rose_y - rose_radius,
                      rose_x + rose_radius, rose_y + rose_radius],
                     fill=255, outline=0, width=2)

        # Cardinal directions
        directions = ['N', 'E', 'S', 'W']
        for i, direction in enumerate(directions):
            angle = i * 90
            text_x = rose_x + int((rose_radius - 15) * math.sin(math.radians(angle)))
            text_y = rose_y - int((rose_radius - 15) * math.cos(math.radians(angle)))

            bbox = draw.textbbox((0, 0), direction, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((text_x - text_width // 2, text_y - text_height // 2),
                      direction, fill=0, font=self.font_small)

        # Heading indicator (if we have valid heading data or forced)
        if heading > 0 or force_show:
            # Draw heading line
            head_x = rose_x + int((rose_radius - 10) * math.sin(math.radians(heading)))
            head_y = rose_y - int((rose_radius - 10) * math.cos(math.radians(heading)))
            draw.line([rose_x, rose_y, head_x, head_y], fill=0, width=3)

            # Draw heading triangle
            triangle_size = 8
            triangle_x = rose_x + int((rose_radius - 5) * math.sin(math.radians(heading)))
            triangle_y = rose_y - int((rose_radius - 5) * math.cos(math.radians(heading)))

            # Calculate triangle points
            angle_rad = math.radians(heading)
            p1_x = triangle_x + int(triangle_size * math.sin(angle_rad))
            p1_y = triangle_y - int(triangle_size * math.cos(angle_rad))
            p2_x = triangle_x + int(triangle_size * math.sin(angle_rad + 2.618))  # 150 degrees
            p2_y = triangle_y - int(triangle_size * math.cos(angle_rad + 2.618))
            p3_x = triangle_x + int(triangle_size * math.sin(angle_rad - 2.618))  # -150 degrees
            p3_y = triangle_y - int(triangle_size * math.cos(angle_rad - 2.618))

            draw.polygon([(p1_x, p1_y), (p2_x, p2_y), (p3_x, p3_y)], fill=0)

    def _draw_info_panel(self, draw, lat, lon, zoom, metadata):
        """Draw information panel in lower right corner with rounded corners"""
        panel_width = 280
        panel_height = 120
        panel_x = self.width - panel_width - 10
        panel_y = self.height - panel_height - 10
        corner_radius = 10

        # Draw rounded rectangle background
        self._draw_rounded_rectangle(draw, panel_x, panel_y, panel_x + panel_width, panel_y + panel_height,
                                     corner_radius, fill=255, outline=0, width=2)

        # Content
        y_offset = panel_y + 10

        # Coordinates
        coord_text = f"Lat: {lat:.5f}"
        draw.text((panel_x + 10, y_offset), coord_text, fill=0, font=self.font_small)
        y_offset += 15

        coord_text = f"Lon: {lon:.5f}"
        draw.text((panel_x + 10, y_offset), coord_text, fill=0, font=self.font_small)
        y_offset += 15

        # Zoom and region info
        region_name = metadata.get('region_name', 'Unknown')
        if len(region_name) > 25:
            region_name = region_name[:22] + "..."

        zoom_text = f"Zoom: {zoom} | {region_name}"
        draw.text((panel_x + 10, y_offset), zoom_text, fill=0, font=self.font_small)
        y_offset += 15

        # Tile info
        tiles_found = metadata.get('tiles_found', 0)
        tiles_missing = metadata.get('tiles_missing', 0)
        availability = metadata.get('availability_ratio', 0)

        tile_text = f"Tiles: {tiles_found}/{tiles_found + tiles_missing} ({availability:.0%})"
        draw.text((panel_x + 10, y_offset), tile_text, fill=0, font=self.font_small)
        y_offset += 15

        # Zoom adjustment info
        if metadata.get('zoom_adjusted', False):
            actual_zoom = metadata.get('actual_zoom', zoom)
            zoom_adj_text = f"Using zoom {actual_zoom} (adjusted)"
            draw.text((panel_x + 10, y_offset), zoom_adj_text, fill=0, font=self.font_small)

    def _draw_rounded_rectangle(self, draw, x1, y1, x2, y2, radius, fill=None, outline=None, width=1):
        """Draw a rounded rectangle"""
        # Draw the main rectangle
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill, outline=outline, width=width)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill, outline=outline, width=width)

        # Draw the corners
        draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill, outline=outline, width=width)
        draw.pieslice([x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill, outline=outline, width=width)
        draw.pieslice([x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill, outline=outline, width=width)
        draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill, outline=outline, width=width)

    def render_waiting_screen(self, wifi_status=None):
        """Render waiting for GPS signal screen"""
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Draw status bar
        self._draw_status_bar(draw, wifi_status, None, 0, 0)

        # Main message with rounded corners
        msg_width = 400
        msg_height = 200
        msg_x = (self.width - msg_width) // 2
        msg_y = (self.height - msg_height) // 2
        corner_radius = 15

        # Draw rounded rectangle background
        self._draw_rounded_rectangle(draw, msg_x, msg_y, msg_x + msg_width, msg_y + msg_height,
                                     corner_radius, fill=255, outline=0, width=3)

        # Title
        title = "Waiting for GPS Signal"
        bbox = draw.textbbox((0, 0), title, font=self.font_large)
        title_width = bbox[2] - bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, msg_y + 40), title, fill=0, font=self.font_large)

        # Instructions
        instructions = [
            "• Ensure GPS antenna has clear sky view",
            "• Initial GPS fix may take 1-5 minutes",
            "• Check GPS module connections",
            "• Press any button to continue"
        ]

        y_pos = msg_y + 80
        for instruction in instructions:
            bbox = draw.textbbox((0, 0), instruction, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_x = (self.width - text_width) // 2
            draw.text((text_x, y_pos), instruction, fill=0, font=self.font_small)
            y_pos += 25

        return image


class GPSNavigationSystem:
    """Main GPS Navigation System"""

    def __init__(self, config_file='navigation_config.json'):
        # Load configuration
        self.config = self._load_config(config_file)

        # Initialize components
        self.display = EPaperDisplay()
        self.gps = GPSModule()
        self.gy511 = GY511()
        self.wifi = WiFiManager()
        self.db = DatabaseManager()

        # Initialize MBTiles manager
        assets_folder = self.config.get('assets_folder', '/opt/elcano/assets')
        self.mbtiles_manager = MBTilesManager(assets_folder)

        # Initialize sync manager
        self.sync_manager = SyncManager(self.db)

        # Initialize map renderer
        self.map_renderer = MapRenderer(self.mbtiles_manager)

        # Initialize menu system
        self.menu = MenuSystem(self.db, self.sync_manager)

        # Initialize buttons
        self.button_up = Button(2)
        self.button_down = Button(3)
        self.button_left = Button(4)
        self.button_right = Button(17)
        self.button_center = Button(27)

        # Setup button callbacks
        self.button_up.when_pressed = self.on_button_up
        self.button_down.when_pressed = self.on_button_down
        self.button_left.when_pressed = self.on_button_left
        self.button_right.when_pressed = self.on_button_right
        self.button_center.when_pressed = self.on_button_center

        # State management
        self.current_zoom = self.config.get('default_zoom', 14)
        self.min_zoom = self.config.get('min_zoom', 8)
        self.max_zoom = self.config.get('max_zoom', 18)
        self.running = False
        self.in_menu = False
        self.last_display_update = 0
        self.display_update_interval = self.config.get('display_update_interval', 5)

        # Sync timing
        self.last_sync_attempt = 0
        self.sync_interval = self.config.get('sync_interval', 300)  # 5 minutes

        # Logbook management
        self.last_logbook_entry = 0
        self.logbook_interval = self.config.get('logbook_interval', 60)  # 1 minute

        # Current trip
        self.current_trip_id = None

        # GY-511 heading integration
        self._last_gy511_heading = None
        self._gy511_update_time = 0

        logger.info("GPS Navigation System initialized")

    def _load_config(self, config_file):
        """Load configuration from JSON file"""
        default_config = {
            'default_zoom': 14,
            'min_zoom': 8,
            'max_zoom': 18,
            'display_update_interval': 5,
            'sync_interval': 300,
            'logbook_interval': 60,
            'assets_folder': '/opt/elcano/assets'
        }

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            logger.warning(f"Could not load config file {config_file}: {e}")
            return default_config

    def start(self):
        """Start the navigation system"""
        logger.info("Starting GPS Navigation System")

        # Check sync configuration first
        if not self.sync_manager.is_valid_sync_key():
            logger.warning("Invalid or missing sync key - showing setup screen")
            self._show_sync_setup_screen()
            return

        # Initialize display
        if not self.display.init():
            logger.error("Failed to initialize display")
            return

        # Start GPS
        if not self.gps.start_reading():
            logger.error("Failed to start GPS")
            return

        # Start GY-511 sensor
        if not self.gy511.start():
            logger.warning("Failed to start GY-511 sensor - continuing without compass")

        # Show initial screen
        self._show_waiting_screen()

        # Main loop
        self.running = True
        self._main_loop()

    def _show_sync_setup_screen(self):
        """Show sync setup configuration screen and wait for button press"""
        if not self.display.init():
            logger.error("Failed to initialize display for sync setup")
            return

        # Render and display sync setup screen
        setup_image = self.map_renderer.render_sync_setup_screen()
        self.display.display_image(setup_image)

        # Wait for any button press
        logger.info("Waiting for button press to retry sync key detection...")
        button_pressed = False

        def on_any_button():
            nonlocal button_pressed
            button_pressed = True

        # Temporarily assign all buttons to the same callback
        self.button_up.when_pressed = on_any_button
        self.button_down.when_pressed = on_any_button
        self.button_left.when_pressed = on_any_button
        self.button_right.when_pressed = on_any_button
        self.button_center.when_pressed = on_any_button

        # Wait for button press
        while not button_pressed:
            time.sleep(0.1)

        # Restore original button callbacks
        self.button_up.when_pressed = self.on_button_up
        self.button_down.when_pressed = self.on_button_down
        self.button_left.when_pressed = self.on_button_left
        self.button_right.when_pressed = self.on_button_right
        self.button_center.when_pressed = self.on_button_center

        # Re-check sync key
        self.sync_manager = SyncManager(self.db)  # Reinitialize to re-read key

        if self.sync_manager.is_valid_sync_key():
            logger.info("Valid sync key detected - continuing with normal startup")
            # Continue with normal startup
            self.start()
        else:
            logger.info("Still no valid sync key - showing setup screen again")
            self._show_sync_setup_screen()  # Show again

    def _show_waiting_screen(self):
        """Show waiting for GPS screen"""
        wifi_status = self.wifi.get_status()
        waiting_image = self.map_renderer.render_waiting_screen(wifi_status)
        self.display.display_image(waiting_image)

    def _main_loop(self):
        """Main application loop"""
        logger.info("Entering main loop")

        while self.running:
            try:
                current_time = time.time()

                # Update WiFi status
                self.wifi.check_wifi_status()

                # Get GPS status
                gps_status = self.gps.get_status()

                # Get GY-511 heading if available
                gy511_heading = self.gy511.get_heading()
                if gy511_heading is not None:
                    self._last_gy511_heading = gy511_heading
                    self._gy511_update_time = current_time

                # Use GY-511 heading if available and recent, otherwise GPS heading
                heading = 0
                if (self._last_gy511_heading is not None and
                        current_time - self._gy511_update_time < 5):  # Use if updated within 5 seconds
                    heading = self._last_gy511_heading
                elif gps_status.get('heading', 0) > 0:
                    heading = gps_status.get('heading', 0)

                # Check if we have GPS fix
                if gps_status.get('fix_quality', 0) > 0:
                    lat = gps_status['latitude']
                    lon = gps_status['longitude']

                    # Handle menu mode
                    if self.in_menu:
                        self._handle_menu_mode()
                    else:
                        # Update display if enough time has passed
                        if current_time - self.last_display_update >= self.display_update_interval:
                            self._update_map_display(lat, lon, heading, gps_status)
                            self.last_display_update = current_time

                        # Handle sync operations
                        self._handle_sync_operations(gps_status)

                        # Handle logbook entries
                        self._handle_logbook_entries(gps_status)
                else:
                    # No GPS fix - show waiting screen
                    if current_time - self.last_display_update >= self.display_update_interval:
                        self._show_waiting_screen()
                        self.last_display_update = current_time

                time.sleep(0.5)  # Main loop delay

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(1)

        self.stop()

    def _update_map_display(self, lat, lon, heading, gps_status):
        """Update the map display"""
        try:
            wifi_status = self.wifi.get_status()

            # Get current trip points if we have an active trip
            map_points = None
            if self.current_trip_id:
                map_points = self.db.get_trip_points(self.current_trip_id)

            # Render map
            map_image, metadata = self.map_renderer.render_map(
                lat, lon, self.current_zoom, heading,
                wifi_status, gps_status, map_points
            )

            # Display the map
            self.display.display_image(map_image)

            logger.debug(f"Map updated: {lat:.4f}, {lon:.4f}, zoom {self.current_zoom}, "
                         f"heading {heading:.1f}°")

        except Exception as e:
            logger.error(f"Error updating map display: {e}")

    def _handle_menu_mode(self):
        """Handle menu mode operations"""
        try:
            menu_image = self.menu.render()
            self.display.display_image(menu_image)
        except Exception as e:
            logger.error(f"Error in menu mode: {e}")
            self.in_menu = False

    def _handle_sync_operations(self, gps_status):
        """Handle synchronization operations"""
        current_time = time.time()

        # Skip if sync is not enabled
        if not self.sync_manager.is_enabled():
            return

        # Skip if no WiFi
        if not self.wifi.is_connected:
            return

        try:
            # Send ping if needed
            if self.sync_manager.should_ping():
                success, message = self.sync_manager.ping_device(gps_status)
                if success:
                    logger.debug("Device ping successful")
                else:
                    logger.warning(f"Device ping failed: {message}")

            # Full sync if enough time has passed
            if current_time - self.last_sync_attempt >= self.sync_interval:
                logger.info("Performing sync operations")

                # Sync device data
                success, message = self.sync_manager.sync_device_data()
                if success:
                    logger.info(f"Device sync: {message}")
                else:
                    logger.warning(f"Device sync failed: {message}")

                # Sync pending data
                sync_results = self.sync_manager.sync_pending_data()
                for result in sync_results:
                    logger.info(f"Sync result: {result}")

                self.last_sync_attempt = current_time

        except Exception as e:
            logger.error(f"Error in sync operations: {e}")

    def _handle_logbook_entries(self, gps_status):
        """Handle automatic logbook entries"""
        current_time = time.time()

        # Create logbook entry if enough time has passed or significant change
        if (current_time - self.last_logbook_entry >= self.logbook_interval or
                self.gps.has_significant_change()):

            try:
                entry_data = {
                    'latitude': gps_status['latitude'],
                    'longitude': gps_status['longitude'],
                    'speed': gps_status.get('speed', 0),
                    'heading': gps_status.get('heading', 0),
                    'altitude': gps_status.get('altitude', 0),
                    'satellites': gps_status.get('satellites', 0),
                    'trip_id': self.current_trip_id,
                    'content': 'Automatic GPS tracker entry'
                }

                self.db.add_logbook_entry(entry_data)
                self.last_logbook_entry = current_time

                logger.debug(f"Added logbook entry: {gps_status['latitude']:.4f}, {gps_status['longitude']:.4f}")

            except Exception as e:
                logger.error(f"Error adding logbook entry: {e}")

    # Button handlers
    def on_button_up(self):
        """Handle up button press"""
        if self.in_menu:
            self.menu.navigate_up()
        else:
            # Zoom in
            if self.current_zoom < self.max_zoom:
                self.current_zoom += 1
                logger.info(f"Zoomed in to level {self.current_zoom}")

    def on_button_down(self):
        """Handle down button press"""
        if self.in_menu:
            self.menu.navigate_down()
        else:
            # Zoom out
            if self.current_zoom > self.min_zoom:
                self.current_zoom -= 1
                logger.info(f"Zoomed out to level {self.current_zoom}")

    def on_button_left(self):
        """Handle left button press"""
        if self.in_menu:
            self.menu.navigate_back()
        else:
            # Previous map region or other function
            logger.info("Left button pressed")

    def on_button_right(self):
        """Handle right button press"""
        if self.in_menu:
            self.menu.navigate_forward()
        else:
            # Next map region or other function
            logger.info("Right button pressed")

    def on_button_center(self):
        """Handle center button press"""
        if self.in_menu:
            result = self.menu.select()
            if result == 'exit_menu':
                self.in_menu = False
                logger.info("Exited menu mode")
            elif result == 'start_trip':
                # Handle trip start
                self.current_trip_id = self.menu.get_selected_trip_id()
                logger.info(f"Started trip: {self.current_trip_id}")
                self.in_menu = False
            elif result == 'stop_trip':
                # Handle trip stop
                logger.info(f"Stopped trip: {self.current_trip_id}")
                self.current_trip_id = None
                self.in_menu = False
        else:
            # Enter menu mode
            self.in_menu = True
            logger.info("Entered menu mode")

    def stop(self):
        """Stop the navigation system"""
        logger.info("Stopping GPS Navigation System")
        self.running = False

        # Stop components
        self.gps.stop()
        self.gy511.stop()
        self.mbtiles_manager.close_all()

        # Close database
        self.db.close()

        logger.info("GPS Navigation System stopped")


def main():
    """Main entry point"""
    try:
        # Create and start the navigation system
        nav_system = GPSNavigationSystem()
        nav_system.start()

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
    finally:
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    main()
