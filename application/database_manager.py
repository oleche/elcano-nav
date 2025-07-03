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

    def __init__(self, db_path='navigation.db'):
        self.db_path = db_path
        self.connection = None
        self.lock = threading.Lock()
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database with required tables"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

            # Create tables
            self._create_tables()
            logger.info(f"Database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _create_tables(self):
        """Create database tables"""
        cursor = self.connection.cursor()

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
                title TEXT,
                date TEXT,
                status TEXT,
                total_distance REAL,
                estimated_duration INTEGER,
                owner_id TEXT,
                owner_first_name TEXT,
                owner_last_name TEXT,
                owner_email TEXT,
                created_at TEXT,
                updated_at TEXT,
                is_active INTEGER DEFAULT 0,
                local_status TEXT,
                needs_sync INTEGER DEFAULT 0
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

        # Logbook entries table (for pending sync)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logbook_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id TEXT,
                timestamp TEXT,
                latitude REAL,
                longitude REAL,
                altitude REAL,
                speed REAL,
                heading REAL,
                content TEXT,
                synced INTEGER DEFAULT 0,
                created_at TEXT,
                FOREIGN KEY (trip_id) REFERENCES trips (id)
            )
        ''')

        # Sync status table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        ''')

        self.connection.commit()
        logger.info("Database tables created/verified")

    def store_device_sync_data(self, sync_data):
        """Store device and trips data from sync API"""
        with self.lock:
            cursor = self.connection.cursor()

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
                for trip in trips:
                    cursor.execute('''
                        INSERT OR REPLACE INTO trips 
                        (id, title, date, status, total_distance, estimated_duration,
                         owner_id, owner_first_name, owner_last_name, owner_email,
                         created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        trip.get('id'),
                        trip.get('title'),
                        trip.get('date'),
                        trip.get('status'),
                        trip.get('totalDistance'),
                        trip.get('estimatedDuration'),
                        trip.get('owner', {}).get('id'),
                        trip.get('owner', {}).get('firstName'),
                        trip.get('owner', {}).get('lastName'),
                        trip.get('owner', {}).get('email'),
                        trip.get('createdAt'),
                        trip.get('updatedAt')
                    ))

                    # Store map points for this trip
                    map_points = trip.get('mapPoints', [])
                    for point in map_points:
                        cursor.execute('''
                            INSERT OR REPLACE INTO map_points 
                            (id, trip_id, longitude, latitude, altitude, speed, type,
                             timestamp, address, notes, distance_from_previous,
                             time_from_previous, sequence_order)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            point.get('id'),
                            trip.get('id'),
                            point.get('longitude'),
                            point.get('latitude'),
                            point.get('altitude'),
                            point.get('speed'),
                            point.get('type'),
                            point.get('timestamp'),
                            point.get('address'),
                            point.get('notes'),
                            point.get('distanceFromPrevious'),
                            point.get('timeFromPrevious'),
                            point.get('sequenceOrder')
                        ))

                self.connection.commit()
                logger.info(f"Stored {len(trips)} trips with map points")
                return True

            except Exception as e:
                logger.error(f"Error storing sync data: {e}")
                self.connection.rollback()
                return False

    def get_trips(self):
        """Get all trips from database"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT * FROM trips 
                ORDER BY date DESC, created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def get_trip_by_id(self, trip_id):
        """Get specific trip by ID"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_map_points_for_trip(self, trip_id):
        """Get all map points for a specific trip"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT * FROM map_points 
                WHERE trip_id = ? 
                ORDER BY sequence_order ASC, timestamp ASC
            ''', (trip_id,))
            return [dict(row) for row in cursor.fetchall()]

    def set_active_trip(self, trip_id):
        """Set a trip as active (deactivate others)"""
        with self.lock:
            cursor = self.connection.cursor()

            # Deactivate all trips
            cursor.execute('UPDATE trips SET is_active = 0')

            # Activate selected trip
            cursor.execute('UPDATE trips SET is_active = 1 WHERE id = ?', (trip_id,))

            self.connection.commit()
            logger.info(f"Set trip {trip_id} as active")

    def get_active_trip(self):
        """Get the currently active trip"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM trips WHERE is_active = 1 LIMIT 1')
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_trip_status(self, trip_id, status, needs_sync=True):
        """Update trip status locally"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE trips 
                SET local_status = ?, needs_sync = ?, updated_at = ?
                WHERE id = ?
            ''', (status, 1 if needs_sync else 0, datetime.now().isoformat(), trip_id))

            self.connection.commit()
            logger.info(f"Updated trip {trip_id} status to {status}")

    def get_trips_needing_sync(self):
        """Get trips that need status sync"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM trips WHERE needs_sync = 1')
            return [dict(row) for row in cursor.fetchall()]

    def mark_trip_synced(self, trip_id):
        """Mark trip as synced"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                UPDATE trips 
                SET needs_sync = 0, status = local_status
                WHERE id = ?
            ''', (trip_id,))
            self.connection.commit()

    def add_logbook_entry(self, trip_id, gps_data, content=None):
        """Add logbook entry for active trip"""
        with self.lock:
            cursor = self.connection.cursor()

            entry_content = content or f"GPS update - Speed: {gps_data.get('speed', 0):.1f} km/h, Heading: {gps_data.get('heading', 0):.0f}°"

            cursor.execute('''
                INSERT INTO logbook_entries 
                (trip_id, timestamp, latitude, longitude, altitude, speed, heading, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trip_id,
                datetime.now(timezone.utc).isoformat(),
                gps_data.get('latitude'),
                gps_data.get('longitude'),
                gps_data.get('altitude', 0),
                gps_data.get('speed', 0),
                gps_data.get('heading', 0),
                entry_content,
                datetime.now().isoformat()
            ))

            self.connection.commit()
            return cursor.lastrowid

    def get_unsynced_logbook_entries(self, trip_id=None):
        """Get logbook entries that haven't been synced"""
        with self.lock:
            cursor = self.connection.cursor()

            if trip_id:
                cursor.execute('''
                    SELECT * FROM logbook_entries 
                    WHERE trip_id = ? AND synced = 0 
                    ORDER BY timestamp ASC
                ''', (trip_id,))
            else:
                cursor.execute('''
                    SELECT * FROM logbook_entries 
                    WHERE synced = 0 
                    ORDER BY timestamp ASC
                ''')

            return [dict(row) for row in cursor.fetchall()]

    def mark_logbook_entries_synced(self, entry_ids):
        """Mark logbook entries as synced"""
        with self.lock:
            cursor = self.connection.cursor()
            placeholders = ','.join(['?' for _ in entry_ids])
            cursor.execute(f'UPDATE logbook_entries SET synced = 1 WHERE id IN ({placeholders})', entry_ids)
            self.connection.commit()

    def set_sync_status(self, key, value):
        """Set sync status value"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO sync_status (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, str(value), datetime.now().isoformat()))
            self.connection.commit()

    def get_sync_status(self, key, default=None):
        """Get sync status value"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('SELECT value FROM sync_status WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def store_ping_position(self, position_data):
        """Store last ping position data"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO sync_status (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', ('last_ping_position', json.dumps(position_data), datetime.now().isoformat()))
            self.connection.commit()

    def get_last_ping_position(self):
        """Get last ping position data"""
        with self.lock:
            cursor = self.connection.cursor()
            cursor.execute('SELECT value FROM sync_status WHERE key = ?', ('last_ping_position',))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
            return None

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
