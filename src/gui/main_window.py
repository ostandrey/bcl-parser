"""Main window for BCL Parser application."""
import logging
from datetime import timedelta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QDialog,
    QFrame, QGroupBox, QLineEdit, QCalendarWidget
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QMouseEvent, QFont
from datetime import datetime
from .date_picker import MaterialDateRangeDialog
from ..config import Config
from ..database.db_manager import DatabaseManager
from ..utils.date_tracker import DateTracker

logger = logging.getLogger(__name__)

# Material Design 3 color scheme
COLORS = {
    'primary': '#6750A4',  # M3 Primary Purple
    'primary_container': '#EADDFF',
    'on_primary': '#FFFFFF',
    'secondary': '#625B71',
    'secondary_container': '#E8DEF8',
    'tertiary': '#7D5260',
    'surface': '#FFFBFE',  # M3 Surface
    'surface_variant': '#E7E0EC',
    'background': '#FEF7FF',  # M3 Background
    'on_surface': '#1C1B1F',
    'on_surface_variant': '#49454F',
    'outline': '#79747E',
    'outline_variant': '#CAC4D0',
    'shadow': 'rgba(0, 0, 0, 0.15)',
    'scrim': 'rgba(0, 0, 0, 0.32)',
    'error': '#BA1A1A',
    'error_container': '#F9DEDC',
    'success': '#1B5E20',
    'success_container': '#C8E6C9',
    'warning': '#F57C00',
    'warning_container': '#FFE0B2',
}


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.db_manager = DatabaseManager()
        self.date_tracker = DateTracker(self.db_manager)
        
        self.setWindowTitle("BCL Parser")
        self.setGeometry(100, 100, 700, 500)
        
        self._apply_global_styles()
        self._init_ui()
        self._check_missing_days()
    
    def _apply_global_styles(self):
        """Apply global application styles."""
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QWidget {{
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 10pt;
            }}
            /* Calendar Widget Styling */
            QCalendarWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 8px;
                color: {COLORS['on_surface']};
            }}
            QCalendarWidget QTableView {{
                selection-background-color: {COLORS['primary_container']};
                selection-color: {COLORS['on_surface']};
                gridline-color: {COLORS['outline_variant']};
            }}
            QCalendarWidget QTableView::item {{
                padding: 4px;
                border-radius: 4px;
            }}
            QCalendarWidget QTableView::item:selected {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
            }}
            QCalendarWidget QTableView::item:hover {{
                background-color: {COLORS['primary_container']};
            }}
            QCalendarWidget QHeaderView::section {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                padding: 8px;
                font-weight: 600;
                border: none;
                border-bottom: 1px solid {COLORS['primary']};
            }}
            QCalendarWidget QSpinBox {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 4px;
                padding: 4px;
                color: {COLORS['on_surface']};
            }}
            QCalendarWidget QToolButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: 600;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: {COLORS['primary']};
                opacity: 0.9;
            }}
            QCalendarWidget QToolButton:pressed {{
                background-color: {COLORS['primary']};
                opacity: 0.8;
            }}
            /* Buttons - cursor pointer when enabled */
            QPushButton:enabled {{
                cursor: pointer;
            }}
        """)
    
    def _init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        central_widget.setLayout(main_layout)
        
        # Header
        header_label = QLabel("BCL Parser")
        header_font = QFont()
        header_font.setPointSize(24)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(f"color: {COLORS['on_surface']}; margin-bottom: 10px;")
        main_layout.addWidget(header_label)
        
        # Date Range - Compact
        date_group = QGroupBox("Date Range")
        date_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 12pt;
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 12px;
                background-color: {COLORS['surface']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: {COLORS['on_surface']};
            }}
        """)
        date_layout = QHBoxLayout()
        date_layout.setSpacing(8)
        date_layout.setContentsMargins(10, 8, 10, 10)
        
        from_label = QLabel("From:")
        from_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-weight: 500; font-size: 11pt;")
        date_layout.addWidget(from_label)
        
        # Date range input with single calendar button
        date_range_widget = QWidget()
        date_range_layout = QHBoxLayout()
        date_range_layout.setContentsMargins(0, 0, 0, 0)
        date_range_layout.setSpacing(8)
        
        # From date input - disabled
        self.date_from_input = QLineEdit()
        self.date_from_input.setReadOnly(True)
        self.date_from_input.setEnabled(False)
        self.date_from_input.setText(QDate.currentDate().toString("dd.MM.yyyy"))
        self.date_from_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 8px;
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 4px;
                background-color: {COLORS['surface_variant']};
                min-width: 120px;
                font-size: 10pt;
                color: {COLORS['on_surface']};
            }}
        """)
        date_range_layout.addWidget(self.date_from_input)
        
        # To label
        to_label = QLabel("to")
        to_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-weight: 500; font-size: 10pt;")
        date_range_layout.addWidget(to_label)
        
        # To date input - disabled
        self.date_to_input = QLineEdit()
        self.date_to_input.setReadOnly(True)
        self.date_to_input.setEnabled(False)
        self.date_to_input.setText(QDate.currentDate().toString("dd.MM.yyyy"))
        self.date_to_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 6px 8px;
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 4px;
                background-color: {COLORS['surface_variant']};
                min-width: 120px;
                font-size: 10pt;
                color: {COLORS['on_surface']};
            }}
        """)
        date_range_layout.addWidget(self.date_to_input)
        
        # Beautiful calendar button for range picker
        self.date_range_button = QPushButton("📅")
        self.date_range_button.setToolTip("Select Date Range")
        self.date_range_button.clicked.connect(self._open_date_range_picker)
        self.date_range_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.date_range_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {COLORS['primary']}, stop:1 #5A3F8F);
                color: {COLORS['on_primary']};
                border: none;
                border-radius: 4px;
                padding: 1px 8px;
                font-size: 18pt;
                min-width: 56px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7D5FB8, stop:1 {COLORS['primary']});
            }}
            QPushButton:pressed {{
                background: {COLORS['primary']};
                opacity: 0.9;
            }}
        """)
        date_range_layout.addWidget(self.date_range_button)
        date_range_widget.setLayout(date_range_layout)
        date_layout.addWidget(date_range_widget)
        
        date_layout.addStretch()
        date_group.setLayout(date_layout)
        main_layout.addWidget(date_group)
        
        # Status and notification section
        status_frame = QFrame()
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['outline_variant']};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        status_layout = QVBoxLayout()
        status_layout.setSpacing(6)
        status_frame.setLayout(status_layout)
        
        self.status_label = QLabel("Ready to parse")
        self.status_label.setStyleSheet(f"color: {COLORS['on_surface_variant']}; font-size: 12pt; font-weight: 400;")
        status_layout.addWidget(self.status_label)
        
        self.missing_days_label = QLabel()
        self.missing_days_label.mousePressEvent = self._on_missing_days_clicked
        self.missing_days_label.setStyleSheet(f"""
            QLabel {{
                padding: 6px 8px;
                border-radius: 4px;
                background-color: {COLORS['background']};
                color: {COLORS['on_surface']};
                font-size: 10pt;
            }}
        """)
        status_layout.addWidget(self.missing_days_label)
        
        main_layout.addWidget(status_frame)
        
        # Main action button
        # Material Design 3 Filled Button
        self.parse_button = QPushButton("🚀 Start Parsing")
        self.parse_button.setMinimumHeight(56)
        self.parse_button.clicked.connect(self._on_start_parsing)
        self.parse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.parse_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: {COLORS['on_primary']};
                border: none;
                border-radius: 20px;
                padding: 14px 32px;
                font-size: 14pt;
                font-weight: 500;
                letter-spacing: 0.1px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                box-shadow: 0px 4px 8px {COLORS['shadow']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['primary']};
                box-shadow: 0px 2px 4px {COLORS['shadow']};
            }}
        """)
        main_layout.addWidget(self.parse_button)
        
        # Secondary buttons
        buttons_frame = QFrame()
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        buttons_frame.setLayout(buttons_layout)
        
        # Material Design 3 Outlined Button
        create_table_button = QPushButton("➕ Create Table")
        create_table_button.clicked.connect(self._on_create_table)
        create_table_button.setCursor(Qt.CursorShape.PointingHandCursor)
        create_table_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['primary']};
                border: 1px solid {COLORS['outline']};
                border-radius: 20px;
                padding: 10px 24px;
                font-weight: 500;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_container']};
                border-color: {COLORS['primary']};
            }}
        """)
        buttons_layout.addWidget(create_table_button)
        
        settings_button = QPushButton("⚙️ Settings")
        settings_button.clicked.connect(self._on_settings)
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['primary']};
                border: 1px solid {COLORS['outline']};
                border-radius: 20px;
                padding: 10px 24px;
                font-weight: 500;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_container']};
                border-color: {COLORS['primary']};
            }}
        """)
        buttons_layout.addWidget(settings_button)
        
        buttons_layout.addStretch()
        main_layout.addWidget(buttons_frame)
        
        main_layout.addStretch()
    
    def _open_date_range_picker(self):
        """Open the Material Design date range picker dialog."""
        try:
            # Get current dates
            current_start = self.date_from_input.text()
            current_end = self.date_to_input.text()
            
            # Open the date range picker
            start, end = MaterialDateRangeDialog.get_range(
                self.date_range_button, 
                current_start, 
                current_end
            )
            
            # Update UI if a range was selected
            if start and end:
                self.date_from_input.setText(start)
                self.date_to_input.setText(end)
        except Exception as e:
            logger.exception("Error opening date range picker")
            QMessageBox.warning(
                self,
                "Calendar Error",
                f"Could not open calendar picker:\n{str(e)}"
            )
    
    def _parse_date_string(self, date_str):
        """Parse date string in format 'd.m.Y' to QDate."""
        try:
            # Handle format like "21.02.2026"
            date_obj = datetime.strptime(date_str, "%d.%m.%Y")
            return QDate(date_obj.year, date_obj.month, date_obj.day)
        except ValueError:
            # Try alternative format
            try:
                date_obj = datetime.strptime(date_str, "%d.%m.%y")
                return QDate(date_obj.year, date_obj.month, date_obj.day)
            except ValueError:
                logger.warning(f"Could not parse date string: {date_str}")
                return QDate.currentDate()
    
    def _check_missing_days(self):
        """Check for missing days and display notification."""
        table_name = self.config.default_table
        today = self.date_tracker.get_today()
        
        # Check last 30 days for missing dates
        start_date = today - timedelta(days=30)
        missing = self.date_tracker.check_missing_days(table_name, start_date, today)
        
        if missing:
            self.missing_days_label.setText(
                f"⚠️ {len(missing)} days missed. Click to fill missing days."
            )
            self.missing_days_label.setStyleSheet(f"""
                QLabel {{
                    padding: 6px 8px;
                    border-radius: 4px;
                    background-color: {COLORS['warning_container']};
                    color: {COLORS['on_surface']};
                    border: 1px solid {COLORS['warning']};
                    font-size: 10pt;
                }}
            """)
            self._has_missing_days = True
        else:
            self.missing_days_label.setText("✅ All days parsed")
            self.missing_days_label.setStyleSheet(f"""
                QLabel {{
                    padding: 6px 8px;
                    border-radius: 4px;
                    background-color: {COLORS['success_container']};
                    color: {COLORS['on_surface']};
                    border: 1px solid {COLORS['success']};
                    font-size: 10pt;
                }}
            """)
            self._has_missing_days = False
    
    def _on_missing_days_clicked(self, event: QMouseEvent):
        """Handle click on missing days label."""
        if self._has_missing_days:
            self._fill_missing_days()
        event.accept()
    
    def _fill_missing_days(self):
        """Fill missing days with parsing."""
        # TODO: Implement missing days filling
        QMessageBox.information(
            self, 
            "Fill Missing Days", 
            "This feature will be implemented in the next phase."
        )
    
    def _on_start_parsing(self):
        """Handle start parsing button click."""
        try:
            logger.info("Start parsing button clicked")
            
            table_name = self.config.default_table
            # Parse date strings from input fields
            date_from_qdate = self._parse_date_string(self.date_from_input.text())
            date_to_qdate = self._parse_date_string(self.date_to_input.text())
            date_from = date_from_qdate.toPyDate()
            date_to = date_to_qdate.toPyDate()
            
            # Validate date range
            if date_from > date_to:
                QMessageBox.warning(
                    self,
                    "Invalid Date Range",
                    "The 'From' date must be before or equal to the 'To' date."
                )
                return
            
            logger.info(f"Table: {table_name}, Date range: {date_from} to {date_to}")
            
            # Check credentials
            if not self.config.site_username or not self.config.site_password:
                logger.warning("Missing YouScan.io credentials")
                QMessageBox.warning(
                    self,
                    "Missing Credentials",
                    "Please configure YouScan.io credentials in Settings.\n\n"
                    "You can set YOUSCAN_EMAIL and YOUSCAN_PASSWORD environment variables."
                )
                return
            
            if not self.config.google_sheets_id:
                logger.warning("Missing Google Sheets ID")
                QMessageBox.warning(
                    self,
                    "Missing Configuration",
                    "Please configure Google Sheets ID in Settings."
                )
                return
            
            # Open parsing dialog
            logger.info("Opening parsing dialog")
            from .parser_dialog import ParserDialog
            dialog = ParserDialog(
                self,
                self.config,
                self.db_manager,
                self.date_tracker,
                table_name,
                date_from,
                date_to
            )
            dialog.exec()
            
            # Refresh missing days check
            self._check_missing_days()
        except Exception as e:
            logger.exception("Error in _on_start_parsing")
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred:\n{str(e)}\n\nCheck console for details."
            )
    
    def _on_settings(self):
        """Handle settings button click."""
        from .settings_dialog import SettingsDialog
        dialog = SettingsDialog(self, self.config)
        dialog.exec()
    
    def _on_create_table(self):
        """Handle create table button click."""
        from .create_table_dialog import CreateTableDialog
        dialog = CreateTableDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            created_table = dialog.get_created_table_name()
            if created_table:
                # Update default table to the newly created one
                self.config.default_table = created_table
                logger.info(f"Created new table: {created_table}")

