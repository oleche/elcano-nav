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
from mbtiles_to_png import MBTilesReader

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

    def _scan_assets_folder(self):
        """Scan assets folder for MBTiles files"""
        if not self.assets_folder.exists():
            logger.error(f"Assets folder does not exist: {self.assets_folder}")
            return

        logger.info(f"Scanning assets folder: {self.assets_folder}")

        mbtiles_files = list(self.assets_folder.glob("*.mbtiles"))

        if not mbtiles_files:
            logger.warning(f"No MBTiles files found in {self.assets_folder}")
            return

        for file_path in mbtiles_files:
            try:
                # Get file info without keeping it open
                temp_reader = MBTilesReader(str(file_path))
                file_info = temp_reader.get_file_info()
                file_info['path'] = str(file_path)
                file_info['filename'] = file_path.name
                temp_reader.close()

                self.available_files[file_path.name] = file_info
                logger.info(f"Found MBTiles file: {file_path.name} - {file_info.get('name', 'Unknown')}")

            except Exception as e:
                logger.error(f"Error reading MBTiles file {file_path}: {e}")

        logger.info(f"Loaded {len(self.available_files)} MBTiles files")

    def get_reader_for_coordinates(self, lat, lon):
        """Get the appropriate MBTiles reader for given coordinates"""
        logger.debug(f"Looking for map covering coordinates: {lat:.4f}, {lon:.4f}")

        # First check if current file still contains coordinates
        if self.current_file and self.current_reader:
            if self._check_coordinates_in_file(self.current_file, lat, lon):
                # Update last used time
                if self.current_file in self.open_files:
                    self.open_files[self.current_file] = (self.current_reader, time.time())
                logger.debug(f"Coordinates still in current file: {self.current_file}")
                return self.current_reader

        # Search for file containing coordinates
        for filename, file_info in self.available_files.items():
            bounds = file_info.get('bounds')
            if bounds:
                logger.debug(f"Checking {filename}: bounds {bounds}")
                if self._coordinates_in_bounds(lat, lon, bounds):
                    logger.info(f"Found matching map: {filename} for coordinates {lat:.4f}, {lon:.4f}")
                    reader = self._get_or_open_file(filename)
                    if reader:
                        self.current_file = filename
                        self.current_reader = reader
                        return reader
            else:
                logger.warning(f"No bounds found for {filename}")

        # No file found containing coordinates
        logger.warning(f"No MBTiles file found for coordinates {lat:.4f}, {lon:.4f}")
        logger.info(f"Available files: {list(self.available_files.keys())}")
        return None

    def _check_coordinates_in_file(self, filename, lat, lon):
        """Check if coordinates are in the specified file"""
        file_info = self.available_files.get(filename)
        if not file_info:
            return False
        return self._coordinates_in_bounds(lat, lon, file_info.get('bounds'))

    def _coordinates_in_bounds(self, lat, lon, bounds):
        """Check if coordinates are within bounds with better logging"""
        if not bounds:
            return False

        in_bounds = (bounds['min_lat'] <= lat <= bounds['max_lat'] and
                     bounds['min_lon'] <= lon <= bounds['max_lon'])

        logger.debug(f"Coordinate check: {lat:.4f},{lon:.4f} in bounds "
                     f"[{bounds['min_lat']:.4f},{bounds['min_lat']:.4f}] to "
                     f"[{bounds['max_lat']:.4f},{bounds['max_lon']:.4f}]: {in_bounds}")

        return in_bounds

    def _get_or_open_file(self, filename):
        """Get reader for file, opening if necessary"""
        # Check if already open
        if filename in self.open_files:
            reader, _ = self.open_files[filename]
            self.open_files[filename] = (reader, time.time())  # Update last used
            return reader

        # Need to open file
        file_info = self.available_files.get(filename)
        if not file_info:
            logger.error(f"File info not found for: {filename}")
            return None

        try:
            # Clean up old files if at limit
            self._cleanup_old_files()

            # Open new file
            reader = MBTilesReader(file_info['path'])
            self.open_files[filename] = (reader, time.time())
            logger.info(f"Opened MBTiles file: {filename}")
            return reader

        except Exception as e:
            logger.error(f"Error opening MBTiles file {filename}: {e}")
            return None

    def _cleanup_old_files(self):
        """Close old files to manage memory"""
        current_time = time.time()

        # Close files that haven't been used recently
        files_to_close = []
        for filename, (reader, last_used) in self.open_files.items():
            if current_time - last_used > self.cache_timeout:
                files_to_close.append(filename)

        for filename in files_to_close:
            self._close_file(filename)

        # If still at limit, close oldest files
        while len(self.open_files) >= self.max_open_files:
            # Find oldest file
            oldest_file = min(self.open_files.keys(),
                              key=lambda f: self.open_files[f][1])
            self._close_file(oldest_file)

    def _close_file(self, filename):
        """Close a specific file"""
        if filename in self.open_files:
            reader, _ = self.open_files[filename]
            try:
                reader.close()
                logger.debug(f"Closed MBTiles file: {filename}")
            except Exception as e:
                logger.warning(f"Error closing file {filename}: {e}")

            del self.open_files[filename]

            # Update current file if it was closed
            if self.current_file == filename:
                self.current_file = None
                self.current_reader = None

    def get_available_files(self):
        """Get list of available files with info"""
        return self.available_files.copy()

    def get_current_file_info(self):
        """Get info about currently active file"""
        if self.current_file:
            return self.available_files.get(self.current_file)
        return None

    def force_file_switch(self, filename):
        """Force switch to specific file (for testing)"""
        if filename in self.available_files:
            reader = self._get_or_open_file(filename)
            if reader:
                self.current_file = filename
                self.current_reader = reader
                logger.info(f"Forced switch to: {filename}")
                return True
        return False

    def get_coverage_info(self, lat, lon):
        """Get information about which files cover given coordinates"""
        covering_files = []
        for filename, file_info in self.available_files.items():
            if self._coordinates_in_bounds(lat, lon, file_info.get('bounds')):
                covering_files.append({
                    'filename': filename,
                    'name': file_info.get('name', 'Unknown'),
                    'description': file_info.get('description', ''),
                    'bounds': file_info.get('bounds')
                })
        return covering_files

    def close_all(self):
        """Close all open files"""
        for filename in list(self.open_files.keys()):
            self._close_file(filename)

        self.current_file = None
        self.current_reader = None
        logger.info("Closed all MBTiles files")

    def list_available_regions(self):
        """List all available regions with their coverage"""
        logger.info("Available MBTiles regions:")
        for filename, file_info in self.available_files.items():
            bounds = file_info.get('bounds')
            name = file_info.get('name', filename)
            if bounds:
                logger.info(f"  {name} ({filename}): "
                            f"[{bounds['min_lat']:.4f},{bounds['min_lon']:.4f}] to "
                            f"[{bounds['max_lat']:.4f},{bounds['max_lon']:.4f}]")
            else:
                logger.info(f"  {name} ({filename}): No bounds information")
