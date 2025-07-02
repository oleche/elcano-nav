import sqlite3
import io
import math
from PIL import Image

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
        y_flipped = (2**zoom - 1) - y
        
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
    
    def close(self):
        """Close the database connection."""
        self.conn.close()

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
