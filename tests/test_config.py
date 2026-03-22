"""Tests for config module: table detection, column mapping, social network detection."""
import pytest
from datetime import date

from src.config import (
    detect_table_from_link,
    detect_table_from_entry,
    detect_social_network_from_link,
    get_column_mapping,
    SOCIAL_NETWORK_COLUMNS,
    MEDIA_COLUMNS,
)
from src.database.models import ParsedEntry


# ── detect_table_from_link ─────────────────────────────────────────────────────

class TestDetectTableFromLink:
    def test_facebook_goes_to_social(self):
        result = detect_table_from_link("https://facebook.com/post/123", date(2025, 3, 1))
        assert result == "Соцмережі 2025"

    def test_instagram_goes_to_social(self):
        result = detect_table_from_link("https://www.instagram.com/p/abc", date(2026, 1, 15))
        assert result == "Соцмережі 2026"

    def test_telegram_goes_to_social(self):
        assert detect_table_from_link("https://t.me/channel/123", date(2025, 6, 1)) == "Соцмережі 2025"

    def test_news_site_goes_to_media(self):
        result = detect_table_from_link("https://ukrinform.ua/news/123", date(2025, 5, 10))
        assert result == "ЗМІ 2025"

    def test_unknown_link_goes_to_media(self):
        assert detect_table_from_link("https://example.com/article", date(2025, 1, 1)) == "ЗМІ 2025"

    def test_year_from_entry_date_2026(self):
        result = detect_table_from_link("https://youtube.com/watch?v=abc", date(2026, 2, 28))
        assert "2026" in result

    def test_no_date_uses_current_year(self):
        result = detect_table_from_link("https://facebook.com/post")
        assert str(date.today().year) in result


# ── detect_table_from_entry ────────────────────────────────────────────────────

class TestDetectTableFromEntry:
    def _make_entry(self, social_network="", link="", entry_date=None):
        return ParsedEntry(
            social_network=social_network,
            link=link,
            date=entry_date or date(2025, 4, 1),
        )

    def test_social_network_set_goes_to_social(self):
        entry = self._make_entry(social_network="Facebook")
        assert detect_table_from_entry(entry) == "Соцмережі 2025"

    def test_no_social_network_falls_back_to_link(self):
        entry = self._make_entry(link="https://facebook.com/p/123")
        assert detect_table_from_entry(entry) == "Соцмережі 2025"

    def test_no_social_network_news_link_goes_to_media(self):
        entry = self._make_entry(link="https://hromadske.ua/posts/article")
        assert detect_table_from_entry(entry) == "ЗМІ 2025"

    def test_year_reflected_from_entry_date(self):
        entry = self._make_entry(social_network="Telegram", entry_date=date(2026, 7, 4))
        assert detect_table_from_entry(entry) == "Соцмережі 2026"

    def test_empty_social_network_string_falls_back_to_link(self):
        entry = self._make_entry(social_network="   ", link="https://t.me/ch/1")
        assert detect_table_from_entry(entry) == "Соцмережі 2025"


# ── detect_social_network_from_link ───────────────────────────────────────────

class TestDetectSocialNetworkFromLink:
    @pytest.mark.parametrize("url,expected", [
        ("https://facebook.com/page",         "Facebook"),
        ("https://www.instagram.com/p/xyz",   "Instagram"),
        ("https://twitter.com/user/status",   "Twitter (X)"),
        ("https://x.com/user/status",         "Twitter (X)"),
        ("https://t.me/channel",              "Telegram"),
        ("https://youtube.com/watch?v=abc",   "YouTube"),
        ("https://youtu.be/abc",              "YouTube"),
        ("https://tiktok.com/@user",          "Tiktok"),
        ("https://threads.net/@user",         "threads.net"),
        ("https://linkedin.com/in/user",      "LinkedIn"),
        ("https://soundcloud.com/artist",     "soundcloud"),
        ("https://ukrinform.ua/news",         ""),   # not a social network
        ("https://example.com",               ""),
    ])
    def test_detection(self, url, expected):
        assert detect_social_network_from_link(url) == expected


# ── get_column_mapping ─────────────────────────────────────────────────────────

class TestGetColumnMapping:
    def test_social_2025(self):
        assert get_column_mapping("Соцмережі 2025") == SOCIAL_NETWORK_COLUMNS

    def test_social_2026(self):
        assert get_column_mapping("Соцмережі 2026") == SOCIAL_NETWORK_COLUMNS

    def test_media_2025(self):
        assert get_column_mapping("ЗМІ 2025") == MEDIA_COLUMNS

    def test_media_2026(self):
        assert get_column_mapping("ЗМІ 2026") == MEDIA_COLUMNS

    def test_social_columns_have_required_keys(self):
        m = get_column_mapping("Соцмережі 2025")
        for key in ("Місяць", "Назва", "Хто це", "Тема", "Соцмережа", "Лінк", "Примітки"):
            assert key in m

    def test_media_columns_have_required_keys(self):
        m = get_column_mapping("ЗМІ 2025")
        for key in ("Місяць", "Медіа", "Тема", "Лінк", "Примітки"):
            assert key in m
