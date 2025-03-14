#!/usr/bin/env python3
import sqlite3
import io
import math
import json
import argparse
from PIL import Image

class MBTilesReader:
    def __init__(self, mbtiles_path):
        """Initialize the MBTiles reader with the path to the MBTiles file."""
        self.conn = sqlite3.connect(mbtiles_path)
        self.cursor = self.conn.cursor()
        self.format = self._detect_format()
        self.layers = self._detect_layers()
        self.available_zooms = self._get_available_zoom_levels()

    def _detect_format(self):
        """Detect the format of the MBTiles file (raster or vector)."""
        try:
            self.cursor.execute("SELECT value FROM metadata WHERE name='format'")
            result = self.cursor.fetchone()
            if result:
                return result[0]
            return "unknown"
        except sqlite3.Error:
            return "unknown"

    def _detect_layers(self):
        """Detect available layers in the MBTiles file."""
        layers = []

        # Check for vector tile layers in the metadata
        try:
            self.cursor.execute("SELECT value FROM metadata WHERE name='json'")
            result = self.cursor.fetchone()
            if result:
                try:
                    json_data = json.loads(result[0])
                    if 'vector_layers' in json_data:
                        return [layer['id'] for layer in json_data['vector_layers']]
                except (json.JSONDecodeError, KeyError):
                    pass
        except sqlite3.Error:
            pass

        # Check for UTFGrid layer
        try:
            self.cursor.execute("SELECT COUNT(*) FROM grids")
            if self.cursor.fetchone()[0] > 0:
                layers.append("utfgrid")
        except sqlite3.Error:
            pass

        # Check for custom layer table if it exists
        try:
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='layers'")
            if self.cursor.fetchone():
                self.cursor.execute("SELECT * FROM layers")
                for row in self.cursor.fetchall():
                    layers.append(row[0])  # Assuming first column is layer name
        except sqlite3.Error:
            pass

        # If no specific layers found, add default layer
        if not layers:
            layers.append("default")

        return layers

    def _get_available_zoom_levels(self):
        """Get all available zoom levels in the MBTiles file."""
        try:
            self.cursor.execute("SELECT DISTINCT zoom_level FROM tiles ORDER BY zoom_level")
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error:
            return []

    def get_closest_zoom_level(self, zoom):
        """Get the closest available zoom level to the requested one."""
        if not self.available_zooms:
            return None
        if zoom in self.available_zooms:
            return zoom

        # Find the closest zoom level
        closest = min(self.available_zooms, key=lambda x: abs(x - zoom))
        return closest

    def get_metadata(self):
        """Get metadata from the MBTiles file."""
        metadata = {}
        self.cursor.execute("SELECT name, value FROM metadata")
        for name, value in self.cursor.fetchall():
            metadata[name] = value
        return metadata

    def deg2num(self, lat_deg, lon_deg, zoom):
        """Convert latitude, longitude to tile coordinates."""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (xtile, ytile)

    def get_tile(self, zoom, x, y, layer=None):
        """Get a tile from the MBTiles file."""
        # In MBTiles, the y coordinate is flipped from TMS to XYZ
        y_flipped = (2 ** zoom - 1) - y

        # Standard MBTiles query
        self.cursor.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (zoom, x, y_flipped)
        )
        result = self.cursor.fetchone()

        if result:
            return result[0]

        # If no result and we have a layer parameter, try layer-specific query
        if layer and layer != "default":
            try:
                self.cursor.execute(
                    f"SELECT tile_data FROM tiles_{layer} WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (zoom, x, y_flipped)
                )
                result = self.cursor.fetchone()
                if result:
                    return result[0]
            except sqlite3.Error:
                pass

        return None

    def check_tile_exists(self, zoom, x, y, layer=None):
        """Check if a tile exists at the given coordinates and zoom level."""
        y_flipped = (2 ** zoom - 1) - y

        self.cursor.execute(
            "SELECT COUNT(*) FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (zoom, x, y_flipped)
        )
        count = self.cursor.fetchone()[0]

        if count > 0:
            return True

        # Check layer-specific table if specified
        if layer and layer != "default":
            try:
                self.cursor.execute(
                    f"SELECT COUNT(*) FROM tiles_{layer} WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (zoom, x, y_flipped)
                )
                count = self.cursor.fetchone()[0]
                if count > 0:
                    return True
            except sqlite3.Error:
                pass

        return False

    def get_tile_as_png(self, zoom, x, y, layer=None):
        """Get a tile as a PNG image."""
        tile_data = self.get_tile(zoom, x, y, layer)
        if not tile_data:
            return None

        # For vector tiles (MVT/PBF format), we would need to render them
        if self.format == "pbf" or self.format == "mvt":
            print(f"Warning: Vector tile format ({self.format}) detected. Cannot convert to PNG directly.")
            return None

        try:
            # Convert the tile data to a PIL Image
            img = Image.open(io.BytesIO(tile_data))

            # Convert to PNG if it's not already
            output = io.BytesIO()
            img.save(output, format='PNG')
            return output.getvalue()
        except Exception as e:
            print(f"Error processing tile: {e}")
            return None

    def get_png_from_coordinates(self, lat, lon, zoom, layer=None, use_closest_zoom=False):
        """Get a PNG tile from geographic coordinates."""
        actual_zoom = zoom

        # If requested to use closest zoom and the requested zoom isn't available
        if use_closest_zoom and zoom not in self.available_zooms:
            closest_zoom = self.get_closest_zoom_level(zoom)
            if closest_zoom is not None:
                actual_zoom = closest_zoom
                print(f"Zoom level {zoom} not available. Using closest available zoom: {actual_zoom}")
            else:
                print("No zoom levels available in this MBTiles file.")
                return None, None, None, None

        x, y = self.deg2num(lat, lon, actual_zoom)
        return self.get_tile_as_png(actual_zoom, x, y, layer), x, y, actual_zoom

    def save_png_from_coordinates(self, lat, lon, zoom, output_path, layer=None, use_closest_zoom=False):
        """Save a PNG tile from geographic coordinates to a file."""
        png_data, x, y, actual_zoom = self.get_png_from_coordinates(lat, lon, zoom, layer, use_closest_zoom)
        if png_data:
            with open(output_path, 'wb') as f:
                f.write(png_data)
            return True, x, y, actual_zoom
        return False, x, y, actual_zoom

    def check_available_tiles_at_location(self, lat, lon):
        """Check which zoom levels have tiles available at the given coordinates."""
        available_tiles = []

        for zoom in self.available_zooms:
            x, y = self.deg2num(lat, lon, zoom)
            if self.check_tile_exists(zoom, x, y):
                available_tiles.append((zoom, x, y))

        return available_tiles

    def close(self):
        """Close the database connection."""
        self.conn.close()