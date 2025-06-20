#!/usr/bin/env python3
import sqlite3
import os
import argparse
import json
import time
from pathlib import Path


class MBTilesMerger:
    def __init__(self, output_path):
        """Initialize the MBTiles merger with the output file path."""
        # Remove output file if it already exists
        if os.path.exists(output_path):
            os.remove(output_path)

        self.conn = sqlite3.connect(output_path)
        self.cursor = self.conn.cursor()
        self._create_schema()
        self.metadata = {}

    def _create_schema(self):
        """Create the basic MBTiles schema in the output file."""
        self.cursor.execute(
            """
            CREATE TABLE metadata (
                name TEXT,
                value TEXT
            )
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE tiles (
                zoom_level INTEGER,
                tile_column INTEGER,
                tile_row INTEGER,
                tile_data BLOB
            )
            """
        )

        # Create indices for faster querying
        self.cursor.execute(
            """
            CREATE UNIQUE INDEX idx_tiles ON tiles (zoom_level, tile_column, tile_row)
            """
        )

        self.conn.commit()

    def merge_file(self, input_path, priority=1, overwrite=False):
        """
        Merge an MBTiles file into the output file.

        Args:
            input_path: Path to the input MBTiles file
            priority: Priority level (higher numbers take precedence for overlapping tiles)
            overwrite: Whether to overwrite existing tiles regardless of priority

        Returns:
            tuple: (tiles_added, tiles_skipped, metadata_merged)
        """
        if not os.path.exists(input_path):
            print(f"Error: Input file {input_path} does not exist.")
            return 0, 0, 0

        try:
            # Connect to the input file
            input_conn = sqlite3.connect(input_path)
            input_cursor = input_conn.cursor()

            # Merge metadata
            metadata_merged = self._merge_metadata(input_cursor)

            # Merge tiles
            tiles_added, tiles_skipped = self._merge_tiles(input_cursor, priority, overwrite)

            # Close the input connection
            input_conn.close()

            return tiles_added, tiles_skipped, metadata_merged

        except sqlite3.Error as e:
            print(f"SQLite error when merging {input_path}: {e}")
            return 0, 0, 0

    def _merge_metadata(self, input_cursor):
        """Merge metadata from the input file into the output file."""
        try:
            # Get metadata from input file
            input_cursor.execute("SELECT name, value FROM metadata")
            input_metadata = {name: value for name, value in input_cursor.fetchall()}

            # Merge with existing metadata
            metadata_merged = 0
            for name, value in input_metadata.items():
                if name not in self.metadata:
                    self.metadata[name] = value
                    self.cursor.execute(
                        "INSERT INTO metadata (name, value) VALUES (?, ?)",
                        (name, value)
                    )
                    metadata_merged += 1
                elif name == 'bounds' and self.metadata[name] != value:
                    # For bounds, we want to take the union of the bounds
                    try:
                        existing_bounds = list(map(float, self.metadata[name].split(',')))
                        new_bounds = list(map(float, value.split(',')))

                        # Format: left,bottom,right,top
                        merged_bounds = [
                            min(existing_bounds[0], new_bounds[0]),  # left (min longitude)
                            min(existing_bounds[1], new_bounds[1]),  # bottom (min latitude)
                            max(existing_bounds[2], new_bounds[2]),  # right (max longitude)
                            max(existing_bounds[3], new_bounds[3])  # top (max latitude)
                        ]

                        merged_value = ','.join(map(str, merged_bounds))
                        self.metadata[name] = merged_value
                        self.cursor.execute(
                            "UPDATE metadata SET value = ? WHERE name = ?",
                            (merged_value, name)
                        )
                        metadata_merged += 1
                    except (ValueError, IndexError):
                        # If we can't parse the bounds, just keep the existing value
                        pass
                elif name == 'json' and self.metadata[name] != value:
                    # For JSON metadata, try to merge the objects
                    try:
                        existing_json = json.loads(self.metadata[name])
                        new_json = json.loads(value)

                        # Merge vector_layers if they exist
                        if 'vector_layers' in existing_json and 'vector_layers' in new_json:
                            # Create a map of layer IDs to layers
                            layer_map = {layer['id']: layer for layer in existing_json['vector_layers']}

                            # Add or update layers from the new file
                            for layer in new_json['vector_layers']:
                                layer_id = layer['id']
                                if layer_id not in layer_map:
                                    layer_map[layer_id] = layer

                            # Update the vector_layers in the existing JSON
                            existing_json['vector_layers'] = list(layer_map.values())

                        # Update other properties as needed
                        merged_value = json.dumps(existing_json)
                        self.metadata[name] = merged_value
                        self.cursor.execute(
                            "UPDATE metadata SET value = ? WHERE name = ?",
                            (merged_value, name)
                        )
                        metadata_merged += 1
                    except json.JSONDecodeError:
                        # If we can't parse the JSON, just keep the existing value
                        pass

            self.conn.commit()
            return metadata_merged

        except sqlite3.Error as e:
            print(f"Error merging metadata: {e}")
            return 0

    def _merge_tiles(self, input_cursor, priority, overwrite):
        """
        Merge tiles from the input file into the output file.

        Args:
            input_cursor: Cursor for the input database
            priority: Priority level for conflict resolution
            overwrite: Whether to overwrite existing tiles

        Returns:
            tuple: (tiles_added, tiles_skipped)
        """
        tiles_added = 0
        tiles_skipped = 0

        try:
            # Get the total number of tiles for progress reporting
            input_cursor.execute("SELECT COUNT(*) FROM tiles")
            total_tiles = input_cursor.fetchone()[0]

            # Process tiles in batches to avoid memory issues with large files
            batch_size = 10000
            offset = 0

            while True:
                input_cursor.execute(
                    "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles LIMIT ? OFFSET ?",
                    (batch_size, offset)
                )
                batch = input_cursor.fetchall()

                if not batch:
                    break

                for zoom_level, tile_column, tile_row, tile_data in batch:
                    # Check if the tile already exists in the output
                    self.cursor.execute(
                        "SELECT 1 FROM tiles WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
                        (zoom_level, tile_column, tile_row)
                    )

                    tile_exists = self.cursor.fetchone() is not None

                    if not tile_exists or overwrite:
                        # If the tile doesn't exist or we're overwriting, add it
                        self.cursor.execute(
                            "INSERT OR REPLACE INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
                            (zoom_level, tile_column, tile_row, tile_data)
                        )
                        tiles_added += 1
                    else:
                        tiles_skipped += 1

                # Commit after each batch
                self.conn.commit()

                # Update offset for next batch
                offset += batch_size

                # Print progress
                progress = min(100, int((offset / total_tiles) * 100))
                print(f"Progress: {progress}% ({offset}/{total_tiles} tiles processed)", end='\r')

            print("\nTile merging complete.")
            return tiles_added, tiles_skipped

        except sqlite3.Error as e:
            print(f"Error merging tiles: {e}")
            return 0, 0

    def create_indices(self):
        """Create indices on the output file for better performance."""
        try:
            print("Creating indices...")

            # Make sure we have the standard index
            self.cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_metadata ON metadata (name)
                """
            )

            self.conn.commit()
            print("Indices created.")

        except sqlite3.Error as e:
            print(f"Error creating indices: {e}")

    def vacuum(self):
        """Vacuum the database to optimize storage."""
        try:
            print("Optimizing database...")
            self.cursor.execute("VACUUM")
            self.conn.commit()
            print("Database optimized.")

        except sqlite3.Error as e:
            print(f"Error vacuuming database: {e}")

    def close(self):
        """Close the database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Merge multiple MBTiles files into a single file.'
    )
    parser.add_argument('output', help='Path to the output MBTiles file')
    parser.add_argument('inputs', nargs='+', help='Paths to input MBTiles files')
    parser.add_argument('--overwrite', action='store_true',
                        help='Overwrite existing tiles when merging')
    parser.add_argument('--no-optimize', action='store_true',
                        help='Skip optimization steps (vacuum, indices)')

    args = parser.parse_args()

    start_time = time.time()

    # Create the merger
    merger = MBTilesMerger(args.output)

    total_added = 0
    total_skipped = 0
    total_metadata = 0

    # Process each input file
    for i, input_file in enumerate(args.inputs):
        print(f"Processing file {i + 1}/{len(args.inputs)}: {input_file}")

        # Higher priority for later files (they will overwrite earlier ones if --overwrite is used)
        priority = i + 1

        added, skipped, metadata = merger.merge_file(input_file, priority, args.overwrite)

        total_added += added
        total_skipped += skipped
        total_metadata += metadata

        print(f"  Added {added} tiles, skipped {skipped} tiles, merged {metadata} metadata items")

    # Create indices and optimize unless --no-optimize is specified
    if not args.no_optimize:
        merger.create_indices()
        merger.vacuum()

    # Close the connection
    merger.close()

    end_time = time.time()
    duration = end_time - start_time

    print(f"\nMerge complete!")
    print(f"Total tiles added: {total_added}")
    print(f"Total tiles skipped: {total_skipped}")
    print(f"Total metadata items merged: {total_metadata}")
    print(f"Time taken: {duration:.2f} seconds")


if __name__ == "__main__":
    main()
