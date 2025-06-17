#!/usr/bin/env python3
"""
Install WiFi Portal Service
This script installs a systemd service to automatically start the WiFi portal
on boot if no WiFi connection is available.
"""

import os
import sys
import subprocess

# Check if script is run as root
if os.geteuid() != 0:
    print("This script must be run as root. Please use sudo.")
    sys.exit(1)

# Get the current directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_command(command):
    """Run a shell command and return the output and return code"""
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    return stdout.decode(), stderr.decode(), process.returncode

def create_service_file():
    """Create the systemd service file"""
    print("Creating systemd service file...")
    
    service_content = f"""[Unit]
Description=Raspberry Pi WiFi Setup Portal
After=network.target

[Service]
ExecStart=/bin/bash -c 'if ! ping -c 1 8.8.8.8 > /dev/null 2>&1; then {SCRIPT_DIR}/wifi_portal.py; else echo "WiFi already connected, not starting portal"; fi'
WorkingDirectory={SCRIPT_DIR}
StandardOutput=inherit
StandardError=inherit
Restart=no
User=root

[Install]
WantedBy=multi-user.target
"""
    
    with open("/etc/systemd/system/wifi-portal.service", "w") as f:
        f.write(service_content)
    
    print("Service file created.")

def enable_service():
    """Enable the systemd service"""
    print("Enabling service...")
    
    run_command("systemctl daemon-reload")
    run_command("systemctl enable wifi-portal.service")
    
    print("Service enabled. It will start automatically on next boot if no WiFi connection is available.")

def main():
    """Main function"""
    print("=== Installing WiFi Portal Service ===")
    
    # Create service file
    create_service_file()
    
    # Enable service
    enable_service()
    
    print("\n=== Installation Complete ===")
    print("The WiFi portal will start automatically on boot if no WiFi connection is available.")
    print("You can manually start it with: sudo systemctl start wifi-portal")
    print("You can check its status with: sudo systemctl status wifi-portal")

if __name__ == "__main__":
    main()