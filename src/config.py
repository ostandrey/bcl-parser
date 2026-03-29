"""Configuration management for BCL Parser."""
import os
import json
from pathlib import Path
from typing import Dict, Optional

# Social network domains (for detection)
SOCIAL_NETWORK_DOMAINS = [
    'facebook.com',
    'instagram.com',
    'twitter.com',
    'x.com',
    'linkedin.com',
    'youtube.com',
    'youtu.be',
    't.me',
    'telegram.me',
    'tiktok.com',
    'threads.net',
    'soundcloud.com',
]

# Table name patterns (year-based)
TABLE_NAME_PATTERNS = {
    'social_network': 'Соцмережі {YEAR}',
    'media': 'ЗМІ {YEAR}',
}

# Legacy mapping for backward compatibility (deprecated, use detect_table_from_entry instead)
SOCIAL_NETWORKS = {
    domain: 'Соцмережі 2025' for domain in SOCIAL_NETWORK_DOMAINS
}

# Default table for non-social networks (deprecated, use detect_table_from_entry instead)
DEFAULT_MEDIA_TABLE = 'ЗМІ 2025'

# Available tables
AVAILABLE_TABLES = ['Соцмережі 2025', 'ЗМІ 2025', 'Вакансії']

# Social network dropdown options (must match Google Sheets dropdown)
SOCIAL_NETWORK_OPTIONS = [
    'Facebook',
    'Instagram',
    'Twitter (X)',
    'LinkedIn',
    'YouTube',
    'Telegram',
    'Tiktok',
    'threads.net',
    'soundcloud'
]

# Tag dropdown options (Тема) - must match Google Sheets dropdown
TAG_OPTIONS = [
    'Активні парки',
    'Альбом бб рішень',
    'ББ маршрути',
    'ББ укриття',
    'Безбар\'єрність',
    'Вакансії',
    'Витачів',
    'КИТ Кураж',
    'Локо Сіті',
    'M86',
    'НУШ',
    'Облаштування житла',
    'Профтех',
    'Профтех Славутич',
    'Психкімнати',
    'ПУМБ',
    'Соцжитло',
    'Терсад',
    'Урбан-парк ВДНГ',
    'Школа Посад',
    'Виставка " 86дМ"',
    'Трансформація шкіл',
    'Візія Маріуполя',
]

# Map domains to dropdown options
DOMAIN_TO_SOCIAL_NETWORK = {
    'facebook.com': 'Facebook',
    'instagram.com': 'Instagram',
    'twitter.com': 'Twitter (X)',
    'x.com': 'Twitter (X)',
    'linkedin.com': 'LinkedIn',
    'youtube.com': 'YouTube',
    'youtu.be': 'YouTube',
    't.me': 'Telegram',
    'telegram.me': 'Telegram',
    'tiktok.com': 'Tiktok',
    'threads.net': 'threads.net',
    'soundcloud.com': 'soundcloud',
}

# Base column mappings (year-agnostic templates)
SOCIAL_NETWORK_COLUMNS = {
    'Місяць': 'A',     # Column A
    'Назва': 'B',      # Column B
    'Хто це': 'C',     # Column C
    'Тема': 'D',       # Column D
    'Соцмережа': 'E',  # Column E
    'Лінк': 'F',       # Column F
    'Примітки': 'G',   # Column G
}

MEDIA_COLUMNS = {
    'Місяць': 'A',
    'Медіа': 'B',
    'Тема': 'C',
    'Лінк': 'D',
    'Примітки': 'E',
}

# Legacy column mappings for backward compatibility
COLUMN_MAPPINGS = {
    'Соцмережі 2025': SOCIAL_NETWORK_COLUMNS,
    'ЗМІ 2025': MEDIA_COLUMNS,
    'Вакансії': {
        # Define when needed
    }
}


def get_column_mapping(table_name: str) -> dict:
    """
    Get column mapping for a table name (supports year-based tables).
    
    Args:
        table_name: Table name (e.g., "Соцмережі 2025", "ЗМІ 2026")
    
    Returns:
        Dictionary mapping column names to column letters
    """
    # Check if it's a social network table (any year)
    if 'Соцмережі' in table_name:
        return SOCIAL_NETWORK_COLUMNS.copy()
    
    # Check if it's a media table (any year)
    if 'ЗМІ' in table_name:
        return MEDIA_COLUMNS.copy()
    
    # Fallback to legacy mappings
    return COLUMN_MAPPINGS.get(table_name, SOCIAL_NETWORK_COLUMNS.copy())


class Config:
    """Application configuration manager."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / '.bcl-parser'
        self.config_dir = config_dir
        self.config_file = config_dir / 'config.json'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value."""
        self._config[key] = value
        self._save_config()
    
    @property
    def site_username(self) -> Optional[str]:
        """Get site username from env or config."""
        return os.getenv('YOUSCAN_EMAIL') or self.get('site_username')
    
    @site_username.setter
    def site_username(self, value: str):
        """Set site username."""
        self.set('site_username', value)
    
    @property
    def site_password(self) -> Optional[str]:
        """Get site password from env or secure storage."""
        # Check environment variable first
        env_password = os.getenv('YOUSCAN_PASSWORD')
        if env_password:
            return env_password
        # Fall back to keyring
        import keyring
        return keyring.get_password('bcl-parser', 'site_password')
    
    @site_password.setter
    def site_password(self, value: str):
        """Set site password (stored securely)."""
        import keyring
        keyring.set_password('bcl-parser', 'site_password', value)
    
    @property
    def google_sheets_email(self) -> Optional[str]:
        """Get Google Sheets email from env or config."""
        return os.getenv('GOOGLE_SHEETS_EMAIL') or self.get('google_sheets_email')
    
    @google_sheets_email.setter
    def google_sheets_email(self, value: str):
        """Set Google Sheets email."""
        self.set('google_sheets_email', value)
    
    @property
    def google_sheets_password(self) -> Optional[str]:
        """Get Google Sheets password from env or secure storage."""
        env_password = os.getenv('GOOGLE_SHEETS_PASSWORD')
        if env_password:
            return env_password
        import keyring
        return keyring.get_password('bcl-parser', 'google_sheets_password')
    
    @google_sheets_password.setter
    def google_sheets_password(self, value: str):
        """Set Google Sheets password."""
        import keyring
        keyring.set_password('bcl-parser', 'google_sheets_password', value)
    
    @property
    def google_sheets_id(self) -> Optional[str]:
        """Get Google Sheets spreadsheet ID."""
        return self.get('google_sheets_id')
    
    @google_sheets_id.setter
    def google_sheets_id(self, value: str):
        """Set Google Sheets spreadsheet ID."""
        self.set('google_sheets_id', value)
    
    @property
    def default_table(self) -> str:
        """Get default table name."""
        return self.get('default_table', 'Соцмережі 2025')
    
    @default_table.setter
    def default_table(self, value: str):
        """Set default table name."""
        self.set('default_table', value)

    @property
    def export_dir(self) -> str:
        """Default directory to export offline reports (Excel)."""
        # Prefer user's Documents folder when available
        default_dir = Path.home() / "Documents" / "bcl-parser-reports"
        return self.get('export_dir', str(default_dir))

    @export_dir.setter
    def export_dir(self, value: str):
        """Set default export directory."""
        self.set('export_dir', value)


def detect_table_from_link(link: str, entry_date=None) -> str:
    """
    Detect which table to use based on link.
    
    Args:
        link: The post URL
        entry_date: Optional date object to determine year. If None, uses current year.
    
    Returns:
        Table name with year (e.g., "Соцмережі 2025" or "ЗМІ 2025")
    """
    from datetime import date
    
    # Determine year
    if entry_date:
        year = entry_date.year
    else:
        year = date.today().year
    
    # Check if link is from a social network
    link_lower = link.lower()
    is_social_network = any(domain in link_lower for domain in SOCIAL_NETWORK_DOMAINS)
    
    # Return appropriate table name based on category
    if is_social_network:
        return TABLE_NAME_PATTERNS['social_network'].format(YEAR=year)
    else:
        return TABLE_NAME_PATTERNS['media'].format(YEAR=year)


def detect_table_from_entry(entry) -> str:
    """
    Detect which table to use based on entry (preferred method).

    Priority: link domain > social_network field.
    The link domain is the ground truth — if the URL is from a news site
    (e.g. interfax.com.ua) it must go to ЗМІ even if a social_network
    value was parsed from context.

    Returns:
        Table name with year (e.g., "Соцмережі 2026" or "ЗМІ 2026")
    """
    from datetime import date

    year = entry.date.year if entry.date else date.today().year

    if entry.link:
        netloc = _extract_netloc(entry.link)
        if any(netloc == d or netloc.endswith('.' + d) for d in SOCIAL_NETWORK_DOMAINS):
            return TABLE_NAME_PATTERNS['social_network'].format(YEAR=year)
        # Link exists but domain is NOT a social network → definitely media
        return TABLE_NAME_PATTERNS['media'].format(YEAR=year)

    # No link — fall back to social_network field
    if entry.social_network and entry.social_network.strip():
        return TABLE_NAME_PATTERNS['social_network'].format(YEAR=year)

    return TABLE_NAME_PATTERNS['media'].format(YEAR=year)


def _extract_netloc(link: str) -> str:
    """Return the bare hostname (lowercase, no www.) from a URL."""
    try:
        from urllib.parse import urlparse
        netloc = urlparse(link).netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return link.lower()


def detect_social_network_from_link(link: str) -> str:
    """Detect social network name from link (for dropdown).

    Uses proper hostname comparison instead of substring matching so that
    domains like 'interfax.com.ua' are never confused with 'x.com'.
    """
    netloc = _extract_netloc(link)
    for domain, network_name in DOMAIN_TO_SOCIAL_NETWORK.items():
        # exact match OR subdomain (e.g. m.facebook.com → facebook.com)
        if netloc == domain or netloc.endswith('.' + domain):
            return network_name
    return ''

