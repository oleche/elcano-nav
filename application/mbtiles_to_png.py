#!/usr/bin/env python3
"""
Enhanced MBTiles to PNG Converter with Smart Zoom Fallback
=========================================================
Converts MBTiles database tiles to PNG images with intelligent zoom level selection
and composite map generation for e-paper displays.
"""

import sqlite3
import io
import math
from PIL import Image, ImageDraw, ImageFont
import logging

logger = logging.getLogger(__name__)


class MBTiles:
    """Enhanced MBTiles reader with smart zoom fallback and composite generation"""

    def __init__(self, mbtiles_path):
        self.mbtiles_path = mbtiles_path
        self.conn = sqlite3.connect(mbtiles_path)
        self.conn.row_factory = sqlite3.Row

        # Cache metadata and available zoom levels
        self._metadata = None
        self._available_zooms = None
        self._tile_counts = {}

        logger.info(f"Opened MBTiles database: {mbtiles_path}")

    def get_metadata(self):
        """Get metadata from MBTiles database"""
        if self._metadata is None:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, value FROM metadata")
            self._metadata = dict(cursor.fetchall())
        return self._metadata

    def get_available_zoom_levels(self):
        """Get all available zoom levels in the database"""
        if self._available_zooms is None:
            cursor = self.conn.cursor()
            cursor.execute("SELECT DISTINCT zoom_level FROM tiles ORDER BY zoom_level")
            self._available_zooms = [row[0] for row in cursor.fetchall()]
            logger.info(f"Available zoom levels: {self._available_zooms}")
        return self._available_zooms

    def get_tile_count_for_zoom(self, zoom_level):
        """Get total number of tiles available for a zoom level"""
        if zoom_level not in self._tile_counts:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM tiles WHERE zoom_level = ?", (zoom_level,))
            self._tile_counts[zoom_level] = cursor.fetchone()[0]
        return self._tile_counts[zoom_level]

    def get_tile_count_in_area(self, zoom_level, min_x, min_y, max_x, max_y):
        """Get number of tiles available in a specific area"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM tiles 
            WHERE zoom_level = ? AND tile_column >= ? AND tile_column <= ? 
            AND tile_row >= ? AND tile_row <= ?
        """, (zoom_level, min_x, max_x, min_y, max_y))
        return cursor.fetchone()[0]

    def get_best_available_zoom(self, requested_zoom, lat, lon, width_tiles, height_tiles):
        """
        Find the best available zoom level for the requested area
        Prioritizes zoom levels 12 and above, checks tile availability
        """
        available_zooms = self.get_available_zoom_levels()

        if not available_zooms:
            logger.warning("No zoom levels available in database")
            return None

        # Calculate tile bounds for the requested area at different zoom levels
        def get_tile_bounds(zoom):
            center_x, center_y = self.deg2num(lat, lon, zoom)
            half_width = width_tiles / 2
            half_height = height_tiles / 2

            min_x = max(0, int(center_x - half_width))
            max_x = int(center_x + half_width)
            min_y = max(0, int(center_y - half_height))
            max_y = int(center_y + half_height)

            return min_x, min_y, max_x, max_y

        # Score each available zoom level
        zoom_scores = []

        for zoom in available_zooms:
            try:
                min_x, min_y, max_x, max_y = get_tile_bounds(zoom)
                expected_tiles = (max_x - min_x + 1) * (max_y - min_y + 1)
                available_tiles = self.get_tile_count_in_area(zoom, min_x, min_y, max_x, max_y)

                if expected_tiles == 0:
                    availability_ratio = 0
                else:
                    availability_ratio = available_tiles / expected_tiles

                # Calculate score based on multiple factors
                score = 0

                # Prefer zoom levels 12 and above
                if zoom >= 12:
                    score += 100
                elif zoom >= 10:
                    score += 50
                else:
                    score += 10

                # Heavily weight tile availability
                score += availability_ratio * 200

                # Prefer zoom levels close to requested
                zoom_diff = abs(zoom - requested_zoom)
                score -= zoom_diff * 10

                # Bonus for exact match
                if zoom == requested_zoom:
                    score += 50

                zoom_scores.append((zoom, score, availability_ratio, available_tiles, expected_tiles))

                logger.debug(f"Zoom {zoom}: score={score:.1f}, availability={availability_ratio:.2%}, "
                             f"tiles={available_tiles}/{expected_tiles}")

            except Exception as e:
                logger.warning(f"Error evaluating zoom level {zoom}: {e}")
                continue

        if not zoom_scores:
            logger.warning("No suitable zoom levels found")
            return None

        # Sort by score (highest first)
        zoom_scores.sort(key=lambda x: x[1], reverse=True)

        # Return the best zoom level, but only if it has reasonable availability
        best_zoom, best_score, best_availability, available_tiles, expected_tiles = zoom_scores[0]

        # Require at least 10% tile availability, unless it's the only option
        if best_availability < 0.1 and len(zoom_scores) > 1:
            logger.warning(f"Best zoom {best_zoom} has low availability ({best_availability:.1%}), "
                           f"trying alternatives")

            # Try to find a zoom with better availability
            for zoom, score, availability, avail_tiles, exp_tiles in zoom_scores[1:]:
                if availability >= 0.1:
                    logger.info(f"Using zoom {zoom} instead (availability: {availability:.1%})")
                    return zoom, availability, avail_tiles, exp_tiles

        logger.info(f"Selected zoom level {best_zoom} (availability: {best_availability:.1%}, "
                    f"tiles: {available_tiles}/{expected_tiles})")

        return best_zoom, best_availability, available_tiles, expected_tiles

    def deg2num(self, lat_deg, lon_deg, zoom):
        """Convert latitude/longitude to tile numbers"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = (lon_deg + 180.0) / 360.0 * n
        y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
        return x, y

    def num2deg(self, x, y, zoom):
        """Convert tile numbers to latitude/longitude"""
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = math.degrees(lat_rad)
        return lat_deg, lon_deg

    def get_tile(self, zoom, x, y):
        """Get a single tile from the database"""
        cursor = self.conn.cursor()

        # MBTiles uses TMS (Tile Map Service) coordinate system
        # Convert from XYZ to TMS
        tms_y = (2 ** zoom - 1) - y

        cursor.execute("""
            SELECT tile_data FROM tiles 
            WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?
        """, (zoom, x, tms_y))

        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def create_placeholder_tile(self, size=256):
        """Create a placeholder tile for missing tiles"""
        image = Image.new('RGB', (size, size), color='#f0f0f0')
        draw = ImageDraw.Draw(image)

        # Draw a subtle grid pattern
        grid_spacing = size // 8
        for i in range(0, size, grid_spacing):
            draw.line([(i, 0), (i, size)], fill='#e0e0e0', width=1)
            draw.line([(0, i), (size, i)], fill='#e0e0e0', width=1)

        # Add "No Data" text in center
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        except:
            font = ImageFont.load_default()

        text = "No Data"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (size - text_width) // 2
        text_y = (size - text_height) // 2

        draw.text((text_x, text_y), text, fill='#999999', font=font)

        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def generate_composite_image(self, lat, lon, zoom, width, height,
                                 use_fallback=True, crop_to_size=True):
        """
        Generate a composite image centered on the given coordinates
        with enhanced zoom fallback and tile availability checking
        """
        try:
            # Calculate how many tiles we need
            tile_size = 256
            tiles_x = math.ceil(width / tile_size) + 1
            tiles_y = math.ceil(height / tile_size) + 1

            # Find the best available zoom level
            zoom_result = self.get_best_available_zoom(zoom, lat, lon, tiles_x, tiles_y)

            if zoom_result is None:
                raise Exception("No suitable zoom level found")

            actual_zoom, availability_ratio, available_tiles, expected_tiles = zoom_result
            zoom_adjusted = actual_zoom != zoom

            # Calculate center tile coordinates
            center_x, center_y = self.deg2num(lat, lon, actual_zoom)

            # Calculate tile bounds
            half_tiles_x = tiles_x // 2
            half_tiles_y = tiles_y // 2

            start_x = int(center_x - half_tiles_x)
            end_x = int(center_x + half_tiles_x)
            start_y = int(center_y - half_tiles_y)
            end_y = int(center_y + half_tiles_y)

            # Create composite image
            composite_width = (end_x - start_x + 1) * tile_size
            composite_height = (end_y - start_y + 1) * tile_size
            composite = Image.new('RGB', (composite_width, composite_height), color='white')

            tiles_found = 0
            tiles_missing = 0

            # Fetch and place tiles
            for tile_y in range(start_y, end_y + 1):
                for tile_x in range(start_x, end_x + 1):
                    try:
                        tile_data = self.get_tile(actual_zoom, tile_x, tile_y)

                        if tile_data:
                            tile_image = Image.open(io.BytesIO(tile_data))
                            tiles_found += 1
                        else:
                            # Create placeholder tile
                            placeholder_data = self.create_placeholder_tile()
                            tile_image = Image.open(io.BytesIO(placeholder_data))
                            tiles_missing += 1

                        # Calculate position in composite
                        pos_x = (tile_x - start_x) * tile_size
                        pos_y = (tile_y - start_y) * tile_size

                        # Handle zoom level differences by scaling
                        if zoom_adjusted and tile_data:  # Only scale actual tiles, not placeholders
                            scale_factor = 2 ** (actual_zoom - zoom)
                            if scale_factor != 1:
                                new_size = int(tile_size * scale_factor)
                                tile_image = tile_image.resize((new_size, new_size), Image.Resampling.LANCZOS)

                                # Crop to tile_size if scaled up
                                if scale_factor > 1:
                                    crop_x = (new_size - tile_size) // 2
                                    crop_y = (new_size - tile_size) // 2
                                    tile_image = tile_image.crop((crop_x, crop_y,
                                                                  crop_x + tile_size,
                                                                  crop_y + tile_size))

                        composite.paste(tile_image, (pos_x, pos_y))

                    except Exception as e:
                        logger.debug(f"Error processing tile {tile_x},{tile_y}: {e}")
                        tiles_missing += 1
                        continue

            # Crop to requested size if needed
            if crop_to_size and (composite.width != width or composite.height != height):
                # Calculate crop area to center the image
                crop_x = max(0, (composite.width - width) // 2)
                crop_y = max(0, (composite.height - height) // 2)

                composite = composite.crop((
                    crop_x, crop_y,
                    min(crop_x + width, composite.width),
                    min(crop_y + height, composite.height)
                ))

                # If cropped image is smaller than requested, paste onto white background
                if composite.width < width or composite.height < height:
                    final_image = Image.new('RGB', (width, height), color='white')
                    paste_x = (width - composite.width) // 2
                    paste_y = (height - composite.height) // 2
                    final_image.paste(composite, (paste_x, paste_y))
                    composite = final_image

            # Convert to bytes
            output_buffer = io.BytesIO()
            composite.save(output_buffer, format='PNG')
            image_data = output_buffer.getvalue()

            # Prepare metadata
            metadata = {
                'requested_zoom': zoom,
                'actual_zoom': actual_zoom,
                'zoom_adjusted': zoom_adjusted,
                'tiles_found': tiles_found,
                'tiles_missing': tiles_missing,
                'availability_ratio': availability_ratio,
                'center_lat': lat,
                'center_lon': lon,
                'image_width': composite.width,
                'image_height': composite.height
            }

            logger.info(f"Generated composite image: {composite.width}x{composite.height}, "
                        f"zoom {actual_zoom} ({'adjusted' if zoom_adjusted else 'requested'}), "
                        f"tiles {tiles_found}/{tiles_found + tiles_missing} "
                        f"({availability_ratio:.1%} available)")

            return image_data, metadata

        except Exception as e:
            logger.error(f"Error generating composite image: {e}")
            raise

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info(f"Closed MBTiles database: {self.mbtiles_path}")


def main():
    """Command line interface for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='MBTiles to PNG converter with smart zoom fallback')
    parser.add_argument('mbtiles_file', help='Path to MBTiles file')
    parser.add_argument('--lat', type=float, required=True, help='Latitude')
    parser.add_argument('--lon', type=float, required=True, help='Longitude')
    parser.add_argument('--zoom', type=int, default=14, help='Zoom level (default: 14)')
    parser.add_argument('--width', type=int, default=800, help='Image width (default: 800)')
    parser.add_argument('--height', type=int, default=480, help='Image height (default: 480)')
    parser.add_argument('--output', default='output.png', help='Output PNG file (default: output.png)')
    parser.add_argument('--info', action='store_true', help='Show database info')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    try:
        # Open MBTiles database
        mbtiles = MBTiles(args.mbtiles_file)

        if args.info:
            # Show database information
            metadata = mbtiles.get_metadata()
            print("Database Metadata:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")

            zoom_levels = mbtiles.get_available_zoom_levels()
            print(f"\nAvailable zoom levels: {zoom_levels}")

            for zoom in zoom_levels:
                count = mbtiles.get_tile_count_for_zoom(zoom)
                print(f"  Zoom {zoom}: {count} tiles")

        # Generate composite image
        print(f"Generating composite image for {args.lat}, {args.lon} at zoom {args.zoom}")
        image_data, metadata = mbtiles.generate_composite_image(
            args.lat, args.lon, args.zoom, args.width, args.height
        )

        # Save to file
        with open(args.output, 'wb') as f:
            f.write(image_data)

        print(f"Saved composite image to {args.output}")
        print(f"Metadata: {metadata}")

        mbtiles.close()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
