# Boot Splash Screen Documentation

## Overview

The boot splash screen displays "Elcano One" on the e-paper display during Raspberry Pi startup, providing a professional boot experience and visual confirmation that the display is working.

## Features

### 🎨 **Visual Design**
- **Centered Title**: "Elcano One" prominently displayed
- **Subtitle**: "GPS Navigation System" 
- **Decorative Elements**: Professional border and corner decorations
- **Status Indicator**: "Initializing..." message
- **E-paper Optimized**: High contrast black and white design

### ⚡ **Boot Integration**
- **Early Boot**: Displays before main navigation system starts
- **Fast Loading**: Optimized for quick display updates
- **Automatic**: Runs without user intervention
- **Reliable**: Robust error handling and fallback options

### 🔧 **Technical Features**
- **Font Fallbacks**: Multiple font options for reliability
- **Error Recovery**: Graceful handling of display issues
- **Logging**: Comprehensive logging for troubleshooting
- **Resource Cleanup**: Proper cleanup after display

## Installation

### Quick Installation

\`\`\`bash
# Download and run the complete installer
chmod +x install_boot_splash.sh
./install_boot_splash.sh
\`\`\`

### Manual Installation

1. **Copy Files**
\`\`\`bash
# Create project directory
mkdir -p ~/gps-navigation
cd ~/gps-navigation

# Copy required files
cp boot_splash.py ~/gps-navigation/
cp epaper_display.py ~/gps-navigation/
\`\`\`

2. **Run Setup**
\`\`\`bash
chmod +x setup_boot_splash.sh
sudo ./setup_boot_splash.sh
\`\`\`

3. **Reboot**
\`\`\`bash
sudo reboot
\`\`\`

## Boot Process Integration

### Systemd Service

The splash screen runs as a systemd service with these characteristics:

#### Service Configuration
- **Type**: `oneshot` - Runs once and exits
- **User**: Runs as the pi user (not root)
- **Timing**: Starts after filesystem is ready, before graphical session
- **Timeout**: 30 seconds maximum execution time

#### Boot Sequence
\`\`\`
1. Raspberry Pi Boot
2. Filesystem Ready
3. Boot Splash Service Starts
4. E-paper Display Shows "Elcano One"
5. Service Completes
6. Normal Boot Continues
7. Main Navigation System Starts
\`\`\`

### Service File Location
\`\`\`
/etc/systemd/system/boot-splash.service
\`\`\`

### Service Dependencies
- **After**: `local-fs.target` (filesystem ready)
- **Before**: `graphical-session.target` (before GUI)
- **Wants**: `local-fs.target` (requires filesystem)

## Configuration

### Display Settings

The splash screen is configured for the Waveshare 7.5" display:

```python
# Display dimensions
width = 800
height = 480

# Font sizes
title_font = 72    # Large title
subtitle_font = 24 # Smaller subtitle
