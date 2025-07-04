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
                        'longitude': response_data.get('lastLongitude'),
                        'heading': response_data.get('lastHeading'),
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
        """Enhance image contrast for e-paper display"""
        # Increase contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Apply threshold to make it more black and white
        import numpy as np
        img_array = np.array(image)
        img_array = np.where(img_array > 128, 255, 0)

        return Image.fromarray(img_array.astype('uint8'))

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

        # Draw compass rose
        self._draw_compass_rose(draw, heading)

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

        # Convert to pixels (assuming 256px tiles)
        pixel_offset_x = tile_offset_x * 256
        pixel_offset_y = tile_offset_y * 256

        # Screen coordinates
        screen_x = self.width // 2 + pixel_offset_x
        screen_y = self.height // 2 + pixel_offset_y

        return int(screen_x), int(screen_y)

    def _draw_status_bar(self, draw, wifi_status, gps_status, lat, lon):
        """Draw status bar at top of screen"""
        bar_height = 30

        # Background for status bar
        draw.rectangle([0, 0, self.width, bar_height], fill=255, outline=0, width=1)

        # WiFi status
        wifi_text = "WiFi On" if wifi_status and wifi_status.get('connected') else "WiFi Off"
        draw.text((10, 5), wifi_text, fill=0, font=self.font_small)

        # GPS status
        gps_text = "GPS Connected" if gps_status and gps_status.get('fix_quality', 0) > 0 else "GPS Disconnected"
        draw.text((100, 5), gps_text, fill=0, font=self.font_small)

        # Coordinates (if available)
        if gps_status and gps_status.get('fix_quality', 0) > 0:
            coord_text = f"{lat:.4f}, {lon:.4f}"
            draw.text((250, 5), coord_text, fill=0, font=self.font_small)

        # Date/Time
        datetime_text = datetime.now().strftime("%Y-%m-%d %H:%M")
        bbox = draw.textbbox((0, 0), datetime_text, font=self.font_small)
        text_width = bbox[2] - bbox[0]
        draw.text((self.width - text_width - 10, 5), datetime_text, fill=0, font=self.font_small)

    def _draw_crosshair(self, draw):
        """Draw center crosshair"""
        center_x = self.width // 2
        center_y = self.height // 2
        size = 20

        # Draw cross
        draw.line([center_x - size, center_y, center_x + size, center_y], fill=0, width=2)
        draw.line([center_x, center_y - size, center_x, center_y + size], fill=0, width=2)

        # Draw circle around center
        draw.ellipse([center_x - 5, center_y - 5, center_x + 5, center_y + 5], outline=0, width=2)

    def _draw_graticule(self, draw, lat, lon, zoom):
        """Draw coordinate grid"""
        # Calculate grid spacing based on zoom level
        if zoom >= 16:
            grid_spacing = 0.001  # ~100m
        elif zoom >= 14:
            grid_spacing = 0.005  # ~500m
        elif zoom >= 12:
            grid_spacing = 0.01  # ~1km
        else:
            grid_spacing = 0.05  # ~5km

        # Draw grid lines every few pixels
        grid_pixel_spacing = 100

        for x in range(0, self.width, grid_pixel_spacing):
            draw.line([x, 0, x, self.height], fill=128, width=1)

        for y in range(0, self.height, grid_pixel_spacing):
            draw.line([0, y, self.width, y], fill=128, width=1)

    def _draw_compass_rose(self, draw, heading):
        """Draw compass rose"""
        center_x = self.width - 80
        center_y = 80
        radius = 60

        # Draw outer circle
        draw.ellipse([center_x - radius, center_y - radius,
                      center_x + radius, center_y + radius], outline=0, width=2)

        # Draw cardinal directions
        directions = ['N', 'E', 'S', 'W']
        angles = [0, 90, 180, 270]

        for direction, angle in zip(directions, angles):
            # Calculate position
            rad = math.radians(angle - heading)
            x = center_x + (radius - 15) * math.sin(rad)
            y = center_y - (radius - 15) * math.cos(rad)

            # Draw direction letter
            bbox = draw.textbbox((0, 0), direction, font=self.font_medium)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((x - text_width // 2, y - text_height // 2), direction, fill=0, font=self.font_medium)

        # Draw north arrow
        north_rad = math.radians(-heading)
        arrow_x = center_x + (radius - 25) * math.sin(north_rad)
        arrow_y = center_y - (radius - 25) * math.cos(north_rad)

        # Draw arrow pointing north
        arrow_points = [
            (arrow_x, arrow_y - 10),
            (arrow_x - 5, arrow_y + 5),
            (arrow_x + 5, arrow_y + 5)
        ]
        draw.polygon(arrow_points, fill=0)

    def _draw_info_panel(self, draw, lat, lon, zoom, metadata):
        """Draw information panel with regional map info"""
        # Background for info panel (moved down for status bar)
        panel_height = 100
        panel_top = 30  # Below status bar
        draw.rectangle([0, panel_top, self.width, panel_top + panel_height], fill=255, outline=0, width=2)

        # GPS coordinates
        coord_text = f"GPS: {lat:.6f}, {lon:.6f}"
        draw.text((10, panel_top + 10), coord_text, fill=0, font=self.font_small)

        # Zoom level
        zoom_text = f"Zoom: {zoom}"
        draw.text((10, panel_top + 30), zoom_text, fill=0, font=self.font_small)

        # Current map file info
        if metadata.get('current_file'):
            file_text = f"Map: {metadata.get('current_file', 'Unknown')}"
            draw.text((10, panel_top + 50), file_text, fill=0, font=self.font_small)

            region_text = f"Region: {metadata.get('region_name', 'Unknown')}"
            draw.text((10, panel_top + 70), region_text, fill=0, font=self.font_small)

        # Tile info
        if metadata and not metadata.get('error'):
            tile_text = f"Tiles: {metadata.get('tiles_found', 0)}/{metadata.get('tiles_found', 0) + metadata.get('tiles_missing', 0)}"
            draw.text((self.width - 150, panel_top + 10), tile_text, fill=0, font=self.font_small)

        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        draw.text((self.width - 100, panel_top + 30), timestamp, fill=0, font=self.font_small)

    def close(self):
        """Close MBTiles manager"""
        if self.mbtiles_manager:
            self.mbtiles_manager.close_all()


class NavigationSystem:
    """Main navigation system controller with multi-regional MBTiles support"""

    def __init__(self, assets_folder=None, config_file='navigation_config.json'):
        self.config_file = config_file
        self.config = self._load_config()

        # Determine assets folder
        if assets_folder:
            self.assets_folder = assets_folder
        else:
            self.assets_folder = self.config.get('assets_folder', '/opt/elcano/assets/')

        # Initialize components
        self.gps = GPSModule()
        self.gy511 = GY511()  # Changed from MPU6050 to GY511
        self.display = EPaperDisplay()

        # Initialize MBTiles manager with multi-regional support
        mbtiles_settings = self.config.get('mbtiles_settings', {})
        self.mbtiles_manager = MBTilesManager(
            self.assets_folder,
            max_open_files=mbtiles_settings.get('max_open_files', 3),
            cache_timeout=mbtiles_settings.get('cache_timeout', 300)
        )

        self.map_renderer = MapRenderer(self.mbtiles_manager)
        self.wifi_manager = WiFiManager()
        self.db = DatabaseManager()
        self.sync_manager = SyncManager(self.db)
        self.menu_system = MenuSystem(self.db)

        # Navigation state
        self.current_zoom = self.config.get('default_zoom', 14)
        self.min_zoom = self.config.get('min_zoom', 8)
        self.max_zoom = self.config.get('max_zoom', 18)
        self.update_interval = self.config.get('update_interval', 30)

        # Trip state
        self.active_trip = None
        self.selected_trip_map_points = None

        # Sync state
        self.last_sync_attempt = None
        self.sync_in_progress = False
        self.show_sync_setup = False

        # Initialize buttons
        self._setup_buttons()

        # Control flags
        self.running = False
        self.force_update = False

        # Check sync key status on startup
        self._check_sync_key_status()

    def _check_sync_key_status(self):
        """Check if sync key is valid and set display mode accordingly"""
        if not self.sync_manager.is_valid_sync_key():
            self.show_sync_setup = True
            logger.warning("Invalid or missing sync key - showing setup screen")
        else:
            self.show_sync_setup = False
            logger.info(f"Valid sync key configured: {self.sync_manager.sync_key[:3]}...")

    def _load_config(self):
        """Load configuration from file"""
        default_config = {
            'default_zoom': 14,
            'min_zoom': 8,
            'max_zoom': 18,
            'update_interval': 30,
            'button_pins': {
                'zoom_in': 16,
                'zoom_out': 20,
                'button3': 21,
                'button4': 26
            },
            'assets_folder': '/opt/elcano/assets/',
            'mbtiles_settings': {
                'max_open_files': 3,
                'cache_timeout': 300,
                'auto_switch': True
            }
        }

        try:
            if Path(self.config_file).exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    default_config.update(config)
        except Exception as e:
            logger.warning(f"Could not load config: {e}")

        return default_config

    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save config: {e}")

    def _setup_buttons(self):
        """Setup button handlers"""
        button_pins = self.config['button_pins']

        self.btn_zoom_in = Button(button_pins['zoom_in'], pull_up=True)
        self.btn_zoom_out = Button(button_pins['zoom_out'], pull_up=True)
        self.btn_3 = Button(button_pins['button3'], pull_up=True)
        self.btn_4 = Button(button_pins['button4'], pull_up=True)

        self.btn_zoom_in.when_pressed = self._button1_pressed
        self.btn_zoom_out.when_pressed = self._button2_pressed
        self.btn_3.when_pressed = self._button3_pressed
        self.btn_4.when_pressed = self._button4_pressed

    def _button1_pressed(self):
        """Handle button 1 - Zoom in or menu navigation"""
        if self.show_sync_setup:
            # Any button press in sync setup mode retries sync key detection
            self._check_sync_key_status()
            self.force_update = True
            return

        if self.menu_system.is_visible():
            self.menu_system.navigate_up()
            self.force_update = True
        else:
            # Zoom in
            if self.current_zoom < self.max_zoom:
                self.current_zoom += 1
                self.force_update = True
                logger.info(f"Zoomed in to level {self.current_zoom}")

    def _button2_pressed(self):
        """Handle button 2 - Zoom out or menu navigation"""
        if self.show_sync_setup:
            # Any button press in sync setup mode retries sync key detection
            self._check_sync_key_status()
            self.force_update = True
            return

        if self.menu_system.is_visible():
            self.menu_system.navigate_down()
            self.force_update = True
        else:
            # Zoom out
            if self.current_zoom > self.min_zoom:
                self.current_zoom -= 1
                self.force_update = True
                logger.info(f"Zoomed out to level {self.current_zoom}")

    def _button3_pressed(self):
        """Handle button 3 - Sync or menu selection"""
        if self.show_sync_setup:
            # Any button press in sync setup mode retries sync key detection
            self._check_sync_key_status()
            self.force_update = True
            return

        if self.menu_system.is_visible():
            action = self.menu_system.select_current()
            self._handle_menu_action(action)
        else:
            # Sync functionality
            if self.wifi_manager.check_wifi_status() and self.sync_manager.is_enabled():
                if not self.sync_in_progress:
                    logger.info("Button 3 pressed - Starting sync")
                    threading.Thread(target=self._perform_sync, daemon=True).start()
                else:
                    logger.info("Sync already in progress")
            else:
                logger.info("Button 3 pressed - WiFi not available or sync not configured")

    def _button4_pressed(self):
        """Handle button 4 - Menu toggle"""
        if self.show_sync_setup:
            # Any button press in sync setup mode retries sync key detection
            self._check_sync_key_status()
            self.force_update = True
            return

        if self.menu_system.is_visible():
            action = self.menu_system.go_back()
            self._handle_menu_action(action)
        else:
            self.menu_system.toggle_menu()
            self.force_update = True

    def _handle_menu_action(self, action):
        """Handle menu system actions"""
        if action == 'trip_selected':
            # Load map points for selected trip
            selected_trip = self.menu_system.get_selected_trip()
            if selected_trip:
                self.selected_trip_map_points = self.db.get_map_points_for_trip(selected_trip['id'])
                logger.info(f"Loaded {len(self.selected_trip_map_points)} map points for trip {selected_trip['title']}")
                self.force_update = True

        elif action == 'start_trip':
            selected_trip = self.menu_system.get_selected_trip()
            if selected_trip:
                self.db.set_active_trip(selected_trip['id'])
                self.db.update_trip_status(selected_trip['id'], 'IN_ROUTE')
                self.active_trip = selected_trip
                self.menu_system.hide_menu()
                logger.info(f"Started trip: {selected_trip['title']}")
                self.force_update = True

                # Sync trip status if WiFi available
                if self.wifi_manager.is_connected:
                    threading.Thread(target=self._sync_trip_status, args=(selected_trip['id'], 'IN_ROUTE'),
                                     daemon=True).start()

        elif action == 'stop_trip':
            selected_trip = self.menu_system.get_selected_trip()
            if selected_trip:
                self.db.update_trip_status(selected_trip['id'], 'COMPLETED')
                self.db.set_active_trip(None)  # Deactivate trip
                self.active_trip = None
                self.menu_system.hide_menu()
                logger.info(f"Stopped trip: {selected_trip['title']}")
                self.force_update = True

                # Sync trip status if WiFi available
                if self.wifi_manager.is_connected:
                    threading.Thread(target=self._sync_trip_status, args=(selected_trip['id'], 'COMPLETED'),
                                     daemon=True).start()

        elif action in ['back_to_map', 'back_to_list']:
            self.force_update = True

    def _sync_trip_status(self, trip_id, status):
        """Sync trip status to API"""
        try:
            success, message = self.sync_manager.update_trip_status(trip_id, status)
            if success:
                self.db.mark_trip_synced(trip_id)
                logger.info(f"Trip status synced: {message}")
            else:
                logger.warning(f"Trip status sync failed: {message}")
        except Exception as e:
            logger.error(f"Error syncing trip status: {e}")

    def initialize(self):
        """Initialize all components"""
        logger.info("Initializing navigation system...")

        # Initialize display
        if not self.display.initialize():
            logger.error("Failed to initialize display")
            return False

        # Initialize GPS
        if not self.gps.start_reading():
            logger.error("Failed to initialize GPS")
            return False

        # Initialize GY-511 (optional sensor)
        self.gy511_available = self.gy511.initialize()
        if not self.gy511_available:
            logger.info("GY-511 compass sensor not available - using GPS heading only")

        # Load active trip if exists
        self.active_trip = self.db.get_active_trip()
        if self.active_trip:
            logger.info(f"Loaded active trip: {self.active_trip['title']}")

        # Log MBTiles manager status
        available_files = self.mbtiles_manager.get_available_files()
        logger.info(f"MBTiles Manager initialized with {len(available_files)} regional files")

        logger.info("Navigation system initialized successfully")
        return True

    def run(self):
        """Main navigation loop"""
        if not self.initialize():
            return False

        self.running = True
        last_update = 0
        last_ping = 0

        logger.info("Starting navigation system...")

        try:
            while self.running:
                current_time = time.time()

                # Check WiFi status
                wifi_connected = self.wifi_manager.check_wifi_status()

                # Ping device every minute if WiFi connected and sync key is valid
                if (wifi_connected and self.sync_manager.should_ping() and
                        self.sync_manager.is_valid_sync_key()):
                    threading.Thread(target=self._ping_device, daemon=True).start()

                # Check if update is needed
                if (current_time - last_update >= self.update_interval or
                        self.force_update):
                    self._update_display()
                    last_update = current_time
                    self.force_update = False

                time.sleep(1)  # Check every second

        except KeyboardInterrupt:
            logger.info("Navigation system stopped by user")
        except Exception as e:
            logger.error(f"Navigation system error: {e}")
        finally:
            self.shutdown()

    def _ping_device(self):
        """Ping device in background with current GPS position"""
        try:
            # Get current GPS status for position data
            gps_status = self.gps.get_status()
            success, message = self.sync_manager.ping_device(gps_status)
            if success:
                logger.debug("Device ping successful with position data")
            else:
                logger.warning(f"Device ping failed: {message}")
        except Exception as e:
            logger.error(f"Error pinging device: {e}")

    def _perform_sync(self):
        """Perform synchronization with API"""
        self.sync_in_progress = True
        try:
            logger.info("Starting synchronization...")

            # Ping device with current position
            gps_status = self.gps.get_status()
            success, message = self.sync_manager.ping_device(gps_status)
            if success:
                logger.info("Device ping successful with position data")
            else:
                logger.warning(f"Device ping failed: {message}")

            # Full device sync (get trips and data)
            success, message = self.sync_manager.sync_device_data()
            if success:
                logger.info(f"Device sync: {message}")
                # Reload active trip in case it changed
                self.active_trip = self.db.get_active_trip()
            else:
                logger.warning(f"Device sync failed: {message}")

            # Sync pending data
            results = self.sync_manager.sync_pending_data()
            for result in results:
                logger.info(f"Sync result: {result}")

            self.last_sync_attempt = datetime.now()
            logger.info("Synchronization completed")

        except Exception as e:
            logger.error(f"Sync error: {e}")
        finally:
            self.sync_in_progress = False

    def _update_display(self):
        """Update the display with current information"""
        try:
            # Check if sync setup screen should be displayed
            if self.show_sync_setup:
                setup_image = self.map_renderer.render_sync_setup_screen()
                self.display.update(setup_image)
                logger.info("Displaying sync setup screen")
                return

            # Check if menu should be displayed
            if self.menu_system.is_visible():
                menu_image = self.menu_system.render_menu()
                if menu_image:
                    self.display.update(menu_image)
                    return

            # Get GPS status
            gps_status = self.gps.get_status()

            # Check WiFi status
            wifi_status = self.wifi_manager.get_status()

            # Handle GPS data for active trip
            if gps_status['fix_quality'] > 0 and self.active_trip:
                # Add logbook entry if there's significant change
                if self.gps.has_significant_change():
                    entry_id = self.db.add_logbook_entry(self.active_trip['id'], gps_status)
                    logger.debug(f"Added logbook entry {entry_id} for trip {self.active_trip['title']}")

                    # Sync immediately if WiFi available and sync key is valid
                    if (wifi_status['connected'] and self.sync_manager.is_enabled() and
                            self.sync_manager.is_valid_sync_key()):
                        threading.Thread(target=self._sync_single_logbook_entry, args=(entry_id,), daemon=True).start()

            if gps_status['fix_quality'] == 0:
                # No GPS fix - show waiting screen
                self._show_waiting_screen(gps_status, wifi_status)
                return

            # Get compass heading (only if GY-511 is available)
            if self.gy511_available:
                compass_heading = self.gy511.get_compass_heading()
            else:
                compass_heading = 0.0  # Default value when sensor not available

            # Use GPS heading if available, otherwise use compass (if available)
            heading = gps_status.get('heading', compass_heading if self.gy511_available else 0.0)

            # Render map with status information and trip map points
            # The map renderer will automatically select the appropriate regional file
            map_image, metadata = self.map_renderer.render_map(
                gps_status['latitude'],
                gps_status['longitude'],
                self.current_zoom,
                heading,
                wifi_status,
                gps_status,
                self.selected_trip_map_points
            )

            # Add GPS info overlay
            self._add_gps_overlay(map_image, gps_status, compass_heading, wifi_status, metadata)

            # Update display
            self.display.update(map_image)

            # Log with regional file info
            current_file_info = self.mbtiles_manager.get_current_file_info()
            current_file = current_file_info['filename'] if current_file_info else 'None'

            logger.info(f"Display updated - GPS: {gps_status['latitude']:.6f}, "
                        f"{gps_status['longitude']:.6f}, Zoom: {self.current_zoom}, "
                        f"WiFi: {'On' if wifi_status['connected'] else 'Off'}, "
                        f"Map: {current_file}, "
                        f"Active Trip: {self.active_trip['title'] if self.active_trip else 'None'}")

        except Exception as e:
            logger.error(f"Error updating display: {e}")

    def _sync_single_logbook_entry(self, entry_id):
        """Sync a single logbook entry immediately"""
        try:
            entries = self.db.get_unsynced_logbook_entries()
            entry_to_sync = [e for e in entries if e['id'] == entry_id]

            if entry_to_sync:
                success, message = self.sync_manager.sync_logbook_entries(entry_to_sync)
                if success:
                    self.db.mark_logbook_entries_synced([entry_id])
                    logger.debug(f"Synced logbook entry {entry_id}")
                else:
                    logger.warning(f"Failed to sync logbook entry {entry_id}: {message}")
        except Exception as e:
            logger.error(f"Error syncing single logbook entry: {e}")

    def _show_waiting_screen(self, gps_status, wifi_status):
        """Show waiting for GPS screen"""
        image = Image.new('L', (800, 480), 255)
        draw = ImageDraw.Draw(image)

        # Draw status bar
        self.map_renderer._draw_status_bar(draw, wifi_status, gps_status, 0, 0)

        # Title
        draw.text((400, 200), "Waiting for GPS Signal...",
                  fill=0, font=self.map_renderer.font_large, anchor="mm")

        # GPS info
        info_text = f"Satellites: {gps_status['satellites']}\n"
        info_text += f"Fix Quality: {gps_status['fix_quality']}\n"
        info_text += f"Last Update: {gps_status['last_update'] or 'Never'}\n"
        info_text += f"WiFi: {'Connected' if wifi_status['connected'] else 'Disconnected'}"

        if self.active_trip:
            info_text += f"\nActive Trip: {self.active_trip['title']}"

        # Show available regional files
        available_files = self.mbtiles_manager.get_available_files()
        if available_files:
            info_text += f"\nAvailable Maps: {len(available_files)} regions"

        # Show sync status
        if not self.sync_manager.is_valid_sync_key():
            info_text += f"\nSync: Configuration required"
        elif self.sync_manager.is_enabled():
            info_text += f"\nSync: Enabled"
        else:
            info_text += f"\nSync: Disabled"

        draw.text((400, 280), info_text, fill=0,
                  font=self.map_renderer.font_medium, anchor="mm")

        self.display.update(image)

    def _add_gps_overlay(self, image, gps_status, compass_heading, wifi_status, metadata):
        """Add GPS information overlay with regional map info"""
        draw = ImageDraw.Draw(image)

        # Speed and heading info
        speed_text = f"Speed: {gps_status['speed']:.1f} km/h"
        heading_text = f"Heading: {gps_status['heading']:.0f}°"
        compass_text = f"Compass: {compass_heading:.0f}°"

        # Draw on right side (moved down for status bar)
        x_pos = self.map_renderer.width - 200
        y_start = 150  # Moved down to accommodate status bar

        draw.text((x_pos, y_start), speed_text, fill=0, font=self.map_renderer.font_small)
        draw.text((x_pos, y_start + 20), heading_text, fill=0, font=self.map_renderer.font_small)
        draw.text((x_pos, y_start + 40), compass_text, fill=0, font=self.map_renderer.font_small)

        # Satellite info
        sat_text = f"Sats: {gps_status['satellites']}"
        draw.text((x_pos, y_start + 60), sat_text, fill=0, font=self.map_renderer.font_small)

        # Regional map info
        current_file_info = self.mbtiles_manager.get_current_file_info()
        if current_file_info:
            map_text = f"Map: {current_file_info['filename'][:15]}"
            region_text = f"Region: {current_file_info.get('name', 'Unknown')[:15]}"
            draw.text((x_pos, y_start + 80), map_text, fill=0, font=self.map_renderer.font_small)
            draw.text((x_pos, y_start + 100), region_text, fill=0, font=self.map_renderer.font_small)

        # Active trip info
        if self.active_trip:
            trip_text = f"Trip: {self.active_trip['title'][:15]}"
            status_text = f"Status: {self.active_trip.get('local_status', self.active_trip.get('status', 'UNKNOWN'))}"
            draw.text((x_pos, y_start + 120), trip_text, fill=0, font=self.map_renderer.font_small)
            draw.text((x_pos, y_start + 140), status_text, fill=0, font=self.map_renderer.font_small)

        # Sync status
        if not self.sync_manager.is_valid_sync_key():
            sync_text = "Sync: Setup required"
        elif self.sync_manager.is_enabled():
            if self.sync_in_progress:
                sync_text = "Syncing..."
            elif self.last_sync_attempt:
                sync_text = f"Last sync: {self.last_sync_attempt.strftime('%H:%M')}"
            else:
                sync_text = "Not synced"
        else:
            sync_text = "Sync disabled"

        draw.text((x_pos, y_start + 160), sync_text, fill=0, font=self.map_renderer.font_small)

        # Queue status
        unsynced_count = len(self.db.get_unsynced_logbook_entries())
        if unsynced_count > 0:
            queue_text = f"Queue: {unsynced_count}"
            draw.text((x_pos, y_start + 180), queue_text, fill=0, font=self.map_renderer.font_small)

    def shutdown(self):
        """Shutdown navigation system"""
        logger.info("Shutting down navigation system...")

        self.running = False

        # Save configuration
        self.config['default_zoom'] = self.current_zoom
        self._save_config()

        # Cleanup components
        if hasattr(self, 'gps'):
            self.gps.stop()

        if hasattr(self, 'map_renderer'):
            self.map_renderer.close()

        if hasattr(self, 'mbtiles_manager'):
            self.mbtiles_manager.close_all()

        if hasattr(self, 'display'):
            self.display.clear()

        if hasattr(self, 'db'):
            self.db.close()

        logger.info("Navigation system shutdown complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='GPS Navigation System with Multi-Regional Maps')
    parser.add_argument('assets_folder', nargs='?',
                        help='Path to assets folder containing MBTiles files (optional, uses config default)')
    parser.add_argument('--config', default='navigation_config.json',
                        help='Configuration file path')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level')

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create and run navigation system
    nav_system = NavigationSystem(args.assets_folder, args.config)
    nav_system.run()


if __name__ == "__main__":
    main()
