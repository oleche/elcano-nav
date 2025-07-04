import sqlite3
import io
import math
from PIL import Image, ImageDraw, ImageFont
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

    def get_available_zoom_levels(self):
        """Get all available zoom levels in the MBTiles file."""
        try:
            self.cursor.execute("SELECT DISTINCT zoom_level FROM tiles ORDER BY zoom_level")
            zoom_levels = [row[0] for row in self.cursor.fetchall()]
            logger.debug(f"Available zoom levels: {zoom_levels}")
            return zoom_levels
        except Exception as e:
            logger.error(f"Error getting zoom levels: {e}")
            return []

    def get_best_available_zoom(self, requested_zoom):
        """Get the best available zoom level for the requested zoom."""
        available_zooms = self.get_available_zoom_levels()
        if not available_zooms:
            return requested_zoom

        # If requested zoom is available, use it
        if requested_zoom in available_zooms:
            return requested_zoom

        # Find closest available zoom level
        closest_zoom = min(available_zooms, key=lambda x: abs(x - requested_zoom))

        # If the closest zoom is significantly lower than 12, try to find a better one
        if closest_zoom < 12 and requested_zoom >= 12:
            higher_zooms = [z for z in available_zooms if z >= 12]
            if higher_zooms:
                closest_zoom = min(higher_zooms)

        logger.info(f"Requested zoom {requested_zoom}, using available zoom {closest_zoom}")
        return closest_zoom

    def get_tile_count_at_zoom(self, zoom, lat, lon, tiles_x, tiles_y):
        """Count how many tiles are available at a specific zoom level for the given area."""
        center_x, center_y = self.deg2num(lat, lon, zoom)
        start_x = int(center_x - tiles_x // 2)
        start_y = int(center_y - tiles_y // 2)

        available_count = 0
        total_count = tiles_x * tiles_y

        for ty in range(tiles_y):
            for tx in range(tiles_x):
                tile_x = start_x + tx
                tile_y = start_y + ty
                if self.get_tile(zoom, tile_x, tile_y):
                    available_count += 1

        return available_count, total_count

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
            'maxzoom': int(metadata.get('maxzoom', 18)),
            'available_zooms': self.get_available_zoom_levels()
        }

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def generate_composite_image(self, lat, lon, zoom, width=800, height=480, use_fallback=True, crop_to_size=True):
        """Generate a composite image for the given coordinates and dimensions with smart zoom fallback"""
        try:
            # Calculate how many tiles we need to cover the requested dimensions
            tile_size = 256
            tiles_x = math.ceil(width / tile_size) + 1
            tiles_y = math.ceil(height / tile_size) + 1

            # Find the best zoom level to use
            original_zoom = zoom
            best_zoom = self.get_best_available_zoom(zoom)

            # If we're using a different zoom, check tile availability
            if best_zoom != zoom:
                available_count, total_count = self.get_tile_count_at_zoom(best_zoom, lat, lon, tiles_x, tiles_y)
                availability_ratio = available_count / total_count if total_count > 0 else 0

                logger.info(
                    f"Zoom {best_zoom}: {available_count}/{total_count} tiles available ({availability_ratio:.1%})")

                # If availability is very low and we have other zoom options, try them
                if availability_ratio < 0.3:
                    available_zooms = self.get_available_zoom_levels()
                    for test_zoom in sorted(available_zooms, key=lambda x: abs(x - zoom)):
                        if test_zoom == best_zoom:
                            continue
                        test_available, test_total = self.get_tile_count_at_zoom(test_zoom, lat, lon, tiles_x, tiles_y)
                        test_ratio = test_available / test_total if test_total > 0 else 0

                        logger.debug(
                            f"Testing zoom {test_zoom}: {test_available}/{test_total} tiles ({test_ratio:.1%})")

                        if test_ratio > availability_ratio and test_ratio > 0.5:
                            logger.info(f"Switching to zoom {test_zoom} with better availability ({test_ratio:.1%})")
                            best_zoom = test_zoom
                            availability_ratio = test_ratio
                            break

            # Calculate the center tile coordinates for the chosen zoom
            center_x, center_y = self.deg2num(lat, lon, best_zoom)

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
                    tile_data = self.get_tile_as_png(best_zoom, tile_x, tile_y)

                    if tile_data:
                        try:
                            # Load tile image
                            tile_image = Image.open(io.BytesIO(tile_data))

                            # Resize tile if we're using a different zoom level
                            if best_zoom != original_zoom:
                                zoom_diff = original_zoom - best_zoom
                                if zoom_diff > 0:
                                    # Zooming in - crop and scale up
                                    scale_factor = 2 ** zoom_diff
                                    new_size = int(tile_size * scale_factor)
                                    tile_image = tile_image.resize((new_size, new_size), Image.LANCZOS)
                                    # Crop to tile_size
                                    crop_offset = (new_size - tile_size) // 2
                                    tile_image = tile_image.crop((crop_offset, crop_offset,
                                                                  crop_offset + tile_size, crop_offset + tile_size))
                                elif zoom_diff < 0:
                                    # Zooming out - scale down
                                    scale_factor = 2 ** abs(zoom_diff)
                                    new_size = tile_size // scale_factor
                                    tile_image = tile_image.resize((new_size, new_size), Image.LANCZOS)
                                    # Center on a tile_size canvas
                                    centered_tile = Image.new('RGB', (tile_size, tile_size), (240, 240, 240))
                                    offset = (tile_size - new_size) // 2
                                    centered_tile.paste(tile_image, (offset, offset))
                                    tile_image = centered_tile

                            # Paste tile into composite
                            paste_x = tx * tile_size
                            paste_y = ty * tile_size
                            composite_image.paste(tile_image, (paste_x, paste_y))
                            tiles_found += 1

                        except Exception as e:
                            logger.warning(f"Error loading tile {tile_x},{tile_y}: {e}")
                            tiles_missing += 1
                            if use_fallback:
                                self._add_fallback_tile(composite_image, tx * tile_size, ty * tile_size, tile_size)
                    else:
                        tiles_missing += 1

                        # Add fallback tile if requested
                        if use_fallback:
                            self._add_fallback_tile(composite_image, tx * tile_size, ty * tile_size, tile_size)

            # Crop to requested size if needed
            if crop_to_size:
                # Calculate crop area to center the image
                crop_x = max(0, (composite_width - width) // 2)
                crop_y = max(0, (composite_height - height) // 2)

                # Ensure we don't crop beyond image bounds
                crop_x2 = min(composite_width, crop_x + width)
                crop_y2 = min(composite_height, crop_y + height)

                composite_image = composite_image.crop((crop_x, crop_y, crop_x2, crop_y2))

                # If the cropped image is smaller than requested, pad it
                if composite_image.size != (width, height):
                    padded_image = Image.new('RGB', (width, height), (255, 255, 255))
                    paste_x = (width - composite_image.width) // 2
                    paste_y = (height - composite_image.height) // 2
                    padded_image.paste(composite_image, (paste_x, paste_y))
                    composite_image = padded_image

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
                'requested_zoom': original_zoom,
                'actual_zoom': best_zoom,
                'zoom_adjusted': best_zoom != original_zoom,
                'composite_size': (composite_image.width, composite_image.height),
                'availability_ratio': tiles_found / (tiles_found + tiles_missing) if (
                                                                                                 tiles_found + tiles_missing) > 0 else 0
            }

            logger.info(f"Generated composite: {tiles_found} tiles found, {tiles_missing} missing, "
                        f"zoom {original_zoom}→{best_zoom}, size {composite_image.size}")

            return image_data, metadata

        except Exception as e:
            logger.error(f"Error generating composite image: {e}")
            # Return a blank image with error info
            blank_image = Image.new('RGB', (width, height), (255, 255, 255))

            # Add error message to the blank image
            try:
                draw = ImageDraw.Draw(blank_image)
                font = ImageFont.load_default()
                error_text = f"Map Error: {str(e)[:50]}"
                bbox = draw.textbbox((0, 0), error_text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = (width - text_width) // 2
                text_y = (height - text_height) // 2
                draw.text((text_x, text_y), error_text, fill=(128, 128, 128), font=font)
            except:
                pass

            output = io.BytesIO()
            blank_image.save(output, format='PNG')

            metadata = {
                'error': str(e),
                'tiles_found': 0,
                'tiles_missing': 0,
                'requested_zoom': zoom,
                'actual_zoom': zoom,
                'zoom_adjusted': False
            }

            return output.getvalue(), metadata

    def _add_fallback_tile(self, composite_image, x, y, size):
        """Add a fallback tile when original tile is missing"""
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
