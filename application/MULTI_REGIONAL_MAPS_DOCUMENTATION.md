# Multi-Regional Maps Documentation

## Overview

The GPS Navigation System now supports multiple regional MBTiles files, automatically selecting the appropriate map based on GPS coordinates. This enables seamless navigation across different geographic regions without manual file switching.

## 🗺️ **Key Features**

### **Automatic Region Detection**
- **Smart Selection**: Automatically chooses the correct regional file based on GPS coordinates
- **Seamless Switching**: Transitions between regions without user intervention
- **Performance Optimization**: Keeps track of current file to minimize lookup time
- **Memory Management**: Intelligently manages multiple open files

### **Multi-File Support**
- **Folder-Based**: Scans assets folder for all .mbtiles files
- **Metadata Reading**: Extracts bounds and region information from each file
- **Fallback Handling**: Graceful handling when no map covers current coordinates
- **Error Recovery**: Continues operation even with corrupted or missing files

## 🏗️ **Architecture**

### **MBTilesManager Class**
Central component that handles:
- **File Discovery**: Scans assets folder for .mbtiles files
- **Bounds Checking**: Determines which file contains given coordinates
- **Memory Management**: Opens/closes files based on usage and memory limits
- **Performance Optimization**: Caches frequently used files

### **File Selection Logic**
\`\`\`
1. Check current file first (performance optimization)
2. If coordinates outside current bounds:
   - Search all available files
   - Find file containing coordinates
   - Switch to new file
   - Update current file tracking
3. If no file found:
   - Display "No Map Available"
   - Show available regions
\`\`\`

## 📁 **Folder Structure**

### **Recommended Layout**
\`\`\`
/opt/elcano/assets/
├── pacific_northwest.mbtiles    # Regional files
├── mediterranean_sea.mbtiles
├── caribbean_islands.mbtiles
├── san_francisco_bay.mbtiles
├── north_atlantic.mbtiles
└── README.txt                   # Documentation
\`\`\`

### **File Naming Conventions**
\`\`\`bash
# Good examples:
pacific_northwest.mbtiles
mediterranean_sea.mbtiles
caribbean_islands.mbtiles
san_francisco_bay.mbtiles
english_channel.mbtiles
great_lakes.mbtiles

# Include geographic region in filename for clarity
\`\`\`

## ⚙️ **Configuration**

### **Updated Config File**
\`\`\`json
{
  "assets_folder": "/opt/elcano/assets/",
  "mbtiles_settings": {
    "max_open_files": 3,        // Memory management
    "cache_timeout": 300,       // Close unused files (seconds)
    "auto_switch": true         // Enable automatic switching
  }
}
\`\`\`

### **Memory Management Settings**
- **max_open_files**: Maximum number of files kept open simultaneously
- **cache_timeout**: Time before unused files are closed (seconds)
- **auto_switch**: Enable/disable automatic file switching

## 🚀 **Usage**

### **Command Line Options**
\`\`\`bash
# Use default assets folder from config
python3 gps_navigation.py

# Specify custom assets folder
python3 gps_navigation.py /path/to/custom/assets/

# With debug logging to see file switching
python3 gps_navigation.py --log-level DEBUG
\`\`\`

### **Setup Process**
\`\`\`bash
# 1. Run setup script
chmod +x setup_assets_folder.sh
./setup_assets_folder.sh

# 2. Copy regional MBTiles files
cp your_region1.mbtiles /opt/elcano/assets/
cp your_region2.mbtiles /opt/elcano/assets/

# 3. Verify files are detected
ls -la /opt/elcano/assets/*.mbtiles

# 4. Run navigation system
python3 gps_navigation.py
\`\`\`

## 📊 **Performance Features**

### **Smart Caching**
- **Current File Priority**: Always checks current file first
- **LRU Management**: Least recently used files closed first
- **Memory Limits**: Configurable maximum open files
- **Lazy Loading**: Files opened only when needed

### **Resource Usage**
\`\`\`
Memory per open file: ~50-100MB
Typical usage (3 files): 150-300MB
Metadata cache: ~1KB per file
File switching time: <1 second
\`\`\`

### **Optimization Strategies**
- **Regional Persistence**: Boats typically stay in one region
- **Efficient Bounds Checking**: Fast coordinate-in-bounds calculations
- **Minimal File Operations**: Reduce disk I/O through caching

## 🔍 **Display Information**

### **Enhanced Status Display**
The navigation screen now shows:
- **Current Map File**: Active regional file name
- **Region Name**: Descriptive name from file metadata
- **File Status**: Coverage and tile availability
- **Automatic Switching**: Real-time region transitions

### **No Map Available Screen**
When no regional file covers current coordinates:
- **Position Display**: Current GPS coordinates
- **Available Regions**: List of loaded regional files
- **Coverage Info**: Bounds information for each region

## 🛠️ **File Requirements**

### **MBTiles Standards**
- **Format**: Standard MBTiles (SQLite database)
- **Extension**: Must have .mbtiles extension
- **Metadata**: Should include bounds, name, description
- **Zoom Levels**: Appropriate for navigation (typically 8-18)

### **Required Metadata**
\`\`\`sql
-- Essential metadata in MBTiles file:
INSERT INTO metadata VALUES('name', 'Pacific Northwest');
INSERT INTO metadata VALUES('description', 'Coastal waters from California to Alaska');
INSERT INTO metadata VALUES('bounds', '-125.0,32.0,-117.0,49.0');
INSERT INTO metadata VALUES('minzoom', '8');
INSERT INTO metadata VALUES('maxzoom', '18');
\`\`\`

### **Bounds Format**
Bounds should be in the format: `"min_lon,min_lat,max_lon,max_lat"`
- **min_lon**: Western boundary (longitude)
- **min_lat**: Southern boundary (latitude)  
- **max_lon**: Eastern boundary (longitude)
- **max_lat**: Northern boundary (latitude)

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Files Not Detected**
\`\`\`bash
# Check assets folder exists
ls -la /opt/elcano/assets/

# Verify .mbtiles extension
ls -la /opt/elcano/assets/*.mbtiles

# Check file permissions
ls -la /opt/elcano/assets/

# Test file format
file /opt/elcano/assets/your_file.mbtiles
# Should show: SQLite 3.x database
\`\`\`

#### **No File Selected for Coordinates**
\`\`\`bash
# Check file bounds in metadata
sqlite3 your_file.mbtiles "SELECT * FROM metadata WHERE name='bounds';"

# Verify coordinate format (should be: min_lon,min_lat,max_lon,max_lat)
# Example: "-125.0,32.0,-117.0,49.0"

# Test coordinate inclusion manually
# Ensure: min_lon <= your_lon <= max_lon AND min_lat <= your_lat <= max_lat
\`\`\`

#### **Memory Issues**
\`\`\`bash
# Reduce max_open_files in config
"max_open_files": 2

# Reduce cache_timeout
"cache_timeout": 180

# Monitor memory usage
htop
\`\`\`

### **Debug Logging**
\`\`\`bash
# Enable debug logging to see file operations
python3 gps_navigation.py --log-level DEBUG

# Look for these log messages:
# "Found MBTiles file: filename.mbtiles"
# "Switching to MBTiles file: filename.mbtiles for coordinates lat, lon"
# "Coordinates still in current file: filename.mbtiles"
# "No MBTiles file found for coordinates lat, lon"
\`\`\`

### **File Validation**
\`\`\`bash
# Check MBTiles file integrity
sqlite3 your_file.mbtiles "PRAGMA integrity_check;"

# Verify required tables exist
sqlite3 your_file.mbtiles ".tables"
# Should show: metadata, tiles

# Check metadata completeness
sqlite3 your_file.mbtiles "SELECT name, value FROM metadata;"

# Verify bounds format
sqlite3 your_file.mbtiles "SELECT value FROM metadata WHERE name='bounds';"
\`\`\`

## 🌍 **Regional Coverage Examples**

### **Maritime Regions**
\`\`\`
north_atlantic.mbtiles      - North Atlantic shipping lanes
mediterranean_sea.mbtiles   - Mediterranean Sea
caribbean_islands.mbtiles   - Caribbean Islands
pacific_northwest.mbtiles   - US/Canada West Coast
english_channel.mbtiles     - English Channel
gulf_of_mexico.mbtiles      - Gulf of Mexico
\`\`\`

### **Coastal Areas**
\`\`\`
san_francisco_bay.mbtiles   - SF Bay Area
puget_sound.mbtiles         - Seattle/Tacoma area
chesapeake_bay.mbtiles      - Maryland/Virginia
great_lakes.mbtiles         - Great Lakes region
florida_keys.mbtiles        - Florida Keys
maine_coast.mbtiles         - Maine coastal waters
\`\`\`

### **International Waters**
\`\`\`
north_sea.mbtiles           - North Sea (Europe)
baltic_sea.mbtiles          - Baltic Sea
red_sea.mbtiles             - Red Sea
persian_gulf.mbtiles        - Persian Gulf
south_china_sea.mbtiles     - South China Sea
\`\`\`

## 🔄 **Migration from Single File**

### **Converting Existing Setup**
\`\`\`bash
# 1. Create assets folder
mkdir -p /opt/elcano/assets/

# 2. Move existing MBTiles file
mv your_old_map.mbtiles /opt/elcano/assets/

# 3. Update configuration
# Change from single file path to assets folder path

# 4. Update command line usage
# Old: python3 gps_navigation.py map.mbtiles
# New: python3 gps_navigation.py
\`\`\`

### **Backward Compatibility**
- Single file in assets folder works perfectly
- Existing configurations easily updated
- No data loss during migration
- Gradual addition of regional files supported

## 📈 **Performance Monitoring**

### **Log Analysis**
\`\`\`bash
# Monitor file switching activity
tail -f gps_navigation.log | grep -i "switching\|mbtiles"

# Check memory usage
grep -i "memory\|cache" gps_navigation.log

# Monitor coordinate coverage
grep -i "coordinates.*file" gps_navigation.log
\`\`\`

### **System Monitoring**
\`\`\`bash
# Memory usage
htop

# Disk I/O
iotop

# File handles
lsof | grep mbtiles
\`\`\`

This multi-regional system provides seamless navigation across different geographic areas while maintaining optimal performance and memory efficiency.
