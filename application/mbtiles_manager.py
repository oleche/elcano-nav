#!/usr/bin/env python3
"""
MBTiles Manager for GPS Navigation System
========================================
Enhanced manager for handling multiple regional MBTiles files with smart selection,
fallback mechanisms, and comprehensive tile management.
"""

import sqlite3
import math
import logging
import os
from pathlib import Path
from PIL import Image
from io import BytesIO
import json

logger = logging.getLogger(__name__)

class MBTilesReader:
    """Enhanced MBTiles file reader with smart tile handling"""
    
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = Path(filepath).name
        self.conn = None
        self.metadata = {}
        self.bounds = None
        self.min_zoom = 0
        self.max_zoom = 18
        self.center_lat = 0
        self.center_lon = 0
        self.name = self.filename
        
        # Open and read metadata
        self._open_database()
        self._read_metadata()
    
    def _open_database(self):
        """Open SQLite database connection"""
        try:
            self.conn = sqlite3.connect(self.filepath)
            self.conn.row_factory = sqlite3.Row
            logger.debug(f"Opened MBTiles file: {self.filename}")
        except Exception as e:
            logger.error(f"Failed to open MBTiles file {self.filepath}: {e}")
            raise
    
    def _read_metadata(self):
        """Read metadata from MBTiles file"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, value FROM metadata")
            
            for row in cursor.fetchall():
                self.metadata[row['name']] = row['value']
            
            # Parse important metadata
            if 'bounds' in self.metadata:
                bounds_str = self.metadata['bounds']
                bounds = [float(x) for x in bounds_str.split(',')]
                self.bounds = {
                    'west': bounds[0],
                    'south': bounds[1], 
                    'east': bounds[2],
                    'north': bounds[3]
                }
                
                # Calculate center
                self.center_lat = (bounds[1] + bounds[3]) / 2
                self.center_lon = (bounds[0] + bounds[2]) / 2
            
            if 'minzoom' in self.metadata:
                self.min_zoom = int(self.metadata['minzoom'])
            
            if 'maxzoom' in self.metadata:
                self.max_zoom = int(self.metadata['maxzoom'])
            
            if 'name' in self.metadata:
                self.name = self.metadata['name']
            
            logger.debug(f"MBTiles metadata loaded for {self.filename}: "
                        f"bounds={self.bounds}, zoom={self.min_zoom}-{self.max_zoom}")
            
        except Exception as e:
            logger.warning(f"Could not read metadata from {self.filename}: {e}")
    
    def contains_coordinates(self, lat, lon):
        """Check if coordinates are within this MBTiles bounds"""
        if not self.bounds:
            return False
        
        return (self.bounds['south'] <= lat <= self.bounds['north'] and
                self.bounds['west'] <= lon <= self.bounds['east'])
    
    def get_distance_to_center(self, lat, lon):
        """Calculate distance from coordinates to center of this MBTiles region"""
        # Simple distance calculation
        lat_diff = lat - self.center_lat
        lon_diff = lon - self.center_lon
        return math.sqrt(lat_diff**2 + lon_diff**2)
    
    def deg2num(self, lat_deg, lon_deg, zoom):
        """Convert lat/lon to tile numbers"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = int((lon_deg + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x, y)
    
    def num2deg(self, x, y, zoom):
        """Convert tile numbers to lat/lon"""
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)
    
    def get_tile(self, z, x, y):
        """Get tile data from MBTiles file"""
        try:
            cursor = self.conn.cursor()
            # MBTiles uses TMS scheme, need to flip Y coordinate
            tms_y = (2**z - 1) - y
            cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?", 
                          (z, x, tms_y))
            row = cursor.fetchone()
            
            if row:
                return row['tile_data']
            else:
                return None
                
        except Exception as e:
            logger.debug(f"Error getting tile {z}/{x}/{y}: {e}")
            return None
    
    def get_available_zoom_levels(self):
        """Get list of available zoom levels"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT zoom_level FROM tiles ORDER BY zoom_level")
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting zoom levels: {e}")
            return list(range(self.min_zoom, self.max_zoom + 1))
    
    def find_best_zoom(self, target_zoom):
        """Find the best available zoom level for target zoom"""
        available_zooms = self.get_available_zoom_levels()
        
        if target_zoom in available_zooms:
            return target_zoom
        
        # Find closest zoom level
        closest_zoom = min(available_zooms, key=lambda x: abs(x - target_zoom))
        return closest_zoom
    
    def generate_composite_image(self, center_lat, center_lon, zoom, width, height, 
                               use_fallback=True, crop_to_size=True):
        """Generate composite image from tiles with enhanced fallback handling"""
        try:
            # Find best available zoom
            actual_zoom = self.find_best_zoom(zoom)
            zoom_adjusted = actual_zoom != zoom
            
            # Calculate tile coverage needed
            center_x, center_y = self.deg2num(center_lat, center_lon, actual_zoom)
            
            # Calculate how many tiles we need
            tile_size = 256
            tiles_x = math.ceil(width / tile_size) + 1
            tiles_y = math.ceil(height / tile_size) + 1
            
            # Ensure odd number of tiles for centering
            if tiles_x % 2 == 0:
                tiles_x += 1
            if tiles_y % 2 == 0:
                tiles_y += 1
            
            # Calculate tile range
            half_tiles_x = tiles_x // 2
            half_tiles_y = tiles_y // 2
            
            start_x = center_x - half_tiles_x
            end_x = center_x + half_tiles_x + 1
            start_y = center_y - half_tiles_y
            end_y = center_y + half_tiles_y + 1
            
            # Create composite image
            composite_width = tiles_x * tile_size
            composite_height = tiles_y * tile_size
            composite = Image.new('RGB', (composite_width, composite_height), (240, 240, 240))
            
            tiles_found = 0
            tiles_missing = 0
            
            # Load and place tiles
            for ty in range(start_y, end_y):
                for tx in range(start_x, end_x):
                    tile_data = self.get_tile(actual_zoom, tx, ty)
                    
                    if tile_data:
                        try:
                            tile_image = Image.open(BytesIO(tile_data))
                            
                            # Calculate position in composite
                            pos_x = (tx - start_x) * tile_size
                            pos_y = (ty - start_y) * tile_size
                            
                            composite.paste(tile_image, (pos_x, pos_y))
                            tiles_found += 1
                            
                        except Exception as e:
                            logger.debug(f"Error loading tile image {actual_zoom}/{tx}/{ty}: {e}")
                            self._draw_placeholder_tile(composite, (tx - start_x) * tile_size, 
                                                      (ty - start_y) * tile_size, tile_size)
                            tiles_missing += 1
                    else:
                        # Create placeholder tile
                        if use_fallback:
                            self._draw_placeholder_tile(composite, (tx - start_x) * tile_size, 
                                                      (ty - start_y) * tile_size, tile_size)
                        tiles_missing += 1
            
            # Crop to requested size if needed
            if crop_to_size and (composite.width != width or composite.height != height):
                # Calculate crop area to center the image
                left = (composite.width - width) // 2
                top = (composite.height - height) // 2
                right = left + width
                bottom = top + height
                
                composite = composite.crop((left, top, right, bottom))
            
            # Convert to bytes
            output = BytesIO()
            composite.save(output, format='PNG')
            image_data = output.getvalue()
            
            # Prepare metadata
            metadata = {
                'zoom_requested': zoom,
                'actual_zoom': actual_zoom,
                'zoom_adjusted': zoom_adjusted,
                'tiles_found': tiles_found,
                'tiles_missing': tiles_missing,
                'total_tiles': tiles_found + tiles_missing,
                'availability_ratio': tiles_found / (tiles_found + tiles_missing) if (tiles_found + tiles_missing) > 0 else 0,
                'center_lat': center_lat,
                'center_lon': center_lon,
                'image_width': width,
                'image_height': height
            }
            
            return image_data, metadata
            
        except Exception as e:
            logger.error(f"Error generating composite image: {e}")
            # Return error image
            error_image = Image.new('RGB', (width, height), (200, 200, 200))
            output = BytesIO()
            error_image.save(output, format='PNG')
            return output.getvalue(), {'error': str(e)}
    
    def _draw_placeholder_tile(self, image, x, y, size):
        """Draw a placeholder tile on the composite image"""
        from PIL import ImageDraw
        
        # Create a light gray tile with border
        draw = ImageDraw.Draw(image)
        
        # Fill with light gray
        draw.rectangle([x, y, x + size - 1, y + size - 1], fill=(220, 220, 220))
        
        # Draw border
        draw.rectangle([x, y, x + size - 1, y + size - 1], outline=(180, 180, 180), width=1)
        
        # Draw diagonal lines
        draw.line([x, y, x + size - 1, y + size - 1], fill=(180, 180, 180), width=1)
        draw.line([x + size - 1, y, x, y + size - 1], fill=(180, 180, 180), width=1)
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None

class MBTilesManager:
    """Enhanced manager for multiple MBTiles files with smart selection"""
    
    def __init__(self, assets_folder):
        self.assets_folder = Path(assets_folder)
        self.readers = {}
        self.current_reader = None
        self.file_list = []
        self.current_file_index = 0
        
        # Ensure assets folder exists
        self.assets_folder.mkdir(parents=True, exist_ok=True)
        
        # Load all MBTiles files
        self._load_mbtiles_files()
        
        logger.info(f"MBTilesManager initialized with {len(self.readers)} files")
    
    def _load_mbtiles_files(self):
        """Load all MBTiles files from assets folder"""
        mbtiles_files = list(self.assets_folder.glob("*.mbtiles"))
        
        if not mbtiles_files:
            logger.warning(f"No MBTiles files found in {self.assets_folder}")
            return
        
        for filepath in mbtiles_files:
            try:
                reader = MBTilesReader(str(filepath))
                self.readers[filepath.name] = reader
                self.file_list.append(filepath.name)
                logger.info(f"Loaded MBTiles file: {filepath.name} ({reader.name})")
                
            except Exception as e:
                logger.error(f"Failed to load MBTiles file {filepath}: {e}")
        
        # Set first file as current if available
        if self.file_list:
            self.current_reader = self.readers[self.file_list[0]]
            logger.info(f"Set current MBTiles file: {self.file_list[0]}")
    
    def get_reader_for_coordinates(self, lat, lon):
        """Get the best MBTiles reader for given coordinates"""
        if not self.readers:
            return None
        
        # First, try to find a reader that contains the coordinates
        containing_readers = []
        for filename, reader in self.readers.items():
            if reader.contains_coordinates(lat, lon):
                containing_readers.append((filename, reader))
        
        if containing_readers:
            # If multiple readers contain the coordinates, pick the first one
            # In the future, we could add logic to pick the best one based on zoom levels, etc.
            selected_filename, selected_reader = containing_readers[0]
            
            # Update current reader if it's different
            if self.current_reader != selected_reader:
                self.current_reader = selected_reader
                self.current_file_index = self.file_list.index(selected_filename)
                logger.info(f"Auto-switched to MBTiles file: {selected_filename} for coordinates {lat:.4f}, {lon:.4f}")
            
            return selected_reader
        
        # If no reader contains the coordinates, find the closest one
        closest_reader = None
        min_distance = float('inf')
        
        for filename, reader in self.readers.items():
            distance = reader.get_distance_to_center(lat, lon)
            if distance < min_distance:
                min_distance = distance
                closest_reader = reader
        
        if closest_reader and self.current_reader != closest_reader:
            # Find filename for the closest reader
            for filename, reader in self.readers.items():
                if reader == closest_reader:
                    self.current_reader = closest_reader
                    self.current_file_index = self.file_list.index(filename)
                    logger.info(f"Auto-switched to closest MBTiles file: {filename} for coordinates {lat:.4f}, {lon:.4f}")
                    break
        
        return closest_reader or self.current_reader
    
    def switch_to_next_file(self):
        """Switch to next MBTiles file"""
        if len(self.file_list) <= 1:
            return False
        
        self.current_file_index = (self.current_file_index + 1) % len(self.file_list)
        filename = self.file_list[self.current_file_index]
        self.current_reader = self.readers[filename]
        
        logger.info(f"Switched to MBTiles file: {filename}")
        return True
    
    def switch_to_previous_file(self):
        """Switch to previous MBTiles file"""
        if len(self.file_list) <= 1:
            return False
        
        self.current_file_index = (self.current_file_index - 1) % len(self.file_list)
        filename = self.file_list[self.current_file_index]
        self.current_reader = self.readers[filename]
        
        logger.info(f"Switched to MBTiles file: {filename}")
        return True
    
    def get_current_file_info(self):
        """Get information about current MBTiles file"""
        if not self.current_reader:
            return None
        
        filename = self.file_list[self.current_file_index] if self.file_list else "Unknown"
        
        return {
            'filename': filename,
            'name': self.current_reader.name,
            'bounds': self.current_reader.bounds,
            'min_zoom': self.current_reader.min_zoom,
            'max_zoom': self.current_reader.max_zoom,
            'center_lat': self.current_reader.center_lat,
            'center_lon': self.current_reader.center_lon,
            'metadata': self.current_reader.metadata
        }
    
    def get_available_files(self):
        """Get list of available MBTiles files with their info"""
        files_info = {}
        for filename, reader in self.readers.items():
            files_info[filename] = {
                'name': reader.name,
                'bounds': reader.bounds,
                'min_zoom': reader.min_zoom,
                'max_zoom': reader.max_zoom,
                'center_lat': reader.center_lat,
                'center_lon': reader.center_lon
            }
        return files_info
    
    def cleanup(self):
        """Close all database connections"""
        for reader in self.readers.values():
            reader.close()
        self.readers.clear()
        self.file_list.clear()
        self.current_reader = None
        logger.info("MBTilesManager cleanup completed")

def main():
    """Test the MBTiles manager"""
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python mbtiles_manager.py <assets_folder>")
        return 1
    
    assets_folder = sys.argv[1]
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Create manager
        manager = MBTilesManager(assets_folder)
        
        if not manager.readers:
            print("No MBTiles files found")
            return 1
        
        # Test coordinates (Amsterdam)
        test_lat, test_lon = 52.3676, 4.9041
        
        print(f"Testing with coordinates: {test_lat}, {test_lon}")
        
        # Get reader for coordinates
        reader = manager.get_reader_for_coordinates(test_lat, test_lon)
        
        if reader:
            print(f"Selected reader: {reader.filename}")
            print(f"Reader name: {reader.name}")
            print(f"Bounds: {reader.bounds}")
            print(f"Zoom range: {reader.min_zoom}-{reader.max_zoom}")
            
            # Test image generation
            print("Generating test image...")
            image_data, metadata = reader.generate_composite_image(
                test_lat, test_lon, 14, 800, 480
            )
            
            print(f"Generated image: {len(image_data)} bytes")
            print(f"Metadata: {metadata}")
            
            # Save test image
            with open("test_output.png", "wb") as f:
                f.write(image_data)
            print("Test image saved as test_output.png")
            
        else:
            print("No suitable reader found for coordinates")
        
        # Cleanup
        manager.cleanup()
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
