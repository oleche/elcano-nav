#!/usr/bin/env python3
"""
MBTiles Manager for Multi-Regional Map Support
==============================================
Manages multiple MBTiles files for different geographic regions,
automatically selecting the appropriate map based on coordinates.
"""

import os
import sqlite3
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import math
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)


class MBTilesReader:
    """Reader for individual MBTiles files"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.connection = None
        self.metadata = {}
        self.bounds = None
        self.min_zoom = 0
        self.max_zoom = 18

        # Open and read metadata
        self._open_connection()
        self._read_metadata()

    def _open_connection(self):
        """Open SQLite connection to MBTiles file"""
        try:
            self.connection = sqlite3.connect(self.filepath)
            self.connection.row_factory = sqlite3.Row
            logger.debug(f"Opened MBTiles file: {self.filename}")
        except Exception as e:
            logger.error(f"Failed to open MBTiles file {self.filepath}: {e}")
            raise

    def _read_metadata(self):
        """Read metadata from MBTiles file"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT name, value FROM metadata")

            for row in cursor.fetchall():
                self.metadata[row['name']] = row['value']

            # Parse bounds
            if 'bounds' in self.metadata:
                bounds_str = self.metadata['bounds']
                self.bounds = [float(x) for x in bounds_str.split(',')]
                logger.debug(f"Bounds for {self.filename}: {self.bounds}")

            # Parse zoom levels
            if 'minzoom' in self.metadata:
                self.min_zoom = int(self.metadata['minzoom'])
            if 'maxzoom' in self.metadata:
                self.max_zoom = int(self.metadata['maxzoom'])

            logger.info(f"Loaded MBTiles: {self.filename} (zoom {self.min_zoom}-{self.max_zoom})")

        except Exception as e:
            logger.error(f"Failed to read metadata from {self.filepath}: {e}")

    def contains_coordinates(self, lat: float, lon: float) -> bool:
        """Check if coordinates are within this MBTiles bounds"""
        if not self.bounds:
            return False

        min_lon, min_lat, max_lon, max_lat = self.bounds
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat

    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        """Get tile data for given coordinates"""
        try:
            cursor = self.connection.cursor()

            # MBTiles uses TMS scheme, convert from XYZ
            tms_y = (2 ** z) - 1 - y

            cursor.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                (z, x, tms_y)
            )

            row = cursor.fetchone()
            return row['tile_data'] if row else None

        except Exception as e:
            logger.debug(f"Error getting tile {z}/{x}/{y}: {e}")
            return None

    def deg2num(self, lat_deg: float, lon_deg: float, zoom: int) -> Tuple[float, float]:
        """Convert lat/lon to tile coordinates"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = (lon_deg + 180.0) / 360.0 * n
        y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        return x, y

    def num2deg(self, x: float, y: float, zoom: int) -> Tuple[float, float]:
        """Convert tile coordinates to lat/lon"""
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return lat_deg, lon_deg

    def generate_composite_image(self, lat: float, lon: float, zoom: int,
                                 width: int, height: int, use_fallback: bool = True,
                                 crop_to_size: bool = True) -> Tuple[bytes, dict]:
        """Generate composite image for given coordinates and size"""
        try:
            # Calculate tile coordinates
            center_x, center_y = self.deg2num(lat, lon, zoom)

            # Calculate how many tiles we need
            tiles_x = math.ceil(width / 256) + 1
            tiles_y = math.ceil(height / 256) + 1

            # Calculate starting tile coordinates
            start_x = int(center_x - tiles_x // 2)
            start_y = int(center_y - tiles_y // 2)

            # Create composite image
            composite_width = tiles_x * 256
            composite_height = tiles_y * 256
            composite = Image.new('RGB', (composite_width, composite_height), (240, 240, 240))

            tiles_found = 0
            tiles_missing = 0

            # Load tiles
            for ty in range(tiles_y):
                for tx in range(tiles_x):
                    tile_x = start_x + tx
                    tile_y = start_y + ty

                    # Get tile data
                    tile_data = self.get_tile(zoom, tile_x, tile_y)

                    if tile_data:
                        try:
                            tile_image = Image.open(BytesIO(tile_data))
                            composite.paste(tile_image, (tx * 256, ty * 256))
                            tiles_found += 1
                        except Exception as e:
                            logger.debug(f"Error loading tile image {zoom}/{tile_x}/{tile_y}: {e}")
                            tiles_missing += 1
                    else:
                        tiles_missing += 1

                        # Create placeholder tile if fallback is enabled
                        if use_fallback:
                            placeholder = self._create_placeholder_tile(zoom, tile_x, tile_y)
                            composite.paste(placeholder, (tx * 256, ty * 256))

            # Calculate crop area to center the requested coordinates
            pixel_x = (center_x - start_x) * 256
            pixel_y = (center_y - start_y) * 256

            crop_x = int(pixel_x - width // 2)
            crop_y = int(pixel_y - height // 2)

            if crop_to_size:
                # Crop to requested size
                crop_box = (crop_x, crop_y, crop_x + width, crop_y + height)
                composite = composite.crop(crop_box)

            # Convert to bytes
            output = BytesIO()
            composite.save(output, format='PNG')
            image_data = output.getvalue()

            # Metadata
            metadata = {
                'tiles_found': tiles_found,
                'tiles_missing': tiles_missing,
                'total_tiles': tiles_found + tiles_missing,
                'availability_ratio': tiles_found / (tiles_found + tiles_missing) if (
                                                                                                 tiles_found + tiles_missing) > 0 else 0,
                'zoom_level': zoom,
                'center_lat': lat,
                'center_lon': lon,
                'image_width': width,
                'image_height': height
            }

            return image_data, metadata

        except Exception as e:
            logger.error(f"Error generating composite image: {e}")
            raise

    def _create_placeholder_tile(self, zoom: int, x: int, y: int) -> Image.Image:
        """Create a placeholder tile for missing data"""
        tile = Image.new('RGB', (256, 256), (220, 220, 220))

        # Add some basic grid lines
        from PIL import ImageDraw
        draw = ImageDraw.Draw(tile)

        # Draw border
        draw.rectangle([0, 0, 255, 255], outline=(180, 180, 180), width=1)

        # Draw grid
        for i in range(0, 256, 64):
            draw.line([i, 0, i, 255], fill=(200, 200, 200), width=1)
            draw.line([0, i, 255, i], fill=(200, 200, 200), width=1)

        return tile

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None


class MBTilesManager:
    """Manager for multiple MBTiles files"""

    def __init__(self, assets_folder: str):
        self.assets_folder = Path(assets_folder)
        self.readers: Dict[str, MBTilesReader] = {}
        self.current_reader: Optional[MBTilesReader] = None
        self.available_files: Dict[str, dict] = {}

        # Ensure assets folder exists
        self.assets_folder.mkdir(parents=True, exist_ok=True)

        # Load all MBTiles files
        self._discover_mbtiles_files()

        logger.info(f"MBTiles Manager initialized with {len(self.readers)} files")

    def _discover_mbtiles_files(self):
        """Discover and load all MBTiles files in assets folder"""
        mbtiles_pattern = "*.mbtiles"

        for mbtiles_file in self.assets_folder.glob(mbtiles_pattern):
            try:
                reader = MBTilesReader(str(mbtiles_file))
                filename = mbtiles_file.name

                self.readers[filename] = reader

                # Store file info
                self.available_files[filename] = {
                    'name': reader.metadata.get('name', filename),
                    'description': reader.metadata.get('description', ''),
                    'bounds': reader.bounds,
                    'min_zoom': reader.min_zoom,
                    'max_zoom': reader.max_zoom,
                    'format': reader.metadata.get('format', 'png'),
                    'version': reader.metadata.get('version', '1.0.0')
                }

                logger.info(f"Loaded MBTiles file: {filename}")

            except Exception as e:
                logger.error(f"Failed to load MBTiles file {mbtiles_file}: {e}")

        # Set first available reader as current
        if self.readers and not self.current_reader:
            first_filename = next(iter(self.readers))
            self.current_reader = self.readers[first_filename]
            logger.info(f"Set current reader to: {first_filename}")

    def get_reader_for_coordinates(self, lat: float, lon: float) -> Optional[MBTilesReader]:
        """Get the best MBTiles reader for given coordinates"""
        # First, try to find a reader that contains the coordinates
        for filename, reader in self.readers.items():
            if reader.contains_coordinates(lat, lon):
                self.current_reader = reader
                logger.debug(f"Selected reader {filename} for coordinates {lat:.4f}, {lon:.4f}")
                return reader

        # If no reader contains the coordinates, return current reader or first available
        if self.current_reader:
            logger.debug(f"No specific reader for coordinates, using current: {self.current_reader.filename}")
            return self.current_reader

        if self.readers:
            first_reader = next(iter(self.readers.values()))
            self.current_reader = first_reader
            logger.debug(f"No current reader, using first available: {first_reader.filename}")
            return first_reader

        logger.warning("No MBTiles readers available")
        return None

    def switch_to_next_file(self):
        """Switch to next available MBTiles file"""
        if not self.readers:
            return

        filenames = list(self.readers.keys())
        if not self.current_reader:
            self.current_reader = self.readers[filenames[0]]
            return

        current_filename = self.current_reader.filename
        try:
            current_index = filenames.index(current_filename)
            next_index = (current_index + 1) % len(filenames)
            next_filename = filenames[next_index]
            self.current_reader = self.readers[next_filename]
            logger.info(f"Switched to next MBTiles file: {next_filename}")
        except ValueError:
            # Current file not in list, use first
            self.current_reader = self.readers[filenames[0]]

    def switch_to_previous_file(self):
        """Switch to previous available MBTiles file"""
        if not self.readers:
            return

        filenames = list(self.readers.keys())
        if not self.current_reader:
            self.current_reader = self.readers[filenames[-1]]
            return

        current_filename = self.current_reader.filename
        try:
            current_index = filenames.index(current_filename)
            prev_index = (current_index - 1) % len(filenames)
            prev_filename = filenames[prev_index]
            self.current_reader = self.readers[prev_filename]
            logger.info(f"Switched to previous MBTiles file: {prev_filename}")
        except ValueError:
            # Current file not in list, use last
            self.current_reader = self.readers[filenames[-1]]

    def get_available_files(self) -> Dict[str, dict]:
        """Get information about all available MBTiles files"""
        return self.available_files.copy()

    def get_current_file_info(self) -> Optional[dict]:
        """Get information about currently selected file"""
        if not self.current_reader:
            return None

        filename = self.current_reader.filename
        return self.available_files.get(filename)

    def close_all(self):
        """Close all MBTiles readers"""
        for reader in self.readers.values():
            reader.close()

        self.readers.clear()
        self.current_reader = None
        logger.info("All MBTiles readers closed")


def main():
    """Test the MBTiles manager"""
    import sys

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python mbtiles_manager.py <assets_folder>")
        return 1

    assets_folder = sys.argv[1]

    try:
        # Create manager
        manager = MBTilesManager(assets_folder)

        # Show available files
        available = manager.get_available_files()
        print(f"\nFound {len(available)} MBTiles files:")
        for filename, info in available.items():
            print(f"  {filename}: {info['name']}")
            if info['bounds']:
                print(f"    Bounds: {info['bounds']}")
            print(f"    Zoom: {info['min_zoom']}-{info['max_zoom']}")

        # Test coordinate lookup
        if available:
            test_coords = [
                (52.3676, 4.9041),  # Amsterdam
                (40.7128, -74.0060),  # New York
                (51.5074, -0.1278),  # London
            ]

            print(f"\nTesting coordinate lookup:")
            for lat, lon in test_coords:
                reader = manager.get_reader_for_coordinates(lat, lon)
                if reader:
                    print(f"  {lat:.4f}, {lon:.4f} -> {reader.filename}")
                else:
                    print(f"  {lat:.4f}, {lon:.4f} -> No suitable file")

        # Cleanup
        manager.close_all()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
