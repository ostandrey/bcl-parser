"""SQLite database manager for BCL Parser."""
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional
from .models import ParsedDate


class DatabaseManager:
    """Manages SQLite database operations."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / '.bcl-parser' / 'parser.db'
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Table for tracking parsed dates
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parsed_dates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    parsed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(table_name, date)
                )
            ''')
            
            # Table for caching parsed data (before submission)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS parsed_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def mark_date_parsed(self, table_name: str, parsed_date: date):
        """Mark a date as parsed for a specific table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO parsed_dates (table_name, date, parsed_at)
                VALUES (?, ?, ?)
            ''', (table_name, parsed_date.isoformat(), datetime.now().isoformat()))
            conn.commit()
    
    def is_date_parsed(self, table_name: str, check_date: date) -> bool:
        """Check if a date has been parsed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM parsed_dates
                WHERE table_name = ? AND date = ?
            ''', (table_name, check_date.isoformat()))
            return cursor.fetchone()[0] > 0
    
    def get_parsed_dates(self, table_name: str) -> List[date]:
        """Get all parsed dates for a table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date FROM parsed_dates
                WHERE table_name = ?
                ORDER BY date
            ''', (table_name,))
            rows = cursor.fetchall()
            return [date.fromisoformat(row[0]) for row in rows]
    
    def get_missing_dates(
        self, 
        table_name: str, 
        start_date: date, 
        end_date: date
    ) -> List[date]:
        """Get dates that haven't been parsed between start and end."""
        parsed_dates = set(self.get_parsed_dates(table_name))
        missing = []
        current = start_date
        while current <= end_date:
            if current not in parsed_dates:
                missing.append(current)
            # Move to next day
            from datetime import timedelta
            current += timedelta(days=1)
        return missing
    
    def clear_cache(self, table_name: Optional[str] = None):
        """Clear parsed cache."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if table_name:
                cursor.execute('DELETE FROM parsed_cache WHERE table_name = ?', (table_name,))
            else:
                cursor.execute('DELETE FROM parsed_cache')
            conn.commit()

