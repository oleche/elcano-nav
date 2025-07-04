#!/bin/bash
# Setup script for MBTiles assets folder

echo "Setting up MBTiles Assets Folder"
echo "================================"

# Default assets folder
DEFAULT_ASSETS_FOLDER="/opt/elcano/assets"

# Check if running as root for system-wide installation
if [ "$EUID" -eq 0 ]; then
    ASSETS_FOLDER="$DEFAULT_ASSETS_FOLDER"
    echo "Running as root - using system-wide assets folder: $ASSETS_FOLDER"
else
    # User installation
    ASSETS_FOLDER="$HOME/elcano/assets"
    echo "Running as user - using user assets folder: $ASSETS_FOLDER"
fi

# Create assets folder
echo "Creating assets folder: $ASSETS_FOLDER"
mkdir -p "$ASSETS_FOLDER"

# Set permissions
if [ "$EUID" -eq 0 ]; then
    # System-wide: make accessible to pi user
    chown -R pi:pi "$ASSETS_FOLDER"
    chmod 755 "$ASSETS_FOLDER"
else
    # User installation: ensure proper permissions
    chmod 755 "$ASSETS_FOLDER"
fi

# Create README file
cat > "$ASSETS_FOLDER/README.txt" << EOF
MBTiles Assets Folder
====================

This folder contains regional MBTiles files for the GPS Navigation System.

Usage:
- Copy your .mbtiles files to this folder
- Files will be automatically detected and used based on GPS coordinates
- Name files descriptively (e.g., "pacific_northwest.mbtiles")

Requirements:
- Files must have .mbtiles extension
- Files should contain proper metadata (bounds, name, description)
- Files should be in standard MBTiles format (SQLite database)

Examples:
- san_francisco_bay.mbtiles
- mediterranean_sea.mbtiles
- caribbean_islands.mbtiles
- north_atlantic.mbtiles

The system will automatically select the appropriate file based on your GPS position.

For more information, see the project documentation.
EOF

# Update navigation config if it exists
CONFIG_FILE="navigation_config.json"
if [ -f "$CONFIG_FILE" ]; then
    echo "Updating configuration file: $CONFIG_FILE"
    
    # Create backup
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
    
    # Update assets_folder path using Python
    python3 -c "
import json
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = json.load(f)
    
    config['assets_folder'] = '$ASSETS_FOLDER/'
    
    with open('$CONFIG_FILE', 'w') as f:
        json.dump(config, f, indent=2)
    
    print('✓ Updated assets_folder in configuration')
except Exception as e:
    print(f'✗ Error updating config: {e}')
    sys.exit(1)
"
else
    echo "Configuration file not found - will use default path"
fi

echo ""
echo "Setup completed successfully!"
echo ""
echo "Assets folder: $ASSETS_FOLDER"
echo ""
echo "Next steps:"
echo "1. Copy your MBTiles files to the assets folder:"
echo "   cp your_region.mbtiles $ASSETS_FOLDER/"
echo ""
echo "2. Verify files are detected:"
echo "   ls -la $ASSETS_FOLDER/*.mbtiles"
echo ""
echo "3. Run the navigation system:"
echo "   python3 gps_navigation.py"
echo ""
echo "The system will automatically select the appropriate regional file"
echo "based on your GPS coordinates."
