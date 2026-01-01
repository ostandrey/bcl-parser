"""Date tracking utilities."""
from datetime import date, timedelta
from typing import List
from ..database.db_manager import DatabaseManager


class DateTracker:
    """Tracks and manages parsed dates."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def check_missing_days(
        self, 
        table_name: str, 
        start_date: date, 
        end_date: date
    ) -> List[date]:
        """Check for missing days between start and end date."""
        return self.db.get_missing_dates(table_name, start_date, end_date)
    
    def get_today(self) -> date:
        """Get today's date."""
        return date.today()
    
    def get_date_range(self, start: date, end: date) -> List[date]:
        """Get all dates in a range."""
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            current += timedelta(days=1)
        return dates
    
    def mark_parsed(self, table_name: str, parsed_date: date):
        """Mark a date as parsed."""
        self.db.mark_date_parsed(table_name, parsed_date)
    
    def is_parsed(self, table_name: str, check_date: date) -> bool:
        """Check if a date is parsed."""
        return self.db.is_date_parsed(table_name, check_date)

