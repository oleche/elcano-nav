#!/usr/bin/env python3
"""
Menu System for GPS Navigation
==============================
Interactive menu system for navigation, trip management, and device settings.
"""

import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class MenuSystem:
    """Interactive menu system for GPS navigation"""

    def __init__(self, database_manager, sync_manager, width=800, height=480):
        self.db = database_manager
        self.sync = sync_manager
        self.width = width
        self.height = height

        # Menu state
        self.current_menu = 'main'
        self.selected_index = 0
        self.menu_stack = []

        # Menu data
        self.trips = []
        self.current_trip = None

        # Load fonts
        self.font_small = self._load_font(12)
        self.font_medium = self._load_font(16)
        self.font_large = self._load_font(20)
        self.font_title = self._load_font(24)

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

    def navigate_up(self):
        """Navigate up in menu"""
        if self.current_menu == 'main':
            menu_items = self._get_main_menu_items()
        elif self.current_menu == 'trips':
            menu_items = self._get_trips_menu_items()
        elif self.current_menu == 'sync':
            menu_items = self._get_sync_menu_items()
        elif self.current_menu == 'settings':
            menu_items = self._get_settings_menu_items()
        else:
            menu_items = []

        if menu_items:
            self.selected_index = (self.selected_index - 1) % len(menu_items)

    def navigate_down(self):
        """Navigate down in menu"""
        if self.current_menu == 'main':
            menu_items = self._get_main_menu_items()
        elif self.current_menu == 'trips':
            menu_items = self._get_trips_menu_items()
        elif self.current_menu == 'sync':
            menu_items = self._get_sync_menu_items()
        elif self.current_menu == 'settings':
            menu_items = self._get_settings_menu_items()
        else:
            menu_items = []

        if menu_items:
            self.selected_index = (self.selected_index + 1) % len(menu_items)

    def navigate_back(self):
        """Navigate back to previous menu"""
        if self.menu_stack:
            previous_menu, previous_index = self.menu_stack.pop()
            self.current_menu = previous_menu
            self.selected_index = previous_index
        else:
            # Exit menu system
            return {'action': 'exit_menu'}

        return None

    def navigate_forward(self):
        """Navigate forward (same as select for most items)"""
        return self.select()

    def select(self):
        """Select current menu item"""
        if self.current_menu == 'main':
            return self._handle_main_menu_select()
        elif self.current_menu == 'trips':
            return self._handle_trips_menu_select()
        elif self.current_menu == 'sync':
            return self._handle_sync_menu_select()
        elif self.current_menu == 'settings':
            return self._handle_settings_menu_select()

        return None

    def _get_main_menu_items(self):
        """Get main menu items"""
        return [
            {'title': 'Trips', 'action': 'trips'},
            {'title': 'Sync', 'action': 'sync'},
            {'title': 'Settings', 'action': 'settings'},
            {'title': 'Exit Menu', 'action': 'exit'}
        ]

    def _get_trips_menu_items(self):
        """Get trips menu items"""
        # Refresh trips from database
        self.trips = self.db.get_trips()

        items = []
        for trip in self.trips:
            status_icon = "▶" if trip.get('local_status') == 'active' else "⏸" if trip.get(
                'local_status') == 'paused' else "⏹"
            items.append({
                'title': f"{status_icon} {trip['title']}",
                'action': 'trip_detail',
                'trip': trip
            })

        items.append({'title': '← Back', 'action': 'back'})
        return items

    def _get_sync_menu_items(self):
        """Get sync menu items"""
        items = []

        if self.sync.is_enabled():
            items.extend([
                {'title': 'Sync Now', 'action': 'sync_now'},
                {'title': 'Sync Status', 'action': 'sync_status'},
                {'title': 'Device Info', 'action': 'device_info'}
            ])
        else:
            items.append({'title': 'Sync Disabled', 'action': 'none'})

        items.append({'title': '← Back', 'action': 'back'})
        return items

    def _get_settings_menu_items(self):
        """Get settings menu items"""
        return [
            {'title': 'Display Settings', 'action': 'display_settings'},
            {'title': 'GPS Settings', 'action': 'gps_settings'},
            {'title': 'System Info', 'action': 'system_info'},
            {'title': '← Back', 'action': 'back'}
        ]

    def _handle_main_menu_select(self):
        """Handle main menu selection"""
        items = self._get_main_menu_items()
        if self.selected_index < len(items):
            action = items[self.selected_index]['action']

            if action == 'exit':
                return {'action': 'exit_menu'}
            elif action in ['trips', 'sync', 'settings']:
                self.menu_stack.append((self.current_menu, self.selected_index))
                self.current_menu = action
                self.selected_index = 0

        return None

    def _handle_trips_menu_select(self):
        """Handle trips menu selection"""
        items = self._get_trips_menu_items()
        if self.selected_index < len(items):
            item = items[self.selected_index]
            action = item['action']

            if action == 'back':
                return self.navigate_back()
            elif action == 'trip_detail':
                trip = item['trip']
                current_status = trip.get('local_status', trip.get('status', 'planned'))

                # Toggle trip status
                if current_status in ['planned', 'paused', 'completed']:
                    new_status = 'active'
                    result_action = 'start_trip'
                else:
                    new_status = 'paused'
                    result_action = 'stop_trip'

                # Update in database
                self.db.update_trip_status(trip['id'], new_status)

                return {
                    'action': result_action,
                    'trip_id': trip['id'],
                    'trip_title': trip['title'],
                    'new_status': new_status
                }

        return None

    def _handle_sync_menu_select(self):
        """Handle sync menu selection"""
        items = self._get_sync_menu_items()
        if self.selected_index < len(items):
            action = items[self.selected_index]['action']

            if action == 'back':
                return self.navigate_back()
            elif action == 'sync_now':
                # Trigger sync operation
                return {'action': 'sync_now'}

        return None

    def _handle_settings_menu_select(self):
        """Handle settings menu selection"""
        items = self._get_settings_menu_items()
        if self.selected_index < len(items):
            action = items[self.selected_index]['action']

            if action == 'back':
                return self.navigate_back()

        return None

    def render(self):
        """Render current menu"""
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Draw title bar
        self._draw_title_bar(draw)

        # Draw menu content
        if self.current_menu == 'main':
            self._draw_main_menu(draw)
        elif self.current_menu == 'trips':
            self._draw_trips_menu(draw)
        elif self.current_menu == 'sync':
            self._draw_sync_menu(draw)
        elif self.current_menu == 'settings':
            self._draw_settings_menu(draw)

        # Draw navigation hints
        self._draw_navigation_hints(draw)

        return image

    def _draw_title_bar(self, draw):
        """Draw title bar"""
        # Background
        draw.rectangle([0, 0, self.width, 50], fill=0)

        # Title
        title_map = {
            'main': 'Main Menu',
            'trips': 'Trips',
            'sync': 'Sync',
            'settings': 'Settings'
        }

        title = title_map.get(self.current_menu, 'Menu')
        bbox = draw.textbbox((0, 0), title, font=self.font_title)
        title_width = bbox[2] - bbox[0]
        title_x = (self.width - title_width) // 2
        draw.text((title_x, 13), title, fill=255, font=self.font_title)

        # Time
        current_time = datetime.now().strftime("%H:%M")
        bbox = draw.textbbox((0, 0), current_time, font=self.font_medium)
        time_width = bbox[2] - bbox[0]
        draw.text((self.width - time_width - 10, 17), current_time, fill=255, font=self.font_medium)

    def _draw_main_menu(self, draw):
        """Draw main menu"""
        items = self._get_main_menu_items()
        self._draw_menu_items(draw, items, 80)

    def _draw_trips_menu(self, draw):
        """Draw trips menu"""
        items = self._get_trips_menu_items()

        # Draw header info
        y_pos = 60
        if self.trips:
            header_text = f"Found {len(self.trips)} trips"
            draw.text((20, y_pos), header_text, fill=0, font=self.font_medium)
            y_pos += 30

        self._draw_menu_items(draw, items, y_pos)

    def _draw_sync_menu(self, draw):
        """Draw sync menu"""
        items = self._get_sync_menu_items()

        # Draw sync status info
        y_pos = 60
        if self.sync.is_enabled():
            last_sync = self.db.get_sync_status('last_full_sync')
            if last_sync:
                sync_text = f"Last sync: {last_sync[:16]}"  # Show date/time part
            else:
                sync_text = "Never synced"

            draw.text((20, y_pos), sync_text, fill=0, font=self.font_small)
            y_pos += 25

        self._draw_menu_items(draw, items, y_pos)

    def _draw_settings_menu(self, draw):
        """Draw settings menu"""
        items = self._get_settings_menu_items()
        self._draw_menu_items(draw, items, 80)

    def _draw_menu_items(self, draw, items, start_y):
        """Draw menu items list"""
        y_pos = start_y
        item_height = 40

        for i, item in enumerate(items):
            # Highlight selected item
            if i == self.selected_index:
                draw.rectangle([10, y_pos - 5, self.width - 10, y_pos + item_height - 5],
                               fill=200, outline=0)

            # Draw item text
            draw.text((20, y_pos + 5), item['title'], fill=0, font=self.font_large)

            y_pos += item_height

    def _draw_navigation_hints(self, draw):
        """Draw navigation hints at bottom"""
        hints = "↑↓ Navigate  ← Back  → Select  ⏎ Select"
        bbox = draw.textbbox((0, 0), hints, font=self.font_small)
        text_width = bbox[2] - bbox[0]
        text_x = (self.width - text_width) // 2

        # Background
        draw.rectangle([0, self.height - 30, self.width, self.height], fill=240)

        # Text
        draw.text((text_x, self.height - 25), hints, fill=0, font=self.font_small)


def main():
    """Test the menu system"""
    import sys

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Mock database and sync managers for testing
    class MockDB:
        def get_trips(self):
            return [
                {'id': '1', 'title': 'Test Trip 1', 'status': 'planned'},
                {'id': '2', 'title': 'Test Trip 2', 'status': 'active', 'local_status': 'active'}
            ]

        def update_trip_status(self, trip_id, status):
            print(f"Updated trip {trip_id} to {status}")

        def get_sync_status(self, key):
            return "2024-01-01 12:00:00" if key == 'last_full_sync' else None

    class MockSync:
        def is_enabled(self):
            return True

    try:
        # Create menu system
        menu = MenuSystem(MockDB(), MockSync())

        # Test menu rendering
        image = menu.render()

        # Save test image
        image.save('/tmp/menu_test.png')
        print("Menu test image saved to /tmp/menu_test.png")

        # Test navigation
        print("Testing navigation...")
        menu.navigate_down()
        menu.navigate_down()
        result = menu.select()
        print(f"Selection result: {result}")

        print("Menu system test completed")

    except Exception as e:
        print(f"Menu system test failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
