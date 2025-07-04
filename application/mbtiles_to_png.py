import sqlite3
import io
import math
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class MBTilesReader:
    def __init__(self, mbtiles_path):
        """Initialize the MBTiles reader with the path to the MBTiles file."""
        self.conn = sqlite3.connect(mbtiles_path)
        self.cursor = self.conn.cursor()

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

    def get_tile(self, zoom, x, y):
        """Get a tile from the MBTiles file."""
        # In MBTiles, the y coordinate is flipped from TMS to XYZ
        y_flipped = (2 ** zoom - 1) - y

        self.cursor.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (zoom, x, y_flipped)
        )
        result = self.cursor.fetchone()

        if result:
            return result[0]
        return None

    def get_tile_as_png(self, zoom, x, y):
        """Get a tile as a PNG image."""
        tile_data = self.get_tile(zoom, x, y)
        if tile_data:
            # Convert the tile data to a PIL Image
            img = Image.open(io.BytesIO(tile_data))

            # Convert to PNG if it's not already
            if img.format != 'PNG':
                output = io.BytesIO()
                img.save(output, format='PNG')
                return output.getvalue()
            return tile_data
        return None

    def get_png_from_coordinates(self, lat, lon, zoom):
        """Get a PNG tile from geographic coordinates."""
        x, y = self.deg2num(lat, lon, zoom)
        return self.get_tile_as_png(zoom, x, y), x, y

    def save_png_from_coordinates(self, lat, lon, zoom, output_path):
        """Save a PNG tile from geographic coordinates to a file."""
        png_data, x, y = self.get_png_from_coordinates(lat, lon, zoom)
        if png_data:
            with open(output_path, 'wb') as f:
                f.write(png_data)
            return True, x, y
        return False, x, y

    def get_bounds(self):
        """Get the bounds of the MBTiles file."""
        try:
            self.cursor.execute("SELECT value FROM metadata WHERE name='bounds'")
            result = self.cursor.fetchone()
            if result:
                # Bounds format: "minlon,minlat,maxlon,maxlat"
                bounds_str = result[0]
                bounds = [float(x) for x in bounds_str.split(',')]
                return {
                    'min_lon': bounds[0],
                    'min_lat': bounds[1],
                    'max_lon': bounds[2],
                    'max_lat': bounds[3]
                }
        except Exception as e:
            logger.warning(f"Could not get bounds from metadata: {e}")

        # Fallback: calculate bounds from available tiles
        try:
            self.cursor.execute("""
                SELECT MIN(tile_column), MIN(tile_row), MAX(tile_column), MAX(tile_row), zoom_level
                FROM tiles 
                GROUP BY zoom_level 
                ORDER BY zoom_level DESC 
                LIMIT 1
            """)
            result = self.cursor.fetchone()
            if result:
                min_x, min_y, max_x, max_y, zoom = result

                # Convert tile coordinates to lat/lon
                min_lon, max_lat = self.num2deg(min_x, min_y, zoom)
                max_lon, min_lat = self.num2deg(max_x + 1, max_y + 1, zoom)

                return {
                    'min_lon': min_lon,
                    'min_lat': min_lat,
                    'max_lon': max_lon,
                    'max_lat': max_lat
                }
        except Exception as e:
            logger.warning(f"Could not calculate bounds from tiles: {e}")

        return None

    def num2deg(self, xtile, ytile, zoom):
        """Convert tile coordinates to latitude, longitude."""
        import math
        n = 2.0 ** zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)
        return (lon_deg, lat_deg)

    def contains_coordinates(self, lat, lon):
        """Check if the MBTiles file contains the given coordinates."""
        bounds = self.get_bounds()
        if not bounds:
            return False

        return (bounds['min_lat'] <= lat <= bounds['max_lat'] and
                bounds['min_lon'] <= lon <= bounds['max_lon'])

    def get_file_info(self):
        """Get information about the MBTiles file."""
        metadata = self.get_metadata()
        bounds = self.get_bounds()

        return {
            'name': metadata.get('name', 'Unknown'),
            'description': metadata.get('description', ''),
            'version': metadata.get('version', ''),
            'bounds': bounds,
            'format': metadata.get('format', 'png'),
            'minzoom': int(metadata.get('minzoom', 0)),
            'maxzoom': int(metadata.get('maxzoom', 18))
        }

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def generate_composite_image(self, lat, lon, zoom, width=800, height=480, use_fallback=True, crop_to_size=True):
        """Generate a composite image for the given coordinates and dimensions"""
        try:
            # Calculate the center tile coordinates
            center_x, center_y = self.deg2num(lat, lon, zoom)

            # Calculate how many tiles we need to cover the requested dimensions
            # Assuming 256px tiles
            tile_size = 256
            tiles_x = math.ceil(width / tile_size) + 1
            tiles_y = math.ceil(height / tile_size) + 1

            # Calculate the starting tile coordinates
            start_x = int(center_x - tiles_x // 2)
            start_y = int(center_y - tiles_y // 2)

            # Create a larger image to hold all tiles
            composite_width = tiles_x * tile_size
            composite_height = tiles_y * tile_size
            composite_image = Image.new('RGB', (composite_width, composite_height), (255, 255, 255))

            tiles_found = 0
            tiles_missing = 0

            # Fetch and place tiles
            for ty in range(tiles_y):
                for tx in range(tiles_x):
                    tile_x = start_x + tx
                    tile_y = start_y + ty

                    # Get tile data
                    tile_data = self.get_tile_as_png(zoom, tile_x, tile_y)

                    if tile_data:
                        try:
                            # Load tile image
                            tile_image = Image.open(io.BytesIO(tile_data))

                            # Paste tile into composite
                            paste_x = tx * tile_size
                            paste_y = ty * tile_size
                            composite_image.paste(tile_image, (paste_x, paste_y))
                            tiles_found += 1

                        except Exception as e:
                            logger.warning(f"Error loading tile {tile_x},{tile_y}: {e}")
                            tiles_missing += 1
                    else:
                        tiles_missing += 1

                        # Add fallback tile if requested
                        if use_fallback:
                            self._add_fallback_tile(composite_image, tx * tile_size, ty * tile_size, tile_size)

            # Crop to requested size if needed
            if crop_to_size:
                # Calculate crop area to center the image
                crop_x = (composite_width - width) // 2
                crop_y = (composite_height - height) // 2

                composite_image = composite_image.crop((
                    crop_x, crop_y,
                    crop_x + width, crop_y + height
                ))

            # Convert to bytes
            output = io.BytesIO()
            composite_image.save(output, format='PNG')
            image_data = output.getvalue()

            # Metadata
            metadata = {
                'tiles_found': tiles_found,
                'tiles_missing': tiles_missing,
                'center_tile_x': center_x,
                'center_tile_y': center_y,
                'zoom': zoom,
                'composite_size': (composite_image.width, composite_image.height)
            }

            return image_data, metadata

        except Exception as e:
            logger.error(f"Error generating composite image: {e}")
            # Return a blank image with error info
            blank_image = Image.new('RGB', (width, height), (255, 255, 255))
            output = io.BytesIO()
            blank_image.save(output, format='PNG')

            metadata = {
                'error': str(e),
                'tiles_found': 0,
                'tiles_missing': 0
            }

            return output.getvalue(), metadata

    def _add_fallback_tile(self, composite_image, x, y, size):
        """Add a fallback tile when original tile is missing"""
        from PIL import ImageDraw, ImageFont

        # Create a simple fallback tile
        fallback = Image.new('RGB', (size, size), (240, 240, 240))
        draw = ImageDraw.Draw(fallback)

        # Draw a simple grid pattern
        grid_spacing = size // 4
        for i in range(0, size, grid_spacing):
            draw.line([i, 0, i, size], fill=(200, 200, 200), width=1)
            draw.line([0, i, size, i], fill=(200, 200, 200), width=1)

        # Add "No Tile" text
        try:
            font = ImageFont.load_default()
            text = "No Tile"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (size - text_width) // 2
            text_y = (size - text_height) // 2
            draw.text((text_x, text_y), text, fill=(128, 128, 128), font=font)
        except:
            pass

        # Paste fallback tile into composite
        composite_image.paste(fallback, (x, y))


# Example usage
if __name__ == "__main__":
    # This is a demo - you would need an actual MBTiles file
    # For demonstration, we'll just print the steps

    print("MBTiles to PNG Converter")
    print("------------------------")
    print("In a real application, you would:")
    print("1. Initialize the reader with an MBTiles file path")
    print("2. Specify coordinates and zoom level")
    print("3. Get or save the PNG tile")

    print("\nExample code:")
    print("reader = MBTilesReader('path/to/map.mbtiles')")
    print("lat, lon = 37.7749, -122.4194  # San Francisco")
    print("zoom = 12")
    print("success, x, y = reader.save_png_from_coordinates(lat, lon, zoom, 'sf_tile.png')")
    print("print(f'Saved tile at coordinates ({x}, {y}) to sf_tile.png')")
    print("reader.close()")
