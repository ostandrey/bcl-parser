"""Tests for DatabaseManager — uses in-memory SQLite (no filesystem side effects)."""
import pytest
from datetime import date
from pathlib import Path
import tempfile

from src.database.db_manager import DatabaseManager


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(db_path=tmp_path / "test.db")


class TestMarkDateParsed:
    def test_mark_and_check(self, db):
        d = date(2025, 3, 15)
        db.mark_date_parsed("Соцмережі 2025", d)
        assert db.is_date_parsed("Соцмережі 2025", d) is True

    def test_different_table_not_parsed(self, db):
        d = date(2025, 3, 15)
        db.mark_date_parsed("Соцмережі 2025", d)
        assert db.is_date_parsed("ЗМІ 2025", d) is False

    def test_double_mark_no_error(self, db):
        d = date(2025, 1, 1)
        db.mark_date_parsed("Соцмережі 2025", d)
        db.mark_date_parsed("Соцмережі 2025", d)  # should not raise
        assert db.is_date_parsed("Соцмережі 2025", d) is True

    def test_not_parsed_returns_false(self, db):
        assert db.is_date_parsed("Соцмережі 2025", date(2025, 1, 1)) is False


class TestGetParsedDates:
    def test_returns_sorted_dates(self, db):
        dates = [date(2025, 3, 5), date(2025, 1, 10), date(2025, 2, 20)]
        for d in dates:
            db.mark_date_parsed("Соцмережі 2025", d)
        result = db.get_parsed_dates("Соцмережі 2025")
        assert result == sorted(dates)

    def test_empty_when_no_dates(self, db):
        assert db.get_parsed_dates("Соцмережі 2025") == []

    def test_isolated_by_table(self, db):
        db.mark_date_parsed("Соцмережі 2025", date(2025, 5, 1))
        assert db.get_parsed_dates("ЗМІ 2025") == []


class TestGetMissingDates:
    def test_all_missing_when_none_parsed(self, db):
        start, end = date(2025, 1, 1), date(2025, 1, 3)
        missing = db.get_missing_dates("Соцмережі 2025", start, end)
        assert missing == [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]

    def test_no_missing_when_all_parsed(self, db):
        for day in range(1, 4):
            db.mark_date_parsed("Соцмережі 2025", date(2025, 1, day))
        missing = db.get_missing_dates("Соцмережі 2025", date(2025, 1, 1), date(2025, 1, 3))
        assert missing == []

    def test_partial_missing(self, db):
        db.mark_date_parsed("Соцмережі 2025", date(2025, 1, 2))
        missing = db.get_missing_dates("Соцмережі 2025", date(2025, 1, 1), date(2025, 1, 3))
        assert date(2025, 1, 2) not in missing
        assert date(2025, 1, 1) in missing
        assert date(2025, 1, 3) in missing

    def test_single_day_range(self, db):
        d = date(2025, 6, 15)
        missing = db.get_missing_dates("Соцмережі 2025", d, d)
        assert missing == [d]

    def test_single_day_range_already_parsed(self, db):
        d = date(2025, 6, 15)
        db.mark_date_parsed("Соцмережі 2025", d)
        assert db.get_missing_dates("Соцмережі 2025", d, d) == []
