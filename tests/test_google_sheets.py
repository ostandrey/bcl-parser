"""Tests for GoogleSheetsWriter._entry_to_row_data — no network calls needed."""
import pytest
from datetime import date
from unittest.mock import MagicMock

from src.database.models import ParsedEntry
from src.config import get_column_mapping


def make_writer():
    """Return a GoogleSheetsWriter instance without connecting."""
    from src.sheets.google_sheets import GoogleSheetsWriter
    w = GoogleSheetsWriter.__new__(GoogleSheetsWriter)
    w.spreadsheet_id = "fake-id"
    w.email = None
    w.password = None
    w.client = None
    w.spreadsheet = None
    return w


def make_entry(**kwargs):
    defaults = dict(
        name="Test Name",
        social_network="Facebook",
        tag="Безбар'єрність",
        note="Some note",
        link="https://facebook.com/post/1",
        description="Хто це",
        date=date(2025, 3, 15),
        table_name="Соцмережі 2025",
    )
    defaults.update(kwargs)
    return ParsedEntry(**defaults)


class TestEntryToRowDataSocial:
    def setup_method(self):
        self.writer = make_writer()
        self.mapping = get_column_mapping("Соцмережі 2025")

    def test_returns_dict(self):
        entry = make_entry()
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_month_name_in_ukrainian(self):
        entry = make_entry(date=date(2025, 3, 15))
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
        assert result[self.mapping["Місяць"]] == "Березень"

    def test_all_months(self):
        expected = [
            "Січень", "Лютий", "Березень", "Квітень",
            "Травень", "Червень", "Липень", "Серпень",
            "Вересень", "Жовтень", "Листопад", "Грудень",
        ]
        for month_num, name in enumerate(expected, start=1):
            entry = make_entry(date=date(2025, month_num, 1))
            result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
            assert result[self.mapping["Місяць"]] == name

    def test_name_field(self):
        entry = make_entry(name="BCL Post")
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
        assert result[self.mapping["Назва"]] == "BCL Post"

    def test_social_network_field(self):
        entry = make_entry(social_network="Telegram")
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
        assert result[self.mapping["Соцмережа"]] == "Telegram"

    def test_works_for_2026_sheet(self):
        mapping_2026 = get_column_mapping("Соцмережі 2026")
        entry = make_entry(date=date(2026, 1, 5))
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2026", mapping_2026)
        assert result[mapping_2026["Місяць"]] == "Січень"

    def test_empty_date_gives_empty_month(self):
        entry = make_entry(date=None)
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
        assert result[self.mapping["Місяць"]] == ""

    def test_none_fields_become_empty_string(self):
        entry = make_entry(note=None, description=None)
        result = self.writer._entry_to_row_data(entry, "Соцмережі 2025", self.mapping)
        assert result[self.mapping["Примітки"]] == ""
        assert result[self.mapping["Хто це"]] == ""


class TestEntryToRowDataMedia:
    def setup_method(self):
        self.writer = make_writer()
        self.mapping = get_column_mapping("ЗМІ 2025")

    def test_returns_dict(self):
        entry = make_entry(social_network="", link="https://ukrinform.ua/news/1")
        result = self.writer._entry_to_row_data(entry, "ЗМІ 2025", self.mapping)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_month_field(self):
        entry = make_entry(date=date(2025, 11, 1))
        result = self.writer._entry_to_row_data(entry, "ЗМІ 2025", self.mapping)
        assert result[self.mapping["Місяць"]] == "Листопад"

    def test_media_name_field(self):
        entry = make_entry(name="Укрінформ")
        result = self.writer._entry_to_row_data(entry, "ЗМІ 2025", self.mapping)
        assert result[self.mapping["Медіа"]] == "Укрінформ"

    def test_works_for_2026_sheet(self):
        mapping_2026 = get_column_mapping("ЗМІ 2026")
        entry = make_entry(date=date(2026, 6, 15))
        result = self.writer._entry_to_row_data(entry, "ЗМІ 2026", mapping_2026)
        assert result[mapping_2026["Місяць"]] == "Червень"

    def test_unknown_sheet_returns_empty(self):
        result = self.writer._entry_to_row_data(
            make_entry(), "Вакансії", {}
        )
        assert result == {}
