# GPS Navigation System - Enhanced Documentation

## Overview

The GPS Navigation System has been significantly enhanced with database storage, trip management, menu system, and comprehensive API synchronization. This document covers all the new features and functionality.

## New Features

### 🗄️ Database Storage (SQLite)
- **Local Storage**: All trip data, map points, and logbook entries stored locally
- **Offline Capability**: System works without internet connection
- **Data Persistence**: Trip progress and logbook entries preserved between sessions
- **Automatic Sync**: Data synchronized when WiFi becomes available

### 📱 Menu System
- **Trip Selection**: Browse and select available trips
- **Trip Management**: Start/stop trips with status tracking
- **Navigation**: Use zoom buttons to navigate menus
- **Visual Interface**: Clear menu display optimized for e-paper

### 🗺️ Trip Visualization
- **Route Overlay**: Display trip map points as route lines on the map
- **Real-time Tracking**: Show current position relative to planned route
- **Trip Progress**: Visual indication of trip completion

### 📊 Enhanced Logbook
- **Automatic Entries**: Create logbook entries on significant GPS changes
- **Trip Association**: All entries linked to active trip
- **Real-time Sync**: Immediate upload when WiFi available
- **Offline Queue**: Store entries locally when offline

## Database Schema

### Tables Created

#### device_info
Stores device information from API sync
- Device details, model, owner information
- Last sync timestamps

#### trips
Stores trip information
- Trip details, status, distance, duration
- Local status tracking for offline changes
- Active trip designation

#### map_points
Stores route points for each trip
- Geographic coordinates, sequence, metadata
- Distance and time calculations

#### logbook_entries
Stores GPS tracking entries
- Position, speed, heading data
- Trip association and sync status

#### sync_status
Stores synchronization metadata
- Last sync times, status information

## Button Controls

### Enhanced Button Functions

#### Button 1 (Zoom In / Navigate Up)
- **Map Mode**: Increase zoom level
- **Menu Mode**: Navigate up in menu lists

#### Button 2 (Zoom Out / Navigate Down)  
- **Map Mode**: Decrease zoom level
- **Menu Mode**: Navigate down in menu lists

#### Button 3 (Sync / Select)
- **Map Mode**: Trigger synchronization (when WiFi available)
- **Menu Mode**: Select current menu item

#### Button 4 (Menu Toggle / Back)
- **Map Mode**: Open trip menu
- **Menu Mode**: Go back or close menu

## Menu System

### Menu States

#### Trip List
- Shows all available trips from database
- Highlights active trip (if any)
- Prevents selection of other trips when one is active

#### Trip Options
- **Start Trip**: Begin tracking for selected trip
- **Stop Trip**: Complete active trip
- **Back**: Return to previous menu or map

### Navigation Flow

\`\`\`
Map View → Button 4 → Trip List
         ↓
    Select Trip → Trip Options
         ↓
    Start/Stop → Back to Map
\`\`\`

## Trip Management

### Trip Lifecycle

1. **Sync Trips**: Download available trips from API
2. **Select Trip**: Choose trip from menu
3. **Start Trip**: Begin active tracking
4. **Track Progress**: Automatic logbook entries
5. **Stop Trip**: Complete and sync final status

### Status Management

#### Trip Statuses
- `NOT_STARTED`: Trip available but not begun
- `IN_ROUTE`: Trip actively being tracked
- `COMPLETED`: Trip finished successfully
- `NOT_COMPLETED`: Trip stopped without completion

#### Local vs Remote Status
- **Local Status**: Immediate status changes stored locally
- **Remote Status**: Synced to API when WiFi available
- **Conflict Resolution**: Local changes take precedence

## Synchronization

### Automatic Sync Events

#### Device Ping (Every Minute)
- Updates device last-seen timestamp
- Maintains connection with API
- Only when WiFi connected

#### Full Sync (Manual/Startup)
- Downloads all trip data and map points
- Uploads pending status changes
- Syncs queued logbook entries

#### Real-time Logbook Sync
- Immediate upload of GPS changes during active trip
- Falls back to queue when offline
- Bulk upload when WiFi restored

### Sync Data Flow

\`\`\`
GPS Change → Logbook Entry → Local Database
     ↓
WiFi Available? → Yes → Immediate API Upload
     ↓
    No → Queue for Later Sync
\`\`\`

## Enhanced Ping Functionality

### Position Reporting

The system now automatically reports the vessel's position during ping operations:

#### Automatic Position Updates
- **Every Minute**: When WiFi connected, ping includes current GPS position
- **Manual Sync**: Button 3 sync includes position data in ping
- **Position Data**: Latitude, longitude, heading, and course transmitted
- **Fallback**: Ping works without position data if GPS unavailable

#### Data Transmitted

\`\`\`json
{
  "lastLatitude": 34.0522,
  "lastLongitude": -118.2437,
  "lastHeading": 275,
  "lastCourse": 280
}
\`\`\`

#### Position Storage
- **Local Storage**: Last ping position stored in database
- **Sync Status**: Position data available for status display
- **History**: Ping timestamps and positions tracked

### Benefits

#### Fleet Management
- **Real-time Tracking**: Know exact vessel positions
- **Course Monitoring**: Track heading and course changes
- **Connectivity Status**: Last known position when offline

#### Safety Features
- **Position Reporting**: Automatic position updates for safety
- **Emergency Tracking**: Last known position available
- **Route Monitoring**: Track vessel progress remotely

### Implementation Details

#### GPS Integration
- Position data only sent when GPS fix available
- Heading used for both heading and course fields
- Automatic fallback to ping without position

#### Network Efficiency
- Position data included in existing ping requests
- No additional network overhead
- Efficient JSON payload format

#### Error Handling
- Graceful degradation when GPS unavailable
- Ping continues to work without position data
- Robust error logging and recovery

### Usage Examples

#### Viewing Last Ping Position

\`\`\`bash
# Check last ping position in database
sqlite3 navigation.db "SELECT value FROM sync_status WHERE key='last_ping_position';"

# View ping history
sqlite3 navigation.db "SELECT * FROM sync_status WHERE key LIKE 'last_ping%';"
\`\`\`

#### API Response Example

\`\`\`json
{
  "message": "Device sync time updated",
  "syncKey": "ABC1234567",
  "lastUpdate": "2023-07-20T15:30:00.000Z",
  "lastLatitude": 34.0522,
  "lastLongitude": -118.2437,
  "lastHeading": 275,
  "lastCourse": 280
}
\`\`\`

This enhancement provides comprehensive vessel tracking capabilities while maintaining the existing ping functionality for devices without GPS or when GPS is unavailable.

## Installation

### Database Setup

SQLite is included with Raspberry Pi OS. The system automatically creates the database on first run:

\`\`\`bash
# Database file created automatically
ls -la navigation.db

# View database structure
sqlite3 navigation.db ".schema"
\`\`\`

### Enhanced Installation

\`\`\`bash
chmod +x install_dependencies.sh
./install_dependencies.sh
\`\`\`

### Environment Setup

\`\`\`bash
# Set sync key
export ELCANONAV_SYNC_KEY=ABC1234567

# Optional: Custom API URL
export ELCANONAV_API_URL=https://api.elcanonav.com
\`\`\`

## Configuration

### Enhanced Config File

\`\`\`json
{
  "default_zoom": 14,
  "min_zoom": 8,
  "max_zoom": 18,
  "update_interval": 30,
  "button_pins": {
    "zoom_in": 16,
    "zoom_out": 20,
    "button3": 21,
    "button4": 26
  },
  "gps_settings": {
    "port": "/dev/ttyAMA0",
    "baudrate": 9600,
    "speed_change_threshold": 2.0,
    "heading_change_threshold": 15.0
  },
  "sync_settings": {
    "api_base_url": "https://api.elcanonav.com",
    "ping_interval": 60,
    "auto_sync_logbook": true
  }
}
\`\`\`

## Usage Examples

### Basic Operation

\`\`\`bash
# Start the enhanced system
python3 gps_navigation.py /path/to/map.mbtiles

# With debug logging
python3 gps_navigation.py map.mbtiles --log-level DEBUG
\`\`\`

### Trip Management Workflow

1. **Initial Sync**: Press Button 3 to download trips
2. **Select Trip**: Press Button 4 → Navigate with Buttons 1/2 → Select with Button 3
3. **Start Tracking**: Choose "Start Trip" from menu
4. **Monitor Progress**: GPS changes automatically logged
5. **Complete Trip**: Press Button 4 → Select "Stop Trip"

### Database Operations

\`\`\`bash
# View trips
sqlite3 navigation.db "SELECT title, status, date FROM trips;"

# View logbook entries for a trip
sqlite3 navigation.db "SELECT timestamp, latitude, longitude, speed FROM logbook_entries WHERE trip_id='TRIP_ID';"

# Check sync status
sqlite3 navigation.db "SELECT * FROM sync_status;"
\`\`\`

## API Integration

### Enhanced Endpoints

#### Trip Status Updates
\`\`\`bash
# Update trip status
PUT /api/sync/device/{syncKey}/trip/{tripId}
{
  "status": "IN_ROUTE"
}
\`\`\`

#### Bulk Logbook Sync
\`\`\`bash
# Upload tracking data
POST /api/logbook/sync/{syncKey}/bulk
{
  "entries": [
    {
      "trip": "trip_id",
      "timestamp": "2023-07-20T14:00:00.000Z",
      "location": {
        "longitude": -122.4194,
        "latitude": 37.7749
      },
      "vessel": {
        "speed": 8.5,
        "course": 180
      }
    }
  ]
}
\`\`\`

## Troubleshooting

### Database Issues

**Database locked errors:**
\`\`\`bash
# Check for processes using database
lsof navigation.db

# Restart application if needed
sudo systemctl restart gps-navigation
\`\`\`

**Corrupted database:**
\`\`\`bash
# Backup and recreate
mv navigation.db navigation.db.backup
# Restart application to recreate
\`\`\`

### Menu Navigation Issues

**Menu not responding:**
- Check button connections
- Verify GPIO pin configuration
- Review logs for button press events

**Trip not starting:**
- Ensure GPS fix is available
- Check WiFi for immediate sync
- Verify trip status in database

### Sync Issues

**Logbook entries not syncing:**
\`\`\`bash
# Check unsynced entries
sqlite3 navigation.db "SELECT COUNT(*) FROM logbook_entries WHERE synced=0;"

# Manual sync trigger
# Press Button 3 when WiFi connected
\`\`\`

**Trip status out of sync:**
\`\`\`bash
# Check trips needing sync
sqlite3 navigation.db "SELECT title, status, local_status FROM trips WHERE needs_sync=1;"
\`\`\`

## Performance Optimization

### Database Optimization

\`\`\`bash
# Vacuum database periodically
sqlite3 navigation.db "VACUUM;"

# Analyze query performance
sqlite3 navigation.db "ANALYZE;"
\`\`\`

### Memory Management

- Logbook entries automatically managed
- Old entries can be archived
- Database size monitored

### Network Efficiency

- Batch uploads minimize requests
- Intelligent sync timing
- Offline queue management

## Security Considerations

### Data Protection
- Local database not encrypted (consider encryption for sensitive data)
- Sync key stored as environment variable
- No user credentials stored locally

### Network Security
- HTTPS for all API communications
- Device-level authentication via sync key
- No sensitive data in logs

## Future Enhancements

### Planned Features
- Database encryption
- Trip planning integration
- Weather data integration
- Emergency features
- Multi-device synchronization

### Extensibility
- Plugin system for custom overlays
- Custom logbook entry types
- Advanced route analysis
- Integration with other marine systems

This enhanced system provides a complete offline-capable GPS navigation solution with comprehensive trip management and cloud synchronization capabilities.
