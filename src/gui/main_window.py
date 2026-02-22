"""Main window for BCL Parser application."""
import logging
from datetime import timedelta, datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QDialog, QFrame
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QMouseEvent, QFont

from .date_picker import MaterialDateRangeDialog
from ..config import Config
from ..database.db_manager import DatabaseManager
from ..utils.date_tracker import DateTracker

logger = logging.getLogger(__name__)

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    'primary':           '#6750A4',
    'primary_dark':      '#4F378B',
    'primary_container': '#EADDFF',
    'on_primary':        '#FFFFFF',
    'surface':           '#FFFFFF',
    'surface_variant':   '#F3EFF7',
    'background':        '#F6F2FB',
    'on_surface':        '#1C1B1F',
    'on_surface_dim':    '#6B6572',
    'outline':           '#CAC4D0',
    'outline_strong':    '#79747E',
    'warning':           '#B45309',
    'warning_container': '#FEF3C7',
    'warning_border':    '#FCD34D',
    'success':           '#166534',
    'success_container': '#DCFCE7',
    'success_border':    '#86EFAC',
}

# ── Shared styles ──────────────────────────────────────────────────────────────
_CARD = f"""
    QFrame {{
        background-color: {C['surface']};
        border: 1.5px solid {C['outline']};
        border-radius: 16px;
    }}
"""

_FILLED_BTN = f"""
    QPushButton {{
        background-color: {C['primary']};
        color: {C['on_primary']};
        border: none;
        border-radius: 26px;
        font-size: 12pt;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    QPushButton:hover {{ background-color: {C['primary_dark']}; }}
    QPushButton:pressed {{ background-color: #3B2A6E; }}
    QPushButton:disabled {{
        background-color: {C['surface_variant']};
        color: {C['on_surface_dim']};
    }}
"""

# Secondary buttons — tonal (filled soft) instead of outlined
_TONAL_BTN = f"""
    QPushButton {{
        background-color: {C['primary_container']};
        color: {C['primary']};
        border: none;
        border-radius: 20px;
        padding: 10px 22px;
        font-weight: 600;
        font-size: 10pt;
    }}
    QPushButton:hover {{
        background-color: #D8CAFF;
    }}
    QPushButton:pressed {{ background-color: #C4B0F5; }}
"""

# Date chip — looks interactive, not like a disabled input
_DATE_CHIP = f"""
    QPushButton {{
        background-color: {C['surface']};
        color: {C['on_surface']};
        border: 1.5px solid {C['outline']};
        border-radius: 12px;
        padding: 0 14px;
        font-size: 10.5pt;
        font-weight: 500;
        text-align: left;
    }}
    QPushButton:hover {{
        background-color: {C['primary_container']};
        border-color: {C['primary']};
        color: {C['primary']};
    }}
    QPushButton:pressed {{
        background-color: #D8CAFF;
    }}
"""


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.db_manager = DatabaseManager()
        self.date_tracker = DateTracker(self.db_manager)
        self._has_missing_days = False

        self.setWindowTitle("BCL Parser")
        self.setMinimumSize(560, 420)
        self.resize(660, 460)

        self._apply_global_styles()
        self._init_ui()
        self._check_missing_days()

    # ── Global styles ──────────────────────────────────────────────────────────
    def _apply_global_styles(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {C['background']};
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 10pt;
                color: {C['on_surface']};
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
        lay.addWidget(self._build_status_banner())   # compact, not a card
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
        row.setSpacing(10)

        icon = QLabel("🗂")
        icon.setStyleSheet("font-size: 22pt; background: transparent; border: none;")
        row.addWidget(icon)

        title = QLabel("BCL Parser")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C['primary']}; background: transparent; border: none;")
        row.addWidget(title)
        row.addStretch()
        return w

    # ── Date card ──────────────────────────────────────────────────────────────
    def _build_date_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(_CARD)

        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(10)

        # Section label
        lbl = QLabel("DATE RANGE")
        lbl.setStyleSheet(f"""
            color: {C['on_surface_dim']};
            font-size: 7.5pt;
            font-weight: 700;
            letter-spacing: 1.5px;
            background: transparent;
            border: none;
        """)
        outer.addWidget(lbl)

        # Chips row — no Edit button, chips ARE the action
        row = QHBoxLayout()
        row.setSpacing(6)

        row.addWidget(self._date_chip_widget("From", is_from=True))

        arrow = QLabel("→")
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFixedWidth(28)
        arrow.setStyleSheet(
            f"color: {C['on_surface_dim']}; font-size: 12pt; "
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
            color: {C['on_surface_dim']};
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 0.6px;
            background: transparent;
            border: none;
        """)
        col.addWidget(lbl)

        # Chip: "📅  22.02.2026" — icon makes it obviously clickable
        btn = QPushButton(f"📅  {QDate.currentDate().toString('dd.MM.yyyy')}")
        btn.setFixedHeight(40)
        btn.setMinimumWidth(150)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._open_date_range_picker)
        btn.setStyleSheet(_DATE_CHIP)
        col.addWidget(btn)

        if is_from:
            self.date_from_btn = btn
        else:
            self.date_to_btn = btn

        return w

    # ── Status banner — compact inline, not a full card ────────────────────────
    def _build_status_banner(self) -> QWidget:
        """Compact status row. Expands to warning banner when needed."""
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        col = QVBoxLayout(w)
        col.setContentsMargins(4, 0, 4, 0)
        col.setSpacing(6)

        # Status row
        status_row = QHBoxLayout()
        status_row.setSpacing(6)

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(
            f"color: {C['on_surface_dim']}; font-size: 8pt; "
            f"background: transparent; border: none;"
        )
        status_row.addWidget(self._status_dot)

        self.status_label = QLabel("Ready to parse")
        self.status_label.setStyleSheet(
            f"color: {C['on_surface_dim']}; font-size: 9.5pt; font-weight: 500; "
            f"background: transparent; border: none;"
        )
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        col.addLayout(status_row)

        # Warning banner — hidden until needed
        self.missing_days_label = QLabel()
        self.missing_days_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.missing_days_label.mousePressEvent = self._on_missing_days_clicked
        self.missing_days_label.setWordWrap(False)
        self.missing_days_label.hide()
        col.addWidget(self.missing_days_label)

        return w

    # ── Parse button ───────────────────────────────────────────────────────────
    def _build_parse_button(self) -> QPushButton:
        self.parse_button = QPushButton("🚀  Start Parsing")
        self.parse_button.setMinimumHeight(52)
        self.parse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.parse_button.clicked.connect(self._on_start_parsing)
        self.parse_button.setStyleSheet(_FILLED_BTN)
        return self.parse_button

    # ── Secondary buttons — tonal, balanced with parse btn ────────────────────
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
            btn.setStyleSheet(_TONAL_BTN)
            row.addWidget(btn)

        row.addStretch()
        return w

    # ── Date helpers ───────────────────────────────────────────────────────────
    def _open_date_range_picker(self):
        # Strip the calendar icon prefix before passing to dialog
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
        # Strip emoji prefix if present
        clean = date_str.replace("📅  ", "").replace("📅 ", "").strip()
        for fmt in ("%d.%m.%Y", "%d.%m.%y"):
            try:
                d = datetime.strptime(clean, fmt)
                return QDate(d.year, d.month, d.day)
            except ValueError:
                continue
        return QDate.currentDate()

    # ── Missing days ───────────────────────────────────────────────────────────
    def _check_missing_days(self):
        table_name = self.config.default_table
        today = self.date_tracker.get_today()
        start_date = today - timedelta(days=30)
        missing = self.date_tracker.check_missing_days(table_name, start_date, today)

        if missing:
            self._has_missing_days = True
            self.missing_days_label.setText(
                f"⚠️  {len(missing)} days missed — click to fill"
            )
            self.missing_days_label.setStyleSheet(f"""
                QLabel {{
                    padding: 8px 14px;
                    border-radius: 10px;
                    background-color: {C['warning_container']};
                    color: {C['warning']};
                    border: 1.5px solid {C['warning_border']};
                    font-size: 9.5pt;
                    font-weight: 600;
                }}
            """)
            self.missing_days_label.show()
            self._status_dot.setStyleSheet(
                f"color: {C['warning']}; font-size: 8pt; background: transparent; border: none;"
            )
            self.status_label.setText("Action required")
        else:
            self._has_missing_days = False
            self.missing_days_label.hide()
            self._status_dot.setStyleSheet(
                f"color: {C['success']}; font-size: 8pt; background: transparent; border: none;"
            )
            self.status_label.setText("All days parsed — ready")

    def _on_missing_days_clicked(self, event: QMouseEvent):
        if self._has_missing_days:
            self._fill_missing_days()
        event.accept()

    def _fill_missing_days(self):
        QMessageBox.information(self, "Fill Missing Days",
                                "This feature will be implemented in the next phase.")

    # ── Actions ────────────────────────────────────────────────────────────────
    def _on_start_parsing(self):
        try:
            table_name = self.config.default_table
            date_from = self._parse_date_string(self.date_from_btn.text()).toPyDate()
            date_to   = self._parse_date_string(self.date_to_btn.text()).toPyDate()

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
                                  self.date_tracker, table_name, date_from, date_to)
            dialog.exec()
            self._check_missing_days()

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