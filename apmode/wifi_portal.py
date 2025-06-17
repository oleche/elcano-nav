#!/usr/bin/env python3
"""
Raspberry Pi Zero WiFi Setup Portal
This script configures a Raspberry Pi Zero to function as a WiFi access point
with a captive portal that allows configuration of WiFi settings.
"""

import os
import sys
import subprocess
import time
import shutil
import signal
import atexit

# Check if script is run as root
if os.geteuid() != 0:
    print("This script must be run as root. Please use sudo.")
    sys.exit(1)

# Configuration variables - modify these as needed
AP_SSID = "Elcano_One"
AP_PASSWORD = "elcanoone"  # Minimum 8 characters
AP_CHANNEL = 7
AP_COUNTRY = "NL"  # Change to your country code
IP_ADDRESS = "192.168.4.1"
IP_SUBNET = "255.255.255.0"
DHCP_RANGE_START = "192.168.4.100"
DHCP_RANGE_END = "192.168.4.200"
PORTAL_PORT = 80
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Global variables for process management
web_server_process = None
hostapd_process = None
dnsmasq_process = None

def run_command(command):
    """Run a shell command and return the output and return code"""
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    return stdout.decode(), stderr.decode(), process.returncode

def check_wifi_adapter():
    """Check if WiFi adapter is available"""
    print("Checking WiFi adapter...")
    stdout, _, _ = run_command("iw dev | grep Interface")
    if not stdout:
        print("Error: No WiFi interface found.")
        sys.exit(1)
    
    # Extract the interface name
    interface = stdout.strip().split()[1]
    print(f"Found WiFi interface: {interface}")
    return interface

def install_dependencies():
    """Install required packages"""
    print("Installing required packages...")
    packages = ["hostapd", "dnsmasq", "python3-flask", "python3-pip", "iw", "wireless-tools"]
    
    # Update package lists
    print("Updating package lists...")
    run_command("apt-get update")
    
    # Install packages
    for package in packages:
        print(f"Checking if {package} is installed...")
        _, _, return_code = run_command(f"dpkg -s {package}")
        if return_code != 0:
            print(f"Installing {package}...")
            _, stderr, return_code = run_command(f"apt-get install -y {package}")
            if return_code != 0:
                print(f"Error installing {package}: {stderr}")
                sys.exit(1)
        else:
            print(f"{package} is already installed.")
    
    # Install required Python packages
    print("Installing required Python packages...")
    run_command("pip3 install flask flask-wtf")

def configure_dhcp_server():
    """Configure DHCP server (dnsmasq)"""
    print("Configuring DHCP server (dnsmasq)...")
    
    # Backup original configuration
    if os.path.exists("/etc/dnsmasq.conf"):
        shutil.copy2("/etc/dnsmasq.conf", "/etc/dnsmasq.conf.bak")
        print("Backed up original dnsmasq configuration.")
    
    # Create new configuration
    dnsmasq_conf = f"""
# dnsmasq configuration for WiFi AP
interface=wlan0
dhcp-range={DHCP_RANGE_START},{DHCP_RANGE_END},12h
domain=wlan
address=/gw.wlan/{IP_ADDRESS}
address=/#/{IP_ADDRESS}
"""
    
    with open("/etc/dnsmasq.conf", "w") as f:
        f.write(dnsmasq_conf)
    
    # Stop dnsmasq service if it's running
    run_command("systemctl stop dnsmasq")
    
    print("DHCP server configured.")

def configure_hostapd(interface):
    """Configure hostapd for the access point"""
    print("Configuring hostapd...")
    
    # Create hostapd configuration file
    hostapd_conf = f"""
# hostapd configuration for WiFi AP
interface={interface}
driver=nl80211
ssid={AP_SSID}
hw_mode=g
channel={AP_CHANNEL}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
wpa=2
wpa_passphrase={AP_PASSWORD}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code={AP_COUNTRY}
"""
    
    with open("/etc/hostapd/hostapd.conf", "w") as f:
        f.write(hostapd_conf)
    
    # Update hostapd default configuration
    with open("/etc/default/hostapd", "w") as f:
        f.write('DAEMON_CONF="/etc/hostapd/hostapd.conf"')
    
    # Stop hostapd service if it's running
    run_command("systemctl stop hostapd")
    
    print("hostapd configured.")

def configure_network_interface(interface):
    """Configure network interface"""
    print(f"Configuring network interface {interface}...")
    
    # Stop network services
    run_command("systemctl stop dhcpcd")
    run_command("systemctl stop wpa_supplicant")
    
    # Configure static IP for wlan0
    dhcpcd_conf = f"""
interface {interface}
    static ip_address={IP_ADDRESS}/24
    nohook wpa_supplicant
"""
    
    # Backup original configuration
    if os.path.exists("/etc/dhcpcd.conf"):
        shutil.copy2("/etc/dhcpcd.conf", "/etc/dhcpcd.conf.bak")
        print("Backed up original dhcpcd configuration.")
    
    # Append to dhcpcd.conf
    with open("/etc/dhcpcd.conf", "a") as f:
        f.write(dhcpcd_conf)
    
    print("Network interface configured.")

def configure_captive_portal():
    """Configure iptables for captive portal"""
    print("Configuring captive portal redirects...")
    
    # Configure iptables to redirect all HTTP traffic to our portal
    iptables_rules = [
        f"iptables -t nat -A PREROUTING -s {IP_ADDRESS}/24 -p tcp --dport 80 -j DNAT --to-destination {IP_ADDRESS}:{PORTAL_PORT}",
        f"iptables -t nat -A POSTROUTING -j MASQUERADE"
    ]
    
    for rule in iptables_rules:
        run_command(rule)
    
    print("Captive portal redirects configured.")

def start_services():
    """Start the configured services"""
    print("Starting services...")
    
    global hostapd_process, dnsmasq_process
    
    # Start dhcpcd
    run_command("systemctl start dhcpcd")
    time.sleep(2)  # Give dhcpcd time to start
    
    # Start hostapd
    print("Starting hostapd...")
    hostapd_process = subprocess.Popen(
        ["hostapd", "/etc/hostapd/hostapd.conf"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)  # Give hostapd time to start
    
    # Check if hostapd started successfully
    if hostapd_process.poll() is not None:
        print("Error: hostapd failed to start.")
        _, stderr = hostapd_process.communicate()
        print(f"hostapd error: {stderr.decode()}")
        sys.exit(1)
    
    # Start dnsmasq
    print("Starting dnsmasq...")
    dnsmasq_process = subprocess.Popen(
        ["dnsmasq", "-C", "/etc/dnsmasq.conf", "-d"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(2)  # Give dnsmasq time to start
    
    # Check if dnsmasq started successfully
    if dnsmasq_process.poll() is not None:
        print("Error: dnsmasq failed to start.")
        _, stderr = dnsmasq_process.communicate()
        print(f"dnsmasq error: {stderr.decode()}")
        sys.exit(1)
    
    print("Services started successfully.")

def start_web_server():
    """Start the Flask web server for the captive portal"""
    print("Starting web server...")
    
    global web_server_process
    
    # Start the Flask web server
    web_server_process = subprocess.Popen(
        ["python3", f"{SCRIPT_DIR}/web_portal.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    time.sleep(2)  # Give the web server time to start
    
    # Check if the web server started successfully
    if web_server_process.poll() is not None:
        print("Error: Web server failed to start.")
        _, stderr = web_server_process.communicate()
        print(f"Web server error: {stderr.decode()}")
        sys.exit(1)
    
    print(f"Web server started on port {PORTAL_PORT}.")

def cleanup():
    """Clean up processes on exit"""
    print("\nCleaning up...")
    
    # Terminate processes
    if web_server_process and web_server_process.poll() is None:
        web_server_process.terminate()
        print("Web server stopped.")
    
    if hostapd_process and hostapd_process.poll() is None:
        hostapd_process.terminate()
        print("hostapd stopped.")
    
    if dnsmasq_process and dnsmasq_process.poll() is None:
        dnsmasq_process.terminate()
        print("dnsmasq stopped.")
    
    print("Cleanup complete.")

def create_web_portal_files():
    """Create the web portal files"""
    print("Creating web portal files...")
    
    # Create the web portal script
    web_portal_py = """#!/usr/bin/env python3
import os
import subprocess
import time
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)
app.secret_key = 'raspberry_pi_wifi_setup'

# Path to store WiFi credentials
WIFI_CONFIG_PATH = '/etc/wpa_supplicant/wpa_supplicant.conf'
WIFI_CONNECT_SCRIPT = '/usr/local/bin/connect_wifi.sh'
SCAN_RESULTS_FILE = '/tmp/wifi_scan_results.json'
ELCANO_INFO_FILE = '/opt/elcano/settings.ini'

def get_wifi_networks():
    # Scan for available WiFi networks
    try:
        # Kill any existing wpa_supplicant processes
        subprocess.run(['killall', 'wpa_supplicant'], stderr=subprocess.DEVNULL)
        time.sleep(1)
        
        # Scan for networks
        subprocess.run(['iwlist', 'wlan0', 'scan'], stdout=subprocess.PIPE)
        
        # Parse scan results
        result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        
        networks = []
        current_network = {}
        
        for line in result.stdout.split('\\n'):
            line = line.strip()
            
            if 'Cell' in line and 'Address' in line:
                if current_network and 'ssid' in current_network:
                    networks.append(current_network)
                current_network = {'address': line.split('Address: ')[1]}
            
            elif 'ESSID' in line:
                essid = line.split('ESSID:')[1].strip('"')
                if essid:  # Only add non-empty SSIDs
                    current_network['ssid'] = essid
            
            elif 'Quality' in line:
                quality_part = line.split('Quality=')[1].split(' ')[0]
                if '/' in quality_part:
                    num, denom = quality_part.split('/')
                    quality = int(float(num) / float(denom) * 100)
                else:
                    quality = int(quality_part)
                current_network['quality'] = quality
            
            elif 'Encryption key' in line:
                current_network['encrypted'] = 'on' in line.lower()
        
        # Add the last network
        if current_network and 'ssid' in current_network:
            networks.append(current_network)
        
        # Sort networks by quality
        networks.sort(key=lambda x: x.get('quality', 0), reverse=True)
        
        # Remove duplicates (keep the one with highest quality)
        unique_networks = []
        seen_ssids = set()
        
        for network in networks:
            if network['ssid'] not in seen_ssids:
                unique_networks.append(network)
                seen_ssids.add(network['ssid'])
        
        # Save scan results to file
        with open(SCAN_RESULTS_FILE, 'w') as f:
            json.dump(unique_networks, f)
        
        return unique_networks
    
    except Exception as e:
        print(f"Error scanning WiFi networks: {e}")
        return []

def connect_to_wifi(ssid, password):
    # Create WPA supplicant configuration and connect to WiFi
    try:
        # Create WPA supplicant configuration
        config = f'''ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
'''
        # Write configuration to file
        with open(WIFI_CONFIG_PATH, 'w') as f:
            f.write(config)
        
        # Set permissions
        os.chmod(WIFI_CONFIG_PATH, 0o600)
        
        # Create connect script
        connect_script = f'''#!/bin/bash
# Disable AP mode and connect to WiFi
systemctl stop hostapd
systemctl stop dnsmasq
systemctl disable hostapd
systemctl disable dnsmasq

# Restore original network configuration
if [ -f /etc/dhcpcd.conf.bak ]; then
    cp /etc/dhcpcd.conf.bak /etc/dhcpcd.conf
fi

# Restart networking services
systemctl restart dhcpcd
wpa_supplicant -B -i wlan0 -c {WIFI_CONFIG_PATH}
dhclient wlan0

# Wait for connection
echo "Waiting for WiFi connection..."
for i in $(seq 1 30); do
    if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
        echo "Connected to the internet!"
        exit 0
    fi
    sleep 1
done

echo "Failed to connect to WiFi or no internet access."
exit 1
'''
        
        # Write connect script to file
        with open(WIFI_CONNECT_SCRIPT, 'w') as f:
            f.write(connect_script)
        
        # Set permissions
        os.chmod(WIFI_CONNECT_SCRIPT, 0o755)
        
        # Execute connect script in background
        subprocess.Popen([WIFI_CONNECT_SCRIPT], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)
        
        return True
    
    except Exception as e:
        print(f"Error connecting to WiFi: {e}")
        return False

@app.route('/')
def index():
    # Render the WiFi setup page
    networks = get_wifi_networks()
    setting = ''
    f = open(ELCANO_INFO_FILE,"r")
    setting = f.read()

    setting.replace('token=', '', 1)
    return render_template('index.html', networks=networks, setting=setting)

@app.route('/scan')
def scan():
    # Scan for WiFi networks and return JSON
    networks = get_wifi_networks()
    return jsonify(networks)

@app.route('/connect', methods=['POST'])
def connect():
    # Connect to the selected WiFi network
    ssid = request.form.get('ssid')
    password = request.form.get('password')
    token = request.form.get('token')
    
    if not ssid:
        return render_template('error.html', 
                              message='No WiFi network selected')
                              
    if not token:
        return render_template('error.html', 
                              message='No Elcano token assigned, please write the 10 characters token')
    
    with open(ELCANO_INFO_FILE, "w") as f:
        f.write("token="+token)
    
    success = connect_to_wifi(ssid, password)
    
    if success:
        return render_template('success.html', 
                              ssid=ssid)
    else:
        return render_template('error.html', 
                              message='Failed to connect to WiFi')

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=80, debug=True)
"""
    
    # Create the templates directory
    os.makedirs(f"{SCRIPT_DIR}/templates", exist_ok=True)
    
    # Create the index.html template
    index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ElcanoNav WiFi Setup</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #e74c3c;
            text-align: center;
        }
        .container {
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .network-list {
            margin-bottom: 20px;
        }
        .network-item {
            padding: 10px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
        }
        .network-item:hover {
            background-color: #f0f0f0;
        }
        .network-item.selected {
            background-color: #e8f4fc;
        }
        .signal-strength {
            float: right;
            font-size: 0.8em;
            color: #666;
        }
        .locked {
            margin-left: 5px;
            color: #e74c3c;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"],
        input[type="password"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background-color: #e74c3c;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        button:hover {
            background-color: #c0392b;
        }
        .refresh-btn {
            background-color: #3498db;
            margin-bottom: 10px;
        }
        .refresh-btn:hover {
            background-color: #2980b9;
        }
        .loading {
            text-align: center;
            margin: 20px 0;
        }
        .spinner {
            border: 4px solid rgba(0, 0, 0, 0.1);
            border-radius: 50%;
            border-top: 4px solid #e74c3c;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Elcano Nav WiFi Setup</h1>
        
        <button id="refresh-btn" class="refresh-btn">Refresh WiFi Networks</button>
        
        <div id="loading" class="loading" style="display: none;">
            <div class="spinner"></div>
            <p>Scanning for networks...</p>
        </div>
        
        <form id="wifi-form" action="/connect" method="post">
            <div class="form-group">
                <label for="network-list">Select WiFi Network:</label>
                <div id="network-list" class="network-list">
                    {% if networks %}
                        {% for network in networks %}
                            <div class="network-item" data-ssid="{{ network.ssid }}" data-encrypted="{{ network.encrypted }}">
                                {{ network.ssid }}
                                {% if network.encrypted %}
                                    <span class="locked">🔒</span>
                                {% endif %}
                                <span class="signal-strength">{{ network.quality }}%</span>
                            </div>
                        {% endfor %}
                    {% else %}
                        <p>No networks found. Click "Refresh WiFi Networks" to scan again.</p>
                    {% endif %}
                </div>
            </div>
            
            <div class="form-group">
                <label for="ssid">Selected Network:</label>
                <input type="text" id="ssid" name="ssid" readonly required>
            </div>
            
            <div class="form-group" id="password-group" style="display: none;">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password">
            </div>
            
            <div class="form-group" id="password-group">
                <label for="token">Elcano Token:</label>
                <input type="text" id="token" name="token" value={{setting}}>
            </div>
            
            <button type="submit">Connect</button>
        </form>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const networkItems = document.querySelectorAll('.network-item');
            const ssidInput = document.getElementById('ssid');
            const passwordGroup = document.getElementById('password-group');
            const passwordInput = document.getElementById('password');
            const refreshBtn = document.getElementById('refresh-btn');
            const loadingDiv = document.getElementById('loading');
            const networkList = document.getElementById('network-list');
            
            // Handle network selection
            networkItems.forEach(item => {
                item.addEventListener('click', function() {
                    // Remove selected class from all items
                    networkItems.forEach(i => i.classList.remove('selected'));
                    
                    // Add selected class to clicked item
                    this.classList.add('selected');
                    
                    // Set the SSID input value
                    ssidInput.value = this.dataset.ssid;
                    
                    // Show/hide password field based on encryption
                    if (this.dataset.encrypted === 'True') {
                        passwordGroup.style.display = 'block';
                        passwordInput.required = true;
                    } else {
                        passwordGroup.style.display = 'none';
                        passwordInput.required = false;
                    }
                });
            });
            
            // Handle refresh button
            refreshBtn.addEventListener('click', function() {
                loadingDiv.style.display = 'block';
                networkList.style.display = 'none';
                
                fetch('/scan')
                    .then(response => response.json())
                    .then(networks => {
                        // Clear current network list
                        networkList.innerHTML = '';
                        
                        if (networks.length > 0) {
                            // Add new networks to the list
                            networks.forEach(network => {
                                const item = document.createElement('div');
                                item.className = 'network-item';
                                item.dataset.ssid = network.ssid;
                                item.dataset.encrypted = network.encrypted;
                                
                                let html = network.ssid;
                                if (network.encrypted) {
                                    html += '<span class="locked">🔒</span>';
                                }
                                html += `<span class="signal-strength">${network.quality}%</span>`;
                                
                                item.innerHTML = html;
                                
                                // Add click event listener
                                item.addEventListener('click', function() {
                                    // Remove selected class from all items
                                    document.querySelectorAll('.network-item').forEach(i => i.classList.remove('selected'));
                                    
                                    // Add selected class to clicked item
                                    this.classList.add('selected');
                                    
                                    // Set the SSID input value
                                    ssidInput.value = this.dataset.ssid;
                                    
                                    // Show/hide password field based on encryption
                                    if (this.dataset.encrypted === 'true') {
                                        passwordGroup.style.display = 'block';
                                        passwordInput.required = true;
                                    } else {
                                        passwordGroup.style.display = 'none';
                                        passwordInput.required = false;
                                    }
                                });
                                
                                networkList.appendChild(item);
                            });
                        } else {
                            networkList.innerHTML = '<p>No networks found. Click "Refresh WiFi Networks" to scan again.</p>';
                        }
                        
                        // Hide loading, show network list
                        loadingDiv.style.display = 'none';
                        networkList.style.display = 'block';
                        
                        // Clear selected network
                        ssidInput.value = '';
                        passwordGroup.style.display = 'none';
                    })
                    .catch(error => {
                        console.error('Error scanning networks:', error);
                        networkList.innerHTML = '<p>Error scanning networks. Please try again.</p>';
                        loadingDiv.style.display = 'none';
                        networkList.style.display = 'block';
                    });
            });
        });
    </script>
</body>
</html>
"""
    
    # Create the success.html template
    success_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Setup Success</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #27ae60;
            text-align: center;
        }
        .container {
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        .success-icon {
            font-size: 64px;
            color: #27ae60;
            margin-bottom: 20px;
        }
        p {
            margin-bottom: 15px;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✓</div>
        <h1>WiFi Setup Successful</h1>
        <p>Your Raspberry Pi is now connecting to <strong>{{ ssid }}</strong>.</p>
        <p>The access point mode will be disabled, and your Raspberry Pi will restart in client mode.</p>
        <p>If you need to change WiFi settings in the future, you can run the setup script again.</p>
    </div>
</body>
</html>
"""
    
    # Create the error.html template
    error_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Setup Error</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            color: #e74c3c;
            text-align: center;
        }
        .container {
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            text-align: center;
        }
        .error-icon {
            font-size: 64px;
            color: #e74c3c;
            margin-bottom: 20px;
        }
        p {
            margin-bottom: 15px;
            line-height: 1.5;
        }
        .back-btn {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            text-decoration: none;
            display: inline-block;
            margin-top: 20px;
        }
        .back-btn:hover {
            background-color: #2980b9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">✗</div>
        <h1>WiFi Setup Error</h1>
        <p>{{ message }}</p>
        <a href="/" class="back-btn">Back to WiFi Setup</a>
    </div>
</body>
</html>
"""
    
    # Write files
    with open(f"{SCRIPT_DIR}/web_portal.py", "w") as f:
        f.write(web_portal_py)
    
    with open(f"{SCRIPT_DIR}/templates/index.html", "w") as f:
        f.write(index_html)
    
    with open(f"{SCRIPT_DIR}/templates/success.html", "w") as f:
        f.write(success_html)
    
    with open(f"{SCRIPT_DIR}/templates/error.html", "w") as f:
        f.write(error_html)
    
    # Make web_portal.py executable
    os.chmod(f"{SCRIPT_DIR}/web_portal.py", 0o755)
    
    print("Web portal files created.")

def main():
    """Main function"""
    print("=== Raspberry Pi Zero WiFi Setup Portal ===")
    
    # Register cleanup function
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
    
    # Check WiFi adapter
    interface = check_wifi_adapter()
    
    # Install dependencies
    install_dependencies()
    
    # Configure network interface
    configure_network_interface(interface)
    
    # Configure DHCP server
    configure_dhcp_server()
    
    # Configure hostapd
    configure_hostapd(interface)
    
    # Configure captive portal
    configure_captive_portal()
    
    # Create web portal files
    create_web_portal_files()
    
    # Start services
    start_services()
    
    # Start web server
    start_web_server()
    
    print("\n=== Setup Complete ===")
    print(f"Your Raspberry Pi is now configured as a WiFi access point with:")
    print(f"SSID: {AP_SSID}")
    print(f"Password: {AP_PASSWORD}")
    print(f"IP Address: {IP_ADDRESS}")
    print("\nConnect to this WiFi network from another device and navigate to:")
    print(f"http://{IP_ADDRESS}")
    print("\nPress Ctrl+C to stop the server and clean up.")
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()