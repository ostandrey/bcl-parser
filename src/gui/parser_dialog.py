"""Parsing dialog with preview and error handling."""
import asyncio
import base64
import logging
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Dict

# Inline SVG checkmark — works in both dev and frozen .exe (no file path needed)
_CHECKMARK_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18">'
    b'<polyline points="3,9 7,13 15,5" stroke="white" stroke-width="2.5" '
    b'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
_CHECKMARK_URI = "data:image/svg+xml;base64," + base64.b64encode(_CHECKMARK_SVG).decode()

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QProgressBar,
    QMessageBox, QCheckBox, QTextEdit, QLineEdit,
    QFileDialog, QWidget, QGroupBox, QSizePolicy, QComboBox,
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont

from ..database.models import ParsedEntry
from ..parser.youscan_parser import YouScanParser
from ..sheets.google_sheets import GoogleSheetsWriter
from ..config import Config, SOCIAL_NETWORK_OPTIONS, TAG_OPTIONS
from ..database.db_manager import DatabaseManager
from ..export.excel_exporter import export_entries_to_xlsx
from .theme import COLORS

logger = logging.getLogger(__name__)

DEFAULT_MEDIA_TABLE = 'ЗМІ 2025'
MAX_ERROR_DISPLAY = 20
NOTE_TRUNCATE_LENGTH = 100


def _group_entries_by_table(entries: List[ParsedEntry]) -> Dict[str, List[ParsedEntry]]:
    entries_by_table = defaultdict(list)
    for entry in entries:
        table_name = entry.table_name or DEFAULT_MEDIA_TABLE
        entries_by_table[table_name].append(entry)
    return entries_by_table


# ── Threads ────────────────────────────────────────────────────────────────────

class ExcelExportThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, entries: List[ParsedEntry], output_path: str):
        super().__init__()
        self._entries = entries
        self._output_path = output_path

    def run(self):
        try:
            out = export_entries_to_xlsx(
                self._entries, self._output_path,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m)
            )
            self.finished.emit(str(out))
        except Exception as e:
            self.failed.emit(str(e))


class SheetsFetchThread(QThread):
    """Fetches sheet names in background so pills can show warnings before Submit."""
    finished = pyqtSignal(list)   # list of sheet name strings
    failed   = pyqtSignal()       # silent fail — no crash, just no warning

    def __init__(self, spreadsheet_id: str):
        super().__init__()
        self._spreadsheet_id = spreadsheet_id

    def run(self):
        try:
            writer = GoogleSheetsWriter(self._spreadsheet_id)
            writer.connect()
            self.finished.emit(writer.get_sheet_names())
        except Exception:
            self.failed.emit()


class SheetsWriteThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)   # {table: result_dict}
    failed   = pyqtSignal(str)

    def __init__(
        self,
        spreadsheet_id: str,
        entries_by_table: Dict[str, list],
        selected_tables: set,
        remapping: Dict[str, str],
    ):
        super().__init__()
        self._spreadsheet_id   = spreadsheet_id
        self._entries_by_table = entries_by_table
        self._selected_tables  = selected_tables
        self._remapping        = remapping

    def run(self):
        writer = GoogleSheetsWriter(self._spreadsheet_id)
        try:
            writer.connect()
        except Exception as e:
            self.failed.emit(f"Could not connect to Google Sheets:\n{e}")
            return
        try:
            results: Dict[str, dict] = {}
            for orig_name, table_entries in self._entries_by_table.items():
                if orig_name not in self._selected_tables:
                    continue
                effective_name = self._remapping.get(orig_name, orig_name)
                result = writer.write_entries(
                    effective_name, table_entries,
                    progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                )
                result['effective_name'] = effective_name
                result['orig_name']      = orig_name
                results[orig_name]       = result
            self.finished.emit(results)
        except Exception as e:
            self.failed.emit(str(e))


class ParsingThread(QThread):
    progress     = pyqtSignal(int, int, str)
    entry_parsed = pyqtSignal(object)
    finished     = pyqtSignal(list, list)
    error        = pyqtSignal(str, object)

    def __init__(self, parser: YouScanParser, dates: List[date], table_name: str):
        super().__init__()
        self.parser     = parser
        self.dates      = dates
        self.table_name = table_name
        self.entries    = []
        self.errors     = []
        self._stop_requested = False

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_async())
        finally:
            loop.close()

    async def _run_async(self):
        try:
            await self.parser.start_async()
        except Exception as e:
            self.errors.append({'date': None, 'error': f"Failed to start browser: {e}", 'entry': None})
            self.finished.emit(self.entries, self.errors)
            return

        try:
            total_days = len(self.dates)
            if self.dates:
                await self.parser.set_date_range_async(min(self.dates), max(self.dates))

            for day_idx, target_date in enumerate(self.dates):
                if self._stop_requested:
                    break
                self.progress.emit(day_idx + 1, total_days, f"Parsing {target_date}")
                try:
                    day_entries = await self.parser.parse_all_entries_async(target_date)
                    for entry in day_entries:
                        if self._stop_requested:
                            break
                        self.entries.append(entry)
                        self.entry_parsed.emit(entry)
                except Exception as e:
                    self.errors.append({'date': target_date, 'error': str(e), 'entry': None})
                    self.error.emit(f"Error parsing {target_date}: {e}", None)
        finally:
            try:
                await self.parser.close_async()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

        self.finished.emit(self.entries, self.errors)

    def stop(self):
        self._stop_requested = True


# ── Helper widgets ─────────────────────────────────────────────────────────────

class _Badge(QLabel):
    """Small pill badge: «6 entries» / «0 errors»."""
    def __init__(self, count: int, label: str, text_color: str, bg_color: str, parent=None):
        super().__init__(parent)
        self._text_color = text_color
        self._bg_color   = bg_color
        self.set_value(count, label)

    def set_value(self, count: int, label: str):
        self.setText(f"  {count} {label}  ")
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {self._bg_color};
                color: {self._text_color};
                border-radius: 12px;
                padding: 3px 10px;
                font-size: 11pt;
                font-weight: 600;
            }}
        """)


class _SectionCard(QGroupBox):
    """Rounded card with bold title."""
    def __init__(self, title: str, accent: str = None, parent=None):
        super().__init__(title, parent)
        accent = accent or COLORS['on_surface']
        self.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 700;
                font-size: 11pt;
                color: {accent};
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 10px;
                margin-top: 14px;
                background-color: {COLORS['surface']};
                padding-top: 4px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 6px;
                background-color: {COLORS['surface']};
            }}
        """)


def _make_social_pill(text: str) -> QWidget:
    """Фиолетовый pill-тег для колонки Social Network."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(f"""
        QLabel {{
            background-color: {COLORS['primary_container']};
            color: {COLORS['primary']};
            border-radius: 10px;
            padding: 2px 10px;
            font-size: 9pt;
            font-weight: 600;
        }}
    """)
    layout.addWidget(lbl)
    container.setStyleSheet("background: transparent;")
    return container

def _make_table_pill(
    table_name: str,
    count: int,
    checked: bool = True,
    missing: bool = False,
    available_sheets: Optional[List[str]] = None,
) -> QWidget:
    """Pill with checkbox, table name badge, and optional missing-table warning + remap dropdown."""
    is_warning = missing

    bg_color     = COLORS['warning_container'] if is_warning else COLORS['primary_container']
    border_color = COLORS['warning']           if is_warning else COLORS['primary']
    text_color   = COLORS['warning']           if is_warning else COLORS['primary']
    badge_color  = COLORS['warning']           if is_warning else COLORS['primary']
    cb_border    = COLORS['warning']           if is_warning else COLORS['primary']
    cb_checked   = COLORS['warning']           if is_warning else COLORS['primary']
    cb_checked_h = '#E65100'                   if is_warning else '#7965AF'

    container = QWidget()
    container.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    container.setObjectName("pill_container")
    container.setStyleSheet(f"""
        QWidget#pill_container {{
            background-color: {bg_color};
            border: 1.5px solid {border_color};
            border-radius: 18px;
        }}
    """)

    layout = QHBoxLayout(container)
    layout.setContentsMargins(10, 0, 14, 0)
    layout.setSpacing(8)

    cb = QCheckBox()
    cb.setChecked(checked)
    cb.setStyleSheet(f"""
        QCheckBox {{
            spacing: 0px;
            background: transparent;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {cb_border};
            border-radius: 4px;
            background: {COLORS['surface']};
        }}
        QCheckBox::indicator:hover {{
            border-color: {cb_border};
            background: {bg_color};
        }}
        QCheckBox::indicator:checked {{
            background-color: {cb_checked};
            border-color: {cb_checked};
            image: url("{_CHECKMARK_URI}");
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {cb_checked_h};
            border-color: {cb_checked_h};
        }}
    """)

    layout.addWidget(cb)

    if is_warning:
        warn_lbl = QLabel("⚠")
        warn_lbl.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['warning']};
                font-size: 11pt;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(warn_lbl)

        # Remap dropdown: choose existing table instead
        combo = QComboBox()
        combo.setFixedHeight(26)
        sheets = available_sheets or []
        combo.addItems(sheets)
        # Pre-select the closest existing sheet (same type, latest year available)
        prefix = table_name.rsplit(' ', 1)[0] if ' ' in table_name else table_name
        candidates = [s for s in sheets if s.startswith(prefix)]
        if candidates:
            combo.setCurrentText(candidates[-1])  # last = highest year available
        combo.setStyleSheet(f"""
            QComboBox {{
                background: white;
                border: 1px solid {COLORS['warning']};
                border-radius: 6px;
                padding: 0 6px;
                font-size: 9pt;
                color: {COLORS['on_surface']};
            }}
            QComboBox::drop-down {{ border: none; }}
        """)
        layout.addWidget(combo)
        container.setProperty('remap_combo', combo)
    else:
        name_lbl = QLabel(table_name)
        name_lbl.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-weight: 600;
                font-size: 10pt;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(name_lbl)

    badge = QLabel(str(count))
    badge.setFixedSize(22, 22)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(f"""
        QLabel {{
            background-color: {badge_color};
            color: white;
            border-radius: 11px;
            font-size: 9pt;
            font-weight: 700;
            border: none;
        }}
    """)
    layout.addWidget(badge)

    # Adjust height: fixed for normal, minimum for warning (has combo)
    if is_warning:
        container.setMinimumHeight(36)
    else:
        container.setFixedHeight(36)

    container.setProperty('checkbox',   cb)
    container.setProperty('table_name', table_name)
    return container

# ── Main dialog ────────────────────────────────────────────────────────────────

class ParserDialog(QDialog):
    """Dialog for parsing with preview and submission."""

    def __init__(
        self,
        parent,
        config: Config,
        db_manager: DatabaseManager,
        table_name: str,
        date_from: date,
        date_to: date,
    ):
        super().__init__(parent)
        self.config      = config
        self.db_manager  = db_manager
        self.table_name  = table_name
        self.date_from    = date_from
        self.date_to      = date_to

        self.entries: List[ParsedEntry]       = []
        self.errors:  List[Dict]              = []
        self.parser:  Optional[YouScanParser] = None
        self.parsing_thread: Optional[ParsingThread] = None
        self._pill_widgets: Dict[str, QWidget] = {}
        self._available_sheets: List[str]     = []   # real sheets from Google Sheets

        self.setWindowTitle("Parsing Data")
        self.setMinimumSize(1280, 720)
        self._apply_styles()
        self._init_ui()

    # ── Styles ─────────────────────────────────────────────────────────────────

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
            }}
            * {{
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
        """)

    # ── UI build ───────────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("Parsing Data")
        title_lbl.setStyleSheet(f"font-size: 16pt; font-weight: 700; color: {COLORS['primary']};")
        sub_lbl = QLabel("YouScan → Google Sheets")
        sub_lbl.setStyleSheet(f"font-size: 9pt; color: {COLORS['on_surface_variant']};")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        header.addLayout(title_col)
        header.addStretch()

        self._entries_badge = _Badge(0, "entries", COLORS['primary'], COLORS['primary_container'])
        self._errors_badge  = _Badge(0, "errors",  COLORS['success'], COLORS['success_container'])
        header.addWidget(self._entries_badge)
        header.addWidget(self._errors_badge)
        root.addLayout(header)

        # ── Progress card ────────────────────────────────────────────────────
        prog_card = _SectionCard("Progress")
        prog_layout = QVBoxLayout(prog_card)
        prog_layout.setContentsMargins(14, 18, 14, 14)
        prog_layout.setSpacing(6)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Preparing to parse...")
        self.status_label.setStyleSheet(f"font-size: 10pt; color: {COLORS['on_surface_variant']};")
        self._pct_label = QLabel("0%")
        self._pct_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {COLORS['primary']};")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self._pct_label)
        prog_layout.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 5px;
                background-color: {COLORS['surface_variant']};
            }}
            QProgressBar::chunk {{
                border-radius: 5px;
                background-color: {COLORS['primary']};
            }}
        """)
        prog_layout.addWidget(self.progress_bar)
        root.addWidget(prog_card)

        # ── Parsed Entries card ──────────────────────────────────────────────
        self._table_card = _SectionCard("Parsed Entries")
        table_layout = QVBoxLayout(self._table_card)
        table_layout.setContentsMargins(10, 18, 10, 10)
        table_layout.setSpacing(4)

        self.entries_table = QTableWidget()
        self.entries_table.setColumnCount(7)
        self.entries_table.setHorizontalHeaderLabels(
            ['Table', 'Name', 'Social Network', 'Tag', 'Link', 'Note', 'Description']
        )
        self.entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entries_table.verticalHeader().setVisible(False)
        self.entries_table.setShowGrid(True)
        self.entries_table.setAlternatingRowColors(True)
        self.entries_table.setColumnWidth(0, 150)
        self.entries_table.setColumnWidth(1, 160)
        self.entries_table.setColumnWidth(2, 130)
        self.entries_table.setColumnWidth(3, 90)
        self.entries_table.setColumnWidth(4, 180)
        self.entries_table.setColumnWidth(5, 200)
        self.entries_table.horizontalHeader().setStretchLastSection(True)
        self.entries_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1.5px solid {COLORS['outline_variant']};
                border-radius: 10px;
                background-color: {COLORS['surface']};
                gridline-color: {COLORS['outline_variant']};
                font-size: 9pt;
                color: {COLORS['on_surface']};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
                border: none;
            }}
            QTableWidget::item:alternate {{
                background-color: #F5F0FC;
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['primary_container']};
                color: {COLORS['on_surface']};
            }}
            QTableWidget::item:hover {{
                background-color: #E8DEFF;
            }}
            QHeaderView::section {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                padding: 8px 10px;
                border: none;
                border-right: 1px solid #7B62B8;
                font-weight: 600;
                font-size: 9pt;
                letter-spacing: 0.3px;
            }}
            QHeaderView::section:first {{
                border-top-left-radius: 8px;
            }}
            QHeaderView::section:last {{
                border-top-right-radius: 8px;
                border-right: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['surface_variant']};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['outline']};
                border-radius: 5px;
                min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['primary']};
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {COLORS['surface_variant']};
                height: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background: {COLORS['outline']};
                border-radius: 5px;
                min-width: 24px;
            }}
        """)
        table_layout.addWidget(self.entries_table)
        root.addWidget(self._table_card)
        root.setStretch(root.count() - 1, 1)

        # ── Tables to Write card ─────────────────────────────────────────────
        self.table_selection_group = _SectionCard("Tables to Write", accent=COLORS['primary'])
        _card_vbox = QVBoxLayout()
        _card_vbox.setContentsMargins(14, 18, 14, 14)
        _card_vbox.setSpacing(6)

        # Warning banner (hidden until missing tables detected)
        self._missing_tables_warning = QLabel()
        self._missing_tables_warning.setWordWrap(True)
        self._missing_tables_warning.setVisible(False)
        self._missing_tables_warning.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['warning_container']};
                color: {COLORS['warning']};
                border: 1px solid {COLORS['warning']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 9pt;
                font-weight: 600;
            }}
        """)
        _card_vbox.addWidget(self._missing_tables_warning)

        self._pills_layout = QHBoxLayout()
        self._pills_layout.setSpacing(10)
        self._pills_layout.addStretch()
        _card_vbox.addLayout(self._pills_layout)

        self.table_selection_group.setLayout(_card_vbox)
        self.table_selection_group.setVisible(False)
        root.addWidget(self.table_selection_group)

        # ── Errors card (hidden until errors) ───────────────────────────────
        self.errors_group = _SectionCard("Errors")
        self.errors_group.setStyleSheet(
            self.errors_group.styleSheet()
            .replace(f"color: {COLORS['on_surface']};", f"color: {COLORS['error']};")
            .replace(f"border: 1px solid {COLORS['outline_variant']};",
                     f"border: 1px solid {COLORS['error']};")
            .replace(f"background-color: {COLORS['surface']};",
                     f"background-color: {COLORS['error_container']};")
        )
        self.errors_group.setVisible(False)
        errors_layout = QVBoxLayout(self.errors_group)
        errors_layout.setContentsMargins(14, 18, 14, 14)
        errors_layout.setSpacing(6)

        self.errors_checkbox = QCheckBox("Show error details")
        self.errors_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['error']};
                font-weight: 500;
                font-size: 10pt;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border: 2px solid {COLORS['error']};
                border-radius: 3px;
                background: {COLORS['surface']};
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['error']};
                border-color: {COLORS['error']};
            }}
        """)
        self.errors_checkbox.toggled.connect(self._toggle_errors)
        errors_layout.addWidget(self.errors_checkbox)

        self.errors_text = QTextEdit()
        self.errors_text.setMaximumHeight(80)
        self.errors_text.setVisible(False)
        self.errors_text.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 6px;
                background: {COLORS['surface']};
                padding: 6px;
                font-size: 9pt;
            }}
        """)
        errors_layout.addWidget(self.errors_text)
        root.addWidget(self.errors_group)

        # ── Options card ─────────────────────────────────────────────────────
        options_card = _SectionCard("Options")
        options_layout = QVBoxLayout(options_card)
        options_layout.setContentsMargins(14, 18, 14, 14)
        options_layout.setSpacing(10)

        # Export path label
        exp_lbl = QLabel("Export path:")
        exp_lbl.setStyleSheet(
            f"font-size: 10pt; font-weight: 500; color: {COLORS['on_surface_variant']};"
        )
        options_layout.addWidget(exp_lbl)

        # Export path row
        exp_h = QHBoxLayout()
        exp_h.setSpacing(8)

        self.export_path_input = QLineEdit()
        self.export_path_input.setPlaceholderText("Select a folder for the Excel report…")
        self.export_path_input.setText(self.config.export_dir)
        self.export_path_input.setFixedHeight(36)
        self.export_path_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 10px;
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 8px;
                background: {COLORS['surface']};
                font-size: 10pt;
                color: {COLORS['on_surface']};
            }}
            QLineEdit:hover {{ border-color: {COLORS['primary']}; }}
            QLineEdit:focus {{ border: 2px solid {COLORS['primary']}; }}
        """)
        exp_h.addWidget(self.export_path_input)

        self.browse_export_button = QPushButton("Browse…")
        self.browse_export_button.clicked.connect(self._on_browse_export_path)
        self.browse_export_button.setFixedHeight(36)
        self.browse_export_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['primary']};
                border: 1.5px solid {COLORS['primary']};
                border-radius: 18px;
                padding: 6px 18px;
                font-weight: 600;
                font-size: 10pt;
                white-space: nowrap;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_container']};
            }}
        """)
        exp_h.addWidget(self.browse_export_button)
        options_layout.addLayout(exp_h)
        root.addWidget(options_card)

        # ── Action buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        self.cancel_button = QPushButton("Close")
        self.cancel_button.clicked.connect(self._on_cancel)
        self.cancel_button.setFixedHeight(38)
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['on_surface_variant']};
                border: 1.5px solid {COLORS['outline_variant']};
                border-radius: 19px;
                padding: 8px 24px;
                font-weight: 500;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_variant']};
                border-color: {COLORS['outline']};
            }}
        """)
        btn_row.addWidget(self.cancel_button)

        self.export_button = QPushButton("📊  Generate Excel Report")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export_excel)
        self.export_button.setFixedHeight(38)
        self.export_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success_container']};
                color: {COLORS['success']};
                border: none;
                border-radius: 19px;
                padding: 8px 24px;
                font-weight: 600;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: #A5D6A7;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['outline_variant']};
                color: {COLORS['on_surface_variant']};
            }}
        """)
        btn_row.addWidget(self.export_button)

        self.submit_button = QPushButton("🔗  Submit to Google Sheets")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self._on_submit)
        self.submit_button.setFixedHeight(38)
        self.submit_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                border: none;
                border-radius: 19px;
                padding: 8px 24px;
                font-weight: 600;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: #7965AF;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['outline_variant']};
                color: {COLORS['on_surface_variant']};
            }}
        """)
        btn_row.addWidget(self.submit_button)

        root.addLayout(btn_row)

        self._start_parsing()

    # ── Progress helpers ───────────────────────────────────────────────────────

    def _set_progress(self, value: int, message: str, done: bool = False):
        self.status_label.setText(message)
        self.progress_bar.setValue(value)
        self._pct_label.setText(f"{value}%")
        color = COLORS['success'] if done else COLORS['primary']
        self._pct_label.setStyleSheet(f"font-size: 10pt; font-weight: 600; color: {color};")
        chunk_color = '#43A047' if done else COLORS['primary']
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 5px;
                background-color: {COLORS['surface_variant']};
            }}
            QProgressBar::chunk {{
                border-radius: 5px;
                background-color: {chunk_color};
            }}
        """)

    # ── Parsing ────────────────────────────────────────────────────────────────

    def _start_parsing(self):
        email    = self.config.site_username
        password = self.config.site_password

        if not email or not password:
            QMessageBox.critical(self, "Missing Credentials",
                                 "Please configure YouScan.io credentials in Settings.")
            self.reject()
            return

        try:
            self.parser = YouScanParser(
                email, password, headless=False, use_persistent_context=True
            )
        except Exception as e:
            QMessageBox.critical(self, "Initialization Error",
                                 f"Failed to initialize parser:\n{e}")
            self.reject()
            return

        dates, current = [], self.date_from
        while current <= self.date_to:
            dates.append(current)
            current += timedelta(days=1)

        self.parsing_thread = ParsingThread(self.parser, dates, self.table_name)
        self.parsing_thread.progress.connect(self._on_progress)
        self.parsing_thread.entry_parsed.connect(self._on_entry_parsed)
        self.parsing_thread.finished.connect(self._on_parsing_finished)
        self.parsing_thread.error.connect(self._on_parsing_error)
        self.parsing_thread.start()

    def _on_progress(self, current: int, total: int, message: str):
        pct = int((current / total) * 100)
        self._set_progress(pct, message)

    def _make_combo(self, options: list, current: str) -> QComboBox:
        """Small editable dropdown for preview table cells."""
        combo = QComboBox()
        combo.addItems(options)
        if current in options:
            combo.setCurrentText(current)
        elif current:
            combo.insertItem(0, current)
            combo.setCurrentIndex(0)
        combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 9pt;
                background: {COLORS['surface']};
                color: {COLORS['on_surface']};
            }}
            QComboBox::drop-down {{ border: none; width: 18px; }}
            QComboBox:hover {{ border-color: {COLORS['primary']}; }}
        """)
        return combo

    def _on_entry_parsed(self, entry: ParsedEntry):
        row = self.entries_table.rowCount()
        self.entries_table.insertRow(row)
        self.entries_table.setRowHeight(row, 36)

        table_name = entry.table_name or DEFAULT_MEDIA_TABLE
        note_short = (entry.note or '')[:NOTE_TRUNCATE_LENGTH]
        if len(entry.note or '') > NOTE_TRUNCATE_LENGTH:
            note_short += '...'

        # Plain text columns: 0=Table, 1=Name, 4=Link, 5=Note, 6=Description
        plain = {
            0: table_name,
            1: entry.name or '',
            4: entry.link or '',
            5: note_short,
            6: entry.description or '',
        }
        for col, val in plain.items():
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col == 5:
                item.setToolTip(entry.note or '')
            if col == 6:
                item.setToolTip(entry.description or '')
            self.entries_table.setItem(row, col, item)

        # Col 2: Social Network — combo for Соцмережі, plain dash for ЗМІ
        is_media_table = 'змі' in table_name.lower() or 'зми' in table_name.lower()
        if is_media_table:
            _sn_item = QTableWidgetItem('—')
            _sn_item.setFlags(_sn_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            _sn_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.entries_table.setItem(row, 2, _sn_item)
        else:
            self.entries_table.setCellWidget(
                row, 2, self._make_combo(SOCIAL_NETWORK_OPTIONS, entry.social_network or '')
            )
        # Col 3: Tag dropdown
        self.entries_table.setCellWidget(
            row, 3, self._make_combo(TAG_OPTIONS, entry.tag or '')
        )

        self.entries_table.scrollToBottom()
        self._entries_badge.set_value(row + 1, "entries")
        self._table_card.setTitle(f"Parsed Entries · {row + 1} rows")

    def _on_parsing_finished(self, entries: List[ParsedEntry], errors: List[Dict]):
        self.entries = entries
        self.errors  = errors

        err_count = len(errors)
        self._set_progress(100, "✅ Parsing complete", done=True)

        if err_count:
            self._errors_badge._text_color = COLORS['error']
            self._errors_badge._bg_color   = COLORS['error_container']
        self._errors_badge.set_value(err_count, "errors")

        self._update_table_selection(_group_entries_by_table(entries))

        if errors:
            self.errors_group.setVisible(True)
            self.errors_text.setPlainText("\n".join(
                f"Date {e.get('date','?')}: {e.get('error','unknown')}"
                for e in errors
            ))

        self.submit_button.setEnabled(bool(entries))
        self.export_button.setEnabled(bool(entries))
        self.cancel_button.setText("Close")

        # Fetch real sheet names in background so pills show yellow warnings immediately
        spreadsheet_id = self.config.google_sheets_id
        if spreadsheet_id and entries:
            self._fetch_thread = SheetsFetchThread(spreadsheet_id)
            self._fetch_thread.finished.connect(self._on_sheets_fetched)
            self._fetch_thread.start()

    def _update_table_selection(self, entries_by_table: Dict[str, List[ParsedEntry]]):
        # Clear pills
        while self._pills_layout.count():
            item = self._pills_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pill_widgets.clear()

        available = self._available_sheets
        missing_tables = []

        for table_name, table_entries in entries_by_table.items():
            count = len(table_entries)
            is_missing = bool(available) and table_name not in available
            if is_missing:
                missing_tables.append(table_name)
            pill = _make_table_pill(
                table_name, count, checked=True,
                missing=is_missing,
                available_sheets=available if is_missing else None,
            )
            insert_pos = self._pills_layout.count()
            self._pills_layout.insertWidget(insert_pos, pill)
            self._pill_widgets[table_name] = pill

        self._pills_layout.addStretch()

        # Show/update warning banner
        if missing_tables:
            names = ', '.join(f'"{t}"' for t in missing_tables)
            self._missing_tables_warning.setText(
                f"⚠  Таблиці {names} не знайдено у Google Sheets.\n"
                f"Оберіть існуючу таблицю у випадаючому списку — або створіть нову через «Create Table»."
            )
            self._missing_tables_warning.setVisible(True)
        else:
            self._missing_tables_warning.setVisible(False)

        self.table_selection_group.setVisible(bool(entries_by_table))

    def _get_edited_entries(self) -> List[ParsedEntry]:
        """Return entries with social_network and tag updated from dropdown widgets."""
        import dataclasses
        edited = []
        for row_idx, entry in enumerate(self.entries):
            social_combo = self.entries_table.cellWidget(row_idx, 2)
            tag_combo    = self.entries_table.cellWidget(row_idx, 3)

            # For ЗМІ entries there is no Social Network column — keep it empty
            table_item = self.entries_table.item(row_idx, 0)
            tname = table_item.text() if table_item else (entry.table_name or '')
            is_media = 'змі' in tname.lower() or 'зми' in tname.lower()

            sn = '' if is_media else (
                social_combo.currentText() if social_combo else entry.social_network
            )
            updated = dataclasses.replace(
                entry,
                social_network=sn,
                tag=tag_combo.currentText() if tag_combo else entry.tag,
            )
            edited.append(updated)
        return edited

    def _get_selected_tables(self) -> set:
        """Return set of original table names that are checked."""
        selected = set()
        for table_name, pill in self._pill_widgets.items():
            cb = pill.property('checkbox')
            if cb and cb.isChecked():
                selected.add(table_name)
        return selected

    def _get_table_remapping(self) -> Dict[str, str]:
        """Return mapping of original_table_name → effective_table_name (after remap dropdown)."""
        remapping: Dict[str, str] = {}
        for table_name, pill in self._pill_widgets.items():
            combo = pill.property('remap_combo')
            if combo and combo.currentText():
                remapping[table_name] = combo.currentText()
            else:
                remapping[table_name] = table_name
        return remapping

    # ── Misc handlers ──────────────────────────────────────────────────────────

    def _on_sheets_fetched(self, sheet_names: list):
        self._available_sheets = sheet_names
        self._update_table_selection(_group_entries_by_table(self.entries))

    def _on_parsing_error(self, message: str, entry):
        pass

    def _toggle_errors(self, checked: bool):
        self.errors_text.setVisible(checked)

    def _on_browse_export_path(self):
        start = self.export_path_input.text().strip() or self.config.export_dir
        directory = QFileDialog.getExistingDirectory(self, "Select export folder", start)
        if directory:
            self.export_path_input.setText(directory)
            self.config.export_dir = directory

    def _on_export_excel(self):
        if not self.entries:
            QMessageBox.warning(self, "No Data", "No entries to export.")
            return

        base = self.export_path_input.text().strip() or self.config.export_dir
        if not base:
            QMessageBox.warning(self, "Missing Path", "Please choose an export folder.")
            return

        safe_table = (self.table_name or "report").replace("/", "_").replace("\\", "_")
        filename   = f"{safe_table}_{self.date_from.isoformat()}_{self.date_to.isoformat()}.xlsx"
        out_path   = Path(base)
        if out_path.suffix.lower() != ".xlsx":
            out_path = out_path / filename

        self.config.export_dir = str(Path(base))

        for w in (self.export_button, self.submit_button,
                  self.cancel_button, self.browse_export_button):
            w.setEnabled(False)

        self._set_progress(0, "Generating Excel report…")

        self._excel_thread = ExcelExportThread(list(self.entries), str(out_path))
        self._excel_thread.progress.connect(self._on_progress)

        def on_done(path_str):
            self._set_progress(100, f"Excel saved: {path_str}", done=True)
            QMessageBox.information(self, "Excel exported", f"Report saved to:\n{path_str}")
            for w in (self.export_button, self.submit_button,
                      self.cancel_button, self.browse_export_button):
                w.setEnabled(True)

        def on_fail(err):
            QMessageBox.critical(self, "Excel export failed", err)
            for w in (self.export_button, self.submit_button,
                      self.cancel_button, self.browse_export_button):
                w.setEnabled(True)

        self._excel_thread.finished.connect(on_done)
        self._excel_thread.failed.connect(on_fail)
        self._excel_thread.start()

    def _on_cancel(self):
        if self.parsing_thread and self.parsing_thread.isRunning():
            reply = QMessageBox.question(
                self, "Cancel Parsing?",
                "Parsing is in progress. Do you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.parsing_thread._stop_requested = True
                self.parsing_thread.wait()
                if self.parser:
                    self.parser.close()
                self.reject()
        else:
            if self.parser:
                self.parser.close()
            self.reject()

    def _on_submit(self):
        if not self.entries:
            QMessageBox.warning(self, "No Data", "No entries to submit.")
            return

        spreadsheet_id = self.config.google_sheets_id
        if not spreadsheet_id:
            QMessageBox.critical(self, "Missing Configuration",
                                 "Please configure Google Sheets ID in Settings.")
            return

        entries_by_table = _group_entries_by_table(self._get_edited_entries())
        selected_tables  = self._get_selected_tables()
        remapping        = self._get_table_remapping()

        if not selected_tables:
            QMessageBox.warning(self, "No Tables Selected",
                                "Please select at least one table to write to.")
            return

        if self._available_sheets:
            existing = set(self._available_sheets)
            truly_missing = [
                remapping.get(t, t) for t in selected_tables
                if remapping.get(t, t) not in existing
            ]
            if truly_missing:
                names = '\n'.join(f'  • {t}' for t in truly_missing)
                reply = QMessageBox.question(
                    self, "Таблиці не існують",
                    f"Наступні таблиці не знайдено у Google Sheets:\n{names}\n\n"
                    f"Якщо продовжити — вони будуть створені автоматично.\n"
                    f"Натисніть «Ні», щоб скасувати і обрати іншу таблицю.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self._set_progress(0, "")
                    return

        for w in (self.submit_button, self.export_button,
                  self.cancel_button, self.browse_export_button):
            w.setEnabled(False)
        self._set_progress(0, "Connecting to Google Sheets…")

        self._sheets_thread = SheetsWriteThread(
            spreadsheet_id, entries_by_table, selected_tables, remapping
        )
        self._sheets_thread.progress.connect(
            lambda c, t, m: self._set_progress(int((c / t) * 100) if t else 0, m)
        )
        self._sheets_thread.finished.connect(self._on_sheets_write_done)
        self._sheets_thread.failed.connect(self._on_sheets_write_failed)
        self._sheets_thread.start()

    def _on_sheets_write_done(self, results: Dict):
        for w in (self.submit_button, self.export_button,
                  self.cancel_button, self.browse_export_button):
            w.setEnabled(True)

        total_written, total_failed = 0, []
        edited_by_table = _group_entries_by_table(self._get_edited_entries())
        for orig_name, result in results.items():
            effective_name = result.get('effective_name', orig_name)
            total_written += result.get('written', 0)
            for fe in result.get('failed', []):
                fe['table'] = effective_name
                total_failed.append(fe)
            if result.get('success'):
                table_entries = edited_by_table.get(orig_name, [])
                for entry in table_entries:
                    if entry.date:
                        self.db_manager.mark_date_parsed(effective_name, entry.date)

        if total_failed:
            total_all = total_written + len(total_failed)
            pct = int(total_written / total_all * 100) if total_all else 0
            self._set_progress(pct, f"⚠️ Partial — {total_written} written, {len(total_failed)} failed")
            reply = QMessageBox.question(
                self, "Partial Success",
                f"Wrote {total_written} entries, but {len(total_failed)} failed.\n\n"
                "Do you want to see error details?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                details = "\n".join(
                    f"Table {e.get('table','?')}, Row {e.get('row','?')}: {e.get('error','?')}"
                    for e in total_failed[:MAX_ERROR_DISPLAY]
                )
                if len(total_failed) > MAX_ERROR_DISPLAY:
                    details += f"\n… and {len(total_failed) - MAX_ERROR_DISPLAY} more"
                QMessageBox.warning(self, "Failed Entries", details)
        else:
            self._set_progress(100, f"✅ Written {total_written} entries", done=True)
            QMessageBox.information(
                self, "Success",
                f"Successfully wrote {total_written} entries to "
                f"{len(results)} table(s):\n"
                + ", ".join(r.get('effective_name', k) for k, r in results.items())
            )
            self.accept()

    def _on_sheets_write_failed(self, error: str):
        for w in (self.submit_button, self.export_button,
                  self.cancel_button, self.browse_export_button):
            w.setEnabled(True)
        self._set_progress(0, "")
        logger.exception("Error writing to Google Sheets")
        QMessageBox.critical(self, "Error Writing to Sheets",
                             f"Failed to write to Google Sheets:\n{error}")