#!/usr/bin/env python3
"""
Database Manager for GPS Navigation System
==========================================
Manages SQLite database for storing trips, logbook entries, and sync data.
"""

import sqlite3
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Database manager for navigation system data"""

    def __init__(self, db_path: str = '/opt/elcano/navigation.db'):
        self.db_path = Path(db_path)
        self.connection = None

        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._initialize_database()

        logger.info(f"Database manager initialized: {self.db_path}")

    def _initialize_database(self):
        """Initialize database connection and create tables"""
        try:
            self.connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

            # Create tables
            self._create_tables()

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _create_tables(self):
        """Create database tables"""
        cursor = self.connection.cursor()

        # Trips table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'planned',
                local_status TEXT,
                sync_status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Logbook entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logbook_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed REAL DEFAULT 0,
                heading REAL DEFAULT 0,
                altitude REAL DEFAULT 0,
                satellites INTEGER DEFAULT 0,
                trip_id TEXT,
                content TEXT,
                sync_status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id)
            )
        ''')

        # Waypoints table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS waypoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id TEXT NOT NULL,
                name TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                order_index INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id)
            )
        ''')

        # Sync status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.connection.commit()
        logger.debug("Database tables created/verified")

    def add_trip(self, trip_data: Dict[str, Any]) -> bool:
        """Add a new trip"""
        try:
            cursor = self.connection.cursor()

            cursor.execute('''
                INSERT INTO trips (id, title, description, start_date, end_date, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                trip_data.get('id'),
                trip_data.get('title'),
                trip_data.get('description', ''),
                trip_data.get('start_date'),
                trip_data.get('end_date'),
                trip_data.get('status', 'planned')
            ))

            self.connection.commit()
            logger.info(f"Added trip: {trip_data.get('title')}")
            return True

        except Exception as e:
            logger.error(f"Error adding trip: {e}")
            return False

    def get_trips(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trips, optionally filtered by status"""
        try:
            cursor = self.connection.cursor()

            if status:
                cursor.execute('SELECT * FROM trips WHERE status = ? ORDER BY created_at DESC', (status,))
            else:
                cursor.execute('SELECT * FROM trips ORDER BY created_at DESC')

            trips = []
            for row in cursor.fetchall():
                trips.append(dict(row))

            return trips

        except Exception as e:
            logger.error(f"Error getting trips: {e}")
            return []

    def get_current_trip(self) -> Optional[Dict[str, Any]]:
        """Get currently active trip"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM trips WHERE status = ? ORDER BY updated_at DESC LIMIT 1', ('active',))

            row = cursor.fetchone()
            return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting current trip: {e}")
            return None

    def update_trip_status(self, trip_id: str, status: str) -> bool:
        """Update trip status"""
        try:
            cursor = self.connection.cursor()

            cursor.execute('''
                UPDATE trips 
                SET status = ?, local_status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            ''', (status, status, trip_id))

            self.connection.commit()
            logger.info(f"Updated trip {trip_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Error updating trip status: {e}")
            return False

    def add_logbook_entry(self, entry_data: Dict[str, Any]) -> bool:
        """Add a logbook entry"""
        try:
            cursor = self.connection.cursor()

            cursor.execute('''
                INSERT INTO logbook_entries 
                (timestamp, latitude, longitude, speed, heading, altitude, satellites, trip_id, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                entry_data.get('latitude'),
                entry_data.get('longitude'),
                entry_data.get('speed', 0),
                entry_data.get('heading', 0),
                entry_data.get('altitude', 0),
                entry_data.get('satellites', 0),
                entry_data.get('trip_id'),
                entry_data.get('content', '')
            ))

            self.connection.commit()
            logger.debug("Added logbook entry")
            return True

        except Exception as e:
            logger.error(f"Error adding logbook entry: {e}")
            return False

    def get_logbook_entries(self, trip_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get logbook entries"""
        try:
            cursor = self.connection.cursor()

            if trip_id:
                cursor.execute('''
                    SELECT * FROM logbook_entries 
                    WHERE trip_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (trip_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM logbook_entries 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))

            entries = []
            for row in cursor.fetchall():
                entries.append(dict(row))

            return entries

        except Exception as e:
            logger.error(f"Error getting logbook entries: {e}")
            return []

    def get_unsynced_logbook_entries(self) -> List[Dict[str, Any]]:
        """Get logbook entries that need to be synced"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT * FROM logbook_entries 
                WHERE sync_status = 'pending' 
                ORDER BY timestamp ASC
            ''')

            entries = []
            for row in cursor.fetchall():
                entries.append(dict(row))

            return entries

        except Exception as e:
            logger.error(f"Error getting unsynced logbook entries: {e}")
            return []

    def mark_logbook_entries_synced(self, entry_ids: List[int]) -> bool:
        """Mark logbook entries as synced"""
        try:
            cursor = self.connection.cursor()

            for entry_id in entry_ids:
                cursor.execute('''
                    UPDATE logbook_entries 
                    SET sync_status = 'synced' 
                    WHERE id = ?
                ''', (entry_id,))

            self.connection.commit()
            logger.info(f"Marked {len(entry_ids)} logbook entries as synced")
            return True

        except Exception as e:
            logger.error(f"Error marking logbook entries as synced: {e}")
            return False

    def add_waypoint(self, waypoint_data: Dict[str, Any]) -> bool:
        """Add a waypoint to a trip"""
        try:
            cursor = self.connection.cursor()

            cursor.execute('''
                INSERT INTO waypoints (trip_id, name, latitude, longitude, order_index)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                waypoint_data.get('trip_id'),
                waypoint_data.get('name', ''),
                waypoint_data.get('latitude'),
                waypoint_data.get('longitude'),
                waypoint_data.get('order_index', 0)
            ))

            self.connection.commit()
            logger.debug(f"Added waypoint for trip {waypoint_data.get('trip_id')}")
            return True

        except Exception as e:
            logger.error(f"Error adding waypoint: {e}")
            return False

    def get_trip_waypoints(self, trip_id: str) -> List[Dict[str, Any]]:
        """Get waypoints for a trip"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT * FROM waypoints 
                WHERE trip_id = ? 
                ORDER BY order_index ASC
            ''', (trip_id,))

            waypoints = []
            for row in cursor.fetchall():
                waypoints.append(dict(row))

            return waypoints

        except Exception as e:
            logger.error(f"Error getting trip waypoints: {e}")
            return []

    def get_trip_points(self, trip_id: str) -> List[Dict[str, Any]]:
        """Get all points (waypoints + logbook entries) for a trip"""
        waypoints = self.get_trip_waypoints(trip_id)
        logbook_entries = self.get_logbook_entries(trip_id)

        # Convert to common format
        points = []

        # Add waypoints
        for wp in waypoints:
            points.append({
                'latitude': wp['latitude'],
                'longitude': wp['longitude'],
                'type': 'waypoint',
                'name': wp.get('name', ''),
                'order': wp.get('order_index', 0)
            })

        # Add logbook entries
        for entry in logbook_entries:
            points.append({
                'latitude': entry['latitude'],
                'longitude': entry['longitude'],
                'type': 'logbook',
                'timestamp': entry['timestamp'],
                'speed': entry.get('speed', 0)
            })

        return points

    def store_device_sync_data(self, sync_data: Dict[str, Any]) -> bool:
        """Store device sync data from API"""
        try:
            # Store trips
            trips = sync_data.get('trips', [])
            for trip in trips:
                # Check if trip exists
                cursor = self.connection.cursor()
                cursor.execute('SELECT id FROM trips WHERE id = ?', (trip['id'],))

                if cursor.fetchone():
                    # Update existing trip
                    cursor.execute('''
                        UPDATE trips 
                        SET title = ?, description = ?, start_date = ?, end_date = ?, status = ?
                        WHERE id = ?
                    ''', (
                        trip.get('title'),
                        trip.get('description', ''),
                        trip.get('startDate'),
                        trip.get('endDate'),
                        trip.get('status', 'planned'),
                        trip['id']
                    ))
                else:
                    # Insert new trip
                    cursor.execute('''
                        INSERT INTO trips (id, title, description, start_date, end_date, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        trip['id'],
                        trip.get('title'),
                        trip.get('description', ''),
                        trip.get('startDate'),
                        trip.get('endDate'),
                        trip.get('status', 'planned')
                    ))

                # Store waypoints if present
                waypoints = trip.get('waypoints', [])
                for i, waypoint in enumerate(waypoints):
                    cursor.execute('''
                        INSERT OR REPLACE INTO waypoints (trip_id, name, latitude, longitude, order_index)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        trip['id'],
                        waypoint.get('name', f'Waypoint {i + 1}'),
                        waypoint.get('latitude'),
                        waypoint.get('longitude'),
                        i
                    ))

            self.connection.commit()
            logger.info(f"Stored sync data for {len(trips)} trips")
            return True

        except Exception as e:
            logger.error(f"Error storing device sync data: {e}")
            return False

    def get_trips_needing_sync(self) -> List[Dict[str, Any]]:
        """Get trips that need to be synced"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT * FROM trips 
                WHERE local_status IS NOT NULL 
                AND (sync_status = 'pending' OR sync_status IS NULL)
            ''')

            trips = []
            for row in cursor.fetchall():
                trips.append(dict(row))

            return trips

        except Exception as e:
            logger.error(f"Error getting trips needing sync: {e}")
            return []

    def mark_trip_synced(self, trip_id: str) -> bool:
        """Mark trip as synced"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE trips 
                SET sync_status = 'synced', local_status = NULL 
                WHERE id = ?
            ''', (trip_id,))

            self.connection.commit()
            logger.info(f"Marked trip {trip_id} as synced")
            return True

        except Exception as e:
            logger.error(f"Error marking trip as synced: {e}")
            return False

    def set_sync_status(self, key: str, value: str) -> bool:
        """Set sync status value"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO sync_status (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))

            self.connection.commit()
            return True

        except Exception as e:
            logger.error(f"Error setting sync status: {e}")
            return False

    def get_sync_status(self, key: str) -> Optional[str]:
        """Get sync status value"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT value FROM sync_status WHERE key = ?', (key,))

            row = cursor.fetchone()
            return row['value'] if row else None

        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return None

    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))

            self.connection.commit()
            return True

        except Exception as e:
            logger.error(f"Error setting setting: {e}")
            return False

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting value"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))

            row = cursor.fetchone()
            return row['value'] if row else default

        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return default

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Database connection closed")


def main():
    """Test the database manager"""
    import tempfile
    import os

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Create database manager
        db = DatabaseManager(db_path)

        # Test trip operations
        print("Testing trip operations...")

        trip_data = {
            'id': 'test-trip-1',
            'title': 'Test Trip',
            'description': 'A test trip for database testing',
            'start_date': '2024-01-01',
            'end_date': '2024-01-07',
            'status': 'planned'
        }

        db.add_trip(trip_data)
        trips = db.get_trips()
        print(f"Added trip, total trips: {len(trips)}")

        # Test logbook operations
        print("Testing logbook operations...")

        entry_data = {
            'latitude': 52.3676,
            'longitude': 4.9041,
            'speed': 5.5,
            'heading': 180,
            'trip_id': 'test-trip-1',
            'content': 'Test logbook entry'
        }

        db.add_logbook_entry(entry_data)
        entries = db.get_logbook_entries()
        print(f"Added logbook entry, total entries: {len(entries)}")

        # Test waypoint operations
        print("Testing waypoint operations...")

        waypoint_data = {
            'trip_id': 'test-trip-1',
            'name': 'Test Waypoint',
            'latitude': 52.3676,
            'longitude': 4.9041,
            'order_index': 0
        }

        db.add_waypoint(waypoint_data)
        waypoints = db.get_trip_waypoints('test-trip-1')
        print(f"Added waypoint, total waypoints: {len(waypoints)}")

        # Test settings
        print("Testing settings...")

        db.set_setting('test_key', 'test_value')
        value = db.get_setting('test_key')
        print(f"Set and retrieved setting: {value}")

        # Cleanup
        db.close()
        print("Database tests completed successfully")

    except Exception as e:
        print(f"Database test error: {e}")
        return 1
    finally:
        # Clean up temporary file
        try:
            os.unlink(db_path)
        except:
            pass

    return 0


if __name__ == "__main__":
    exit(main())
