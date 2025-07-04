#!/usr/bin/env python3
"""
MBTiles Manager for Multi-Regional Maps
=======================================
Manages multiple MBTiles files for different geographic regions.
"""

import os
import logging
import time
from pathlib import Path
from mbtiles_to_png import MBTiles

logger = logging.getLogger(__name__)


class MBTilesManager:
    """Manager for multiple regional MBTiles files"""

    def __init__(self, assets_folder, max_open_files=3, cache_timeout=300):
        self.assets_folder = Path(assets_folder)
        self.max_open_files = max_open_files
        self.cache_timeout = cache_timeout

        # File management
        self.available_files = {}  # filename -> file_info
        self.open_files = {}  # filename -> (reader, last_used_time)
        self.current_file = None  # Currently active filename
        self.current_reader = None  # Currently active reader

        # Initialize
        self._scan_assets_folder()
        self._load_file_metadata()

        logger.info(f"MBTilesManager initialized with {len(self.available_files)} files")

    def _scan_assets_folder(self):
        """Scan assets folder for MBTiles files"""
        if not self.assets_folder.exists():
            logger.warning(f"Assets folder does not exist: {self.assets_folder}")
            return

        for mbtiles_file in self.assets_folder.glob("*.mbtiles"):
            filename = mbtiles_file.name
            self.available_files[filename] = {
                'path': str(mbtiles_file),
                'size': mbtiles_file.stat().st_size,
                'modified': mbtiles_file.stat().st_mtime
            }
            logger.info(f"Found MBTiles file: {filename}")

    def _load_file_metadata(self):
        """Load metadata for all available files"""
        for filename in list(self.available_files.keys()):
            try:
                file_info = self.available_files[filename]
                reader = self._open_file(filename)

                if reader:
                    metadata = reader.get_metadata()
                    bounds_str = metadata.get('bounds')

                    if bounds_str:
                        bounds = self._parse_bounds(bounds_str)
                        file_info['bounds'] = bounds
                        file_info['metadata'] = metadata
                        file_info['name'] = metadata.get('name', filename.replace('.mbtiles', ''))

                        logger.info(f"Loaded metadata for {filename}: {file_info['name']}")
                        logger.debug(f"  Bounds: {bounds}")
                    else:
                        logger.warning(f"No bounds found in {filename}")

                    # Close immediately after loading metadata
                    reader.close()
                    if filename in self.open_files:
                        del self.open_files[filename]

            except Exception as e:
                logger.error(f"Error loading metadata for {filename}: {e}")
                # Remove problematic file from available files
                del self.available_files[filename]

    def _parse_bounds(self, bounds_str):
        """Parse bounds string from metadata"""
        try:
            # Bounds format: "min_lon,min_lat,max_lon,max_lat"
            parts = bounds_str.split(',')
            if len(parts) == 4:
                return {
                    'min_lon': float(parts[0]),
                    'min_lat': float(parts[1]),
                    'max_lon': float(parts[2]),
                    'max_lat': float(parts[3])
                }
        except Exception as e:
            logger.error(f"Error parsing bounds '{bounds_str}': {e}")
        return None

    def _coordinates_in_bounds(self, lat, lon, bounds):
        """Check if coordinates are within bounds"""
        if not bounds:
            return False

        return (bounds['min_lat'] <= lat <= bounds['max_lat'] and
                bounds['min_lon'] <= lon <= bounds['max_lon'])

    def _open_file(self, filename):
        """Open an MBTiles file"""
        try:
            file_info = self.available_files.get(filename)
            if not file_info:
                return None

            reader = MBTiles(file_info['path'])
            return reader

        except Exception as e:
            logger.error(f"Error opening {filename}: {e}")
            return None

    def _get_cached_reader(self, filename):
        """Get reader from cache or open new one"""
        current_time = time.time()

        # Check if file is already open
        if filename in self.open_files:
            reader, last_used = self.open_files[filename]

            # Check if cache is still valid
            if current_time - last_used < self.cache_timeout:
                # Update last used time
                self.open_files[filename] = (reader, current_time)
                return reader
            else:
                # Cache expired, close and remove
                try:
                    reader.close()
                except:
                    pass
                del self.open_files[filename]

        # Open new reader
        reader = self._open_file(filename)
        if reader:
            # Manage cache size
            if len(self.open_files) >= self.max_open_files:
                self._close_oldest_file()

            # Add to cache
            self.open_files[filename] = (reader, current_time)

        return reader

    def _close_oldest_file(self):
        """Close the least recently used file"""
        if not self.open_files:
            return

        oldest_file = None
        oldest_time = time.time()

        for filename, (reader, last_used) in self.open_files.items():
            if last_used < oldest_time:
                oldest_time = last_used
                oldest_file = filename

        if oldest_file:
            try:
                reader, _ = self.open_files[oldest_file]
                reader.close()
                del self.open_files[oldest_file]
                logger.debug(f"Closed oldest file: {oldest_file}")
            except Exception as e:
                logger.error(f"Error closing {oldest_file}: {e}")

    def get_reader_for_coordinates(self, lat, lon):
        """Get the appropriate MBTiles reader for given coordinates"""
        logger.debug(f"Looking for map covering {lat:.4f}, {lon:.4f}")

        # Check if current reader still covers the coordinates
        if (self.current_reader and self.current_file and
                self.current_file in self.available_files):

            file_info = self.available_files[self.current_file]
            bounds = file_info.get('bounds')

            if bounds and self._coordinates_in_bounds(lat, lon, bounds):
                logger.debug(f"Current file {self.current_file} still covers coordinates")
                return self.current_reader

        # Search for appropriate file
        best_file = None
        for filename, file_info in self.available_files.items():
            bounds = file_info.get('bounds')
            if bounds and self._coordinates_in_bounds(lat, lon, bounds):
                best_file = filename
                logger.info(f"Found matching map: {filename} for {lat:.4f}, {lon:.4f}")
                break

        if not best_file:
            logger.warning(f"No map file found for coordinates {lat:.4f}, {lon:.4f}")
            self._log_available_regions()
            return None

        # Get reader for the best file
        reader = self._get_cached_reader(best_file)
        if reader:
            self.current_reader = reader
            self.current_file = best_file
            return reader

        return None

    def _log_available_regions(self):
        """Log available regions for debugging"""
        logger.info("Available map regions:")
        for filename, file_info in self.available_files.items():
            bounds = file_info.get('bounds')
            name = file_info.get('name', filename)
            if bounds:
                logger.info(f"  {name}: [{bounds['min_lat']:.2f},{bounds['min_lon']:.2f}] "
                            f"to [{bounds['max_lat']:.2f},{bounds['max_lon']:.2f}]")
            else:
                logger.info(f"  {name}: No bounds available")

    def get_available_files(self):
        """Get dictionary of available files with metadata"""
        return self.available_files.copy()

    def get_current_file_info(self):
        """Get information about the currently selected file"""
        if self.current_file and self.current_file in self.available_files:
            info = self.available_files[self.current_file].copy()
            info['filename'] = self.current_file
            return info
        return None

    def list_available_regions(self):
        """List all available regions"""
        logger.info("=== Available Map Regions ===")
        for filename, file_info in self.available_files.items():
            name = file_info.get('name', filename.replace('.mbtiles', ''))
            bounds = file_info.get('bounds')
            size_mb = file_info.get('size', 0) / (1024 * 1024)

            logger.info(f"Region: {name}")
            logger.info(f"  File: {filename} ({size_mb:.1f} MB)")

            if bounds:
                logger.info(f"  Coverage: {bounds['min_lat']:.4f},{bounds['min_lon']:.4f} "
                            f"to {bounds['max_lat']:.4f},{bounds['max_lon']:.4f}")
            else:
                logger.info("  Coverage: Unknown (no bounds)")

            logger.info("")

    def close_all(self):
        """Close all open files"""
        for filename, (reader, _) in list(self.open_files.items()):
            try:
                reader.close()
                logger.debug(f"Closed {filename}")
            except Exception as e:
                logger.error(f"Error closing {filename}: {e}")

        self.open_files.clear()
        self.current_reader = None
        self.current_file = None

        logger.info("All MBTiles files closed")


def main():
    """Test the MBTiles manager"""
    import sys

    if len(sys.argv) < 4:
        print("Usage: python mbtiles_manager.py <assets_folder> <lat> <lon>")
        sys.exit(1)

    assets_folder = sys.argv[1]
    lat = float(sys.argv[2])
    lon = float(sys.argv[3])

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Create manager
        manager = MBTilesManager(assets_folder)

        # List available regions
        manager.list_available_regions()

        # Find reader for coordinates
        reader = manager.get_reader_for_coordinates(lat, lon)

        if reader:
            print(f"\nFound reader for {lat}, {lon}")
            current_info = manager.get_current_file_info()
            print(f"Using: {current_info['name']} ({current_info['filename']})")

            # Test image generation
            image_data, metadata = reader.generate_composite_image(lat, lon, 14, 800, 480)
            print(f"Generated test image: {len(image_data)} bytes")
            print(f"Metadata: {metadata}")
        else:
            print(f"No reader found for {lat}, {lon}")

        # Cleanup
        manager.close_all()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
