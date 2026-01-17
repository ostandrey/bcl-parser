"""Configuration management for BCL Parser."""
import os
import json
from pathlib import Path
from typing import Dict, Optional

# Social network to table mapping
SOCIAL_NETWORKS = {
    'facebook.com': 'Соцмережі 2025',
    'instagram.com': 'Соцмережі 2025',
    'twitter.com': 'Соцмережі 2025',
    'x.com': 'Соцмережі 2025',
    'linkedin.com': 'Соцмережі 2025',
    'youtube.com': 'Соцмережі 2025',
    'youtu.be': 'Соцмережі 2025',
    't.me': 'Соцмережі 2025',
    'tiktok.com': 'Соцмережі 2025',
    'threads.net': 'Соцмережі 2025',
    'soundcloud.com': 'Соцмережі 2025',
}

# Default table for non-social networks
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
    'tiktok.com': 'Tiktok',
    'threads.net': 'threads.net',
    'soundcloud.com': 'soundcloud',
}

# Column mappings for Google Sheets
COLUMN_MAPPINGS = {
    'Соцмережі 2025': {
        'Місяць': 'A',     # Column A
        'Назва': 'B',      # Column B
        'Хто це': 'C',     # Column C
        'Тема': 'D',       # Column D
        'Соцмережа': 'E',  # Column E
        'Лінк': 'F',       # Column F
        'Примітки': 'G',   # Column G
    },
    'ЗМІ 2025': {
        'Місяць': 'A',
        'Медіа': 'B',
        'Тема': 'C',
        'Лінк': 'D',
        'Примітки': 'E',
    },
    'Вакансії': {
        # Define when needed
    }
}


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


def detect_table_from_link(link: str) -> str:
    """Detect which table to use based on link."""
    link_lower = link.lower()
    for domain, table in SOCIAL_NETWORKS.items():
        if domain in link_lower:
            return table
    return DEFAULT_MEDIA_TABLE


def detect_social_network_from_link(link: str) -> str:
    """Detect social network name from link (for dropdown)."""
    link_lower = link.lower()
    for domain, network_name in DOMAIN_TO_SOCIAL_NETWORK.items():
        if domain in link_lower:
            return network_name
    return ''  # Empty if not a recognized social network

