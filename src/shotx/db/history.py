"""SQLite database manager for tracking capture history."""

from __future__ import annotations

import sqlite3
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class HistoryRecord:
    id: int
    filepath: str
    timestamp: datetime
    url: Optional[str]
    size_bytes: int
    capture_type: str

class HistoryManager:
    """Manages the SQLite database containing capture history."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Create the tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filepath TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        url TEXT,
                        size_bytes INTEGER DEFAULT 0,
                        capture_type TEXT DEFAULT 'image'
                    )
                    """
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize history database: {e}")

    def add_record(self, filepath: str | Path, size_bytes: int = 0, capture_type: str = "image") -> Optional[int]:
        """Insert a new capture record and return its ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    """
                    INSERT INTO history (filepath, size_bytes, capture_type, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (str(filepath), size_bytes, capture_type, now_str)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to insert history record: {e}")
            return None

    def update_url(self, id: int, url: str) -> bool:
        """Update the URL for a given history record."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE history SET url = ? WHERE id = ?",
                    (url, id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to update URL in history: {e}")
            return False

    def update_url_by_path(self, filepath: str | Path, url: str) -> bool:
        """Update the URL using the exact system file path."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE history SET url = ? WHERE filepath = ?",
                    (url, str(filepath))
                )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to update URL by path in history: {e}")
            return False

    def get_all(self, limit: int = 200, offset: int = 0, search: str = "") -> List[HistoryRecord]:
        """Retrieve recent history records, optionally filtered by search query.

        The search query matches against filepath and url columns using
        case-insensitive LIKE.
        """
        records = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if search:
                    pattern = f"%{search}%"
                    cursor = conn.execute(
                        "SELECT * FROM history "
                        "WHERE filepath LIKE ? OR url LIKE ? "
                        "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                        (pattern, pattern, limit, offset),
                    )
                else:
                    cursor = conn.execute(
                        "SELECT * FROM history ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                        (limit, offset),
                    )
                
                for row in cursor.fetchall():
                    # Parse timestamp (SQLite defaults to 'YYYY-MM-DD HH:MM:SS')
                    ts = row['timestamp']
                    try:
                        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        dt = datetime.now() # Fallback

                    records.append(
                        HistoryRecord(
                            id=row['id'],
                            filepath=row['filepath'],
                            timestamp=dt,
                            url=row['url'],
                            size_bytes=row['size_bytes'],
                            capture_type=row['capture_type']
                        )
                    )
        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve history: {e}")
            
        return records

    def delete_record(self, id: int) -> bool:
        """Delete a record from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM history WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to delete history record: {e}")
            return False
            
    def clear_all(self) -> bool:
        """Delete all records from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM history")
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to clear history: {e}")
            return False
