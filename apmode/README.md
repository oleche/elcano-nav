### Raspberry Pi Zero WiFi Setup Portal

I'll create a comprehensive solution that enables AP mode on your Raspberry Pi Zero and serves a captive portal for WiFi configuration. When a user connects to the Pi's AP, they'll be presented with a web page to configure WiFi settings. Once configured, the Pi will connect to the specified network and disable AP mode.

This solution consists of multiple files:

1. Main setup script
2. Flask web application for the captive portal
3. HTML templates for the configuration page
4. Scripts to handle WiFi connection and mode switching



## How to Use This Solution

1. Save all the files to your Raspberry Pi Zero in the same directory
2. Make the scripts executable:

```shellscript
chmod +x wifi_portal.py disable_ap_mode.py install_service.py
```


3. Run the main script to start the WiFi portal:

```shellscript
sudo python3 wifi_portal.py
```


4. Optionally, install the service to automatically start the portal on boot if no WiFi connection is available:

```shellscript
sudo python3 install_service.py
```




## How It Works

1. **AP Mode Setup**: The `wifi_portal.py` script configures your Raspberry Pi Zero as a WiFi access point.
2. **Captive Portal**: When a user connects to the Pi's WiFi network, they'll be automatically redirected to a web page.
3. **WiFi Configuration**: The web page allows the user to:

1. Scan for available WiFi networks
2. Select a network
3. Enter the password (if required)
4. Connect the Pi to that network



4. **Automatic Mode Switching**: Once the user configures WiFi settings, the Pi will:

1. Save the WiFi credentials
2. Disable AP mode
3. Connect to the specified WiFi network
4. Return to normal operation



5. **Auto-Start Service**: If you install the service, the Pi will automatically start the WiFi portal on boot if it can't connect to the internet.


## Customization

You can customize the following variables in the `wifi_portal.py` script:

- `AP_SSID`: The name of your WiFi network (default: "RaspberryPi_Setup")
- `AP_PASSWORD`: The password for your WiFi network (default: "raspberry")
- `AP_CHANNEL`: WiFi channel (default: 7)
- `AP_COUNTRY`: Your country code (default: "US")
- `IP_ADDRESS`: The IP address of your Raspberry Pi (default: "192.168.4.1")


## Troubleshooting

If you encounter issues:

1. Check the system logs: `sudo journalctl -xe`
2. Verify that hostapd and dnsmasq are installed: `dpkg -s hostapd dnsmasq`
3. Make sure your WiFi adapter supports AP mode: `iw list | grep "Supported interface modes" -A 10`
4. If the web portal doesn't start, check for errors: `sudo python3 web_portal.py`

## Requirements

1. `sudo apt-get install -y dnsmasq hostapd dhcpcd`
2. `mkdir /opt/elcano`
3. `echo "token=" > /opt/elcano/settings.ini`