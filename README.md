# elcano-nav
GPS Navigator inspired in Juan Sebastian Elcano

## How to Use with Zoom Level Support

1. **List Available Zoom Levels**:

```plaintext
python mbtiles_zoom_extract.py map.mbtiles 0 0 dummy.png --list-zooms
```


2. **Check Available Tiles at a Location**:

```plaintext
python mbtiles_zoom_extract.py map.mbtiles 37.7749 -122.4194 dummy.png --check-location
```


3. **Use the Closest Available Zoom Level**:

```plaintext
python mbtiles_zoom_extract.py map.mbtiles 37.7749 -122.4194 output.png --zoom 11 --use-closest-zoom
```


4. **Extract a Tile with Specific Zoom and Layer**:

```plaintext
python mbtiles_zoom_extract.py map.mbtiles 37.7749 -122.4194 output.png --zoom 10 --layer buildings
```




## New Features

This enhanced version adds several capabilities to address your zoom level issue:

1. **Zoom Level Detection**: The script now detects and reports all available zoom levels in the MBTiles file
2. **Closest Zoom Level Option**: With `--use-closest-zoom`, the script will automatically use the closest available zoom level if the requested one isn't available
3. **Location Checking**: The `--check-location` flag shows which zoom levels have tiles available at your specified coordinates
4. **Better Error Reporting**: The script now provides more helpful information when a tile isn't found, including available zoom levels


## Understanding MBTiles Zoom Levels

MBTiles files typically don't contain tiles for all possible zoom levels (0-22) because:

1. **Storage Efficiency**: Each additional zoom level roughly quadruples the number of tiles
2. **Data Source Limitations**: The original data may only be appropriate for certain zoom levels
3. **Purpose-Specific**: Files are often created for specific use cases with limited zoom ranges


Online viewers often:

1. Generate missing zoom levels on-the-fly by scaling existing tiles
2. Fetch missing tiles from other sources
3. Use vector tiles which can be rendered at any zoom level


## Example Workflow

If you're having trouble finding tiles at certain zoom levels:

```shellscript
# First, check what zoom levels are available in your file
python mbtiles_zoom_extract.py map.mbtiles 0 0 dummy.png --list-zooms

# Then check which zoom levels have tiles at your location
python mbtiles_zoom_extract.py map.mbtiles 37.7749 -122.4194 dummy.png --check-location

# Extract a tile using the closest available zoom level
python mbtiles_zoom_extract.py map.mbtiles 37.7749 -122.4194 output.png --zoom 11 --use-closest-zoom
```

This should help you work with MBTiles files that have limited zoom level coverage!