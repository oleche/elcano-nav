#!/bin/bash
# Copy all project files to the correct location

echo "Copying GPS Navigation Project Files"
echo "==================================="

# Get user info
REAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$REAL_USER)
PROJECT_DIR="$USER_HOME/gps-navigation"

echo "Target directory: $PROJECT_DIR"

# Create project directory
mkdir -p "$PROJECT_DIR"

# List of required files
FILES=(
    "gps_navigation.py"
    "mbtiles_manager.py"
    "mbtiles_to_png.py"
    "epaper_display.py"
    "database_manager.py"
    "menu_system.py"
    "navigation_config.json"
    "requirements.txt"
    "install_dependencies.sh"
    "setup_sync.sh"
    "fix_service_setup.sh"
    "debug_service.sh"
)

# Copy files if they exist in current directory
echo "Copying files..."
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$PROJECT_DIR/"
        echo "✓ Copied: $file"
    else
        echo "ℹ Not found: $file"
    fi
done

# Set permissions
chown -R $REAL_USER:$REAL_USER "$PROJECT_DIR"
chmod +x "$PROJECT_DIR"/*.py 2>/dev/null || true
chmod +x "$PROJECT_DIR"/*.sh 2>/dev/null || true

echo ""
echo "Project files copied to: $PROJECT_DIR"
echo ""
echo "Next steps:"
echo "1. cd $PROJECT_DIR"
echo "2. ./install_dependencies.sh"
echo "3. ./fix_service_setup.sh"
echo "4. Test: python3 gps_navigation.py"
