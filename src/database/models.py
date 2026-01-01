"""Database models for BCL Parser."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ParsedDate:
    """Represents a parsed date record."""
    id: Optional[int] = None
    table_name: str = ''
    date: date = None
    parsed_at: Optional[datetime] = None


@dataclass
class ParsedEntry:
    """Represents a parsed data entry."""
    name: str = ''              # Назва
    social_network: str = ''    # Соцмережа
    tag: str = ''               # Тема (first tag or empty)
    note: str = ''              # Примітки
    link: str = ''              # Лінк
    description: str = ''       # Хто це
    date: Optional[date] = None
    table_name: str = ''        # Target table name

