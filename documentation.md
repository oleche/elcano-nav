### MBTiles Reader Documentation

## Table of Contents

1. [Overview](#overview)
2. [MBTilesReader Class](#mbtilesreader-class)
3. [Command Line Interface](#command-line-interface)
4. [Usage Examples](#usage-examples)
5. [Troubleshooting](#troubleshooting)


## Overview

The MBTiles Reader is a comprehensive Python toolkit for working with MBTiles files - a specification for storing tiled map data in SQLite databases. This toolkit provides both a powerful Python class (`MBTilesReader`) and a command-line interface for extracting individual tiles or generating composite images from MBTiles data.

### Key Features

- **Single Tile Extraction**: Extract individual map tiles as PNG images
- **Composite Image Generation**: Create large images by combining multiple tiles
- **Intelligent Fallback System**: Automatically handle missing tiles using alternative layers or zoom levels
- **Multi-layer Support**: Work with MBTiles files containing multiple data layers
- **Flexible Resolution**: Generate images at any resolution with automatic tile grid calculation
- **Geographic Coordinate Support**: Work with latitude/longitude coordinates directly


---

## MBTilesReader Class

### Class Overview

The `MBTilesReader` class provides programmatic access to MBTiles files with advanced features for tile extraction, image composition, and fallback handling.

```python
from mbtiles import MBTilesReader

# Initialize reader
reader = MBTilesReader('path/to/map.mbtiles')

# Use the reader
image_data, metadata = reader.generate_composite_image(37.7749, -122.4194, 12, 800, 480)

# Always close when done
reader.close()
```

### Constructor

#### `__init__(mbtiles_path)`

Initialize the MBTiles reader with a path to an MBTiles file.

**Parameters:**

- `mbtiles_path` (str): Path to the MBTiles file


**Raises:**

- `sqlite3.Error`: If the file cannot be opened or is not a valid SQLite database


**Example:**

```python
reader = MBTilesReader('/path/to/map.mbtiles')
```

### Core Properties

After initialization, the following properties are automatically detected:

- `reader.format` (str): Detected format ('png', 'jpg', 'pbf', 'mvt', etc.)
- `reader.layers` (list): Available layers in the MBTiles file
- `reader.available_zooms` (list): Available zoom levels
- `reader.tile_size` (int): Size of individual tiles in pixels (typically 256 or 512)


### Coordinate Conversion Methods

#### `deg2num(lat_deg, lon_deg, zoom)`

Convert geographic coordinates to tile coordinates.

**Parameters:**

- `lat_deg` (float): Latitude in decimal degrees
- `lon_deg` (float): Longitude in decimal degrees
- `zoom` (int): Zoom level


**Returns:**

- `tuple`: (x, y) tile coordinates


**Example:**

```python
x, y = reader.deg2num(37.7749, -122.4194, 12)
print(f"Tile coordinates: ({x}, {y})")  # Output: Tile coordinates: (655, 1582)
```

#### `num2deg(xtile, ytile, zoom)`

Convert tile coordinates to geographic coordinates.

**Parameters:**

- `xtile` (int): X tile coordinate
- `ytile` (int): Y tile coordinate
- `zoom` (int): Zoom level


**Returns:**

- `tuple`: (latitude, longitude) in decimal degrees


**Example:**

```python
lat, lon = reader.num2deg(655, 1582, 12)
print(f"Geographic coordinates: ({lat:.6f}, {lon:.6f})")
```

### Tile Retrieval Methods

#### `get_tile(zoom, x, y, layer=None)`

Get raw tile data from the MBTiles file.

**Parameters:**

- `zoom` (int): Zoom level
- `x` (int): X tile coordinate
- `y` (int): Y tile coordinate
- `layer` (str, optional): Specific layer name


**Returns:**

- `bytes` or `None`: Raw tile data or None if not found


**Example:**

```python
tile_data = reader.get_tile(12, 655, 1582)
if tile_data:
    with open('tile.png', 'wb') as f:
        f.write(tile_data)
```

#### `get_tile_with_fallback(zoom, x, y, layer=None, fallback_layers=None, fallback_zooms=None)`

Get tile data with intelligent fallback mechanisms.

**Parameters:**

- `zoom` (int): Target zoom level
- `x` (int): X tile coordinate
- `y` (int): Y tile coordinate
- `layer` (str, optional): Primary layer to try
- `fallback_layers` (list, optional): Alternative layers to try
- `fallback_zooms` (list, optional): Alternative zoom levels to try


**Returns:**

- `tuple`: (tile_data, actual_zoom, actual_layer, is_scaled)

- `tile_data` (bytes): Raw tile data
- `actual_zoom` (int): Zoom level actually used
- `actual_layer` (str): Layer actually used
- `is_scaled` (bool): Whether tile was scaled from different zoom level





**Example:**

```python
tile_data, zoom_used, layer_used, scaled = reader.get_tile_with_fallback(
    15, 655, 1582, 
    fallback_layers=['satellite', 'terrain'],
    fallback_zooms=[14, 13, 16]
)
if tile_data:
    print(f"Got tile from zoom {zoom_used}, layer {layer_used}, scaled: {scaled}")
```

#### `get_tile_as_png(zoom, x, y, layer=None)`

Get tile data converted to PNG format.

**Parameters:**

- `zoom` (int): Zoom level
- `x` (int): X tile coordinate
- `y` (int): Y tile coordinate
- `layer` (str, optional): Specific layer name


**Returns:**

- `bytes` or `None`: PNG image data or None if not found


**Example:**

```python
png_data = reader.get_tile_as_png(12, 655, 1582)
if png_data:
    with open('tile.png', 'wb') as f:
        f.write(png_data)
```

### Single Tile Coordinate Methods

#### `get_png_from_coordinates(lat, lon, zoom, layer=None, use_closest_zoom=False)`

Get a PNG tile using geographic coordinates.

**Parameters:**

- `lat` (float): Latitude in decimal degrees
- `lon` (float): Longitude in decimal degrees
- `zoom` (int): Zoom level
- `layer` (str, optional): Specific layer name
- `use_closest_zoom` (bool): Use closest available zoom if requested zoom unavailable


**Returns:**

- `tuple`: (png_data, x, y, actual_zoom)


**Example:**

```python
png_data, x, y, zoom_used = reader.get_png_from_coordinates(37.7749, -122.4194, 12)
if png_data:
    print(f"Retrieved tile ({x}, {y}) at zoom {zoom_used}")
```

#### `save_png_from_coordinates(lat, lon, zoom, output_path, layer=None, use_closest_zoom=False)`

Save a PNG tile to file using geographic coordinates.

**Parameters:**

- `lat` (float): Latitude in decimal degrees
- `lon` (float): Longitude in decimal degrees
- `zoom` (int): Zoom level
- `output_path` (str): Path to save the PNG file
- `layer` (str, optional): Specific layer name
- `use_closest_zoom` (bool): Use closest available zoom if requested zoom unavailable


**Returns:**

- `tuple`: (success, x, y, actual_zoom)


**Example:**

```python
success, x, y, zoom_used = reader.save_png_from_coordinates(
    37.7749, -122.4194, 12, 'san_francisco.png'
)
if success:
    print(f"Saved tile to san_francisco.png")
```

### Composite Image Methods

#### `calculate_tile_grid(center_lat, center_lon, zoom, width, height)`

Calculate the tile grid needed to cover specified dimensions.

**Parameters:**

- `center_lat` (float): Center latitude
- `center_lon` (float): Center longitude
- `zoom` (int): Zoom level
- `width` (int): Desired image width in pixels
- `height` (int): Desired image height in pixels


**Returns:**

- `dict`: Grid information with keys:

- `tiles_x`, `tiles_y`: Number of tiles in each direction
- `start_x`, `start_y`, `end_x`, `end_y`: Tile coordinate bounds
- `actual_width`, `actual_height`: Actual image dimensions
- `center_tile_x`, `center_tile_y`: Center tile coordinates
- `bounds`: Geographic bounds dictionary





**Example:**

```python
grid = reader.calculate_tile_grid(37.7749, -122.4194, 12, 800, 480)
print(f"Need {grid['tiles_x']}x{grid['tiles_y']} tiles")
print(f"Actual size: {grid['actual_width']}x{grid['actual_height']}")
```

#### `generate_composite_image(center_lat, center_lon, zoom, width=800, height=480, **kwargs)`

Generate a composite image by combining multiple tiles.

**Parameters:**

- `center_lat` (float): Center latitude
- `center_lon` (float): Center longitude
- `zoom` (int): Target zoom level
- `width` (int): Desired image width (default: 800)
- `height` (int): Desired image height (default: 480)
- `layer` (str, optional): Primary layer to use
- `use_fallback` (bool): Enable fallback mechanisms (default: True)
- `fallback_layers` (list, optional): Alternative layers
- `fallback_zooms` (list, optional): Alternative zoom levels
- `crop_to_size` (bool): Crop final image to exact dimensions (default: True)


**Returns:**

- `tuple`: (image_data, metadata)

- `image_data` (bytes): PNG image data
- `metadata` (dict): Detailed information about the generated image





**Example:**

```python
image_data, metadata = reader.generate_composite_image(
    37.7749, -122.4194, 12, 
    width=1024, height=768,
    use_fallback=True
)

print(f"Generated {metadata['actual_size'][0]}x{metadata['actual_size'][1]} image")
print(f"Tiles found: {metadata['tiles_found']}, missing: {metadata['tiles_missing']}")

with open('composite.png', 'wb') as f:
    f.write(image_data)
```

#### `save_composite_image(center_lat, center_lon, zoom, output_path, **kwargs)`

Save a composite image directly to file.

**Parameters:**

- Same as `generate_composite_image()` plus:
- `output_path` (str): Path to save the image


**Returns:**

- `tuple`: (success, metadata)


**Example:**

```python
success, metadata = reader.save_composite_image(
    37.7749, -122.4194, 12, 'san_francisco_composite.png',
    width=800, height=480
)
if success:
    print(f"Saved composite image with {metadata['tiles_found']} tiles")
```

### Utility Methods

#### `create_empty_tile(size=None, color=(240, 240, 240))`

Create an empty placeholder tile.

**Parameters:**

- `size` (int, optional): Tile size in pixels (defaults to detected tile size)
- `color` (tuple): RGB background color


**Returns:**

- `bytes`: PNG image data for empty tile


#### `check_tile_exists(zoom, x, y, layer=None)`

Check if a tile exists at given coordinates.

**Parameters:**

- `zoom` (int): Zoom level
- `x` (int): X tile coordinate
- `y` (int): Y tile coordinate
- `layer` (str, optional): Specific layer name


**Returns:**

- `bool`: True if tile exists


#### `check_available_tiles_at_location(lat, lon)`

Check which zoom levels have tiles at given coordinates.

**Parameters:**

- `lat` (float): Latitude
- `lon` (float): Longitude


**Returns:**

- `list`: List of (zoom, x, y) tuples for available tiles


#### `get_closest_zoom_level(zoom)`

Find the closest available zoom level.

**Parameters:**

- `zoom` (int): Target zoom level


**Returns:**

- `int` or `None`: Closest available zoom level


#### `get_metadata()`

Get MBTiles file metadata.

**Returns:**

- `dict`: Metadata key-value pairs


#### `close()`

Close the database connection. Always call this when finished.

---

## Command Line Interface

### Basic Syntax

```shellscript
python mbtiles-cli.py <mbtiles_file> <latitude> <longitude> <output_file> [options]
```

### Required Arguments

- `mbtiles_file`: Path to the MBTiles file
- `latitude`: Latitude in decimal degrees
- `longitude`: Longitude in decimal degrees
- `output_file`: Path for the output PNG file


### Core Options

#### `--zoom LEVEL`

Set the zoom level (default: 12)

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --zoom 15
```

#### `--layer LAYER_NAME`

Specify which layer to extract

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --layer satellite
```

### Composite Image Options

#### `--composite`

Generate a composite image from multiple tiles instead of a single tile

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --composite
```

#### `--width WIDTH` and `--height HEIGHT`

Set composite image dimensions (default: 800x480)

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --composite --width 1024 --height 768
```

#### `--no-crop`

Don't crop composite image to exact dimensions

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --composite --no-crop
```

### Fallback Options

#### `--use-fallback` / `--no-fallback`

Enable or disable fallback mechanisms (fallback enabled by default)

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --no-fallback
```

#### `--fallback-layers LAYER1 LAYER2 ...`

Specify which layers to use as fallbacks

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --fallback-layers terrain satellite
```

#### `--fallback-zooms ZOOM1 ZOOM2 ...`

Specify which zoom levels to use as fallbacks

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --fallback-zooms 11 13 14
```

#### `--use-closest-zoom`

Automatically use the closest available zoom level

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 output.png --use-closest-zoom
```

### Information Options

#### `--info`

Display MBTiles file metadata

```shellscript
python mbtiles-cli.py map.mbtiles 0 0 dummy.png --info
```

#### `--list-layers`

List available layers in the MBTiles file

```shellscript
python mbtiles-cli.py map.mbtiles 0 0 dummy.png --list-layers
```

#### `--list-zooms`

List available zoom levels

```shellscript
python mbtiles-cli.py map.mbtiles 0 0 dummy.png --list-zooms
```

#### `--check-location`

Check which zoom levels have tiles at the specified coordinates

```shellscript
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 dummy.png --check-location
```

---

## Usage Examples

### Basic Single Tile Extraction

Extract a single tile at zoom level 12:

```shellscript
python mbtiles-cli.py world.mbtiles 37.7749 -122.4194 sf_tile.png --zoom 12
```

### Generate 800x480 Composite Image

Create a composite image with fallback enabled:

```shellscript
python mbtiles-cli.py world.mbtiles 37.7749 -122.4194 sf_composite.png --composite
```

### High Resolution Composite

Generate a high-resolution composite image:

```shellscript
python mbtiles-cli.py world.mbtiles 37.7749 -122.4194 sf_hires.png --composite --width 1920 --height 1080 --zoom 14
```

### Working with Multiple Layers

Extract from a specific layer with fallbacks:

```shellscript
python mbtiles-cli.py multi_layer.mbtiles 37.7749 -122.4194 output.png --layer roads --fallback-layers terrain satellite
```

### Programmatic Usage

```python
from mbtiles import MBTilesReader

# Initialize reader
reader = MBTilesReader('world.mbtiles')

try:
    # Check what's available
    print(f"Available zoom levels: {reader.available_zooms}")
    print(f"Available layers: {reader.layers}")
    
    # Generate a composite image
    image_data, metadata = reader.generate_composite_image(
        37.7749, -122.4194, 12,  # San Francisco at zoom 12
        width=800, height=480,
        use_fallback=True
    )
    
    # Save the image
    with open('san_francisco.png', 'wb') as f:
        f.write(image_data)
    
    # Print statistics
    print(f"Generated {metadata['actual_size'][0]}x{metadata['actual_size'][1]} image")
    print(f"Used {metadata['tiles_found']} tiles, {metadata['tiles_missing']} missing")
    print(f"Geographic bounds: {metadata['bounds']}")
    
    # Extract a single tile
    success, x, y, zoom = reader.save_png_from_coordinates(
        37.7749, -122.4194, 15, 'single_tile.png'
    )
    
    if success:
        print(f"Saved single tile ({x}, {y}) at zoom {zoom}")

finally:
    reader.close()
```

### Batch Processing

```python
from mbtiles import MBTilesReader

locations = [
    ("San Francisco", 37.7749, -122.4194),
    ("New York", 40.7128, -74.0060),
    ("London", 51.5074, -0.1278)
]

reader = MBTilesReader('world.mbtiles')

try:
    for name, lat, lon in locations:
        success, metadata = reader.save_composite_image(
            lat, lon, 12, f'{name.lower().replace(" ", "_")}.png',
            width=800, height=480
        )
        if success:
            print(f"Generated {name}: {metadata['tiles_found']} tiles found")
        else:
            print(f"Failed to generate {name}")
finally:
    reader.close()
```

---

## Troubleshooting

### Common Issues

#### "No tiles found at this location"

**Cause:** The MBTiles file doesn't contain data for the specified coordinates or zoom level.

**Solutions:**

1. Check available zoom levels: `--list-zooms`
2. Check tile availability: `--check-location`
3. Use fallback mechanisms: `--use-fallback`
4. Try different zoom levels: `--use-closest-zoom`


#### "Vector tile format detected. Cannot convert to PNG directly"

**Cause:** The MBTiles file contains vector tiles (MVT/PBF format) which need rendering.

**Solutions:**

1. Use a different MBTiles file with raster tiles
2. Convert vector tiles to raster using specialized tools
3. The current tool only supports raster tile formats


#### Empty or partially empty composite images

**Cause:** Missing tiles in the requested area or zoom level.

**Solutions:**

1. Enable fallback mechanisms (enabled by default)
2. Specify fallback layers: `--fallback-layers`
3. Specify fallback zoom levels: `--fallback-zooms`
4. Check data coverage with `--check-location`


#### Permission errors

**Cause:** Insufficient permissions to read the MBTiles file or write output files.

**Solutions:**

1. Check file permissions
2. Run with appropriate user permissions
3. Ensure output directory is writable


### Performance Tips

1. **Large composite images**: Use `--no-crop` to avoid unnecessary processing for very large images
2. **Batch processing**: Reuse the same `MBTilesReader` instance for multiple operations
3. **Memory usage**: For very large composite images, consider generating smaller sections
4. **Fallback performance**: Limit fallback zoom levels to avoid excessive processing


### Debugging

Enable verbose output by checking metadata:

```python
reader = MBTilesReader('map.mbtiles')
metadata = reader.get_metadata()
for key, value in metadata.items():
    print(f"{key}: {value}")
```

Check tile availability systematically:

```shellscript
# Check what zoom levels exist
python mbtiles-cli.py map.mbtiles 0 0 dummy.png --list-zooms

# Check what layers exist  
python mbtiles-cli.py map.mbtiles 0 0 dummy.png --list-layers

# Check specific location
python mbtiles-cli.py map.mbtiles 37.7749 -122.4194 dummy.png --check-location
```

This comprehensive documentation should help you effectively use both the MBTilesReader class and the command-line interface for all your MBTiles processing needs.