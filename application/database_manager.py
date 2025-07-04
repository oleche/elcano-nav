#!/usr/bin/env python3
"""
Database Manager for GPS Navigation System
==========================================
Handles SQLite database operations for trips, map points, and sync data.
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite database manager for navigation system"""

    def __init__(self, db_path='/opt/elcano/navigation.db'):
        self.db_path = db_path
        self.conn = None
        self.lock = threading.Lock()

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

        logger.info(f"Database manager initialized: {db_path}")

    def _init_database(self):
        """Initialize database connection and create tables"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

            # Create tables
            self._create_tables()

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _create_tables(self):
        """Create database tables"""
        cursor = self.conn.cursor()

        # Device info table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_info (
                id TEXT PRIMARY KEY,
                name TEXT,
                sync_key TEXT,
                model_name TEXT,
                model_manufacturer TEXT,
                owner_first_name TEXT,
                owner_last_name TEXT,
                owner_email TEXT,
                last_update TEXT,
                created_at TEXT,
                updated_at TEXT,
                sync_timestamp TEXT
            )
        ''')

        # Trips table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'planned',
                local_status TEXT,
                start_date TEXT,
                end_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sync_status TEXT DEFAULT 'pending',
                metadata TEXT
            )
        ''')

        # Map points table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS map_points (
                id TEXT PRIMARY KEY,
                trip_id TEXT,
                longitude REAL,
                latitude REAL,
                altitude REAL,
                speed REAL,
                type TEXT,
                timestamp TEXT,
                address TEXT,
                notes TEXT,
                distance_from_previous REAL,
                time_from_previous INTEGER,
                sequence_order INTEGER,
                FOREIGN KEY (trip_id) REFERENCES trips (id)
            )
        ''')

        # Trip points table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trip_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                name TEXT,
                description TEXT,
                point_order INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id)
            )
        ''')

        # Logbook entries table (for pending sync)
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sync_status TEXT DEFAULT 'pending',
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

        # Device settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.conn.commit()
        logger.info("Database tables created/verified")

    def store_device_sync_data(self, sync_data):
        """Store device and trips data from sync API"""
        with self.lock:
            cursor = self.conn.cursor()

            try:
                device = sync_data.get('device', {})
                trips = sync_data.get('trips', [])

                # Store device info
                cursor.execute('''
                    INSERT OR REPLACE INTO device_info 
                    (id, name, sync_key, model_name, model_manufacturer, 
                     owner_first_name, owner_last_name, owner_email, 
                     last_update, created_at, updated_at, sync_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    device.get('id'),
                    device.get('name'),
                    device.get('syncKey'),
                    device.get('model', {}).get('name'),
                    device.get('model', {}).get('manufacturer'),
                    device.get('owner', {}).get('firstName'),
                    device.get('owner', {}).get('lastName'),
                    device.get('owner', {}).get('email'),
                    device.get('lastUpdate'),
                    device.get('createdAt'),
                    device.get('updatedAt'),
                    sync_data.get('syncTimestamp')
                ))

                # Store trips
                for trip_data in trips:
                    # Check if trip already exists
                    cursor.execute('SELECT id FROM trips WHERE id = ?', (trip_data.get('id'),))

                    if cursor.fetchone():
                        # Update existing trip
                        cursor.execute('''
                            UPDATE trips 
                            SET title = ?, description = ?, status = ?, start_date = ?, end_date = ?, 
                                metadata = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (
                            trip_data.get('title'),
                            trip_data.get('description'),
                            trip_data.get('status'),
                            trip_data.get('start_date'),
                            trip_data.get('end_date'),
                            json.dumps(trip_data.get('metadata', {})),
                            trip_data.get('id')
                        ))
                    else:
                        # Insert new trip
                        self.add_trip(trip_data)

                    # Store trip points for this trip
                    if 'points' in trip_data:
                        for i, point in enumerate(trip_data['points']):
                            cursor.execute('''
                                INSERT INTO trip_points (trip_id, latitude, longitude, name, description, point_order)
                                VALUES (?, ?, ?, ?, ?, ?)
                            ''', (
                                trip_data.get('id'),
                                point.get('latitude'),
                                point.get('longitude'),
                                point.get('name'),
                                point.get('description'),
                                i
                            ))

                self.conn.commit()
                logger.info(f"Stored {len(trips)} trips with map points")
                return True

            except Exception as e:
                logger.error(f"Error storing sync data: {e}")
                self.conn.rollback()
                return False

    def get_trips(self, status=None):
        """Get all trips from database"""
        with self.lock:
            cursor = self.conn.cursor()

            if status:
                cursor.execute('SELECT * FROM trips WHERE status = ? ORDER BY created_at DESC', (status,))
            else:
                cursor.execute('SELECT * FROM trips ORDER BY created_at DESC')

            trips = []
            for row in cursor.fetchall():
                trip = dict(row)
                trip['metadata'] = json.loads(trip['metadata']) if trip['metadata'] else {}
                trips.append(trip)

            return trips

    def get_trip_by_id(self, trip_id):
        """Get specific trip by ID"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_map_points_for_trip(self, trip_id):
        """Get all map points for a specific trip"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM map_points 
                WHERE trip_id = ? 
                ORDER BY sequence_order ASC, timestamp ASC
            ''', (trip_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trip_points(self, trip_id):
        """Get points for a specific trip"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM trip_points 
                WHERE trip_id = ? 
                ORDER BY point_order
            ''', (trip_id,))

            return [dict(row) for row in cursor.fetchall()]

    def set_active_trip(self, trip_id):
        """Set a trip as active (deactivate others)"""
        with self.lock:
            cursor = self.conn.cursor()

            # Deactivate all trips
            cursor.execute('UPDATE trips SET is_active = 0')

            # Activate selected trip
            cursor.execute('UPDATE trips SET is_active = 1 WHERE id = ?', (trip_id,))

            self.conn.commit()
            logger.info(f"Set trip {trip_id} as active")

    def get_active_trip(self):
        """Get the currently active trip"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE is_active = 1 LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_trip_status(self, trip_id, status):
        """Update trip status locally"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE trips 
                SET local_status = ?, updated_at = CURRENT_TIMESTAMP, sync_status = 'pending'
                WHERE id = ?
            ''', (status, trip_id))

            self.conn.commit()
            logger.info(f"Updated trip {trip_id} status to {status}")

    def get_trips_needing_sync(self):
        """Get trips that need status sync"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM trips 
                WHERE sync_status = 'pending' AND local_status IS NOT NULL
            ''')

            trips = []
            for row in cursor.fetchall():
                trip = dict(row)
                trip['metadata'] = json.loads(trip['metadata']) if trip['metadata'] else {}
                trips.append(trip)

            return trips

    def mark_trip_synced(self, trip_id):
        """Mark trip as synced"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                UPDATE trips 
                SET sync_status = 'synced', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (trip_id,))

            self.conn.commit()
            return True

    def add_logbook_entry(self, entry_data):
        """Add logbook entry for active trip"""
        with self.lock:
            cursor = self.conn.cursor()

            cursor.execute('''
                INSERT INTO logbook_entries 
                (timestamp, latitude, longitude, speed, heading, altitude, satellites, trip_id, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry_data.get('timestamp'),
                entry_data.get('latitude'),
                entry_data.get('longitude'),
                entry_data.get('speed', 0),
                entry_data.get('heading', 0),
                entry_data.get('altitude', 0),
                entry_data.get('satellites', 0),
                entry_data.get('trip_id'),
                entry_data.get('content')
            ))

            self.conn.commit()
            return True

    def get_logbook_entries(self, trip_id=None, limit=100):
        """Get logbook entries"""
        with self.lock:
            cursor = self.conn.cursor()

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

            return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_logbook_entries(self):
        """Get logbook entries that need to be synced"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM logbook_entries 
                WHERE sync_status = 'pending' 
                ORDER BY timestamp
            ''')

            return [dict(row) for row in cursor.fetchall()]

    def mark_logbook_entries_synced(self, entry_ids):
        """Mark logbook entries as synced"""
        with self.lock:
            cursor = self.conn.cursor()
            placeholders = ','.join(['?' for _ in entry_ids])
            cursor.execute(f'''
                UPDATE logbook_entries 
                SET sync_status = 'synced' 
                WHERE id IN ({placeholders})
            ''', entry_ids)

            self.conn.commit()
            logger.info(f"Marked {len(entry_ids)} logbook entries as synced")
            return True

    def add_trip(self, trip_data):
        """Add a new trip"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO trips (id, title, description, status, start_date, end_date, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                trip_data.get('id'),
                trip_data.get('title'),
                trip_data.get('description'),
                trip_data.get('status', 'planned'),
                trip_data.get('start_date'),
                trip_data.get('end_date'),
                json.dumps(trip_data.get('metadata', {}))
            ))

            # Add trip points if provided
            if 'points' in trip_data:
                for i, point in enumerate(trip_data['points']):
                    cursor.execute('''
                        INSERT INTO trip_points (trip_id, latitude, longitude, name, description, point_order)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        trip_data.get('id'),
                        point.get('latitude'),
                        point.get('longitude'),
                        point.get('name'),
                        point.get('description'),
                        i
                    ))

            self.conn.commit()
            logger.info(f"Added trip: {trip_data.get('title')}")
            return True

        except Exception as e:
            logger.error(f"Error adding trip: {e}")
            return False

    def set_sync_status(self, key, value):
        """Set sync status value"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO sync_status (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))

            self.conn.commit()
            return True

    def get_sync_status(self, key):
        """Get sync status value"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT value FROM sync_status WHERE key = ?', (key,))
            row = cursor.fetchone()

            return row['value'] if row else None

    def set_device_setting(self, key, value):
        """Set device setting"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO device_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))

            self.conn.commit()
            return True

    def get_device_setting(self, key, default=None):
        """Get device setting"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT value FROM device_settings WHERE key = ?', (key,))
            row = cursor.fetchone()

            return row['value'] if row else default

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")


def main():
    """Test the database manager"""
    import sys

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Create database manager
        db = DatabaseManager('/tmp/test_navigation.db')

        # Test trip creation
        test_trip = {
            'id': 'test-trip-001',
            'title': 'Test Trip',
            'description': 'A test trip for database testing',
            'status': 'planned',
            'start_date': '2024-01-01',
            'end_date': '2024-01-02',
            'points': [
                {'latitude': 52.3676, 'longitude': 4.9041, 'name': 'Amsterdam'},
                {'latitude': 52.0907, 'longitude': 5.1214, 'name': 'Utrecht'}
            ]
        }

        if db.add_trip(test_trip):
            print("Test trip added successfully")

        # Test logbook entry
        test_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'latitude': 52.3676,
            'longitude': 4.9041,
            'speed': 15.5,
            'heading': 45.0,
            'content': 'Test logbook entry'
        }

        if db.add_logbook_entry(test_entry):
            print("Test logbook entry added successfully")

        # Get trips
        trips = db.get_trips()
        print(f"Found {len(trips)} trips")

        # Get logbook entries
        entries = db.get_logbook_entries(limit=10)
        print(f"Found {len(entries)} logbook entries")

        # Cleanup
        db.close()

        # Remove test database
        import os
        os.remove('/tmp/test_navigation.db')
        print("Test completed successfully")

    except Exception as e:
        print(f"Test failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
