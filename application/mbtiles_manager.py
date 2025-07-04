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
        self._load_all_metadata()

        logger.info(f"MBTilesManager initialized with {len(self.available_files)} files")

    def _scan_assets_folder(self):
        """Scan assets folder for MBTiles files"""
        if not self.assets_folder.exists():
            logger.warning(f"Assets folder does not exist: {self.assets_folder}")
            return

        for file_path in self.assets_folder.glob("*.mbtiles"):
            filename = file_path.name
            self.available_files[filename] = {
                'path': str(file_path),
                'size': file_path.stat().st_size,
                'modified': file_path.stat().st_mtime
            }

        logger.info(f"Found {len(self.available_files)} MBTiles files")
        for filename, info in self.available_files.items():
            size_mb = info['size'] / (1024 * 1024)
            logger.info(f"  {filename}: {size_mb:.1f} MB")

    def _load_all_metadata(self):
        """Load metadata for all available files"""
        for filename in list(self.available_files.keys()):
            try:
                self._load_file_metadata(filename)
            except Exception as e:
                logger.error(f"Error loading metadata for {filename}: {e}")
                # Remove problematic file from available files
                del self.available_files[filename]

    def _load_file_metadata(self, filename):
        """Load metadata for a specific file"""
        file_info = self.available_files[filename]
        file_path = file_info['path']

        try:
            # Temporarily open file to read metadata
            reader = MBTiles(file_path)
            metadata = reader.get_metadata()
            zoom_levels = reader.get_available_zoom_levels()
            reader.close()

            # Parse bounds
            bounds = self._parse_bounds(metadata.get('bounds'))

            # Update file info
            file_info.update({
                'metadata': metadata,
                'bounds': bounds,
                'name': metadata.get('name', filename),
                'description': metadata.get('description', ''),
                'zoom_levels': zoom_levels,
                'min_zoom': min(zoom_levels) if zoom_levels else 0,
                'max_zoom': max(zoom_levels) if zoom_levels else 18
            })

            logger.info(f"Loaded metadata for {filename}: {metadata.get('name', 'Unknown')}")
            if bounds:
                logger.info(f"  Bounds: [{bounds['min_lat']:.4f},{bounds['min_lon']:.4f}] "
                            f"to [{bounds['max_lat']:.4f},{bounds['max_lon']:.4f}]")
            logger.info(f"  Zoom levels: {min(zoom_levels)}-{max(zoom_levels)}")

        except Exception as e:
            logger.error(f"Failed to load metadata for {filename}: {e}")
            raise

    def _parse_bounds(self, bounds_string):
        """Parse bounds string to dictionary"""
        if not bounds_string:
            return None

        try:
            # Bounds format: "min_lon,min_lat,max_lon,max_lat"
            parts = bounds_string.split(',')
            if len(parts) != 4:
                logger.warning(f"Invalid bounds format: {bounds_string}")
                return None

            min_lon, min_lat, max_lon, max_lat = map(float, parts)
            return {
                'min_lat': min_lat,
                'min_lon': min_lon,
                'max_lat': max_lat,
                'max_lon': max_lon
            }
        except Exception as e:
            logger.warning(f"Could not parse bounds: {bounds_string} - {e}")
            return None

    def _coordinates_in_bounds(self, lat, lon, bounds):
        """Check if coordinates are within bounds"""
        if not bounds:
            return False

        return (bounds['min_lat'] <= lat <= bounds['max_lat'] and
                bounds['min_lon'] <= lon <= bounds['max_lon'])

    def _get_or_open_file(self, filename):
        """Get reader from cache or open new reader"""
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
        try:
            file_path = self.available_files[filename]['path']
            reader = MBTiles(file_path)

            # Add to cache, managing cache size
            self._add_to_cache(filename, reader, current_time)

            return reader

        except Exception as e:
            logger.error(f"Failed to open {filename}: {e}")
            return None

    def _add_to_cache(self, filename, reader, current_time):
        """Add reader to cache, managing cache size"""
        # Close oldest files if we're at the limit
        while len(self.open_files) >= self.max_open_files:
            self._close_oldest_file()

        # Add new reader to cache
        self.open_files[filename] = (reader, current_time)
        logger.debug(f"Added {filename} to cache ({len(self.open_files)}/{self.max_open_files})")

    def _close_oldest_file(self):
        """Close the least recently used file"""
        if not self.open_files:
            return

        # Find oldest file
        oldest_filename = None
        oldest_time = time.time()

        for filename, (reader, last_used) in self.open_files.items():
            if last_used < oldest_time:
                oldest_time = last_used
                oldest_filename = filename

        # Close and remove oldest file
        if oldest_filename:
            try:
                reader, _ = self.open_files[oldest_filename]
                reader.close()
                del self.open_files[oldest_filename]
                logger.debug(f"Closed oldest file: {oldest_filename}")
            except Exception as e:
                logger.error(f"Error closing {oldest_filename}: {e}")

    def get_reader_for_coordinates(self, lat, lon):
        """Get the appropriate MBTiles reader for given coordinates"""
        logger.debug(f"Finding map for coordinates: {lat:.4f}, {lon:.4f}")

        # Check if current file still contains coordinates
        if (self.current_file and self.current_reader and
                self._check_coordinates_in_current_file(lat, lon)):
            logger.debug(f"Coordinates still in current file: {self.current_file}")
            return self.current_reader

        # Search for file containing coordinates
        best_match = None
        best_coverage = 0

        for filename, file_info in self.available_files.items():
            bounds = file_info.get('bounds')
            if not bounds:
                continue

            if self._coordinates_in_bounds(lat, lon, bounds):
                # Calculate how well this file covers the area (for overlapping regions)
                coverage = self._calculate_coverage(lat, lon, bounds)

                if coverage > best_coverage:
                    best_match = filename
                    best_coverage = coverage

                logger.debug(f"File {filename} contains coordinates (coverage: {coverage:.2f})")

        if best_match:
            logger.info(f"Selected map file: {best_match} for coordinates {lat:.4f}, {lon:.4f}")
            reader = self._get_or_open_file(best_match)

            if reader:
                self.current_file = best_match
                self.current_reader = reader
                return reader
            else:
                logger.error(f"Failed to open selected file: {best_match}")

        # No suitable file found
        logger.warning(f"No MBTiles file found for coordinates {lat:.4f}, {lon:.4f}")
        self._log_available_regions()
        return None

    def _check_coordinates_in_current_file(self, lat, lon):
        """Check if coordinates are in the current file"""
        if not self.current_file:
            return False

        file_info = self.available_files.get(self.current_file)
        if not file_info:
            return False

        bounds = file_info.get('bounds')
        return self._coordinates_in_bounds(lat, lon, bounds)

    def _calculate_coverage(self, lat, lon, bounds):
        """Calculate how well a file covers the given coordinates"""
        # Simple coverage calculation - distance from bounds center
        center_lat = (bounds['min_lat'] + bounds['max_lat']) / 2
        center_lon = (bounds['min_lon'] + bounds['max_lon']) / 2

        # Calculate distance from center (simple Euclidean distance)
        distance = ((lat - center_lat) ** 2 + (lon - center_lon) ** 2) ** 0.5

        # Convert to coverage score (closer to center = higher score)
        max_distance = max(
            abs(bounds['max_lat'] - bounds['min_lat']),
            abs(bounds['max_lon'] - bounds['min_lon'])
        )

        if max_distance == 0:
            return 1.0

        coverage = max(0, 1.0 - (distance / max_distance))
        return coverage

    def _log_available_regions(self):
        """Log available regions for debugging"""
        logger.info("Available regions:")
        for filename, file_info in self.available_files.items():
            bounds = file_info.get('bounds')
            name = file_info.get('name', filename)

            if bounds:
                logger.info(f"  {name}: [{bounds['min_lat']:.4f},{bounds['min_lon']:.4f}] "
                            f"to [{bounds['max_lat']:.4f},{bounds['max_lon']:.4f}]")
            else:
                logger.info(f"  {name}: No bounds information")

    def get_available_files(self):
        """Get dictionary of available files and their info"""
        return self.available_files.copy()

    def get_current_file_info(self):
        """Get info about the currently selected file"""
        if self.current_file:
            return self.available_files.get(self.current_file)
        return None

    def list_available_regions(self):
        """List all available regions with their bounds"""
        logger.info("Available MBTiles regions:")

        if not self.available_files:
            logger.info("  No MBTiles files available")
            return

        for filename, file_info in self.available_files.items():
            name = file_info.get('name', filename)
            bounds = file_info.get('bounds')
            zoom_levels = file_info.get('zoom_levels', [])

            logger.info(f"  {name} ({filename}):")

            if bounds:
                logger.info(f"    Bounds: [{bounds['min_lat']:.4f},{bounds['min_lon']:.4f}] "
                            f"to [{bounds['max_lat']:.4f},{bounds['max_lon']:.4f}]")
            else:
                logger.info("    Bounds: Not available")

            if zoom_levels:
                logger.info(f"    Zoom levels: {min(zoom_levels)}-{max(zoom_levels)}")
            else:
                logger.info("    Zoom levels: Not available")

            size_mb = file_info.get('size', 0) / (1024 * 1024)
            logger.info(f"    Size: {size_mb:.1f} MB")

    def close_all(self):
        """Close all open files"""
        logger.info("Closing all MBTiles files")

        for filename, (reader, _) in list(self.open_files.items()):
            try:
                reader.close()
                logger.debug(f"Closed {filename}")
            except Exception as e:
                logger.error(f"Error closing {filename}: {e}")

        self.open_files.clear()
        self.current_file = None
        self.current_reader = None

        logger.info("All MBTiles files closed")

    def refresh_files(self):
        """Refresh the list of available files"""
        logger.info("Refreshing MBTiles file list")

        # Close all current files
        self.close_all()

        # Clear current data
        self.available_files.clear()

        # Rescan and reload
        self._scan_assets_folder()
        self._load_all_metadata()

        logger.info(f"Refreshed: {len(self.available_files)} files available")


def main():
    """Command line interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='MBTiles Manager for multi-regional maps')
    parser.add_argument('assets_folder', help='Path to assets folder containing MBTiles files')
    parser.add_argument('--list', action='store_true', help='List available regions')
    parser.add_argument('--test-coords', nargs=2, type=float, metavar=('LAT', 'LON'),
                        help='Test coordinate lookup')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    try:
        # Create manager
        manager = MBTilesManager(args.assets_folder)

        if args.list:
            manager.list_available_regions()

        if args.test_coords:
            lat, lon = args.test_coords
            print(f"\nTesting coordinates: {lat}, {lon}")

            reader = manager.get_reader_for_coordinates(lat, lon)
            if reader:
                current_info = manager.get_current_file_info()
                print(f"Selected file: {current_info['name']}")
                print(f"Zoom levels: {current_info['zoom_levels']}")
            else:
                print("No suitable file found for these coordinates")

        manager.close_all()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
