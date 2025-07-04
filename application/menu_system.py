#!/usr/bin/env python3
"""
Menu System for GPS Navigation
==============================
Provides a hierarchical menu system for navigation device configuration,
trip management, and system settings.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

logger = logging.getLogger(__name__)


class MenuItem:
    """Individual menu item"""

    def __init__(self, title: str, action: Optional[str] = None,
                 submenu: Optional['Menu'] = None, callback: Optional[Callable] = None):
        self.title = title
        self.action = action
        self.submenu = submenu
        self.callback = callback
        self.enabled = True

    def execute(self) -> Optional[Dict[str, Any]]:
        """Execute menu item action"""
        if self.callback:
            return self.callback()
        elif self.action:
            return {'action': self.action}
        return None


class Menu:
    """Menu container"""

    def __init__(self, title: str):
        self.title = title
        self.items: List[MenuItem] = []
        self.selected_index = 0
        self.parent: Optional['Menu'] = None

    def add_item(self, item: MenuItem):
        """Add item to menu"""
        self.items.append(item)
        if item.submenu:
            item.submenu.parent = self

    def get_selected_item(self) -> Optional[MenuItem]:
        """Get currently selected item"""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None

    def move_up(self):
        """Move selection up"""
        if self.items:
            self.selected_index = (self.selected_index - 1) % len(self.items)

    def move_down(self):
        """Move selection down"""
        if self.items:
            self.selected_index = (self.selected_index + 1) % len(self.items)

    def select(self) -> Optional[Dict[str, Any]]:
        """Select current item"""
        item = self.get_selected_item()
        if item and item.enabled:
            return item.execute()
        return None


class MenuSystem:
    """Main menu system"""

    def __init__(self, database_manager, sync_manager, width=800, height=480):
        self.db = database_manager
        self.sync_manager = sync_manager
        self.width = width
        self.height = height

        # Current menu state
        self.current_menu: Optional[Menu] = None
        self.menu_stack: List[Menu] = []

        # Fonts
        self.font_small = self._load_font(12)
        self.font_medium = self._load_font(16)
        self.font_large = self._load_font(20)
        self.font_title = self._load_font(24)

        # Build menu structure
        self._build_menus()

        logger.info("Menu system initialized")

    def _load_font(self, size):
        """Load font with fallback"""
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", size)
            except:
                return ImageFont.load_default()

    def _build_menus(self):
        """Build the menu structure"""
        # Main menu
        main_menu = Menu("Main Menu")

        # Trip management submenu
        trip_menu = Menu("Trip Management")
        trip_menu.add_item(MenuItem("View Trips", callback=self._show_trips))
        trip_menu.add_item(MenuItem("Start Trip", callback=self._start_trip))
        trip_menu.add_item(MenuItem("Stop Current Trip", callback=self._stop_trip))
        trip_menu.add_item(MenuItem("Back", action="back"))

        # Logbook submenu
        logbook_menu = Menu("Logbook")
        logbook_menu.add_item(MenuItem("View Recent Entries", callback=self._show_logbook))
        logbook_menu.add_item(MenuItem("Sync Status", callback=self._show_sync_status))
        logbook_menu.add_item(MenuItem("Back", action="back"))

        # System submenu
        system_menu = Menu("System")
        system_menu.add_item(MenuItem("WiFi Status", callback=self._show_wifi_status))
        system_menu.add_item(MenuItem("GPS Status", callback=self._show_gps_status))
        system_menu.add_item(MenuItem("Sync Settings", callback=self._show_sync_settings))
        system_menu.add_item(MenuItem("System Info", callback=self._show_system_info))
        system_menu.add_item(MenuItem("Back", action="back"))

        # Add submenus to main menu
        main_menu.add_item(MenuItem("Trip Management", submenu=trip_menu))
        main_menu.add_item(MenuItem("Logbook", submenu=logbook_menu))
        main_menu.add_item(MenuItem("System", submenu=system_menu))
        main_menu.add_item(MenuItem("Exit Menu", action="exit_menu"))

        self.main_menu = main_menu
        self.current_menu = main_menu

    def navigate_up(self):
        """Navigate up in current menu"""
        if self.current_menu:
            self.current_menu.move_up()

    def navigate_down(self):
        """Navigate down in current menu"""
        if self.current_menu:
            self.current_menu.move_down()

    def navigate_back(self):
        """Navigate back to parent menu"""
        if self.current_menu and self.current_menu.parent:
            self.current_menu = self.current_menu.parent
        elif self.menu_stack:
            self.current_menu = self.menu_stack.pop()

    def navigate_forward(self):
        """Navigate forward (same as select for now)"""
        return self.select()

    def select(self) -> Optional[Dict[str, Any]]:
        """Select current menu item"""
        if not self.current_menu:
            return None

        item = self.current_menu.get_selected_item()
        if not item:
            return None

        # Handle submenu navigation
        if item.submenu:
            self.menu_stack.append(self.current_menu)
            self.current_menu = item.submenu
            return None

        # Handle back action
        if item.action == "back":
            self.navigate_back()
            return None

        # Execute item action
        return item.execute()

    def render(self) -> Image.Image:
        """Render current menu"""
        if not self.current_menu:
            return self._render_error("No menu available")

        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Draw title
        title = self.current_menu.title
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, 30), title, fill=0, font=self.font_title)

        # Draw separator line
        draw.line([50, 70, self.width - 50, 70], fill=0, width=2)

        # Draw menu items
        y_start = 100
        item_height = 40

        for i, item in enumerate(self.current_menu.items):
            y_pos = y_start + i * item_height

            # Highlight selected item
            if i == self.current_menu.selected_index:
                draw.rectangle([50, y_pos - 5, self.width - 50, y_pos + 30],
                               fill=200, outline=0)

            # Draw item text
            text_color = 0 if item.enabled else 128
            draw.text((70, y_pos), item.title, fill=text_color, font=self.font_medium)

            # Draw submenu indicator
            if item.submenu:
                draw.text((self.width - 100, y_pos), "►", fill=text_color, font=self.font_medium)

        # Draw navigation help
        help_text = "↑↓: Navigate  →: Select  ←: Back"
        bbox = draw.textbbox((0, 0), help_text, font=self.font_small)
        help_width = bbox[2] - bbox[0]
        help_x = (self.width - help_width) // 2
        draw.text((help_x, self.height - 40), help_text, fill=128, font=self.font_small)

        return image

    def _render_error(self, message: str) -> Image.Image:
        """Render error message"""
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        bbox = draw.textbbox((0, 0), message, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        text_x = (self.width - text_width) // 2
        text_y = self.height // 2

        draw.text((text_x, text_y), message, fill=0, font=self.font_medium)

        return image

    # Menu action callbacks
    def _show_trips(self) -> Dict[str, Any]:
        """Show trips list"""
        trips = self.db.get_trips()

        # Create trips display menu
        trips_menu = Menu("Available Trips")

        if trips:
            for trip in trips[:10]:  # Show first 10 trips
                title = f"{trip['title']} ({trip['status']})"
                trips_menu.add_item(MenuItem(title, callback=lambda t=trip: self._select_trip(t)))
        else:
            trips_menu.add_item(MenuItem("No trips available"))

        trips_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to trips menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = trips_menu

        return None

    def _select_trip(self, trip: Dict[str, Any]) -> Dict[str, Any]:
        """Select a trip for management"""
        trip_menu = Menu(f"Trip: {trip['title']}")

        if trip['status'] == 'planned':
            trip_menu.add_item(MenuItem("Start Trip",
                                        callback=lambda: self._start_specific_trip(trip['id'])))
        elif trip['status'] == 'active':
            trip_menu.add_item(MenuItem("Stop Trip",
                                        callback=lambda: self._stop_specific_trip(trip['id'])))

        trip_menu.add_item(MenuItem("View Details",
                                    callback=lambda: self._show_trip_details(trip)))
        trip_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to trip menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = trip_menu

        return None

    def _start_trip(self) -> Dict[str, Any]:
        """Start a new trip"""
        # Get available planned trips
        trips = self.db.get_trips('planned')

        if not trips:
            return {'action': 'show_message', 'message': 'No planned trips available'}

        # For now, start the first available trip
        trip = trips[0]
        self.db.update_trip_status(trip['id'], 'active')

        return {
            'action': 'start_trip',
            'trip_id': trip['id'],
            'message': f"Started trip: {trip['title']}"
        }

    def _start_specific_trip(self, trip_id: str) -> Dict[str, Any]:
        """Start a specific trip"""
        self.db.update_trip_status(trip_id, 'active')
        return {
            'action': 'start_trip',
            'trip_id': trip_id
        }

    def _stop_trip(self) -> Dict[str, Any]:
        """Stop current trip"""
        current_trip = self.db.get_current_trip()

        if not current_trip:
            return {'action': 'show_message', 'message': 'No active trip'}

        self.db.update_trip_status(current_trip['id'], 'completed')

        return {
            'action': 'stop_trip',
            'message': f"Stopped trip: {current_trip['title']}"
        }

    def _stop_specific_trip(self, trip_id: str) -> Dict[str, Any]:
        """Stop a specific trip"""
        self.db.update_trip_status(trip_id, 'completed')
        return {
            'action': 'stop_trip'
        }

    def _show_trip_details(self, trip: Dict[str, Any]) -> Dict[str, Any]:
        """Show trip details"""
        details_menu = Menu("Trip Details")

        details_menu.add_item(MenuItem(f"Title: {trip['title']}"))
        details_menu.add_item(MenuItem(f"Status: {trip['status']}"))

        if trip.get('description'):
            desc = trip['description'][:30] + "..." if len(trip['description']) > 30 else trip['description']
            details_menu.add_item(MenuItem(f"Description: {desc}"))

        if trip.get('start_date'):
            details_menu.add_item(MenuItem(f"Start: {trip['start_date']}"))

        if trip.get('end_date'):
            details_menu.add_item(MenuItem(f"End: {trip['end_date']}"))

        # Show waypoint count
        waypoints = self.db.get_trip_waypoints(trip['id'])
        details_menu.add_item(MenuItem(f"Waypoints: {len(waypoints)}"))

        # Show logbook entry count
        entries = self.db.get_logbook_entries(trip['id'])
        details_menu.add_item(MenuItem(f"Log Entries: {len(entries)}"))

        details_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to details menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = details_menu

        return None

    def _show_logbook(self) -> Dict[str, Any]:
        """Show recent logbook entries"""
        entries = self.db.get_logbook_entries(limit=20)

        logbook_menu = Menu("Recent Logbook Entries")

        if entries:
            for entry in entries:
                timestamp = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                time_str = timestamp.strftime('%m/%d %H:%M')
                speed = entry.get('speed', 0)
                title = f"{time_str} - {speed:.1f} km/h"
                logbook_menu.add_item(MenuItem(title))
        else:
            logbook_menu.add_item(MenuItem("No logbook entries"))

        logbook_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to logbook menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = logbook_menu

        return None

    def _show_sync_status(self) -> Dict[str, Any]:
        """Show sync status"""
        sync_menu = Menu("Sync Status")

        # Check sync configuration
        if self.sync_manager.is_enabled():
            sync_menu.add_item(MenuItem("Sync: Enabled"))

            # Last ping
            last_ping = self.db.get_sync_status('last_ping')
            if last_ping:
                ping_time = datetime.fromisoformat(last_ping)
                ping_str = ping_time.strftime('%m/%d %H:%M')
                sync_menu.add_item(MenuItem(f"Last Ping: {ping_str}"))
            else:
                sync_menu.add_item(MenuItem("Last Ping: Never"))

            # Last full sync
            last_sync = self.db.get_sync_status('last_full_sync')
            if last_sync:
                sync_time = datetime.fromisoformat(last_sync)
                sync_str = sync_time.strftime('%m/%d %H:%M')
                sync_menu.add_item(MenuItem(f"Last Sync: {sync_str}"))
            else:
                sync_menu.add_item(MenuItem("Last Sync: Never"))

            # Pending entries
            unsynced = self.db.get_unsynced_logbook_entries()
            sync_menu.add_item(MenuItem(f"Pending Entries: {len(unsynced)}"))

        else:
            sync_menu.add_item(MenuItem("Sync: Disabled"))
            sync_menu.add_item(MenuItem("No sync key configured"))

        sync_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to sync menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = sync_menu

        return None

    def _show_wifi_status(self) -> Dict[str, Any]:
        """Show WiFi status"""
        # This would need to be passed from the main system
        wifi_menu = Menu("WiFi Status")
        wifi_menu.add_item(MenuItem("WiFi status not available"))
        wifi_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to WiFi menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = wifi_menu

        return None

    def _show_gps_status(self) -> Dict[str, Any]:
        """Show GPS status"""
        # This would need to be passed from the main system
        gps_menu = Menu("GPS Status")
        gps_menu.add_item(MenuItem("GPS status not available"))
        gps_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to GPS menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = gps_menu

        return None

    def _show_sync_settings(self) -> Dict[str, Any]:
        """Show sync settings"""
        settings_menu = Menu("Sync Settings")

        if self.sync_manager.is_enabled():
            settings_menu.add_item(MenuItem("Sync Key: Configured"))
            settings_menu.add_item(MenuItem("Force Sync", callback=self._force_sync))
        else:
            settings_menu.add_item(MenuItem("Sync Key: Not Configured"))
            settings_menu.add_item(MenuItem("Configure via WiFi setup"))

        settings_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to settings menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = settings_menu

        return None

    def _force_sync(self) -> Dict[str, Any]:
        """Force synchronization"""
        return {'action': 'force_sync', 'message': 'Sync initiated'}

    def _show_system_info(self) -> Dict[str, Any]:
        """Show system information"""
        info_menu = Menu("System Information")

        # Get system info
        try:
            import platform
            import psutil

            info_menu.add_item(MenuItem(f"OS: {platform.system()}"))
            info_menu.add_item(MenuItem(f"Python: {platform.python_version()}"))

            # Memory usage
            memory = psutil.virtual_memory()
            memory_pct = memory.percent
            info_menu.add_item(MenuItem(f"Memory: {memory_pct:.1f}%"))

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_pct = (disk.used / disk.total) * 100
            info_menu.add_item(MenuItem(f"Disk: {disk_pct:.1f}%"))

        except ImportError:
            info_menu.add_item(MenuItem("System info not available"))

        info_menu.add_item(MenuItem("Back", action="back"))

        # Navigate to info menu
        self.menu_stack.append(self.current_menu)
        self.current_menu = info_menu

        return None


def main():
    """Test the menu system"""
    import tempfile
    import os
    from database_manager import DatabaseManager

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Create database manager
        db = DatabaseManager(db_path)

        # Create mock sync manager
        class MockSyncManager:
            def is_enabled(self):
                return True

        sync_manager = MockSyncManager()

        # Create menu system
        menu_system = MenuSystem(db, sync_manager)

        # Test menu rendering
        print("Testing menu system...")

        # Render main menu
        image = menu_system.render()
        print(f"Rendered main menu: {image.size}")

        # Test navigation
        menu_system.navigate_down()
        menu_system.navigate_down()

        # Test selection
        result = menu_system.select()
        print(f"Selection result: {result}")

        # Render updated menu
        image = menu_system.render()
        print(f"Rendered updated menu: {image.size}")

        print("Menu system test completed successfully")

    except Exception as e:
        print(f"Menu system test error: {e}")
        return 1
    finally:
        # Clean up
        try:
            os.unlink(db_path)
        except:
            pass

    return 0


if __name__ == "__main__":
    exit(main())
