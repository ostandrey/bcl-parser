"""Main window for BCL Parser application."""
import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QDialog, QFrame
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QFont

from .date_picker import MaterialDateRangeDialog
from .theme import COLORS, CARD_STYLE, FILLED_BTN_STYLE, TONAL_BTN_STYLE, DATE_CHIP_STYLE
from ..config import Config
from ..database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config      = Config()
        self.db_manager  = DatabaseManager()

        self.setWindowTitle("BCL Parser")
        self.setMinimumSize(560, 420)
        self.resize(660, 460)

        self._apply_global_styles()
        self._init_ui()

    # ── Global styles ──────────────────────────────────────────────────────────
    def _apply_global_styles(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {COLORS['background']};
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 10pt;
                color: {COLORS['on_surface']};
            }}
        """)

    # ── Layout ─────────────────────────────────────────────────────────────────
    def _init_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        lay = QVBoxLayout(root)
        lay.setSpacing(12)
        lay.setContentsMargins(22, 18, 22, 18)

        lay.addWidget(self._build_header())
        lay.addWidget(self._build_date_card())
        lay.addWidget(self._build_status_row())
        lay.addSpacing(2)
        lay.addWidget(self._build_parse_button())
        lay.addWidget(self._build_secondary_buttons())
        lay.addStretch()

    # ── Header ─────────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(w)
        row.setContentsMargins(4, 0, 0, 4)
        row.setSpacing(12)

        # App icon from the window icon (same as taskbar)
        icon_lbl = QLabel()
        from PyQt6.QtGui import QPixmap
        icon_px = self.windowIcon().pixmap(32, 32)
        if not icon_px.isNull():
            icon_lbl.setPixmap(icon_px)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        row.addWidget(icon_lbl)

        title = QLabel("BCL Parser")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['primary']}; background: transparent; border: none;")
        row.addWidget(title)
        row.addStretch()
        return w

    # ── Date card ──────────────────────────────────────────────────────────────
    def _build_date_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(10)

        lbl = QLabel("DATE RANGE")
        lbl.setStyleSheet(f"""
            color: {COLORS['on_surface_dim']};
            font-size: 7.5pt;
            font-weight: 700;
            letter-spacing: 1.5px;
            background: transparent;
            border: none;
        """)
        outer.addWidget(lbl)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self._date_chip_widget("From", is_from=True))

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(28)
        arrow.setStyleSheet(
            f"color: {COLORS['on_surface_dim']}; font-size: 12pt; "
            f"background: transparent; border: none; padding-top: 18px;"
        )
        row.addWidget(arrow)

        row.addWidget(self._date_chip_widget("To", is_from=False))
        row.addStretch()
        outer.addLayout(row)
        return card

    def _date_chip_widget(self, label_text: str, is_from: bool) -> QWidget:
        """Labeled clickable date chip with calendar icon."""
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"""
            color: {COLORS['on_surface_dim']};
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 0.6px;
            background: transparent;
            border: none;
        """)
        col.addWidget(lbl)

        btn = QPushButton(f"📅  {QDate.currentDate().toString('dd.MM.yyyy')}")
        btn.setFixedHeight(40)
        btn.setMinimumWidth(150)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._open_date_range_picker)
        btn.setStyleSheet(DATE_CHIP_STYLE)
        col.addWidget(btn)

        if is_from:
            self.date_from_btn = btn
        else:
            self.date_to_btn = btn

        return w

    # ── Status row ─────────────────────────────────────────────────────────────
    def _build_status_row(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(w)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(6)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            f"color: {COLORS['on_surface_dim']}; font-size: 8pt; "
            f"background: transparent; border: none;"
        )
        row.addWidget(self._status_dot)

        self.status_label = QLabel("Ready to parse")
        self.status_label.setStyleSheet(
            f"color: {COLORS['on_surface_dim']}; font-size: 9.5pt; font-weight: 500; "
            f"background: transparent; border: none;"
        )
        row.addWidget(self.status_label)
        row.addStretch()
        return w

    # ── Parse button ───────────────────────────────────────────────────────────
    def _build_parse_button(self) -> QPushButton:
        self.parse_button = QPushButton("🚀  Start Parsing")
        self.parse_button.setMinimumHeight(52)
        self.parse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.parse_button.clicked.connect(self._on_start_parsing)
        self.parse_button.setStyleSheet(FILLED_BTN_STYLE)
        return self.parse_button

    # ── Secondary buttons ──────────────────────────────────────────────────────
    def _build_secondary_buttons(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        for label, slot in [("➕  Create Table", self._on_create_table),
                             ("⚙️  Settings",     self._on_settings)]:
            btn = QPushButton(label)
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            btn.setStyleSheet(TONAL_BTN_STYLE)
            row.addWidget(btn)

        row.addStretch()
        return w

    # ── Date helpers ───────────────────────────────────────────────────────────
    def _open_date_range_picker(self):
        raw_from = self.date_from_btn.text().replace("📅  ", "").strip()
        raw_to   = self.date_to_btn.text().replace("📅  ", "").strip()
        try:
            start, end = MaterialDateRangeDialog.get_range(self, raw_from, raw_to)
            if start and end:
                self.date_from_btn.setText(f"📅  {start}")
                self.date_to_btn.setText(f"📅  {end}")
        except Exception as e:
            logger.exception("Error opening date range picker")
            QMessageBox.warning(self, "Calendar Error",
                                f"Could not open calendar picker:\n{e}")

    def _parse_date_string(self, date_str: str) -> QDate:
        clean = date_str.replace("📅  ", "").replace("📅 ", "").strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y"):
            try:
                d = datetime.strptime(clean, fmt)
                return QDate(d.year, d.month, d.day)
            except ValueError:
                continue
        return QDate.currentDate()

    # ── Actions ────────────────────────────────────────────────────────────────
    def _on_start_parsing(self):
        try:
            table_name = self.config.default_table
            date_from  = self._parse_date_string(self.date_from_btn.text()).toPyDate()
            date_to    = self._parse_date_string(self.date_to_btn.text()).toPyDate()

            if date_from > date_to:
                QMessageBox.warning(self, "Invalid Date Range",
                                    "The 'From' date must be before or equal to the 'To' date.")
                return

            if not self.config.site_username or not self.config.site_password:
                QMessageBox.warning(self, "Missing Credentials",
                                    "Please configure YouScan.io credentials in Settings.\n\n"
                                    "Set YOUSCAN_EMAIL and YOUSCAN_PASSWORD environment variables.")
                return

            if not self.config.google_sheets_id:
                QMessageBox.warning(self, "Missing Configuration",
                                    "Please configure Google Sheets ID in Settings.")
                return

            from .parser_dialog import ParserDialog
            dialog = ParserDialog(self, self.config, self.db_manager,
                                  table_name, date_from, date_to)
            dialog.exec()

        except Exception as e:
            logger.exception("Error in _on_start_parsing")
            QMessageBox.critical(self, "Error",
                                 f"An error occurred:\n{e}\n\nCheck console for details.")

    def _on_settings(self):
        from .settings_dialog import SettingsDialog
        SettingsDialog(self, self.config).exec()

    def _on_create_table(self):
        from .create_table_dialog import CreateTableDialog
        dialog = CreateTableDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            created = dialog.get_created_table_name()
            if created:
                self.config.default_table = created
                logger.info(f"Created new table: {created}")
