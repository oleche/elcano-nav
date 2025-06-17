#!/usr/bin/env python3
"""
Disable AP Mode and Connect to WiFi
This script disables AP mode and connects to a configured WiFi network.
"""

import os
import sys
import subprocess
import time
import shutil

# Check if script is run as root
if os.geteuid() != 0:
    print("This script must be run as root. Please use sudo.")
    sys.exit(1)

def run_command(command):
    """Run a shell command and return the output and return code"""
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    return stdout.decode(), stderr.decode(), process.returncode

def disable_ap_mode():
    """Disable AP mode and restore original network configuration"""
    print("Disabling AP mode...")
    
    # Stop and disable hostapd and dnsmasq
    run_command("systemctl stop hostapd")
    run_command("systemctl stop dnsmasq")
    run_command("systemctl disable hostapd")
    run_command("systemctl disable dnsmasq")
    
    # Restore original network configuration
    if os.path.exists("/etc/dhcpcd.conf.bak"):
        shutil.copy2("/etc/dhcpcd.conf.bak", "/etc/dhcpcd.conf")
        print("Restored original dhcpcd configuration.")
    
    # Restart networking services
    run_command("systemctl restart dhcpcd")
    
    print("AP mode disabled.")

def connect_to_wifi():
    """Connect to the configured WiFi network"""
    print("Connecting to WiFi...")
    
    # Check if wpa_supplicant.conf exists
    if not os.path.exists("/etc/wpa_supplicant/wpa_supplicant.conf"):
        print("Error: No WiFi configuration found.")
        print("Please run the WiFi setup portal first.")
        return False
    
    # Start wpa_supplicant
    run_command("wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant/wpa_supplicant.conf")
    
    # Request IP address
    run_command("dhclient wlan0")
    
    # Wait for connection
    print("Waiting for WiFi connection...")
    connected = False
    for i in range(30):
        _, _, return_code = run_command("ping -c 1 8.8.8.8")
        if return_code == 0:
            connected = True
            break
        time.sleep(1)
    
    if connected:
        print("Connected to WiFi successfully!")
        return True
    else:
        print("Failed to connect to WiFi or no internet access.")
        return False

def main():
    """Main function"""
    print("=== Disabling AP Mode and Connecting to WiFi ===")
    
    # Disable AP mode
    disable_ap_mode()
    
    # Connect to WiFi
    success = connect_to_wifi()
    
    if success:
        print("\n=== WiFi Connection Successful ===")
        print("Your Raspberry Pi is now connected to WiFi.")
        print("You can access it remotely using SSH or other services.")
    else:
        print("\n=== WiFi Connection Failed ===")
        print("Please run the WiFi setup portal again to configure WiFi.")

if __name__ == "__main__":
    main()