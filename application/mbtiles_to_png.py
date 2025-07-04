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

    def check_tile_availability_in_area(self, lat, lon, zoom, width_tiles=4, height_tiles=3):
        """Check how many tiles are available in a specific area"""
        center_x, center_y = self.deg2num(lat, lon, zoom)

        # Calculate tile bounds for the area
        min_x = int(center_x - width_tiles // 2)
        max_x = int(center_x + width_tiles // 2)
        min_y = int(center_y - height_tiles // 2)
        max_y = int(center_y + height_tiles // 2)

        # Count available tiles in this area
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM tiles 
            WHERE zoom_level = ? AND tile_column BETWEEN ? AND ? AND tile_row BETWEEN ? AND ?
        """, (zoom, min_x, max_x, min_y, max_y))

        available_tiles = cursor.fetchone()[0]
        total_tiles = (max_x - min_x + 1) * (max_y - min_y + 1)

        availability_ratio = available_tiles / total_tiles if total_tiles > 0 else 0

        logger.debug(f"Zoom {zoom} area availability: {available_tiles}/{total_tiles} ({availability_ratio:.1%})")

        return {
            'available_tiles': available_tiles,
            'total_tiles': total_tiles,
            'availability_ratio': availability_ratio,
            'bounds': (min_x, min_y, max_x, max_y)
        }

    def get_best_available_zoom(self, lat, lon, requested_zoom, min_availability=0.3):
        """Find the best available zoom level for a location"""
        available_zooms = self.get_available_zoom_levels()

        if not available_zooms:
            logger.warning("No zoom levels available in MBTiles file")
            return None

        # Check if requested zoom is available and has good coverage
        if requested_zoom in available_zooms:
            availability = self.check_tile_availability_in_area(lat, lon, requested_zoom)
            if availability['availability_ratio'] >= min_availability:
                logger.debug(
                    f"Using requested zoom {requested_zoom} (availability: {availability['availability_ratio']:.1%})")
                return requested_zoom

        # Find best alternative zoom level
        best_zoom = None
        best_score = -1

        for zoom in available_zooms:
            # Skip zoom levels below 12 unless it's the only option
            if zoom < 12 and len([z for z in available_zooms if z >= 12]) > 0:
                continue

            availability = self.check_tile_availability_in_area(lat, lon, zoom)

            # Skip if availability is too low
            if availability['availability_ratio'] < min_availability:
                continue

            # Calculate score based on availability and proximity to requested zoom
            zoom_distance = abs(zoom - requested_zoom)
            availability_score = availability['availability_ratio']

            # Prefer higher zoom levels and better availability
            score = availability_score * 100 - zoom_distance * 10

            if score > best_score:
                best_score = score
                best_zoom = zoom

        if best_zoom is not None:
            logger.info(f"Selected zoom {best_zoom} instead of {requested_zoom} (score: {best_score:.1f})")
        else:
            # Fallback to any available zoom if nothing meets criteria
            best_zoom = available_zooms[0] if available_zooms else None
            logger.warning(f"Using fallback zoom {best_zoom} - low tile availability expected")

        return best_zoom

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
        cursor.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                       (zoom, x, y))
        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def create_placeholder_tile(self, size=256):
        """Create a placeholder tile for missing tiles"""
        image = Image.new('RGB', (size, size), color='white')
        draw = ImageDraw.Draw(image)

        # Draw grid pattern
        grid_size = size // 8
        for i in range(0, size, grid_size):
            draw.line([i, 0, i, size], fill='lightgray', width=1)
            draw.line([0, i, size, i], fill='lightgray', width=1)

        # Draw diagonal lines
        draw.line([0, 0, size, size], fill='lightgray', width=2)
        draw.line([0, size, size, 0], fill='lightgray', width=2)

        # Add text if possible
        try:
            font = ImageFont.load_default()
            text = "NO DATA"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (size - text_width) // 2
            text_y = (size - text_height) // 2
            draw.text((text_x, text_y), text, fill='gray', font=font)
        except:
            pass

        # Convert to bytes
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def generate_composite_image(self, lat, lon, zoom, width, height, use_fallback=True, crop_to_size=True):
        """
        Generate a composite image centered on the given coordinates
        with enhanced zoom fallback and tile availability checking
        """
        try:
            # Find best available zoom level
            if use_fallback:
                actual_zoom = self.get_best_available_zoom(lat, lon, zoom)
                if actual_zoom is None:
                    raise Exception("No suitable zoom level found")
                zoom_adjusted = (actual_zoom != zoom)
            else:
                actual_zoom = zoom
                zoom_adjusted = False

            # Calculate center tile
            center_x, center_y = self.deg2num(lat, lon, actual_zoom)

            # Calculate how many tiles we need
            tile_size = 256
            tiles_x = math.ceil(width / tile_size) + 1
            tiles_y = math.ceil(height / tile_size) + 1

            # Calculate tile bounds
            start_x = int(center_x - tiles_x // 2)
            start_y = int(center_y - tiles_y // 2)
            end_x = start_x + tiles_x
            end_y = start_y + tiles_y

            # Create composite image
            composite_width = tiles_x * tile_size
            composite_height = tiles_y * tile_size
            composite = Image.new('RGB', (composite_width, composite_height), 'white')

            # Track tile statistics
            tiles_found = 0
            tiles_missing = 0

            # Load and place tiles
            for ty in range(start_y, end_y):
                for tx in range(start_x, end_x):
                    tile_data = self.get_tile(actual_zoom, tx, ty)

                    if tile_data:
                        try:
                            tile_image = Image.open(io.BytesIO(tile_data))
                            tiles_found += 1
                        except Exception as e:
                            logger.debug(f"Error loading tile {actual_zoom}/{tx}/{ty}: {e}")
                            tile_image = Image.open(io.BytesIO(self.create_placeholder_tile()))
                            tiles_missing += 1
                    else:
                        # Create placeholder for missing tile
                        tile_image = Image.open(io.BytesIO(self.create_placeholder_tile()))
                        tiles_missing += 1

                    # Calculate position in composite
                    pos_x = (tx - start_x) * tile_size
                    pos_y = (ty - start_y) * tile_size

                    # Paste tile into composite
                    composite.paste(tile_image, (pos_x, pos_y))

            # Calculate offset for centering
            pixel_x = (center_x - int(center_x)) * tile_size
            pixel_y = (center_y - int(center_y)) * tile_size

            # Calculate crop area to center the requested location
            crop_x = int(composite_width // 2 - width // 2 + pixel_x)
            crop_y = int(composite_height // 2 - height // 2 + pixel_y)

            # Ensure crop area is within bounds
            crop_x = max(0, min(crop_x, composite_width - width))
            crop_y = max(0, min(crop_y, composite_height - height))

            # Crop to requested size if needed
            if crop_to_size:
                final_image = composite.crop((crop_x, crop_y, crop_x + width, crop_y + height))
            else:
                final_image = composite

            # Handle zoom level scaling if we used a different zoom
            if zoom_adjusted and actual_zoom != zoom:
                scale_factor = 2 ** (zoom - actual_zoom)
                if scale_factor != 1:
                    new_width = int(final_image.width * scale_factor)
                    new_height = int(final_image.height * scale_factor)
                    final_image = final_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    # Crop to original size if scaled up
                    if scale_factor > 1 and crop_to_size:
                        crop_x = (new_width - width) // 2
                        crop_y = (new_height - height) // 2
                        final_image = final_image.crop((crop_x, crop_y, crop_x + width, crop_y + height))

            # Convert to bytes
            output_buffer = io.BytesIO()
            final_image.save(output_buffer, format='PNG')
            image_data = output_buffer.getvalue()

            # Prepare metadata
            total_tiles = tiles_found + tiles_missing
            availability_ratio = tiles_found / total_tiles if total_tiles > 0 else 0

            metadata = {
                'zoom_requested': zoom,
                'zoom_actual': actual_zoom,
                'zoom_adjusted': zoom_adjusted,
                'tiles_found': tiles_found,
                'tiles_missing': tiles_missing,
                'total_tiles': total_tiles,
                'availability_ratio': availability_ratio,
                'center_lat': lat,
                'center_lon': lon,
                'image_width': final_image.width,
                'image_height': final_image.height
            }

            logger.info(f"Generated composite image: {tiles_found}/{total_tiles} tiles "
                        f"({availability_ratio:.1%} availability), zoom {actual_zoom}")

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
