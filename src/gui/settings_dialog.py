"""Settings dialog for application configuration."""
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QMessageBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..config import Config
from .theme import (
    COLORS, FILLED_BTN_STYLE, TEXT_BTN_STYLE,
    INPUT_STYLE, GROUP_BOX_STYLE,
)

logger = logging.getLogger(__name__)


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color: {COLORS['on_surface_dim']};
        font-size: 7.5pt;
        font-weight: 700;
        letter-spacing: 1.4px;
        background: transparent;
        border: none;
        padding-bottom: 2px;
    """)
    return lbl


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedWidth(130)
    lbl.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-size: 10pt; background: transparent; border: none;")
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {COLORS['outline_variant']}; background: {COLORS['outline_variant']}; border: none; max-height: 1px;")
    return line


class SettingsDialog(QDialog):
    """Settings dialog for application configuration."""

    def __init__(self, parent, config: Config):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setMinimumSize(460, 400)
        self.setModal(True)
        self._apply_styles()
        self._init_ui()
        self._load_settings()

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 10pt;
                color: {COLORS['on_surface']};
            }}
        """)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 20, 24, 20)

        # ── Header ────────────────────────────────────────────────────────────
        header = QLabel("⚙️  Settings")
        header.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {COLORS['primary']}; background: transparent; border: none;")
        root.addWidget(header)

        root.addWidget(_separator())

        # ── YouScan.io card ───────────────────────────────────────────────────
        root.addWidget(_section_title("YOUSCAN.IO CREDENTIALS"))
        youscan_card = self._build_card([
            ("Email",    "email_input",    False, "Enter YouScan.io email"),
            ("Password", "password_input", True,  "Enter YouScan.io password"),
        ])
        root.addWidget(youscan_card)

        # ── Google Sheets card ────────────────────────────────────────────────
        root.addWidget(_section_title("GOOGLE SHEETS"))
        sheets_card = self._build_card([
            ("Spreadsheet ID", "sheets_id_input",    False, "Paste from Google Sheets URL"),
            ("Google Email",   "sheets_email_input", False, "Google account email (optional)"),
        ])
        root.addWidget(sheets_card)

        # ── Info note ─────────────────────────────────────────────────────────
        note = QLabel(
            "Credentials are stored securely via keyring. "
            "You can also set YOUSCAN_EMAIL / YOUSCAN_PASSWORD "
            "as environment variables."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {COLORS['on_surface_dim']}; font-size: 8.5pt; "
            f"background: transparent; border: none; padding: 0 2px;"
        )
        root.addWidget(note)

        root.addStretch()

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setMinimumHeight(38)
        self._cancel_btn.setMinimumWidth(100)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.reject)
        self._cancel_btn.setStyleSheet(TEXT_BTN_STYLE)
        btn_row.addWidget(self._cancel_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setMinimumHeight(38)
        self._save_btn.setMinimumWidth(100)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setDefault(True)
        self._save_btn.setStyleSheet(FILLED_BTN_STYLE.replace("26px", "10px").replace("12pt", "10pt"))
        btn_row.addWidget(self._save_btn)

        root.addLayout(btn_row)

    def _build_card(self, fields: list) -> QFrame:
        """Build a white-background card with labeled input fields."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1.5px solid {COLORS['outline_variant']};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 14)

        for label_text, attr_name, is_password, placeholder in fields:
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(_field_label(label_text))

            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet(INPUT_STYLE)
            if is_password:
                inp.setEchoMode(QLineEdit.EchoMode.Password)
            row.addWidget(inp)
            setattr(self, attr_name, inp)
            layout.addLayout(row)

        return card

    def _load_settings(self):
        stored_email = self.config.get('site_username')
        if stored_email:
            self.email_input.setText(stored_email)

        sheets_id = self.config.google_sheets_id
        if sheets_id:
            self.sheets_id_input.setText(sheets_id)

        stored_google_email = self.config.get('google_sheets_email')
        if stored_google_email:
            self.sheets_email_input.setText(stored_google_email)

    def _on_save(self):
        try:
            email = self.email_input.text().strip()
            if email:
                self.config.site_username = email

            password = self.password_input.text().strip()
            if password:
                self.config.site_password = password

            sheets_id = self.sheets_id_input.text().strip()
            if sheets_id:
                self.config.google_sheets_id = sheets_id

            google_email = self.sheets_email_input.text().strip()
            if google_email:
                self.config.google_sheets_email = google_email

            logger.info("Settings saved")
            QMessageBox.information(self, "Saved", "Settings saved successfully.")
            self.accept()
        except Exception as e:
            logger.exception("Error saving settings")
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{e}")
