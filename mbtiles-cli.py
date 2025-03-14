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
        description='Extract a PNG tile from an MBTiles file based on geographic coordinates.'
    )
    parser.add_argument('mbtiles_file', help='Path to the MBTiles file')
    parser.add_argument('latitude', type=float, help='Latitude in decimal degrees')
    parser.add_argument('longitude', type=float, help='Longitude in decimal degrees')
    parser.add_argument('output_file', help='Path to save the output PNG file')
    parser.add_argument('--zoom', type=int, default=12, help='Zoom level (default: 12)')
    parser.add_argument('--layer', help='Specific layer to extract (if available)')
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
            return

        # Determine which layer to use
        layer = args.layer
        if layer and layer not in reader.layers:
            print(f"Warning: Layer '{layer}' not found. Available layers: {', '.join(reader.layers)}")
            print(f"Falling back to default layer.")
            layer = None

        # Check if the requested zoom level is available
        if args.zoom not in reader.available_zooms and not args.use_closest_zoom:
            print(f"Warning: Zoom level {args.zoom} not available in this MBTiles file.")
            print(f"Available zoom levels: {', '.join(map(str, reader.available_zooms))}")
            print("Use --use-closest-zoom to automatically select the closest available zoom level.")
            return

        # Extract and save the tile
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

    finally:
        # Always close the connection
        reader.close()


if __name__ == "__main__":
    main()