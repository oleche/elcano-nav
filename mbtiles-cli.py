#!/usr/bin/env python3
import sqlite3
import io
import math
import json
import argparse
from mbtiles import MBTilesReader


def main():
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(
        description='Extract PNG tiles or composite images from an MBTiles file based on geographic coordinates.'
    )
    parser.add_argument('mbtiles_file', help='Path to the MBTiles file')
    parser.add_argument('latitude', type=float, help='Latitude in decimal degrees')
    parser.add_argument('longitude', type=float, help='Longitude in decimal degrees')
    parser.add_argument('output_file', help='Path to save the output PNG file')
    parser.add_argument('--zoom', type=int, default=12, help='Zoom level (default: 12)')
    parser.add_argument('--layer', help='Specific layer to extract (if available)')

    # Image generation options
    parser.add_argument('--composite', action='store_true',
                        help='Generate a composite image from multiple tiles')
    parser.add_argument('--width', type=int, default=800,
                        help='Width of composite image in pixels (default: 800)')
    parser.add_argument('--height', type=int, default=480,
                        help='Height of composite image in pixels (default: 480)')
    parser.add_argument('--no-crop', action='store_true',
                        help='Do not crop composite image to exact dimensions')

    # Fallback options
    parser.add_argument('--use-fallback', action='store_true', default=True,
                        help='Use fallback mechanisms for missing tiles (default: enabled)')
    parser.add_argument('--no-fallback', action='store_true',
                        help='Disable fallback mechanisms')
    parser.add_argument('--fallback-layers', nargs='*',
                        help='Specific layers to use as fallbacks')
    parser.add_argument('--fallback-zooms', type=int, nargs='*',
                        help='Specific zoom levels to use as fallbacks')

    # Information options
    parser.add_argument('--list-layers', action='store_true', help='List available layers in the MBTiles file')
    parser.add_argument('--list-zooms', action='store_true', help='List available zoom levels in the MBTiles file')
    parser.add_argument('--check-location', action='store_true',
                        help='Check which zoom levels have tiles at the specified location')
    parser.add_argument('--use-closest-zoom', action='store_true',
                        help='Use the closest available zoom level if the requested one is not available')
    parser.add_argument('--info', action='store_true', help='Display metadata information about the MBTiles file')

    args = parser.parse_args()

    # Initialize the MBTiles reader
    reader = MBTilesReader(args.mbtiles_file)

    try:
        # If --list-zooms flag is provided, display available zoom levels and exit
        if args.list_zooms:
            print(f"Available zoom levels in {args.mbtiles_file}:")
            if reader.available_zooms:
                for zoom in reader.available_zooms:
                    print(f"  - {zoom}")
            else:
                print("  No zoom levels found.")
            return

        # If --list-layers flag is provided, display available layers and exit
        if args.list_layers:
            print(f"Available layers in {args.mbtiles_file}:")
            for layer in reader.layers:
                print(f"  - {layer}")
            print(f"\nFile format: {reader.format}")
            print(f"Tile size: {reader.tile_size}x{reader.tile_size}")
            return

        # If --check-location flag is provided, check available tiles at the location
        if args.check_location:
            available_tiles = reader.check_available_tiles_at_location(args.latitude, args.longitude)
            print(f"Available tiles at location ({args.latitude}, {args.longitude}):")
            if available_tiles:
                for zoom, x, y in available_tiles:
                    print(f"  - Zoom level {zoom}: Tile ({x}, {y})")
            else:
                print("  No tiles found at this location.")
            return

        # If --info flag is provided, display metadata and exit
        if args.info:
            metadata = reader.get_metadata()
            print("MBTiles Metadata:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
            print(f"\nDetected tile size: {reader.tile_size}x{reader.tile_size}")
            return

        # Determine which layer to use
        layer = args.layer
        if layer and layer not in reader.layers:
            print(f"Warning: Layer '{layer}' not found. Available layers: {', '.join(reader.layers)}")
            print(f"Falling back to default layer.")
            layer = None

        # Handle fallback settings
        use_fallback = args.use_fallback and not args.no_fallback
        fallback_layers = args.fallback_layers
        fallback_zooms = args.fallback_zooms

        # Check if the requested zoom level is available
        if args.zoom not in reader.available_zooms and not args.use_closest_zoom and not use_fallback:
            print(f"Warning: Zoom level {args.zoom} not available in this MBTiles file.")
            print(f"Available zoom levels: {', '.join(map(str, reader.available_zooms))}")
            print("Use --use-closest-zoom or --use-fallback to handle missing zoom levels.")
            return

        # Generate composite image or single tile
        if args.composite:
            print(f"Generating composite image ({args.width}x{args.height}) at zoom level {args.zoom}...")

            success, metadata = reader.save_composite_image(
                args.latitude, args.longitude, args.zoom, args.output_file,
                width=args.width, height=args.height, layer=layer,
                use_fallback=use_fallback, fallback_layers=fallback_layers,
                fallback_zooms=fallback_zooms, crop_to_size=not args.no_crop
            )

            if success:
                print(f"Successfully generated composite image: {args.output_file}")
                print(f"Image details:")
                print(f"  - Final size: {metadata['actual_size'][0]}x{metadata['actual_size'][1]} pixels")
                print(f"  - Tile grid: {metadata['tiles_grid'][0]}x{metadata['tiles_grid'][1]} tiles")
                print(f"  - Tiles found: {metadata['tiles_found']}")
                print(f"  - Tiles missing: {metadata['tiles_missing']}")
                print(f"  - Tiles scaled: {metadata['tiles_scaled']}")
                print(f"  - Geographic bounds:")
                print(f"    North: {metadata['bounds']['north']:.6f}")
                print(f"    South: {metadata['bounds']['south']:.6f}")
                print(f"    West: {metadata['bounds']['west']:.6f}")
                print(f"    East: {metadata['bounds']['east']:.6f}")
            else:
                print("Failed to generate composite image.")
        else:
            # Extract single tile (existing functionality)
            success, x, y, actual_zoom = reader.save_png_from_coordinates(
                args.latitude, args.longitude, args.zoom, args.output_file, layer, args.use_closest_zoom
            )

            if success:
                layer_info = f" from layer '{layer}'" if layer else ""
                zoom_info = f" (requested: {args.zoom})" if actual_zoom != args.zoom else ""
                print(
                    f"Successfully extracted tile at coordinates ({x}, {y}) at zoom level {actual_zoom}{zoom_info}{layer_info} to {args.output_file}")
            else:
                layer_info = f" in layer '{layer}'" if layer else ""
                print(f"No tile found at coordinates ({x}, {y}){layer_info} for zoom level {actual_zoom}")
                print(f"Available zoom levels: {', '.join(map(str, reader.available_zooms))}")
                print("Use --check-location to see which zoom levels have tiles at this location.")
                print("Or try --composite with --use-fallback for better coverage.")

    finally:
        # Always close the connection
        reader.close()


if __name__ == "__main__":
    main()
