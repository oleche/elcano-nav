#!/usr/bin/env python3
"""
Menu System for GPS Navigation
==============================
Handles menu navigation and trip selection interface.
"""

import logging
from PIL import Image, ImageDraw, ImageFont
from enum import Enum

logger = logging.getLogger(__name__)

class MenuState(Enum):
    HIDDEN = "hidden"
    TRIP_LIST = "trip_list"
    TRIP_SELECTED = "trip_selected"

class MenuSystem:
    """Menu system for trip management"""
    
    def __init__(self, database_manager, width=800, height=480):
        self.db = database_manager
        self.width = width
        self.height = height
        self.state = MenuState.HIDDEN
        
        # Menu state
        self.trips = []
        self.selected_trip_index = 0
        self.selected_trip = None
        self.menu_options = []
        self.selected_option_index = 0
        
        # Load fonts
        self.font_small = self._load_font(14)
        self.font_medium = self._load_font(18)
        self.font_large = self._load_font(22)
        
    def _load_font(self, size):
        """Load font with fallback"""
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except:
            try:
                return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", size)
            except:
                return ImageFont.load_default()
    
    def toggle_menu(self):
        """Toggle menu visibility"""
        if self.state == MenuState.HIDDEN:
            self._show_trip_list()
        else:
            self.hide_menu()
    
    def _show_trip_list(self):
        """Show trip list menu"""
        self.trips = self.db.get_trips()
        active_trip = self.db.get_active_trip()
        
        if active_trip:
            # If there's an active trip, show it and don't allow selection of others
            self.selected_trip = active_trip
            self.state = MenuState.TRIP_SELECTED
            self._setup_trip_options()
        else:
            # Show trip list for selection
            self.state = MenuState.TRIP_LIST
            self.selected_trip_index = 0
    
    def _setup_trip_options(self):
        """Setup options for selected trip"""
        if not self.selected_trip:
            return
            
        status = self.selected_trip.get('local_status') or self.selected_trip.get('status')
        
        if status in ['NOT_STARTED', 'NOT_COMPLETED']:
            self.menu_options = ['Start Trip', 'Back']
        elif status == 'IN_ROUTE':
            self.menu_options = ['Stop Trip', 'Back']
        else:
            self.menu_options = ['Back']
        
        self.selected_option_index = 0
    
    def hide_menu(self):
        """Hide menu"""
        self.state = MenuState.HIDDEN
        self.selected_trip = None
        self.menu_options = []
    
    def navigate_up(self):
        """Navigate up in current menu"""
        if self.state == MenuState.TRIP_LIST:
            if self.trips and self.selected_trip_index > 0:
                self.selected_trip_index -= 1
        elif self.state == MenuState.TRIP_SELECTED:
            if self.menu_options and self.selected_option_index > 0:
                self.selected_option_index -= 1
    
    def navigate_down(self):
        """Navigate down in current menu"""
        if self.state == MenuState.TRIP_LIST:
            if self.trips and self.selected_trip_index < len(self.trips) - 1:
                self.selected_trip_index += 1
        elif self.state == MenuState.TRIP_SELECTED:
            if self.menu_options and self.selected_option_index < len(self.menu_options) - 1:
                self.selected_option_index += 1
    
    def select_current(self):
        """Select current menu item"""
        if self.state == MenuState.TRIP_LIST:
            if self.trips and self.selected_trip_index < len(self.trips):
                self.selected_trip = self.trips[self.selected_trip_index]
                self.state = MenuState.TRIP_SELECTED
                self._setup_trip_options()
                return 'trip_selected'
                
        elif self.state == MenuState.TRIP_SELECTED:
            if self.menu_options and self.selected_option_index < len(self.menu_options):
                option = self.menu_options[self.selected_option_index]
                
                if option == 'Start Trip':
                    return 'start_trip'
                elif option == 'Stop Trip':
                    return 'stop_trip'
                elif option == 'Back':
                    if self.db.get_active_trip():
                        self.hide_menu()
                        return 'back_to_map'
                    else:
                        self.state = MenuState.TRIP_LIST
                        return 'back_to_list'
        
        return None
    
    def go_back(self):
        """Go back in menu hierarchy"""
        if self.state == MenuState.TRIP_SELECTED:
            active_trip = self.db.get_active_trip()
            if active_trip:
                self.hide_menu()
                return 'back_to_map'
            else:
                self.state = MenuState.TRIP_LIST
                return 'back_to_list'
        elif self.state == MenuState.TRIP_LIST:
            self.hide_menu()
            return 'back_to_map'
        
        return None
    
    def render_menu(self):
        """Render current menu state"""
        if self.state == MenuState.HIDDEN:
            return None
            
        # Create menu image
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        
        # Draw menu background
        menu_margin = 50
        draw.rectangle([
            menu_margin, menu_margin, 
            self.width - menu_margin, self.height - menu_margin
        ], fill=255, outline=0, width=2)
        
        if self.state == MenuState.TRIP_LIST:
            self._render_trip_list(draw, menu_margin)
        elif self.state == MenuState.TRIP_SELECTED:
            self._render_trip_options(draw, menu_margin)
        
        return image
    
    def _render_trip_list(self, draw, margin):
        """Render trip list menu"""
        # Title
        title = "Select Trip"
        draw.text((margin + 20, margin + 20), title, fill=0, font=self.font_large)
        
        # Instructions
        instructions = "Use Zoom buttons to navigate, Button 3 to select, Button 4 to exit"
        draw.text((margin + 20, margin + 50), instructions, fill=0, font=self.font_small)
        
        # Trip list
        y_start = margin + 90
        line_height = 40
        
        if not self.trips:
            draw.text((margin + 20, y_start), "No trips available", fill=0, font=self.font_medium)
            return
        
        for i, trip in enumerate(self.trips):
            y_pos = y_start + (i * line_height)
            
            # Highlight selected trip
            if i == self.selected_trip_index:
                draw.rectangle([
                    margin + 10, y_pos - 5,
                    self.width - margin - 10, y_pos + line_height - 10
                ], fill=200, outline=0)
            
            # Trip info
            title = trip.get('title', 'Untitled Trip')
            status = trip.get('local_status') or trip.get('status', 'UNKNOWN')
            date = trip.get('date', '')[:10] if trip.get('date') else ''
            
            trip_text = f"{title} - {status}"
            if date:
                trip_text += f" ({date})"
            
            draw.text((margin + 20, y_pos), trip_text, fill=0, font=self.font_medium)
    
    def _render_trip_options(self, draw, margin):
        """Render trip options menu"""
        if not self.selected_trip:
            return
            
        # Trip title
        title = self.selected_trip.get('title', 'Untitled Trip')
        draw.text((margin + 20, margin + 20), title, fill=0, font=self.font_large)
        
        # Trip details
        status = self.selected_trip.get('local_status') or self.selected_trip.get('status', 'UNKNOWN')
        date = self.selected_trip.get('date', '')[:10] if self.selected_trip.get('date') else ''
        distance = self.selected_trip.get('total_distance', 0)
        
        details = f"Status: {status}"
        if date:
            details += f" | Date: {date}"
        if distance:
            details += f" | Distance: {distance:.1f} km"
            
        draw.text((margin + 20, margin + 50), details, fill=0, font=self.font_small)
        
        # Instructions
        instructions = "Use Zoom buttons to navigate, Button 3 to select, Button 4 to go back"
        draw.text((margin + 20, margin + 80), instructions, fill=0, font=self.font_small)
        
        # Options
        y_start = margin + 120
        line_height = 40
        
        for i, option in enumerate(self.menu_options):
            y_pos = y_start + (i * line_height)
            
            # Highlight selected option
            if i == self.selected_option_index:
                draw.rectangle([
                    margin + 10, y_pos - 5,
                    self.width - margin - 10, y_pos + line_height - 10
                ], fill=200, outline=0)
            
            draw.text((margin + 20, y_pos), option, fill=0, font=self.font_medium)
    
    def get_selected_trip(self):
        """Get currently selected trip"""
        return self.selected_trip
    
    def is_visible(self):
        """Check if menu is visible"""
        return self.state != MenuState.HIDDEN
