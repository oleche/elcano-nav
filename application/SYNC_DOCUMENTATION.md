# GPS Navigation System - Synchronization Documentation

## Overview

The GPS Navigation System now includes WiFi monitoring and cloud synchronization capabilities with the ElcanoNav API. This allows the device to upload GPS tracking data and synchronize with cloud-based trip management.

## Features

### Status Bar
The system now displays a status bar at the top of the screen showing:
- **WiFi Status**: "WiFi On/Off" based on connection state
- **GPS Status**: "GPS Connected/Disconnected" based on fix quality
- **Coordinates**: Current latitude/longitude when GPS is available
- **Date/Time**: Current date and time

### Synchronization
When WiFi is connected and a sync key is configured:
- **Button 3** triggers manual synchronization
- GPS data is automatically queued for upload
- System syncs with ElcanoNav API endpoints
- Logbook entries are created from GPS tracking data

## Setup

### 1. Configure Sync Key

Set your ElcanoNav sync key as an environment variable:

\`\`\`bash
export ELCANONAV_SYNC_KEY=your_10_char_key
\`\`\`

Or use the setup script:

\`\`\`bash
chmod +x setup_sync.sh
./setup_sync.sh ABC1234567
\`\`\`

### 2. Install Dependencies

\`\`\`bash
chmod +x install_dependencies.sh
./install_dependencies.sh
\`\`\`

### 3. WiFi Configuration

Ensure your Raspberry Pi is connected to WiFi:

\`\`\`bash
sudo raspi-config
# Navigate to Network Options → Wi-Fi
# Enter your network credentials
\`\`\`

## API Integration

### Supported Endpoints

The system integrates with these ElcanoNav API endpoints:

#### Device Ping
- **Endpoint**: `POST /api/sync/device/{syncKey}/ping`
- **Purpose**: Update device last sync time (heartbeat)
- **Frequency**: Every sync operation

#### Device Info
- **Endpoint**: `GET /api/sync/device/{syncKey}/info`
- **Purpose**: Retrieve device information and configuration
- **Usage**: Sync operations and device validation

#### Bulk Logbook Sync
- **Endpoint**: `POST /api/logbook/sync/{syncKey}/bulk`
- **Purpose**: Upload GPS tracking data as logbook entries
- **Data**: Location, speed, heading, timestamp

### Data Format

GPS data is formatted as logbook entries:

\`\`\`json
{
  "entries": [
    {
      "timestamp": "2023-07-20T14:00:00.000Z",
      "location": {
        "longitude": -122.4194,
        "latitude": 37.7749
      },
      "vessel": {
        "speed": 8.5,
        "course": 180
      },
      "content": "GPS position update - Speed: 8.5 km/h"
    }
  ]
}
\`\`\`

## Operation

### Automatic Data Collection
- GPS positions are automatically queued when GPS fix is available
- Queue size is limited to 1000 entries to manage memory
- Data includes: latitude, longitude, speed, heading, altitude, timestamp

### Manual Synchronization
1. Ensure WiFi is connected (status bar shows "WiFi On")
2. Press **Button 3** to trigger sync
3. System will:
   - Send device ping
   - Upload queued GPS data
   - Retrieve device information
   - Update sync status on display

### Sync Status Display
The right side of the display shows:
- Current sync status ("Syncing...", "Last sync: HH:MM", "Not synced")
- Queue size if entries are waiting to sync
- WiFi connection status

## Configuration

### Environment Variables

\`\`\`bash
# Required: Your ElcanoNav sync key
export ELCANONAV_SYNC_KEY=ABC1234567

# Optional: Custom API base URL
export ELCANONAV_API_URL=https://api.elcanonav.com
\`\`\`

### Config File Settings

Add to `navigation_config.json`:

\`\`\`json
{
  "sync_settings": {
    "api_base_url": "https://api.elcanonav.com",
    "auto_sync_interval": 300,
    "max_queue_size": 1000,
    "batch_size": 100
  }
}
\`\`\`

## Troubleshooting

### WiFi Issues

**WiFi shows "Off" but connection exists:**
- Check `iwconfig` output manually
- Verify wireless interface is up: `sudo ifconfig wlan0 up`
- Restart networking: `sudo systemctl restart networking`

**WiFi connects but sync fails:**
- Test internet connectivity: `ping google.com`
- Check firewall settings
- Verify API endpoint accessibility

### Sync Issues

**"No sync key configured":**
- Set environment variable: `export ELCANONAV_SYNC_KEY=your_key`
- Add to ~/.bashrc for persistence
- Restart the application

**Sync fails with HTTP errors:**
- Verify sync key is valid (10 characters)
- Check API endpoint is accessible
- Review logs for detailed error messages

**Queue keeps growing:**
- Check internet connectivity
- Verify API credentials
- Monitor sync success in logs

### API Errors

**404 Device not found:**
- Verify sync key is correct
- Ensure device is registered in ElcanoNav system
- Contact ElcanoNav support if device should exist

**Rate limiting:**
- Reduce sync frequency
- Implement exponential backoff
- Check API rate limits

## Logging

Sync operations are logged to `gps_navigation.log`:

\`\`\`bash
# Monitor sync activity
tail -f gps_navigation.log | grep -i sync

# Check for errors
grep -i error gps_navigation.log | tail -20
\`\`\`

## Security

### API Security
- Sync keys provide device-level authentication
- No user credentials stored on device
- HTTPS encryption for all API communications

### Local Security
- Sync key stored as environment variable
- No sensitive data cached locally
- GPS data queued in memory only

## Performance

### Memory Usage
- GPS data queue limited to 1000 entries
- Automatic cleanup of old entries
- Batch uploads to minimize memory usage

### Network Usage
- Efficient JSON payload format
- Batch uploads (up to 100 entries per request)
- Only uploads when WiFi is available

### Battery Impact
- Sync only when WiFi connected
- Minimal background processing
- E-paper display updates only when needed

## Future Enhancements

### Planned Features
- Automatic sync intervals (configurable)
- Trip management integration
- Offline map tile synchronization
- Device configuration sync
- Route planning sync

### Button 4 Reservations
Button 4 is reserved for future features such as:
- Trip start/stop control
- Waypoint marking
- Emergency beacon
- Display mode switching
