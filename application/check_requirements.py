#!/usr/bin/env python3
"""
Requirements Checker for GPS Navigation System
==============================================
Checks if all required Python packages are installed and working.
"""

import sys
import importlib
import subprocess
from pathlib import Path

# Required packages with their import names and minimum versions
REQUIRED_PACKAGES = {
    'PIL': {
        'pip_name': 'Pillow',
        'min_version': '8.0.0',
        'description': 'Image processing for display rendering'
    },
    'numpy': {
        'pip_name': 'numpy',
        'min_version': '1.19.0',
        'description': 'Numerical operations for image processing'
    },
    'serial': {
        'pip_name': 'pyserial',
        'min_version': '3.4',
        'description': 'Serial communication for GPS module'
    },
    'requests': {
        'pip_name': 'requests',
        'min_version': '2.25.0',
        'description': 'HTTP requests for API synchronization'
    },
    'gpiozero': {
        'pip_name': 'gpiozero',
        'min_version': '1.6.0',
        'description': 'GPIO control for buttons and hardware'
    }
}

# Hardware-specific packages (Raspberry Pi only)
HARDWARE_PACKAGES = {
    'RPi.GPIO': {
        'pip_name': 'RPi.GPIO',
        'min_version': '0.7.0',
        'description': 'Low-level GPIO control'
    },
    'spidev': {
        'pip_name': 'spidev',
        'min_version': '3.5',
        'description': 'SPI communication for e-paper display'
    },
    'smbus': {
        'pip_name': 'smbus2',
        'min_version': '0.4.0',
        'description': 'I2C communication for sensors',
        'alternatives': ['smbus', 'smbus2']
    }
}

# Optional packages
OPTIONAL_PACKAGES = {
    'psutil': {
        'pip_name': 'psutil',
        'min_version': '5.8.0',
        'description': 'System monitoring and process management'
    }
}


def check_raspberry_pi():
    """Check if running on Raspberry Pi"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except:
        return False


def get_package_version(package_name):
    """Get version of installed package"""
    try:
        module = importlib.import_module(package_name)
        # Try different version attributes
        for attr in ['__version__', 'version', 'VERSION']:
            if hasattr(module, attr):
                version = getattr(module, attr)
                if callable(version):
                    version = version()
                return str(version)
        return "Unknown"
    except ImportError:
        return None
    except Exception as e:
        return f"Error: {e}"


def compare_versions(version1, version2):
    """Compare two version strings"""
    try:
        from packaging import version
        return version.parse(version1) >= version.parse(version2)
    except ImportError:
        # Fallback to simple string comparison
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]

        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))

        return v1_parts >= v2_parts


def check_package(import_name, package_info):
    """Check if a package is installed and meets version requirements"""
    version = get_package_version(import_name)

    if version is None:
        # Try alternatives if specified
        if 'alternatives' in package_info:
            for alt in package_info['alternatives']:
                version = get_package_version(alt)
                if version is not None:
                    import_name = alt
                    break

    if version is None:
        return False, "Not installed", import_name

    if version.startswith("Error:"):
        return False, version, import_name

    if version == "Unknown":
        return True, "Installed (version unknown)", import_name

    min_version = package_info.get('min_version')
    if min_version and not compare_versions(version, min_version):
        return False, f"Version {version} < {min_version}", import_name

    return True, f"Version {version}", import_name


def install_package(pip_name):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_name])
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """Main function to check all requirements"""
    print("GPS Navigation System - Requirements Checker")
    print("=" * 50)

    is_raspberry_pi = check_raspberry_pi()
    print(f"Platform: {'Raspberry Pi' if is_raspberry_pi else 'Other'}")
    print()

    all_good = True
    missing_packages = []

    # Check required packages
    print("Required Packages:")
    print("-" * 20)

    for import_name, package_info in REQUIRED_PACKAGES.items():
        success, message, actual_import = check_package(import_name, package_info)
        status = "✓" if success else "✗"
        print(f"{status} {actual_import}: {message}")
        print(f"   {package_info['description']}")

        if not success:
            all_good = False
            missing_packages.append(package_info['pip_name'])
        print()

    # Check hardware packages (only on Raspberry Pi)
    if is_raspberry_pi:
        print("Hardware Packages (Raspberry Pi):")
        print("-" * 35)

        for import_name, package_info in HARDWARE_PACKAGES.items():
            success, message, actual_import = check_package(import_name, package_info)
            status = "✓" if success else "✗"
            print(f"{status} {actual_import}: {message}")
            print(f"   {package_info['description']}")

            if not success:
                all_good = False
                missing_packages.append(package_info['pip_name'])
            print()
    else:
        print("Hardware Packages: Skipped (not on Raspberry Pi)")
        print()

    # Check optional packages
    print("Optional Packages:")
    print("-" * 20)

    for import_name, package_info in OPTIONAL_PACKAGES.items():
        success, message, actual_import = check_package(import_name, package_info)
        status = "✓" if success else "ℹ"
        print(f"{status} {actual_import}: {message}")
        print(f"   {package_info['description']}")
        print()

    # Summary
    print("Summary:")
    print("-" * 10)

    if all_good:
        print("✓ All required packages are installed and meet version requirements!")
        print("  The GPS Navigation System should work correctly.")
    else:
        print("✗ Some required packages are missing or outdated.")
        print("  The GPS Navigation System may not work correctly.")
        print()
        print("To install missing packages, run:")
        for package in missing_packages:
            print(f"  pip3 install {package}")
        print()
        print("Or run the installation script:")
        print("  chmod +x install_python_requirements.sh")
        print("  ./install_python_requirements.sh")

    # Additional checks
    print()
    print("Additional System Checks:")
    print("-" * 30)

    # Check if SPI is enabled (Raspberry Pi only)
    if is_raspberry_pi:
        try:
            spi_enabled = Path('/dev/spidev0.0').exists()
            print(f"{'✓' if spi_enabled else '✗'} SPI Interface: {'Enabled' if spi_enabled else 'Disabled'}")
            if not spi_enabled:
                print("   Enable with: sudo raspi-config → Interface Options → SPI")
        except:
            print("? SPI Interface: Could not check")

        # Check if I2C is enabled
        try:
            i2c_enabled = Path('/dev/i2c-1').exists()
            print(f"{'✓' if i2c_enabled else '✗'} I2C Interface: {'Enabled' if i2c_enabled else 'Disabled'}")
            if not i2c_enabled:
                print("   Enable with: sudo raspi-config → Interface Options → I2C")
        except:
            print("? I2C Interface: Could not check")

        # Check user groups
        try:
            import os
            import grp
            username = os.getenv('USER')
            user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]

            required_groups = ['gpio', 'spi', 'i2c']
            for group in required_groups:
                in_group = group in user_groups
                print(f"{'✓' if in_group else '✗'} User in {group} group: {'Yes' if in_group else 'No'}")
                if not in_group:
                    print(f"   Add with: sudo usermod -a -G {group} {username}")
        except:
            print("? User groups: Could not check")

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
