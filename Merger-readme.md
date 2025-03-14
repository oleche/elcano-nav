## How to Use the MBTiles Merger

1. **Install Required Libraries**:

```plaintext
pip install Pillow
```


2. **Basic Usage**:

```plaintext
python mbtiles_merger.py output.mbtiles input1.mbtiles input2.mbtiles input3.mbtiles
```


3. **Overwrite Existing Tiles**:

```plaintext
python mbtiles_merger.py output.mbtiles input1.mbtiles input2.mbtiles --overwrite
```


4. **Skip Optimization** (for very large files):

```plaintext
python mbtiles_merger.py output.mbtiles input1.mbtiles input2.mbtiles --no-optimize
```




## How the Merger Works

The merger performs these key operations:

1. **Metadata Merging**:

1. Combines metadata from all input files
2. Special handling for geographic bounds (takes the union)
3. Merges JSON metadata like vector layers



2. **Tile Merging**:

1. Processes tiles in batches to handle large files
2. By default, keeps the first occurrence of each tile
3. With `--overwrite`, later files take precedence



3. **Optimization**:

1. Creates indices for faster querying
2. Vacuums the database to reduce file size





## Merging Strategy

When merging MBTiles files, the tool follows these rules:

1. **For overlapping geographic areas**:

1. Without `--overwrite`: The first file's tiles are kept
2. With `--overwrite`: Later files' tiles replace earlier ones



2. **For different zoom levels**:

1. All zoom levels from all files are preserved
2. This creates a more complete zoom range



3. **For metadata**:

1. Geographic bounds are expanded to include all input files
2. Vector layer definitions are merged
3. Other metadata from the first file is preserved





## Example Workflow

Here's a typical workflow for merging MBTiles files:

```shellscript
# First, check what zoom levels are in each file
python mbtiles_zoom_extract.py file1.mbtiles 0 0 dummy.png --list-zooms
python mbtiles_zoom_extract.py file2.mbtiles 0 0 dummy.png --list-zooms

# Merge the files
python mbtiles_merger.py combined.mbtiles file1.mbtiles file2.mbtiles

# Check the zoom levels in the merged file
python mbtiles_zoom_extract.py combined.mbtiles 0 0 dummy.png --list-zooms

# Extract a tile from the merged file
python mbtiles_zoom_extract.py combined.mbtiles 37.7749 -122.4194 output.png --zoom 12
```

## Notes on Merging MBTiles

- **File Size**: Merged files can become very large, especially with multiple zoom levels
- **Memory Usage**: The merger processes tiles in batches to minimize memory usage
- **Conflict Resolution**: By default, the first file's tiles take precedence; use `--overwrite` to change this
- **Vector vs. Raster**: The merger works with both vector and raster MBTiles, but doesn't convert between formats
- **Performance**: Merging large files can take significant time; the progress indicator helps track status


This tool should help you create more comprehensive MBTiles files by combining multiple sources!