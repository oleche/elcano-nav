#!/usr/bin/env python3
import sqlite3
import io
import math
import json
from PIL import Image, ImageDraw


class MBTilesReader:
    def __init__(self, mbtiles_path):
        """Initialize the MBTiles reader with the path to the MBTiles file."""
        self.conn = sqlite3.connect(mbtiles_path)
        self.cursor = self.conn.cursor()
        self.format = self._detect_format()
        self.layers = self._detect_layers()
        self.available_zooms = self._get_available_zoom_levels()
        self.tile_size = self._get_tile_size()

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

    def _get_tile_size(self):
        """Detect the tile size from the first available tile."""
        try:
            self.cursor.execute("SELECT tile_data FROM tiles LIMIT 1")
            result = self.cursor.fetchone()
            if result:
                img = Image.open(io.BytesIO(result[0]))
                return img.size[0]  # Assuming square tiles
            return 256  # Default tile size
        except Exception:
            return 256

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

    def num2deg(self, xtile, ytile, zoom):
        """Convert tile coordinates to latitude, longitude."""
        n = 2.0 ** zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)

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

    def get_tile_with_fallback(self, zoom, x, y, layer=None, fallback_layers=None, fallback_zooms=None):
        """
        Get a tile with fallback mechanisms for missing tiles.

        Args:
            zoom: Target zoom level
            x, y: Tile coordinates
            layer: Primary layer to try
            fallback_layers: List of layers to try if primary fails
            fallback_zooms: List of zoom levels to try if primary fails

        Returns:
            tuple: (tile_data, actual_zoom, actual_layer, is_scaled)
        """
        # Try the primary layer and zoom first
        tile_data = self.get_tile(zoom, x, y, layer)
        if tile_data:
            return tile_data, zoom, layer, False

        # Try fallback layers at the same zoom level
        if fallback_layers:
            for fallback_layer in fallback_layers:
                if fallback_layer != layer:
                    tile_data = self.get_tile(zoom, x, y, fallback_layer)
                    if tile_data:
                        return tile_data, zoom, fallback_layer, False

        # Try fallback zoom levels
        if fallback_zooms:
            for fallback_zoom in fallback_zooms:
                if fallback_zoom != zoom:
                    # Calculate the corresponding tile coordinates for the fallback zoom
                    scale_factor = 2 ** (zoom - fallback_zoom)
                    fallback_x = x // scale_factor
                    fallback_y = y // scale_factor

                    # Try primary layer first
                    tile_data = self.get_tile(fallback_zoom, fallback_x, fallback_y, layer)
                    if tile_data:
                        # Scale the tile to match the target zoom level
                        scaled_tile = self._scale_tile(tile_data, scale_factor, x % scale_factor, y % scale_factor)
                        return scaled_tile, fallback_zoom, layer, True

                    # Try fallback layers
                    if fallback_layers:
                        for fallback_layer in fallback_layers:
                            tile_data = self.get_tile(fallback_zoom, fallback_x, fallback_y, fallback_layer)
                            if tile_data:
                                scaled_tile = self._scale_tile(tile_data, scale_factor, x % scale_factor,
                                                               y % scale_factor)
                                return scaled_tile, fallback_zoom, fallback_layer, True

        return None, zoom, layer, False

    def _scale_tile(self, tile_data, scale_factor, offset_x, offset_y):
        """
        Scale a tile to extract a portion for higher zoom levels.

        Args:
            tile_data: Original tile data
            scale_factor: How much to scale (2^zoom_diff)
            offset_x, offset_y: Which portion to extract
        """
        try:
            img = Image.open(io.BytesIO(tile_data))

            # Calculate the portion to extract
            tile_size = img.size[0]
            portion_size = tile_size // scale_factor

            left = offset_x * portion_size
            top = offset_y * portion_size
            right = left + portion_size
            bottom = top + portion_size

            # Extract and scale the portion
            portion = img.crop((left, top, right, bottom))
            scaled = portion.resize((tile_size, tile_size), Image.LANCZOS)

            # Convert back to bytes
            output = io.BytesIO()
            scaled.save(output, format='PNG')
            return output.getvalue()

        except Exception as e:
            print(f"Error scaling tile: {e}")
            return None

    def create_empty_tile(self, size=None, color=(240, 240, 240)):
        """Create an empty tile with optional grid lines."""
        if size is None:
            size = self.tile_size

        img = Image.new('RGB', (size, size), color)
        draw = ImageDraw.Draw(img)

        # Draw a subtle border to indicate empty tile
        border_color = (200, 200, 200)
        draw.rectangle([0, 0, size - 1, size - 1], outline=border_color, width=1)

        # Draw diagonal lines to indicate empty tile
        draw.line([0, 0, size - 1, size - 1], fill=border_color, width=1)
        draw.line([0, size - 1, size - 1, 0], fill=border_color, width=1)

        # Convert to bytes
        output = io.BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()

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

    def calculate_tile_grid(self, center_lat, center_lon, zoom, width, height):
        """
        Calculate the tile grid needed to cover the specified dimensions.

        Args:
            center_lat, center_lon: Center coordinates
            zoom: Zoom level
            width, height: Desired image dimensions in pixels

        Returns:
            dict: Grid information including tile coordinates and bounds
        """
        # Calculate how many tiles we need
        tiles_x = math.ceil(width / self.tile_size)
        tiles_y = math.ceil(height / self.tile_size)

        # Get the center tile coordinates
        center_x, center_y = self.deg2num(center_lat, center_lon, zoom)

        # Calculate the tile grid bounds
        start_x = center_x - tiles_x // 2
        start_y = center_y - tiles_y // 2
        end_x = start_x + tiles_x
        end_y = start_y + tiles_y

        # Calculate the actual image size (might be larger than requested)
        actual_width = tiles_x * self.tile_size
        actual_height = tiles_y * self.tile_size

        # Calculate geographic bounds
        top_left_lat, top_left_lon = self.num2deg(start_x, start_y, zoom)
        bottom_right_lat, bottom_right_lon = self.num2deg(end_x, end_y, zoom)

        return {
            'tiles_x': tiles_x,
            'tiles_y': tiles_y,
            'start_x': start_x,
            'start_y': start_y,
            'end_x': end_x,
            'end_y': end_y,
            'actual_width': actual_width,
            'actual_height': actual_height,
            'center_tile_x': center_x,
            'center_tile_y': center_y,
            'bounds': {
                'north': top_left_lat,
                'south': bottom_right_lat,
                'west': top_left_lon,
                'east': bottom_right_lon
            }
        }

    def generate_composite_image(self, center_lat, center_lon, zoom, width=800, height=480,
                                 layer=None, use_fallback=True, fallback_layers=None,
                                 fallback_zooms=None, crop_to_size=True):
        """
        Generate a composite image by combining multiple tiles.

        Args:
            center_lat, center_lon: Center coordinates
            zoom: Target zoom level
            width, height: Desired image dimensions
            layer: Primary layer to use
            use_fallback: Whether to use fallback mechanisms
            fallback_layers: List of fallback layers
            fallback_zooms: List of fallback zoom levels
            crop_to_size: Whether to crop the final image to exact dimensions

        Returns:
            tuple: (image_data, metadata)
        """
        # Set up fallback options
        if use_fallback:
            if fallback_layers is None:
                fallback_layers = [l for l in self.layers if l != layer]
            if fallback_zooms is None:
                # Try zoom levels in order of preference (closest first)
                available_zooms = sorted(self.available_zooms, key=lambda x: abs(x - zoom))
                fallback_zooms = available_zooms[:5]  # Limit to 5 closest zoom levels

        # Calculate the tile grid
        grid = self.calculate_tile_grid(center_lat, center_lon, zoom, width, height)

        # Create the composite image
        composite = Image.new('RGB', (grid['actual_width'], grid['actual_height']), (240, 240, 240))

        tiles_found = 0
        tiles_missing = 0
        tiles_scaled = 0

        # Process each tile in the grid
        for tile_y in range(grid['start_y'], grid['end_y']):
            for tile_x in range(grid['start_x'], grid['end_x']):
                # Calculate position in the composite image
                pos_x = (tile_x - grid['start_x']) * self.tile_size
                pos_y = (tile_y - grid['start_y']) * self.tile_size

                tile_data = None
                actual_zoom = zoom
                actual_layer = layer
                is_scaled = False

                if use_fallback:
                    tile_data, actual_zoom, actual_layer, is_scaled = self.get_tile_with_fallback(
                        zoom, tile_x, tile_y, layer, fallback_layers, fallback_zooms
                    )
                else:
                    tile_data = self.get_tile(zoom, tile_x, tile_y, layer)

                if tile_data:
                    try:
                        tile_img = Image.open(io.BytesIO(tile_data))
                        composite.paste(tile_img, (pos_x, pos_y))
                        tiles_found += 1
                        if is_scaled:
                            tiles_scaled += 1
                    except Exception as e:
                        print(f"Error processing tile ({tile_x}, {tile_y}): {e}")
                        # Create empty tile as fallback
                        empty_tile_data = self.create_empty_tile()
                        empty_tile_img = Image.open(io.BytesIO(empty_tile_data))
                        composite.paste(empty_tile_img, (pos_x, pos_y))
                        tiles_missing += 1
                else:
                    # Create empty tile
                    empty_tile_data = self.create_empty_tile()
                    empty_tile_img = Image.open(io.BytesIO(empty_tile_data))
                    composite.paste(empty_tile_img, (pos_x, pos_y))
                    tiles_missing += 1

        # Crop to exact size if requested
        if crop_to_size and (grid['actual_width'] != width or grid['actual_height'] != height):
            # Calculate crop area to center the image
            crop_x = (grid['actual_width'] - width) // 2
            crop_y = (grid['actual_height'] - height) // 2
            composite = composite.crop((crop_x, crop_y, crop_x + width, crop_y + height))

        # Convert to bytes
        output = io.BytesIO()
        composite.save(output, format='PNG')

        # Prepare metadata
        metadata = {
            'center_lat': center_lat,
            'center_lon': center_lon,
            'zoom': zoom,
            'requested_size': (width, height),
            'actual_size': composite.size,
            'tiles_grid': (grid['tiles_x'], grid['tiles_y']),
            'tiles_found': tiles_found,
            'tiles_missing': tiles_missing,
            'tiles_scaled': tiles_scaled,
            'bounds': grid['bounds'],
            'layer': layer,
            'tile_size': self.tile_size
        }

        return output.getvalue(), metadata

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

    def save_composite_image(self, center_lat, center_lon, zoom, output_path, width=800, height=480,
                             layer=None, use_fallback=True, fallback_layers=None, fallback_zooms=None,
                             crop_to_size=True):
        """Save a composite image to a file."""
        image_data, metadata = self.generate_composite_image(
            center_lat, center_lon, zoom, width, height, layer, use_fallback,
            fallback_layers, fallback_zooms, crop_to_size
        )

        with open(output_path, 'wb') as f:
            f.write(image_data)

        return True, metadata

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
